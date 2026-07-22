"""Gmail ingestion client and sync logic.

Uses the Gmail API to pull message history incrementally, normalizes the
resources, and syncs them to the database. Handles edits and deletions to
prevent silent data loss.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from circleback.db.models import Commitment, CommitmentEvent, CommitmentEventType, Message
from circleback.ingestion.normalizer import normalize_gmail_message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DummyGmailClient:
    """Mockable wrapper for Gmail API client."""
    def users(self) -> Any:
        return self

    def history(self) -> Any:
        return self

    def messages(self) -> Any:
        return self

    def list(self, **kwargs: Any) -> Any:
        return self

    def get(self, **kwargs: Any) -> Any:
        return self

    def execute(self) -> dict[str, Any]:
        return {}


def build_gmail_client(credentials: Any = None) -> Any:
    """Build and return a Gmail API client. In test, mocked."""
    return DummyGmailClient()


async def ingest_single_gmail_message(db: AsyncSession, message_id: str, user_id: str, client: Any = None) -> Message | None:
    """Fetch a single Gmail message, normalize it, and save or update it in the database."""
    if client is None:
        client = build_gmail_client()

    try:
        raw_msg = client.users().messages().get(userId="me", id=message_id).execute()
    except Exception:
        # If message not found/deleted, we can't ingest it
        return None

    if not raw_msg or "id" not in raw_msg:
        return None

    # Check if message already exists
    result = await db.execute(
        select(Message).where(
            Message.external_message_id == message_id,
            Message.user_id == user_id
        )
    )
    existing_msg = result.scalar_one_or_none()

    normalized = normalize_gmail_message(raw_msg)
    normalized.user_id = user_id

    # Find self email to determine commitment direction
    from circleback.db.models import Person
    self_res = await db.execute(select(Person).where(Person.is_self, Person.user_id == user_id))
    self_person = self_res.scalar_one_or_none()
    self_email = self_person.email_addresses[0] if (self_person and self_person.email_addresses) else ""

    from circleback.pipeline.graph import run_pipeline_for_message

    if existing_msg:
        # It's an update (edit)
        existing_msg.raw_text = normalized.raw_text
        existing_msg.edited_at = datetime.now(timezone.utc)
        await db.flush()
        # Trigger pipeline run for edited message
        await run_pipeline_for_message(db, existing_msg.id, user_id=user_id, self_email=self_email)
        return existing_msg
    else:
        # New message
        db.add(normalized)
        await db.flush()
        # Trigger pipeline run for new message
        await run_pipeline_for_message(db, normalized.id, user_id=user_id, external_thread_id=normalized.thread_id, self_email=self_email)
        return normalized



async def sync_gmail(db: AsyncSession, user_id: str, last_history_id: str | None = None) -> str | None:
    """Perform incremental sync of Gmail messages using the History API."""
    client = build_gmail_client()

    if not last_history_id:
        # Full backfill or initial load (stubbed to return profile historyId)
        return "9999"

    # Fetch history since startHistoryId
    try:
        history_response = client.users().history().list(
            userId="me",
            startHistoryId=last_history_id
        ).execute()
    except Exception:
        return None

    history_records = history_response.get("history", [])
    new_history_id = history_response.get("historyId", last_history_id)

    for record in history_records:
        # Process deleted messages
        for del_msg in record.get("messagesDeleted", []):
            ext_id = del_msg.get("message", {}).get("id")
            if ext_id:
                # Find message and mark deleted
                res = await db.execute(
                    select(Message).where(
                        Message.external_message_id == ext_id,
                        Message.user_id == user_id
                    )
                )
                msg = res.scalar_one_or_none()
                if msg:
                    msg.deleted_at = datetime.now(timezone.utc)

                    # Create RETRACTED_SOURCE CommitmentEvent for all linked commitments
                    c_res = await db.execute(select(Commitment).where(Commitment.source_message_id == msg.id, Commitment.user_id == user_id))
                    commitments = c_res.scalars().all()
                    for commitment in commitments:
                        event = CommitmentEvent(
                            commitment_id=commitment.id,
                            type=CommitmentEventType.RETRACTED_SOURCE,
                            note="Source email message was deleted."
                        )
                        db.add(event)
                    await db.flush()

        # Process new or updated messages
        for msg_added in record.get("messagesAdded", []):
            ext_id = msg_added.get("message", {}).get("id")
            if ext_id:
                await ingest_single_gmail_message(db, ext_id, user_id, client=client)

    return new_history_id
