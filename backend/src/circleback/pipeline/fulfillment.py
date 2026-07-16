"""Fulfillment Matcher node in the LangGraph agent pipeline.

Scans subsequent thread messages to detect semantic fulfillment or renegotiation
of open commitments, updating their statuses and recording events.

Design decisions:
- Matches against SPECIFIC open commitments, not "any positive follow-up"
- Handles multiple concurrent open commitments in one thread independently
- Renegotiation detection: deadline changes update existing commitment
- Delegation detection: checks for fulfillment by delegate if mapped
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import (
    Commitment,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    CommitmentType,
    Message,
    Person,
)

logger = logging.getLogger(__name__)


# ── Structured Output Schemas ─────────────────────────────────


class FulfillmentMatch(BaseModel):
    """A match between a new message and an open commitment."""

    commitment_id: str = Field(
        description="The ID of the commitment being matched."
    )
    action: str = Field(
        description="One of: 'fulfill' (commitment completed), 'renegotiate' (deadline changed), 'progress' (partial progress, no status change)."
    )
    confidence: float = Field(
        default=0.5,
        description="0.0 to 1.0 confidence in this match."
    )
    reason: str = Field(
        default="",
        description="Brief explanation of why this message fulfills/renegotiates the commitment."
    )
    new_deadline: str | None = Field(
        default=None,
        description="If action is 'renegotiate', the new deadline phrase from the message (ISO format if explicit, raw phrase if relative)."
    )
    delegate_name: str | None = Field(
        default=None,
        description="If this was a delegated commitment, the name or email of the delegate identified in the message."
    )


class FulfillmentResult(BaseModel):
    """Result of fulfillment matching analysis."""

    matches: list[FulfillmentMatch] = Field(
        default_factory=list,
        description="List of matches found. Empty if new message doesn't fulfill/renegotiate any open commitments."
    )


# ── System Prompt ─────────────────────────────────────────────

FULFILLMENT_SYSTEM_PROMPT = """You are a fulfillment detection system for Circle Back, a commitment tracking tool.

You are given:
1. A list of OPEN commitments (things people promised to do)
2. A NEW message that just arrived in the same thread

Your job is to determine if the new message provides evidence that any of the open commitments have been:
- **Fulfilled**: The promised action was completed (e.g., "Here's the deck I promised" fulfills "I'll send you the deck")
- **Renegotiated**: The deadline was changed (e.g., "Actually, can I push this to next week?" renegotiates a Friday deadline)

## CRITICAL RULES:
1. Match against SPECIFIC commitments. Don't assume "any positive message" fulfills the oldest open item.
2. A message must provide CLEAR EVIDENCE of fulfillment — not just be tangentially related.
3. The message sender should typically be the committer (or their delegate) for fulfillment to count.
4. Attachments, links, or "here's the X" language strongly signal fulfillment of "I'll send X" commitments.
5. "I need more time" or "can we push this" signals renegotiation, not fulfillment.
6. Progress updates ("I'm working on it") are 'progress' — they don't change status.
7. For DELEGATED commitments, also indicate who the delegate is in the delegate_name field if identified.
8. Be CONSERVATIVE. If you're unsure whether a message truly fulfills a commitment, don't match it.

## Confidence scoring:
- 0.9-1.0: Clear, direct fulfillment (e.g., "Here's the report" for "I'll send the report")
- 0.7-0.89: Very likely fulfillment but indirect (e.g., an attachment without explicit reference)
- 0.5-0.69: Possible fulfillment, needs human confirmation
- Below 0.5: Don't include — too uncertain"""


