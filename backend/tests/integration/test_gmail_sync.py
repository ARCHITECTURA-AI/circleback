"""Integration tests for Gmail ingestion.

TDD: These tests define how we interact with the Gmail API, handle sync states,
manage edited/deleted emails, and encrypt/decrypt OAuth credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from circleback.db.models import ChannelType, CommitmentStatus, Message, Person
from circleback.ingestion.gmail import sync_gmail
from tests.conftest import make_commitment, make_message, make_person, MOCK_USER_ID


class TestGmailIngestion:
    """Ingestion, sync history, and encryption tests."""

    @pytest.mark.asyncio
    @patch("circleback.ingestion.gmail.build_gmail_client")
    async def test_gmail_incremental_sync_uses_history_id(
        self, mock_build_client, db_session
    ) -> None:
        """Incremental sync uses the last stored historyId from the user profile/state."""
        # Setup mocks
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Mock list/history responses
        mock_client.users().history().list.return_value.execute = MagicMock(return_value={
            "history": [],
            "historyId": "9999"
        })
        
        # Run sync first time (full backfill/start)
        # In a real sync we might store history_id in a sync state or token record.
        # Let's say we pass the last history_id or keep it in a session.
        await sync_gmail(db_session, user_id=MOCK_USER_ID, last_history_id="12345")
        
        # Verify the history list was called with startHistoryId="12345"
        mock_client.users().history().list.assert_called_with(
            userId="me",
            startHistoryId="12345"
        )

    @pytest.mark.asyncio
    @patch("circleback.ingestion.gmail.build_gmail_client")
    async def test_gmail_edited_message_updates_edited_at(
        self, mock_build_client, db_session
    ) -> None:
        """An edit to an email updates the edited_at field and updates content."""
        # Create an existing message in DB
        msg = make_message(
            raw_text="Original email content",
            channel=ChannelType.EMAIL,
            timestamp=datetime.now(timezone.utc)
        )
        msg.external_message_id = "gmail_msg_edit_123"
        db_session.add(msg)
        await db_session.commit()

        # Mock client to return updated message resource
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        mock_client.users().messages().get.return_value.execute = MagicMock(return_value={
            "id": "gmail_msg_edit_123",
            "internalDate": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "snippet": "Updated email content",
            "payload": {
                "headers": [{"name": "From", "value": "alice@co.com"}],
                "body": {"data": ""}
            }
        })

        # Run single message ingestion for the updated message ID
        # Wait, if we sync a message that already exists, it should update it and set edited_at
        from circleback.ingestion.gmail import ingest_single_gmail_message
        await ingest_single_gmail_message(db_session, "gmail_msg_edit_123", MOCK_USER_ID)

        # Refetch from DB
        await db_session.refresh(msg)
        assert msg.raw_text == "Updated email content"
        assert msg.edited_at is not None

    @pytest.mark.asyncio
    @patch("circleback.ingestion.gmail.build_gmail_client")
    async def test_gmail_deleted_message_sets_deleted_at(
        self, mock_build_client, db_session
    ) -> None:
        """A deleted email sets deleted_at rather than hard-deleting the DB row."""
        # Create message in DB
        msg = make_message(
            raw_text="Soon to be deleted email",
            channel=ChannelType.EMAIL,
        )
        msg.external_message_id = "gmail_msg_del_123"
        db_session.add(msg)
        await db_session.commit()

        # Mock client for list history showing a delete event or messages.get raising 404 (deleted)
        # Actually, in incremental sync, history listing returns messagesDeleted list.
        # Let's say sync_gmail processes a history payload containing a deleted message.
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client
        
        # Return history with a messageDeleted element
        mock_client.users().history().list.return_value.execute = MagicMock(return_value={
            "history": [
                {
                    "id": "history_999",
                    "messagesDeleted": [
                        {"message": {"id": "gmail_msg_del_123"}}
                    ]
                }
            ],
            "historyId": "10000"
        })

        await sync_gmail(db_session, user_id=MOCK_USER_ID, last_history_id="12345")

        # Refetch
        await db_session.refresh(msg)
        assert msg.deleted_at is not None
