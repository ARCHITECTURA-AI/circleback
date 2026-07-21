"""Tests for the Digest Generator and Human Correction Loop.

TDD: These tests define the format and structure of daily/weekly digests,
and verify the correction loop actions (done, dismiss, new_deadline).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from circleback.db.models import (
    CommitmentDirection,
    CommitmentStatus,
    CommitmentEventType,
    CommitmentEvent,
)
from circleback.pipeline.digest import generate_digest, apply_commitment_correction
from tests.conftest import make_commitment, MOCK_USER_ID


class TestDigestAndCorrection:
    """Digest structure and human-in-the-loop action tests."""

    @pytest.mark.asyncio
    async def test_digest_groups_by_direction(self, db_session) -> None:
        """Digest groups commitments into outbound (made_by_user) and inbound (owed_to_user)."""
        # Create outbound commitment
        c1 = make_commitment(
            raw_text_span="I'll send the deck",
            direction=CommitmentDirection.MADE_BY_USER,
            status=CommitmentStatus.OPEN
        )
        # Create inbound commitment
        c2 = make_commitment(
            raw_text_span="He will send the data",
            direction=CommitmentDirection.OWED_TO_USER,
            status=CommitmentStatus.OPEN
        )
        db_session.add_all([c1, c2])
        await db_session.commit()

        digest = await generate_digest(db_session, user_id=MOCK_USER_ID)
        
        # Verify structure
        assert "made_by_user" in digest
        assert "owed_to_user" in digest
        assert len(digest["made_by_user"]) >= 1
        assert len(digest["owed_to_user"]) >= 1

    @pytest.mark.asyncio
    async def test_correction_done_fulfills_commitment(self, db_session) -> None:
        """Applying 'done' correction updates status to FULFILLED and logs a confirmed event."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        db_session.add(c)
        await db_session.commit()

        await apply_commitment_correction(db_session, c.id, "done", user_id=MOCK_USER_ID)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.FULFILLED

        # Verify event
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        assert events[-1].type == CommitmentEventType.CONFIRMED

    @pytest.mark.asyncio
    async def test_correction_dismiss_dismisses_commitment(self, db_session) -> None:
        """Applying 'dismiss' correction updates status to DISMISSED and logs a dismissed event."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        db_session.add(c)
        await db_session.commit()

        await apply_commitment_correction(db_session, c.id, "dismiss", user_id=MOCK_USER_ID)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.DISMISSED

        # Verify event
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        assert events[-1].type == CommitmentEventType.DISMISSED

    @pytest.mark.asyncio
    async def test_correction_new_deadline_renegotiates(self, db_session) -> None:
        """Applying 'new_deadline' correction updates deadline and transitions status to RENEGOTIATED."""
        c = make_commitment(status=CommitmentStatus.OPEN)
        db_session.add(c)
        await db_session.commit()

        new_deadline = datetime.now(timezone.utc) + timedelta(days=5)
        await apply_commitment_correction(
            db_session,
            c.id,
            "new_deadline",
            params={"new_deadline": new_deadline.isoformat()},
            user_id=MOCK_USER_ID,
        )

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.RENEGOTIATED
        assert c.resolved_deadline is not None
        assert c.resolved_deadline.day == new_deadline.day

        # Verify event
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        assert events[-1].type == CommitmentEventType.RENEGOTIATED
