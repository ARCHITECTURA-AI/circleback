"""LLM Extraction node in the LangGraph agent pipeline.

Uses Anthropic's Claude API to perform structured extraction of commitments
from normalized messages, determining type, direction, and confidence.

Design decisions:
- Precision-over-recall bias: borderline items go to review queue, not digest
- Structured output via Pydantic ensures reliable JSON
- System prompt explicitly addresses hedges, hypotheticals, sarcasm, past-tense
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from sqlalchemy import select

from circleback.db.models import (
    Commitment,
    CommitmentDirection,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    CommitmentType,
    Message,
    Person,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Structured Output Schemas ─────────────────────────────────


class ExtractedCommitment(BaseModel):
    """A single commitment extracted from a message."""

    is_commitment: bool = Field(
        description="True if this is a genuine, actionable commitment — not a hedge, hypothetical, sarcasm, or past-tense reference."
    )
    raw_text_span: str = Field(
        description="The exact text span from the message containing the commitment."
    )
    committer_identifier: str = Field(
        default="",
        description="Email address or Slack ID of the person making the commitment. Use 'sender' if it's the message sender."
    )
    commitment_type: str = Field(
        default="simple",
        description="One of: 'simple', 'delegated', 'conditional', 'recurring'."
    )
    raw_temporal_phrase: str | None = Field(
        default=None,
        description="The original temporal language from the text, e.g. 'by Friday', 'tomorrow', 'next week'. Null if no deadline mentioned."
    )
    extraction_confidence: float = Field(
        default=0.5,
        description="0.0 to 1.0 confidence that this is a real commitment. Be conservative — when in doubt, score low."
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of why this is or isn't a commitment."
    )


class ExtractionResult(BaseModel):
    """Result of commitment extraction from a message."""

    commitments: list[ExtractedCommitment] = Field(
        default_factory=list,
        description="List of commitments found in the message. Empty list if none found."
    )


# ── System Prompt ─────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a commitment extraction system for Circle Back, a tool that tracks promises people make in email and Slack.

Your job is to identify GENUINE, ACTIONABLE commitments in messages. A commitment is a statement where someone explicitly promises to do something for someone else.

## What IS a commitment:
- "I'll send you the deck by Friday" → SIMPLE commitment
- "I'll get Sarah to send it" → DELEGATED commitment (the sender commits to making Sarah do it)
- "If the budget is approved, I will start next Monday" → CONDITIONAL commitment
- "I'll send you a weekly update every Monday" → RECURRING commitment
- "Let me look into this and report back tomorrow" → SIMPLE commitment

## What is NOT a commitment:
- Hedges: "I could probably get this done by Friday if things go well" → NOT a commitment (hedging language)
- Hypotheticals: "If I had time, I would do this" → NOT a commitment
- Group/vague: "We'll circle back on this" → NOT a commitment (no individual owner)
- Past tense: "Thanks for sending that over Friday" → NOT a commitment (already happened)
- Sarcasm: "Sure, I'll get right on that 🙄" → NOT a commitment (sarcastic)
- Acknowledgments: "Thanks, sounds good!" → NOT a commitment
- Questions: "Could you send me the report?" → NOT a commitment (it's a request, not a promise)
- Statements of fact: "The meeting is on Friday" → NOT a commitment

## Direction rules:
- If the message SENDER is making the promise → committer_identifier = "sender"
- If the sender is relaying someone else's commitment → use that person's name/identifier

## Confidence scoring:
- 0.9-1.0: Clear, unambiguous commitment with explicit action and timeline
- 0.7-0.89: Clear commitment but some ambiguity in scope or timeline
- 0.5-0.69: Likely a commitment but could be interpreted differently
- 0.3-0.49: Borderline — might be a commitment, route to review queue
- 0.0-0.29: Almost certainly not a commitment

## CRITICAL RULES:
1. BIAS HARD TOWARD PRECISION. It is far worse to flag something as a commitment when it isn't, than to miss a real commitment.
2. When in doubt, set extraction_confidence LOW (below 0.5). Borderline items go to the review queue, never the main digest.
3. Never treat group statements ("we should", "the team will") as individual commitments unless a specific person is named.
4. Look for commitment language IN CONTEXT — the same words can be a commitment or not depending on surrounding text.
5. If the message is a quoted reply or forward, only extract commitments from the NEW content, not the quoted material."""


