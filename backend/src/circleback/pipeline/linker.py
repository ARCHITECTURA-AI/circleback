"""Thread and Entity Linking node in the LangGraph agent pipeline.

Resolves message thread association (Gmail thread ID or Slack thread ts) and
maps raw sender/recipient email addresses or Slack user IDs to Person records.

Design decisions:
- Unrecognized senders are persisted to UnrecognizedSender table for later mapping (§6.5)
- Thread participant lists are updated when new senders are linked
- Manual seed list lookup via email_addresses[] and slack_user_ids[] on Person
"""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import Message, Person, Thread, UnrecognizedSender

logger = logging.getLogger(__name__)


async def link_thread_and_entities(
    db: AsyncSession,
    msg: Message,
    external_thread_id: str | None = None,
) -> None:
    """Group message into Thread and map sender identifier to a Person record."""

    # 1. Thread Grouping
    if external_thread_id:
        result = await db.execute(
            select(Thread).where(
                Thread.external_thread_id == external_thread_id,
                Thread.channel == msg.channel,
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            thread = Thread(
                channel=msg.channel,
                external_thread_id=external_thread_id,
                participant_person_ids=[],
            )
            db.add(thread)
            await db.flush()

        msg.thread_id = thread.id

    # 2. Entity / Person Mapping
    if msg.sender_handle and not msg.sender_person_id:
        handle = msg.sender_handle.strip().lower()

        # Load all Person records
        res = await db.execute(select(Person))
        persons = res.scalars().all()

        matched_person = None
        for person in persons:
            # Check emails
            emails = [e.lower() for e in person.email_addresses]
            if handle in emails:
                matched_person = person
                break

            # Check slack IDs
            slack_ids = [s.lower() for s in person.slack_user_ids]
            if handle in slack_ids:
                matched_person = person
                break

        if matched_person:
            msg.sender_person_id = matched_person.id

            # Update thread participant list if not already present
            if msg.thread_id:
                thread_result = await db.execute(
                    select(Thread).where(Thread.id == msg.thread_id)
                )
                thread = thread_result.scalar_one_or_none()
                if thread and matched_person.id not in thread.participant_person_ids:
                    # Create a new list to trigger SQLAlchemy change detection
                    updated_participants = list(thread.participant_person_ids) + [matched_person.id]
                    thread.participant_person_ids = updated_participants
        else:
            # Persist unrecognized sender for later manual mapping (spec §6.5)
            # Check if already recorded
            existing = await db.execute(
                select(UnrecognizedSender).where(
                    UnrecognizedSender.handle == handle,
                    UnrecognizedSender.channel == msg.channel,
                )
            )
            if not existing.scalar_one_or_none():
                unrecognized = UnrecognizedSender(
                    handle=handle,
                    channel=msg.channel,
                    sample_message_id=msg.id,
                )
                db.add(unrecognized)

            logger.warning(
                "Unrecognized sender handle '%s' on message '%s' — persisted for review",
                msg.sender_handle,
                msg.id,
            )

    await db.flush()
