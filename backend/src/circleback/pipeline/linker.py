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
    user_id: str | None = None,
) -> None:
    """Group message into Thread and map sender/recipient identifiers to Person records."""
    resolved_user_id = user_id or getattr(msg, "user_id", None)

    # 1. Thread Grouping
    if external_thread_id:
        result = await db.execute(
            select(Thread).where(
                Thread.external_thread_id == external_thread_id,
                Thread.channel == msg.channel,
                Thread.user_id == resolved_user_id,
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            thread = Thread(
                user_id=resolved_user_id,
                channel=msg.channel,
                external_thread_id=external_thread_id,
                participant_person_ids=[],
            )
            db.add(thread)
            await db.flush()

        msg.thread_id = thread.id

    # 2. Entity / Person Mapping
    # Load all Person records for this user
    res = await db.execute(select(Person).where(Person.user_id == resolved_user_id))
    persons = res.scalars().all()

    if msg.sender_handle and not msg.sender_person_id:
        handle = msg.sender_handle.strip().lower()

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
                    select(Thread).where(Thread.id == msg.thread_id, Thread.user_id == resolved_user_id)
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
                    UnrecognizedSender.user_id == resolved_user_id,
                )
            )
            if not existing.scalar_one_or_none():
                unrecognized = UnrecognizedSender(
                    user_id=resolved_user_id,
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

    # 3. Recipient Person Mapping (Phase 5)
    if msg.recipient_person_ids:
        resolved_recipients = []
        for recipient_handle in msg.recipient_person_ids:
            handle = str(recipient_handle).strip().lower()
            matched_recipient = None
            for person in persons:
                emails = [e.lower() for e in person.email_addresses]
                if handle in emails:
                    matched_recipient = person
                    break
                slack_ids = [s.lower() for s in person.slack_user_ids]
                if handle in slack_ids:
                    matched_recipient = person
                    break

            if matched_recipient:
                resolved_recipients.append(matched_recipient.id)
                # Also add to thread participants if not already there
                if msg.thread_id:
                    thread_result = await db.execute(
                        select(Thread).where(Thread.id == msg.thread_id, Thread.user_id == resolved_user_id)
                    )
                    thread = thread_result.scalar_one_or_none()
                    if thread and matched_recipient.id not in thread.participant_person_ids:
                        updated_participants = list(thread.participant_person_ids) + [matched_recipient.id]
                        thread.participant_person_ids = updated_participants
            else:
                resolved_recipients.append(recipient_handle)

        msg.recipient_person_ids = resolved_recipients

    await db.flush()