# ── Extraction Logic ─────────────────────────────────────────


async def call_llm_for_extraction(
    text: str,
    thread_context: str = "",
) -> ExtractionResult:
    """Call Claude API for structured commitment extraction.

    In test mode (no ANTHROPIC_API_KEY), returns empty results.
    """
    try:
        from circleback.config import get_settings
        settings = get_settings()
        if not settings.anthropic_api_key:
            logger.debug("No ANTHROPIC_API_KEY configured — returning empty extraction.")
            return ExtractionResult(commitments=[])
    except Exception:
        return ExtractionResult(commitments=[])

    from circleback.pipeline.llm_client import call_claude_structured

    user_message = f"Analyze this message for commitments:\n\n{text}"
    if thread_context:
        user_message = f"Thread context (for reference only — extract from the LATEST message):\n{thread_context}\n\n---\n\nLatest message to analyze:\n\n{text}"

    try:
        result = await call_claude_structured(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message=user_message,
            output_schema=ExtractionResult,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        return result
    except RuntimeError as e:
        # Cost limit exceeded
        logger.error("LLM cost limit exceeded during extraction: %s", e)
        return ExtractionResult(commitments=[])
    except Exception as e:
        logger.error("LLM extraction failed: %s", e, exc_info=True)
        return ExtractionResult(commitments=[])


async def extract_commitments_from_message(
    db: AsyncSession,
    msg: Message,
    self_email: str = "",
    user_id: str | None = None,
) -> list[Commitment]:
    """Extract commitments from a message, saving them to the database."""
    resolved_user_id = user_id or getattr(msg, "user_id", None)

    # Gather thread context if available
    thread_context = ""
    if msg.thread_id:
        from sqlalchemy import and_
        result = await db.execute(
            select(Message).where(
                and_(
                    Message.thread_id == msg.thread_id,
                    Message.id != msg.id,
                    Message.deleted_at.is_(None),
                    Message.user_id == resolved_user_id
                )
            ).order_by(Message.timestamp)
        )
        thread_msgs = result.scalars().all()
        if thread_msgs:
            thread_context = "\n---\n".join(
                f"[{m.sender_handle or 'unknown'}]: {m.raw_text[:500]}"
                for m in thread_msgs[-5:]  # Last 5 messages for context
            )

    # Call the LLM to analyze raw text
    extraction_result = await call_llm_for_extraction(msg.raw_text, thread_context)
    if isinstance(extraction_result, dict):
        extraction_result = ExtractionResult.model_validate(extraction_result)

    extracted_records = []

    # Get sender information to determine direction
    sender_is_self = False
    if msg.sender_person_id:
        result = await db.execute(
            select(Person).where(
                Person.id == msg.sender_person_id,
                Person.user_id == resolved_user_id
            )
        )
        sender = result.scalar_one_or_none()
        if sender and sender.is_self:
            sender_is_self = True
    elif self_email and msg.sender_handle:
        sender_is_self = msg.sender_handle.strip().lower() == self_email.strip().lower()

    for item in extraction_result.commitments:
        if not item.is_commitment:
            continue

        # Direction logic
        committer_id = item.committer_identifier
        if sender_is_self or (committer_id and committer_id.lower() in ("sender", self_email.lower())):
            direction = CommitmentDirection.MADE_BY_USER
        else:
            direction = CommitmentDirection.OWED_TO_USER

        # Parse commitment type
        try:
            commitment_type = CommitmentType(item.commitment_type.lower())
        except ValueError:
            commitment_type = CommitmentType.SIMPLE

        commitment = Commitment(
            user_id=resolved_user_id,
            source_message_id=msg.id,
            thread_id=msg.thread_id,
            committer_person_id=msg.sender_person_id,
            direction=direction,
            raw_text_span=item.raw_text_span,
            commitment_type=commitment_type,
            raw_temporal_phrase=item.raw_temporal_phrase,
            extraction_confidence=item.extraction_confidence,
            status=CommitmentStatus.OPEN,
        )
        db.add(commitment)

        # Log extraction event
        await db.flush()
        event = CommitmentEvent(
            commitment_id=commitment.id,
            type=CommitmentEventType.EXTRACTED,
            evidence_message_id=msg.id,
            note=f"Extracted with confidence {item.extraction_confidence:.2f}. {item.reasoning}",
        )
        db.add(event)

        extracted_records.append(commitment)

    await db.flush()
    return extracted_records
