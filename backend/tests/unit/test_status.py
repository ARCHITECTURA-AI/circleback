"""Tests for the Status Engine.

TDD: These tests define how commitments transition through statuses like OPEN, AT_RISK, and OVERDUE
based on approaching or passed deadlines, and verify audit trail creation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from circleback.db.models import CommitmentStatus, CommitmentEventType, CommitmentEvent
from circleback.pipeline.status import update_commitment_statuses
from tests.conftest import make_commitment


class TestStatusEngine:
    """Commitment status transition tests based on deadline temporal logic."""

    @pytest.mark.asyncio
    async def test_new_commitment_starts_open(self, db_session) -> None:
        """A new commitment should be created with status=OPEN."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        db_session.add(c)
        await db_session.commit()
        assert c.status == CommitmentStatus.OPEN

    @pytest.mark.asyncio
    async def test_transition_open_to_at_risk(self, db_session) -> None:
        """Commitment within 24h of its deadline transitions to AT_RISK status."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        # Set deadline to 12 hours from now
        c.resolved_deadline = datetime.now(timezone.utc) + timedelta(hours=12)
        db_session.add(c)
        await db_session.commit()

        await update_commitment_statuses(db_session, at_risk_hours=24)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.AT_RISK

        # Verify audit trail event
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        assert events[-1].type == CommitmentEventType.CONFIRMED  # State transition confirmed

    @pytest.mark.asyncio
    async def test_transition_at_risk_to_overdue(self, db_session) -> None:
        """Commitment whose deadline has passed transitions to OVERDUE status."""
        c = make_commitment(status=CommitmentStatus.AT_RISK)
        # Set deadline to 2 hours ago
        c.resolved_deadline = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add(c)
        await db_session.commit()

        await update_commitment_statuses(db_session)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.OVERDUE