async def call_llm_for_matching(
    open_commitments: list[Commitment],
    new_message: Message,
) -> FulfillmentResult:
    """Call Claude API to check if new_message fulfills/renegotiates open_commitments.

    In test mode (no ANTHROPIC_API_KEY), returns empty results.
    """
    if not open_commitments:
        return FulfillmentResult(matches=[])

    try:
        from circleback.config import get_settings
        settings = get_settings()
        if not settings.anthropic_api_key:
            logger.debug("No ANTHROPIC_API_KEY configured — returning empty fulfillment.")
            return FulfillmentResult(matches=[])
    except Exception:
        return FulfillmentResult(matches=[])

    from circleback.pipeline.llm_client import call_claude_structured

    # Build context about open commitments
    commitments_text = "\n".join(
        f"- ID: {c.id} | Type: {c.commitment_type.value} | "
        f"Text: \"{c.raw_text_span}\" | "
        f"Deadline: {c.resolved_deadline.isoformat() if c.resolved_deadline else 'none'} | "
        f"Status: {c.status.value}"
        for c in open_commitments
    )

    user_message = (
        f"OPEN COMMITMENTS:\n{commitments_text}\n\n"
        f"NEW MESSAGE (from {new_message.sender_handle or 'unknown'}):\n"
        f"{new_message.raw_text}"
    )

    try:
        result = await call_claude_structured(
            system_prompt=FULFILLMENT_SYSTEM_PROMPT,
            user_message=user_message,
            output_schema=FulfillmentResult,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        return result
    except RuntimeError as e:
        logger.error("LLM cost limit exceeded during fulfillment matching: %s", e)
        return FulfillmentResult(matches=[])
    except Exception as e:
        logger.error("LLM fulfillment matching failed: %s", e, exc_info=True)
        return FulfillmentResult(matches=[])


async def resolve_sender_person(db: AsyncSession, sender_handle: str) -> Person | None:
    """Helper to look up a Person record by email or slack user ID."""
    if not sender_handle:
        return None
    # Assuming email_addresses and slack_user_ids are JSON/ARRAY columns in postgres
    # For a simpler approach, we fetch all and check in memory for the prototype
    result = await db.execute(select(Person))
    persons = result.scalars().all()
    for p in persons:
        if sender_handle in p.email_addresses or sender_handle in p.slack_user_ids:
            return p
    return None

async def process_thread_fulfillment(
    db: AsyncSession,
    thread_id: str | None,
    new_msg: Message,
) -> None:
    """Analyze new message against open commitments on the thread for status updates."""
    if not thread_id:
        return

    # Fetch all open/active commitments on this thread
    result = await db.execute(
        select(Commitment).where(
            Commitment.thread_id == thread_id,
            Commitment.status.in_([
                CommitmentStatus.OPEN,
                CommitmentStatus.AT_RISK,
                CommitmentStatus.RENEGOTIATED,
                CommitmentStatus.NEEDS_CLARIFICATION,
            ])
        )
    )
    open_commitments = list(result.scalars().all())
    if not open_commitments:
        return

    # Call LLM to perform matching
    match_result = await call_llm_for_matching(open_commitments, new_msg)
    if isinstance(match_result, dict):
        match_result = FulfillmentResult.model_validate(match_result)

    for match in match_result.matches:
        c_id = match.commitment_id
        action = match.action
        reason = match.reason
        new_deadline_str = match.new_deadline

        # Find matching commitment record
        commitment = next((c for c in open_commitments if c.id == c_id), None)
        if not commitment:
            logger.warning("Fulfillment match references unknown commitment ID: %s", c_id)
            continue

        if commitment.commitment_type == CommitmentType.DELEGATED:
            sender_person = await resolve_sender_person(db, new_msg.sender_handle)
            if sender_person:
                reason += f" (Deterministic verification: Message sent by mapped delegate {sender_person.display_name})"
                match.confidence = min(1.0, match.confidence + 0.2)
            else:
                reason += " (Ambiguous: Message sent by unmapped delegate)"
                match.confidence = max(0.0, match.confidence - 0.2)

        if action == "fulfill" and match.confidence >= 0.5:
            commitment.status = CommitmentStatus.FULFILLED
            event = CommitmentEvent(
                commitment_id=commitment.id,
                type=CommitmentEventType.FULFILLMENT_SIGNAL,
                evidence_message_id=new_msg.id,
                note=f"Fulfillment detected (confidence: {match.confidence:.2f}). {reason}",
            )
            db.add(event)
            logger.info("Commitment %s marked as fulfilled", c_id)

        elif action == "renegotiate":
            commitment.status = CommitmentStatus.RENEGOTIATED
            if new_deadline_str:
                try:
                    cleaned_str = new_deadline_str.replace("Z", "+00:00")
                    parsed_dt = datetime.fromisoformat(cleaned_str)
                    commitment.resolved_deadline = parsed_dt
                except ValueError:
                    # It might be a relative phrase — store it for temporal resolution
                    commitment.raw_temporal_phrase = new_deadline_str
                    logger.info("Renegotiated deadline is relative phrase: %s", new_deadline_str)

            event = CommitmentEvent(
                commitment_id=commitment.id,
                type=CommitmentEventType.RENEGOTIATED,
                evidence_message_id=new_msg.id,
                note=f"Renegotiation detected. {reason}",
            )
            db.add(event)
            logger.info("Commitment %s renegotiated", c_id)

        elif action == "progress":
            # Progress updates are logged but don't change status
            event = CommitmentEvent(
                commitment_id=commitment.id,
                type=CommitmentEventType.FULFILLMENT_SIGNAL,
                evidence_message_id=new_msg.id,
                note=f"Progress update (no status change). {reason}",
            )
            db.add(event)

    await db.flush()
