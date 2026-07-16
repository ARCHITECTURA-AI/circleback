"""Slack ingestion client and sync logic.

Uses the Slack Web API to sync channel history and process real-time events,
normalizing them into the Message model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import ChannelType, Commitment, CommitmentEvent, CommitmentEventType, Message
from circleback.ingestion.normalizer import normalize_slack_message


class DummySlackClient:
    """Mockable wrapper for Slack Web Client."""
    def conversations_history(self, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "messages": [], "response_metadata": {"next_cursor": ""}}


def build_slack_client(token: str) -> Any:
    """Build and return a Slack Web Client."""
    return DummySlackClient()


async def sync_slack_channel(
    db: AsyncSession,
    channel_id: str,
    token: str,
) -> None:
    """Sync full history of a Slack channel using cursor pagination."""
    # Find self email to determine commitment direction
    from circleback.db.models import Person
    self_res = await db.execute(select(Person).where(Person.is_self == True))
    self_person = self_res.scalar_one_or_none()
    self_email = self_person.email_addresses[0] if (self_person and self_person.email_addresses) else ""

    from circleback.pipeline.graph import run_pipeline_for_message

    client = build_slack_client(token)
    cursor = None

    while True:
        kwargs: dict[str, Any] = {"channel": channel_id, "limit": 100}
        if cursor:
            kwargs["cursor"] = cursor

        response = client.conversations_history(**kwargs)
        if not response.get("ok"):
            break

        messages = response.get("messages", [])
        for raw_msg in messages:
            ts = raw_msg.get("ts")
            if not ts:
                continue

            # Check if message already exists
            res = await db.execute(select(Message).where(Message.external_message_id == ts))
            existing_msg = res.scalar_one_or_none()

            normalized = normalize_slack_message(raw_msg)
            normalized.external_message_id = ts

            if not existing_msg:
                db.add(normalized)
                await db.flush()
                # Run pipeline for new message
                await run_pipeline_for_message(db, normalized.id, external_thread_id=normalized.thread_id, self_email=self_email)

        await db.flush()

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break


async def handle_slack_event(db: AsyncSession, event: dict[str, Any]) -> None:
    """Process a real-time event from the Slack Events API."""
    # Find self email to determine commitment direction
    from circleback.db.models import Person
    self_res = await db.execute(select(Person).where(Person.is_self == True))
    self_person = self_res.scalar_one_or_none()
    self_email = self_person.email_addresses[0] if (self_person and self_person.email_addresses) else ""

    from circleback.pipeline.graph import run_pipeline_for_message

    event_type = event.get("type")
    if event_type != "message":
        return

    subtype = event.get("subtype")

    if subtype == "message_changed":
        sub_msg = event.get("message", {})
        ts = sub_msg.get("ts")
        text = sub_msg.get("text", "")
        if ts:
            res = await db.execute(select(Message).where(Message.external_message_id == ts))
            msg = res.scalar_one_or_none()
            if msg:
                msg.raw_text = text
                msg.edited_at = datetime.now(timezone.utc)
                await db.flush()
                # Run pipeline for edited message
                await run_pipeline_for_message(db, msg.id, self_email=self_email)

    elif subtype == "message_deleted":
        deleted_ts = event.get("deleted_ts")
        if deleted_ts:
            res = await db.execute(select(Message).where(Message.external_message_id == deleted_ts))
            msg = res.scalar_one_or_none()
            if msg:
                msg.deleted_at = datetime.now(timezone.utc)

                # Create RETRACTED_SOURCE CommitmentEvent for all linked commitments
                c_res = await db.execute(select(Commitment).where(Commitment.source_message_id == msg.id))
                commitments = c_res.scalars().all()
                for commitment in commitments:
                    event_record = CommitmentEvent(
                        commitment_id=commitment.id,
                        type=CommitmentEventType.RETRACTED_SOURCE,
                        note="Source Slack message was deleted."
                    )
                    db.add(event_record)
                await db.flush()

    else:
        # Standard new message event
        ts = event.get("ts")
        if ts:
            res = await db.execute(select(Message).where(Message.external_message_id == ts))
            existing = res.scalar_one_or_none()
            if not existing:
                normalized = normalize_slack_message(event)
                normalized.external_message_id = ts
                db.add(normalized)
                await db.flush()
                # Run pipeline for new message
                await run_pipeline_for_message(db, normalized.id, external_thread_id=normalized.thread_id, self_email=self_email)
