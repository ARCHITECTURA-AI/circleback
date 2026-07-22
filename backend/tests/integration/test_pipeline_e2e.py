"""End-to-End Integration tests for the LangGraph pipeline.

TDD: These tests verify that the entire agent pipeline (from message ingestion,
prefiltering, extraction, linking, temporal resolution, status update) runs in
the correct order and updates database state reliably.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from circleback.db.models import (
    ChannelType,
    Commitment,
    CommitmentDirection,
    CommitmentStatus,
    CommitmentType,
    Thread,
)
from circleback.pipeline.graph import compile_pipeline_graph
from tests.conftest import MOCK_USER_ID, make_message, make_person


class TestPipelineE2E:
    """End-to-end graph execution tests."""

    @pytest.mark.asyncio
    @patch("circleback.pipeline.extractor.call_llm_for_extraction")
    async def test_pipeline_message_to_commitment_e2e(
        self, mock_call_llm, db_session
    ) -> None:
        """Raw message is processed through full graph resulting in a resolved, linked commitment."""
        # 1. Setup Person (self)
        self_user = make_person(display_name="Me", email_addresses=["me@company.com"], is_self=True)
        db_session.add(self_user)
        await db_session.commit()

        # 2. Setup Thread
        thread = Thread(user_id=MOCK_USER_ID, channel=ChannelType.EMAIL, external_thread_id="thread_e2e_123")
        db_session.add(thread)
        await db_session.commit()

        # 3. Create message in DB
        msg = make_message(
            raw_text="I will deliver the monthly reports by tomorrow",
            channel=ChannelType.EMAIL,
            sender_person_id=self_user.id,
            thread_id=thread.id
        )
        msg.sender_handle = "me@company.com"
        db_session.add(msg)
        await db_session.commit()

        # 4. Mock LLM output
        mock_call_llm.return_value = {
            "commitments": [
                {
                    "raw_text_span": "I will deliver the monthly reports by tomorrow",
                    "commitment_type": "simple",
                    "raw_temporal_phrase": "tomorrow",
                    "extraction_confidence": 0.95,
                    "committer_identifier": "me@company.com",
                    "recipient_identifiers": ["boss@company.com"],
                    "is_commitment": True
                }
            ]
        }

        # 5. Compile and invoke the LangGraph pipeline
        graph = compile_pipeline_graph()

        # Invoke the graph with the initial state
        initial_state = {
            "user_id": MOCK_USER_ID,
            "message_id": msg.id,
            "external_thread_id": "thread_e2e_123",
            "self_email": "me@company.com"
        }

        await graph.ainvoke(initial_state, {"configurable": {"thread_id": msg.id, "db": db_session, "user_id": MOCK_USER_ID}})

        # 6. Verify database side effects
        from sqlalchemy import select
        res = await db_session.execute(select(Commitment).where(Commitment.source_message_id == msg.id))
        commitments = res.scalars().all()

        assert len(commitments) == 1
        c = commitments[0]
        assert c.raw_text_span == "I will deliver the monthly reports by tomorrow"
        assert c.commitment_type == CommitmentType.SIMPLE
        assert c.direction == CommitmentDirection.MADE_BY_USER
        assert c.status == CommitmentStatus.OPEN
        assert c.resolved_deadline is not None
        assert c.resolved_deadline.day == (datetime.now(timezone.utc) + timedelta(days=1)).day
