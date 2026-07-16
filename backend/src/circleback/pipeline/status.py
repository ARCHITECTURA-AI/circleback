"""Status Engine node in the LangGraph agent pipeline.

Evaluates all active commitments against current time and resolved deadlines,
triggering state transitions to AT_RISK or OVERDUE, and logging events.

Design decisions:
- Overdue framing: "no evidence found — please confirm" not "you failed" (§6.7)
- Every transition logged as CommitmentEvent with evidence (§6.7)
- at_risk threshold is configurable (§6.7)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import (
    Commitment,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
)

logger = logging.getLogger(__name__)


async def update_commitment_statuses(
    db: AsyncSession,
    at_risk_hours: int = 24,
) -> None:
    """Scan active commitments and transition their statuses based on current time.

    State transitions per the spec enum:
    - OPEN/RENEGOTIATED → AT_RISK (within at_risk_hours of deadline)
    - OPEN/AT_RISK/RENEGOTIATED → OVERDUE (deadline passed, no fulfillment evidence)

    The overdue framing is deliberate: "no evidence found that this was completed"
    — never "you failed to deliver." Absence of evidence is surfaced for
    confirmation, not asserted as evidence of absence.
    """
    now = datetime.now(timezone.utc)

    # Fetch all active commitments
    result = await db.execute(
        select(Commitment).where(
            Commitment.status.in_([
                CommitmentStatus.OPEN,
                CommitmentStatus.AT_RISK,
                CommitmentStatus.RENEGOTIATED,
                CommitmentStatus.NEEDS_CLARIFICATION,
            ])
        )
    )
    commitments = result.scalars().all()

    for commitment in commitments:
        deadline = commitment.resolved_deadline
        if not deadline:
            continue

        # Ensure timezone-aware comparison
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        time_left = deadline - now
        total_seconds_left = time_left.total_seconds()

        # 1. Overdue: deadline passed, no fulfillment evidence
        if total_seconds_left < 0:
            if commitment.status != CommitmentStatus.OVERDUE:
                commitment.status = CommitmentStatus.OVERDUE
                event = CommitmentEvent(
                    commitment_id=commitment.id,
                    type=CommitmentEventType.CONFIRMED,
                    note=(
                        "Deadline has passed and no evidence of completion was found. "
                        "Please confirm: was this completed, or does it need follow-up?"
                    ),
                )
                db.add(event)
                logger.info(
                    "Commitment %s → OVERDUE (deadline %s passed)",
                    commitment.id,
                    deadline.isoformat(),
                )

        # 2. At risk: deadline approaching within threshold
        elif total_seconds_left <= at_risk_hours * 3600:
            if commitment.status in (CommitmentStatus.OPEN, CommitmentStatus.RENEGOTIATED):
                commitment.status = CommitmentStatus.AT_RISK
                hours_remaining = total_seconds_left / 3600
                event = CommitmentEvent(
                    commitment_id=commitment.id,
                    type=CommitmentEventType.CONFIRMED,
                    note=(
                        f"Deadline is approaching — approximately {hours_remaining:.1f} hours "
                        f"remaining (threshold: {at_risk_hours}h). No completion evidence found yet."
                    ),
                )
                db.add(event)
                logger.info(
                    "Commitment %s → AT_RISK (%.1fh remaining)",
                    commitment.id,
                    hours_remaining,
                )

    await db.flush()
