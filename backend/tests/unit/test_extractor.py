"""Tests for the LLM Extraction node.

TDD: These tests define the structured extraction contract: identifying commitments,
direction, confidence scores, types, and excluding non-commitments.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from circleback.db.models import ChannelType, CommitmentDirection, CommitmentStatus, CommitmentType
from circleback.pipeline.extractor import extract_commitments_from_message
from tests.conftest import make_message, make_person


class TestLLMCommitmentExtraction:
    """Commitment extraction logic tests with mocked LLM output."""

    @pytest.mark.asyncio
    @patch("circleback.pipeline.extractor.call_llm_for_extraction")
    async def test_extract_simple_commitment(self, mock_call_llm, db_session) -> None:
        """A clear commitment is extracted with correct committer and simple type."""
        # Setup sender
        sender = make_person(display_name="Alice", email_addresses=["alice@co.com"])
        db_session.add(sender)
        await db_session.commit()

        msg = make_message(
            raw_text="I'll send you the deck by Friday",
            channel=ChannelType.EMAIL,
            sender_person_id=sender.id
        )
        db_session.add(msg)
        await db_session.commit()

        # Mock LLM to return standard structured JSON
        mock_call_llm.return_value = {
            "commitments": [
                {
                    "raw_text_span": "I'll send you the deck by Friday",
                    "commitment_type": "simple",
                    "raw_temporal_phrase": "by Friday",
                    "extraction_confidence": 0.95,
                    "committer_identifier": "alice@co.com",
                    "recipient_identifiers": ["self@company.com"],
                    "is_commitment": True
                }
            ]
        }

        # Run extraction
        commitments = await extract_commitments_from_message(db_session, msg, self_email="self@company.com")

        assert len(commitments) == 1
        c = commitments[0]
        assert c.raw_text_span == "I'll send you the deck by Friday"
        assert c.commitment_type == CommitmentType.SIMPLE
        assert c.direction == CommitmentDirection.OWED_TO_USER  # Alice (sender) promised self (recipient)
        assert c.status == CommitmentStatus.OPEN
        assert c.extraction_confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    @patch("circleback.pipeline.extractor.call_llm_for_extraction")
    async def test_extract_detects_direction_made_by_user(self, mock_call_llm, db_session) -> None:
        """When self is the sender, the direction of the commitment is made_by_user."""
        self_user = make_person(display_name="Me", email_addresses=["me@company.com"], is_self=True)
        db_session.add(self_user)
        await db_session.commit()

        msg = make_message(
            raw_text="I will finish this by Monday",
            channel=ChannelType.EMAIL,
            sender_person_id=self_user.id
        )
        db_session.add(msg)
        await db_session.commit()

        mock_call_llm.return_value = {
            "commitments": [
                {
                    "raw_text_span": "I will finish this by Monday",
                    "commitment_type": "simple",
                    "raw_temporal_phrase": "by Monday",
                    "extraction_confidence": 0.9,
                    "committer_identifier": "me@company.com",
                    "recipient_identifiers": ["boss@company.com"],
                    "is_commitment": True
                }
            ]
        }

        commitments = await extract_commitments_from_message(db_session, msg, self_email="me@company.com")
        assert len(commitments) == 1
        assert commitments[0].direction == CommitmentDirection.MADE_BY_USER

    @pytest.mark.asyncio
    @patch("circleback.pipeline.extractor.call_llm_for_extraction")
    async def test_extract_group_commitment_excluded(self, mock_call_llm, db_session) -> None:
        """Group commitments with no individual owner ('we'll circle back') are excluded."""
        sender = make_person(display_name="Alice", email_addresses=["alice@co.com"])
        db_session.add(sender)
        await db_session.commit()

        msg = make_message(
            raw_text="We will circle back on this next week",
            channel=ChannelType.EMAIL,
            sender_person_id=sender.id
        )
        db_session.add(msg)
        await db_session.commit()

        # LLM flags it is_commitment = False because no individual owner
        mock_call_llm.return_value = {
            "commitments": [
                {
                    "raw_text_span": "We will circle back on this next week",
                    "commitment_type": "simple",
                    "raw_temporal_phrase": "next week",
                    "extraction_confidence": 0.3,
                    "committer_identifier": "",
                    "recipient_identifiers": [],
                    "is_commitment": False
                }
            ]
        }

        commitments = await extract_commitments_from_message(db_session, msg, self_email="self@company.com")
        assert len(commitments) == 0

    @pytest.mark.asyncio
    @patch("circleback.pipeline.extractor.call_llm_for_extraction")
    async def test_extract_delegated_type(self, mock_call_llm, db_session) -> None:
        """Delegated commitments (I'll get X to do Y) are categorized as delegated."""
        sender = make_person(display_name="Alice", email_addresses=["alice@co.com"])
        db_session.add(sender)
        await db_session.commit()

        msg = make_message(
            raw_text="I'll get Sarah to send the document",
            channel=ChannelType.EMAIL,
            sender_person_id=sender.id
        )
        db_session.add(msg)
        await db_session.commit()

        mock_call_llm.return_value = {
            "commitments": [
                {
                    "raw_text_span": "I'll get Sarah to send the document",
                    "commitment_type": "delegated",
                    "raw_temporal_phrase": "",
                    "extraction_confidence": 0.88,
                    "committer_identifier": "alice@co.com",
                    "recipient_identifiers": ["self@company.com"],
                    "is_commitment": True
                }
            ]
        }

        commitments = await extract_commitments_from_message(db_session, msg, self_email="self@company.com")
        assert len(commitments) == 1
        assert commitments[0].commitment_type == CommitmentType.DELEGATED
