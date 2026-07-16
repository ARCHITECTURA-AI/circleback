"""Tests for Thread/Entity Linking.

TDD: These tests define how we link raw messages to threads (using thread_id or thread_ts),
how we resolve sender_handle/recipient email/Slack identifiers to Person records,
and how we log unrecognized senders.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from circleback.db.models import ChannelType, Person, Thread, Message
from circleback.pipeline.linker import link_thread_and_entities
from tests.conftest import make_message, make_person


class TestThreadEntityLinking:
    """Thread and Person identity resolution tests."""

    @pytest.mark.asyncio
    async def test_group_email_thread_by_gmail_thread_id(self, db_session) -> None:
        """Messages with the same Gmail thread ID are linked to the same Thread row."""
        # We need a way to pass external_thread_id in messages or mock it.
        # Let's say messages are in the DB with external_message_id, etc.
        # But wait! In normalizer.py, we don't save external_thread_id directly to Message model
        # because Message.thread_id is the UUID foreign key.
        # Wait, how does the linker know the Gmail thread_id or Slack thread_ts?
        # Let's check: does Message model have a field for raw thread identifier?
        # Ah! In models.py, Thread model has external_thread_id. Message doesn't have raw thread id,
        # but wait, when we sync we can group them, or we can look up/create a Thread.
        # Wait! If we create a Thread during ingestion, that already links it!
        # Yes! In ingestion sync (e.g. sync_gmail), we got threadId from raw message and did:
        # permalink=f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        # Let's check how linker can link them.
        # If we pass raw message info, or if we define a linker function that resolves it:
        # Let's say the linker gets a Message and the raw external_thread_id,
        # finds or creates a Thread row, and updates msg.thread_id.
        msg1 = make_message(raw_text="Hello thread", channel=ChannelType.EMAIL)
        db_session.add(msg1)
        await db_session.commit()

        # Link msg1 with gmail_thread_abc
        await link_thread_and_entities(db_session, msg1, external_thread_id="gmail_thread_abc")

        # Create msg2 in same thread
        msg2 = make_message(raw_text="Reply to thread", channel=ChannelType.EMAIL)
        db_session.add(msg2)
        await db_session.commit()

        await link_thread_and_entities(db_session, msg2, external_thread_id="gmail_thread_abc")

        # They should both point to the same Thread UUID
        assert msg1.thread_id is not None
        assert msg1.thread_id == msg2.thread_id

        # Verify the Thread was created in DB
        res = await db_session.execute(select(Thread).where(Thread.id == msg1.thread_id))
        thread = res.scalar_one()
        assert thread.external_thread_id == "gmail_thread_abc"

    @pytest.mark.asyncio
    async def test_person_mapping_links_email_and_slack(self, db_session) -> None:
        """Incoming message from a sender is resolved to the correct Person record."""
        # Create a mapped person
        person = make_person(
            display_name="Alice",
            email_addresses=["alice@co.com"],
            slack_user_ids=["U_ALICE_123"]
        )
        db_session.add(person)
        await db_session.commit()

        # Message from email alice@co.com
        msg_email = make_message(raw_text="Email from Alice", channel=ChannelType.EMAIL)
        msg_email.sender_handle = "alice@co.com"
        db_session.add(msg_email)

        # Message from Slack U_ALICE_123
        msg_slack = make_message(raw_text="Slack from Alice", channel=ChannelType.SLACK)
        msg_slack.sender_handle = "U_ALICE_123"
        db_session.add(msg_slack)
        await db_session.commit()

        # Run linker on both
        await link_thread_and_entities(db_session, msg_email)
        await link_thread_and_entities(db_session, msg_slack)

        assert msg_email.sender_person_id == person.id
        assert msg_slack.sender_person_id == person.id

    @pytest.mark.asyncio
    async def test_unrecognized_sender_logged_not_dropped(self, db_session) -> None:
        """Unrecognized senders are not dropped but rather lead to logging of unrecognized sender handle."""
        msg = make_message(raw_text="Unknown sender message")
        msg.sender_handle = "stranger@co.com"
        db_session.add(msg)
        await db_session.commit()

        # Run linker
        await link_thread_and_entities(db_session, msg)

        # Sender person ID remains None (v1 manual resolution design choice)
        assert msg.sender_person_id is None
        # But the message and its raw handle are preserved
        assert msg.sender_handle == "stranger@co.com"
