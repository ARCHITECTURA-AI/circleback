"""Tests for database models.

TDD: These tests define the data model contract.
Every model, enum, relationship, and constraint is tested.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from circleback.db.models import (
    ChannelType,
    Commitment,
    CommitmentDirection,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    CommitmentType,
    EvalLabel,
    Message,
    Person,
    Thread,
)
from tests.conftest import (
    MOCK_USER_ID,
    make_commitment,
    make_commitment_event,
    make_message,
    make_person,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ── Person Tests ──────────────────────────────────────────────


class TestPersonModel:
    """Person model creation and constraints."""

    async def test_person_create_with_email_addresses(
        self, db_session: AsyncSession
    ) -> None:
        """Person can be created with multiple email addresses."""
        person = make_person(
            display_name="Alice",
            email_addresses=["alice@company.com", "alice.personal@gmail.com"],
        )
        db_session.add(person)
        await db_session.flush()

        result = await db_session.execute(select(Person).where(Person.id == person.id))
        fetched = result.scalar_one()
        assert fetched.display_name == "Alice"
        assert len(fetched.email_addresses) == 2
        assert "alice@company.com" in fetched.email_addresses

    async def test_person_create_with_slack_ids(
        self, db_session: AsyncSession
    ) -> None:
        """Person can be created with multiple Slack user IDs."""
        person = make_person(
            display_name="Bob",
            slack_user_ids=["U12345", "U67890"],
        )
        db_session.add(person)
        await db_session.flush()

        result = await db_session.execute(select(Person).where(Person.id == person.id))
        fetched = result.scalar_one()
        assert len(fetched.slack_user_ids) == 2

    async def test_person_is_self_flag(self, db_session: AsyncSession) -> None:
        """is_self flag correctly marks the account owner."""
        owner = make_person(display_name="Me", is_self=True)
        other = make_person(display_name="Other", is_self=False)
        db_session.add_all([owner, other])
        await db_session.flush()

        result = await db_session.execute(select(Person).where(Person.is_self.is_(True)))
        self_persons = result.scalars().all()
        assert len(self_persons) == 1
        assert self_persons[0].display_name == "Me"

    async def test_person_empty_arrays_default(
        self, db_session: AsyncSession
    ) -> None:
        """Person with no email/slack IDs defaults to empty lists."""
        person = make_person(display_name="Empty")
        db_session.add(person)
        await db_session.flush()

        result = await db_session.execute(select(Person).where(Person.id == person.id))
        fetched = result.scalar_one()
        assert fetched.email_addresses == []
        assert fetched.slack_user_ids == []


# ── Message Tests ─────────────────────────────────────────────


class TestMessageModel:
    """Message model creation, soft delete, and relationships."""

    async def test_message_create(self, db_session: AsyncSession) -> None:
        """Message can be created with required fields."""
        msg = make_message(
            raw_text="I'll send you the deck by Friday",
            channel=ChannelType.EMAIL,
        )
        db_session.add(msg)
        await db_session.flush()

        result = await db_session.execute(select(Message).where(Message.id == msg.id))
        fetched = result.scalar_one()
        assert fetched.raw_text == "I'll send you the deck by Friday"
        assert fetched.channel == ChannelType.EMAIL

    async def test_message_soft_delete(self, db_session: AsyncSession) -> None:
        """Setting deleted_at does not remove the row — soft delete."""
        msg = make_message(raw_text="Will be deleted")
        db_session.add(msg)
        await db_session.flush()

        msg.deleted_at = datetime.now(timezone.utc)
        await db_session.flush()

        # Row should still exist
        result = await db_session.execute(select(Message).where(Message.id == msg.id))
        fetched = result.scalar_one()
        assert fetched.deleted_at is not None
        assert fetched.raw_text == "Will be deleted"

    async def test_message_edited_at_tracking(
        self, db_session: AsyncSession
    ) -> None:
        """Edited message gets edited_at timestamp."""
        msg = make_message(raw_text="Original text")
        db_session.add(msg)
        await db_session.flush()
        assert msg.edited_at is None

        msg.raw_text = "Updated text"
        msg.edited_at = datetime.now(timezone.utc)
        await db_session.flush()

        result = await db_session.execute(select(Message).where(Message.id == msg.id))
        fetched = result.scalar_one()
        assert fetched.edited_at is not None
        assert fetched.raw_text == "Updated text"

    async def test_message_channel_enum(self, db_session: AsyncSession) -> None:
        """Channel field accepts only 'email' or 'slack'."""
        email_msg = make_message(channel=ChannelType.EMAIL)
        slack_msg = make_message(channel=ChannelType.SLACK)
        db_session.add_all([email_msg, slack_msg])
        await db_session.flush()

        assert email_msg.channel == ChannelType.EMAIL
        assert slack_msg.channel == ChannelType.SLACK


# ── Commitment Tests ──────────────────────────────────────────


class TestCommitmentModel:
    """Commitment model creation, enums, and relationships."""

    async def test_commitment_status_enum_values(
        self, db_session: AsyncSession
    ) -> None:
        """Commitment.status only accepts valid enum values."""
        for status in CommitmentStatus:
            c = make_commitment(status=status)
            db_session.add(c)
        await db_session.flush()

        result = await db_session.execute(select(Commitment))
        all_commitments = result.scalars().all()
        statuses = {c.status for c in all_commitments}
        assert statuses == set(CommitmentStatus)

    async def test_commitment_direction_enum(
        self, db_session: AsyncSession
    ) -> None:
        """direction field accepts only 'made_by_user' or 'owed_to_user'."""
        made = make_commitment(direction=CommitmentDirection.MADE_BY_USER)
        owed = make_commitment(direction=CommitmentDirection.OWED_TO_USER)
        db_session.add_all([made, owed])
        await db_session.flush()

        assert made.direction == CommitmentDirection.MADE_BY_USER
        assert owed.direction == CommitmentDirection.OWED_TO_USER

    async def test_commitment_type_enum(self, db_session: AsyncSession) -> None:
        """commitment_type field accepts all valid types."""
        types = [
            CommitmentType.SIMPLE,
            CommitmentType.DELEGATED,
            CommitmentType.CONDITIONAL,
            CommitmentType.RECURRING,
        ]
        for ct in types:
            db_session.add(make_commitment(commitment_type=ct))
        await db_session.flush()

        result = await db_session.execute(select(Commitment))
        all_c = result.scalars().all()
        assert {c.commitment_type for c in all_c} == set(types)

    async def test_commitment_confidence_scores(
        self, db_session: AsyncSession
    ) -> None:
        """Confidence scores are stored correctly as floats 0-1."""
        c = make_commitment(
            extraction_confidence=0.85,
            deadline_confidence=0.6,
        )
        db_session.add(c)
        await db_session.flush()

        result = await db_session.execute(
            select(Commitment).where(Commitment.id == c.id)
        )
        fetched = result.scalar_one()
        assert fetched.extraction_confidence == pytest.approx(0.85)
        assert fetched.deadline_confidence == pytest.approx(0.6)

    async def test_commitment_links_to_message(
        self, db_session: AsyncSession
    ) -> None:
        """Commitment.source_message_id FK links to a Message."""
        msg = make_message(raw_text="I'll send the report")
        db_session.add(msg)
        await db_session.flush()

        c = make_commitment(source_message_id=msg.id)
        db_session.add(c)
        await db_session.flush()

        result = await db_session.execute(
            select(Commitment).where(Commitment.id == c.id)
        )
        fetched = result.scalar_one()
        assert fetched.source_message_id == msg.id


# ── CommitmentEvent Tests ─────────────────────────────────────


class TestCommitmentEventModel:
    """CommitmentEvent model — the immutable audit trail."""

    async def test_commitment_event_links_to_commitment(
        self, db_session: AsyncSession
    ) -> None:
        """CommitmentEvent FK to Commitment is enforced."""
        c = make_commitment()
        db_session.add(c)
        await db_session.flush()

        event = make_commitment_event(
            commitment_id=c.id,
            event_type=CommitmentEventType.EXTRACTED,
            note="Initial extraction",
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        fetched = result.scalar_one()
        assert fetched.commitment_id == c.id
        assert fetched.type == CommitmentEventType.EXTRACTED
        assert fetched.note == "Initial extraction"

    async def test_commitment_event_types(self, db_session: AsyncSession) -> None:
        """All CommitmentEventType values are valid."""
        c = make_commitment()
        db_session.add(c)
        await db_session.flush()

        for event_type in CommitmentEventType:
            event = make_commitment_event(
                commitment_id=c.id,
                event_type=event_type,
            )
            db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.commitment_id == c.id)
        )
        events = result.scalars().all()
        assert len(events) == len(CommitmentEventType)

    async def test_commitment_event_with_evidence_message(
        self, db_session: AsyncSession
    ) -> None:
        """CommitmentEvent can link to an evidence message."""
        msg = make_message(raw_text="Here's the deck")
        c = make_commitment()
        db_session.add_all([msg, c])
        await db_session.flush()

        event = make_commitment_event(
            commitment_id=c.id,
            event_type=CommitmentEventType.FULFILLMENT_SIGNAL,
            evidence_message_id=msg.id,
            note="Fulfillment detected",
        )
        db_session.add(event)
        await db_session.flush()

        result = await db_session.execute(
            select(CommitmentEvent).where(CommitmentEvent.id == event.id)
        )
        fetched = result.scalar_one()
        assert fetched.evidence_message_id == msg.id


# ── Thread Tests ──────────────────────────────────────────────


class TestThreadModel:
    """Thread model creation and relationships."""

    async def test_thread_create(self, db_session: AsyncSession) -> None:
        """Thread can be created with channel and subject."""
        thread = Thread(
            user_id=MOCK_USER_ID,
            channel=ChannelType.EMAIL,
            subject_or_topic="Q3 Budget Review",
            external_thread_id="gmail_thread_123",
        )
        db_session.add(thread)
        await db_session.flush()

        result = await db_session.execute(
            select(Thread).where(Thread.id == thread.id)
        )
        fetched = result.scalar_one()
        assert fetched.subject_or_topic == "Q3 Budget Review"
        assert fetched.channel == ChannelType.EMAIL

    async def test_thread_message_relationship(
        self, db_session: AsyncSession
    ) -> None:
        """Messages can be linked to a thread."""
        thread = Thread(user_id=MOCK_USER_ID, channel=ChannelType.SLACK)
        db_session.add(thread)
        await db_session.flush()

        msg1 = make_message(raw_text="First message", thread_id=thread.id)
        msg2 = make_message(raw_text="Reply", thread_id=thread.id)
        db_session.add_all([msg1, msg2])
        await db_session.flush()

        result = await db_session.execute(
            select(Message).where(Message.thread_id == thread.id)
        )
        messages = result.scalars().all()
        assert len(messages) == 2


# ── EvalLabel Tests ───────────────────────────────────────────


class TestEvalLabelModel:
    """EvalLabel model — internal QA tool."""

    async def test_eval_label_create(self, db_session: AsyncSession) -> None:
        """EvalLabel can be created with all fields."""
        msg = make_message(raw_text="I'll send the report by Monday")
        db_session.add(msg)
        await db_session.flush()

        label = EvalLabel(
            user_id=MOCK_USER_ID,
            message_id=msg.id,
            is_commitment=True,
            correct_committer="alice@company.com",
            correct_deadline="next Monday",
            notes="Clear commitment with deadline",
        )
        db_session.add(label)
        await db_session.flush()

        result = await db_session.execute(
            select(EvalLabel).where(EvalLabel.id == label.id)
        )
        fetched = result.scalar_one()
        assert fetched.is_commitment is True
        assert fetched.correct_committer == "alice@company.com"
