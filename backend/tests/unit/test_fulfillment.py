"""Tests for the Fulfillment Matcher.

TDD: These tests define how follow-up messages are semantically matched to open
commitments on a thread, how renegotiations update deadlines, and how audit trails are created.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from circleback.db.models import (
    ChannelType,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    Thread,
)
from circleback.pipeline.fulfillment import process_thread_fulfillment
from tests.conftest import MOCK_USER_ID, make_commitment, make_message


class TestFulfillmentMatcher:
    """Fulfillment and renegotiation matching logic tests."""

    @pytest.mark.asyncio
    @patch("circleback.pipeline.fulfillment.call_llm_for_matching")
    async def test_fulfillment_matches_specific_commitment(
        self, mock_call_llm, db_session
    ) -> None:
        """A follow-up message saying 'Here is the deck' resolves 'I will send the deck'."""
        # Create thread
        thread = Thread(user_id=MOCK_USER_ID, channel=ChannelType.EMAIL, external_thread_id="thread_abc")
        db_session.add(thread)
        await db_session.commit()

        # Create commitment
        c = make_commitment(
            raw_text_span="I will send you the deck by Friday",
            status=CommitmentStatus.OPEN,
            thread_id=thread.id
        )
        db_session.add(c)
        await db_session.commit()

        # Follow-up message
        msg = make_message(raw_text="Here is the deck you wanted")
        msg.thread_id = thread.id
        db_session.add(msg)
        await db_session.commit()

        # Mock LLM to return a match
        mock_call_llm.return_value = {
            "matches": [
                {
                    "commitment_id": c.id,
                    "action": "fulfill",
                    "reason": "Sender provided the deck",
                    "new_deadline": None
                }
            ]
        }

        await process_thread_fulfillment(db_session, thread.id, msg)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.FULFILLED

        # Verify event was recorded by querying directly
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        event = events[0]
        assert event.type == CommitmentEventType.FULFILLMENT_SIGNAL
        assert event.evidence_message_id == msg.id

    @pytest.mark.asyncio
    @patch("circleback.pipeline.fulfillment.call_llm_for_matching")
    async def test_fulfillment_does_not_match_unrelated_followup(
        self, mock_call_llm, db_session
    ) -> None:
        """A follow-up like 'Thanks, sounds good' does not fulfill a commitment."""
        # Create thread
        thread = Thread(user_id=MOCK_USER_ID, channel=ChannelType.EMAIL, external_thread_id="thread_def")
        db_session.add(thread)
        await db_session.commit()

        c = make_commitment(
            raw_text_span="I'll send the monthly report",
            status=CommitmentStatus.OPEN,
            thread_id=thread.id
        )
        db_session.add(c)
        await db_session.commit()

        msg = make_message(raw_text="Thanks, sounds good")
        msg.thread_id = thread.id
        db_session.add(msg)
        await db_session.commit()

        # Mock LLM to return no matches
        mock_call_llm.return_value = {"matches": []}

        await process_thread_fulfillment(db_session, thread.id, msg)

        await db_session.refresh(c)
        assert c.status == CommitmentStatus.OPEN

    @pytest.mark.asyncio
    @patch("circleback.pipeline.fulfillment.call_llm_for_matching")
    async def test_renegotiation_updates_existing_commitment(
        self, mock_call_llm, db_session
    ) -> None:
        """A message saying 'Let's push to next Tuesday' updates resolved_deadline and sets renegotiated status."""
        # Create thread
        thread = Thread(user_id=MOCK_USER_ID, channel=ChannelType.EMAIL, external_thread_id="thread_ghi")
        db_session.add(thread)
        await db_session.commit()

        c = make_commitment(
            raw_text_span="I will deliver the code by Friday",
            status=CommitmentStatus.OPEN,
            thread_id=thread.id
        )
        c.resolved_deadline = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
        db_session.add(c)
        await db_session.commit()

        msg = make_message(raw_text="Actually, let's push the delivery to next Tuesday")
        msg.thread_id = thread.id
        db_session.add(msg)
        await db_session.commit()

        # Mock LLM to return renegotiated target
        new_deadline_str = "2026-10-20T18:00:00Z"
        mock_call_llm.return_value = {
            "matches": [
                {
                    "commitment_id": c.id,
                    "action": "renegotiate",
                    "reason": "Pushed delivery date to next Tuesday",
                    "new_deadline": new_deadline_str
                }
            ]
        }

        await process_thread_fulfillment(db_session, thread.id, msg)

        await db_session.refresh(c)
        # Verify status and new deadline
        assert c.status == CommitmentStatus.RENEGOTIATED
        assert c.resolved_deadline is not None
        assert c.resolved_deadline.day == 20
        assert c.resolved_deadline.month == 10

        # Verify audit trail event by querying directly
        res_events = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = res_events.scalars().all()
        assert len(events) > 0
        event = events[-1]
        assert event.type == CommitmentEventType.RENEGOTIATED
        assert event.evidence_message_id == msg.id
