"""Digest Generator and Human Correction Loop node in the LangGraph pipeline.

Formats daily/weekly summaries of commitments and processes human corrections
(e.g., done, dismiss, postpone) to resolve ambiguities.

Design decisions:
- Lead with upcoming, not overdue — digest reads as helpful, not an indictment (§6.8)
- Every correction is a CommitmentEvent AND a labeled data point for eval (§6.9)
- Corrections feed back into the eval set over time
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import (
    Commitment,
    CommitmentDirection,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    EvalLabel,
    Message,
)

logger = logging.getLogger(__name__)


def _commitment_sort_key(c_dict: dict[str, Any]) -> str:
    """Sort commitments: at_risk first, then open, then overdue, by deadline."""
    status_order = {"at_risk": "0", "open": "1", "renegotiated": "2", "overdue": "3", "needs_clarification": "4"}
    prefix = status_order.get(c_dict["status"], "9")
    deadline = c_dict["resolved_deadline"] or "9999-12-31"
    return f"{prefix}_{deadline}"


async def generate_digest(db: AsyncSession, user_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Compile active commitments into grouped outbound/inbound lists for a specific user.

    Framing is deliberate: lead with upcoming (at_risk), then open items,
    then overdue — not the other way around (spec §6.8).
    """
    result = await db.execute(
        select(Commitment).where(
            Commitment.status.in_([
                CommitmentStatus.OPEN,
                CommitmentStatus.AT_RISK,
                CommitmentStatus.OVERDUE,
                CommitmentStatus.RENEGOTIATED,
                CommitmentStatus.NEEDS_CLARIFICATION,
            ]),
            Commitment.user_id == user_id
        )
    )
    commitments = result.scalars().all()

    made_by_user: list[dict[str, Any]] = []
    owed_to_user: list[dict[str, Any]] = []

    for c in commitments:
        c_dict: dict[str, Any] = {
            "id": c.id,
            "raw_text_span": c.raw_text_span,
            "status": c.status.value,
            "commitment_type": c.commitment_type.value,
            "resolved_deadline": c.resolved_deadline.isoformat() if c.resolved_deadline else None,
            "raw_temporal_phrase": c.raw_temporal_phrase,
            "extraction_confidence": c.extraction_confidence,
            "deadline_confidence": c.deadline_confidence,
            "committer_person_id": c.committer_person_id,
            "source_message_id": c.source_message_id,
            "thread_id": c.thread_id,
        }

        if c.direction == CommitmentDirection.MADE_BY_USER:
            made_by_user.append(c_dict)
        else:
            owed_to_user.append(c_dict)

    # Sort: at-risk first, then open, then overdue — lead with upcoming (spec §6.8)
    made_by_user.sort(key=_commitment_sort_key)
    owed_to_user.sort(key=_commitment_sort_key)

    return {
        "made_by_user": made_by_user,
        "owed_to_user": owed_to_user,
    }


async def apply_commitment_correction(
    db: AsyncSession,
    commitment_id: str,
    action: str,
    params: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> None:
    """Apply a manual user correction to a commitment.

    Every correction is:
    1. A CommitmentEvent (audit trail)
    2. A labeled data point fed back into the eval set (spec §6.9)

    Actions:
    - "done": Mark as fulfilled
    - "dismiss": Not actually a commitment
    - "new_deadline": Renegotiate with a new deadline
    """
    result = await db.execute(
        select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.user_id == user_id
        )
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise ValueError(f"Commitment with ID {commitment_id} not found.")

    if action == "done":
        commitment.status = CommitmentStatus.FULFILLED
        event = CommitmentEvent(
            commitment_id=commitment.id,
            type=CommitmentEventType.CONFIRMED,
            note="User manually confirmed as completed.",
        )
        db.add(event)

        # Feed back into eval set — this was a real commitment
        await _record_eval_feedback(db, commitment, is_commitment=True, user_id=user_id)

    elif action == "dismiss":
        commitment.status = CommitmentStatus.DISMISSED
        event = CommitmentEvent(
            commitment_id=commitment.id,
            type=CommitmentEventType.DISMISSED,
            note="User dismissed — not actually a commitment.",
        )
        db.add(event)

        # Feed back into eval set — this was NOT a real commitment (false positive)
        await _record_eval_feedback(db, commitment, is_commitment=False, user_id=user_id)

    elif action == "new_deadline":
        commitment.status = CommitmentStatus.RENEGOTIATED
        new_deadline_str = (params or {}).get("new_deadline")
        if new_deadline_str:
            try:
                cleaned_str = new_deadline_str.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(cleaned_str)
                commitment.resolved_deadline = parsed_dt
            except ValueError:
                logger.warning("Could not parse new user deadline: %s", new_deadline_str)

        event = CommitmentEvent(
            commitment_id=commitment.id,
            type=CommitmentEventType.RENEGOTIATED,
            note=f"User manually renegotiated deadline to: {commitment.resolved_deadline}",
        )
        db.add(event)

        # Feed back into eval set — this was a real commitment with corrected deadline
        await _record_eval_feedback(
            db, commitment, is_commitment=True,
            correct_deadline=new_deadline_str,
            user_id=user_id,
        )

    else:
        raise ValueError(f"Unknown correction action: {action}")

    await db.flush()


async def _record_eval_feedback(
    db: AsyncSession,
    commitment: Commitment,
    is_commitment: bool,
    correct_deadline: str | None = None,
    user_id: str | None = None,
) -> None:
    """Record a user correction as a labeled data point in the eval set.

    This is the feedback loop described in §6.9: every correction feeds
    the eval set and, over time, calibrates extraction confidence.
    """
    if not commitment.source_message_id:
        return

    # Check if an eval label already exists for this message
    existing = await db.execute(
        select(EvalLabel).where(
            EvalLabel.message_id == commitment.source_message_id,
            EvalLabel.user_id == user_id
        )
    )
    label = existing.scalar_one_or_none()

    if label:
        # Update existing label
        label.is_commitment = is_commitment
        if correct_deadline:
            label.correct_deadline = correct_deadline
        label.notes = f"Updated via user correction (commitment: {commitment.id})"
    else:
        # Create new eval label from correction
        label = EvalLabel(
            user_id=user_id,
            message_id=commitment.source_message_id,
            is_commitment=is_commitment,
            correct_committer=commitment.committer_person_id,
            correct_deadline=correct_deadline or (
                commitment.raw_temporal_phrase if is_commitment else None
            ),
            notes=f"Auto-generated from user correction (commitment: {commitment.id})",
        )
        db.add(label)
