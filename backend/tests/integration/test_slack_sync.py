"""Integration tests for Slack ingestion.

TDD: These tests define how we process Slack events (channel history, messages,
message edits, deletes) and verify webhook signatures.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from circleback.db.models import ChannelType, Message
from circleback.ingestion.slack import handle_slack_event, sync_slack_channel
from tests.conftest import make_message, MOCK_USER_ID


class TestSlackIngestion:
    """Slack ingestion integration tests."""

    @pytest.mark.asyncio
    @patch("circleback.ingestion.slack.build_slack_client")
    async def test_slack_backfill_paginates_correctly(
        self, mock_build_client, db_session
    ) -> None:
        """Slack channel history backfill uses cursor pagination to fetch all messages."""
        mock_client = MagicMock()
        mock_build_client.return_value = mock_client

        # Mock conversation history API returning paginated responses
        mock_client.conversations_history.side_effect = [
            {
                "ok": True,
                "messages": [
                    {"ts": "1710000000.000100", "user": "U1", "text": "Msg 1"},
                ],
                "response_metadata": {"next_cursor": "cursor_abc"}
            },
            {
                "ok": True,
                "messages": [
                    {"ts": "1710000001.000100", "user": "U2", "text": "Msg 2"},
                ],
                "response_metadata": {"next_cursor": ""}
            }
        ]

        await sync_slack_channel(db_session, "C99999", "xoxb-test", MOCK_USER_ID)

        # Verify it was called twice, once with no cursor and once with cursor_abc
        assert mock_client.conversations_history.call_count == 2
        mock_client.conversations_history.assert_any_call(
            channel="C99999",
            limit=100
        )
        mock_client.conversations_history.assert_any_call(
            channel="C99999",
            limit=100,
            cursor="cursor_abc"
        )

    @pytest.mark.asyncio
    async def test_slack_edit_event_updates_edited_at(self, db_session) -> None:
        """Slack message change event updates the existing message and sets edited_at."""
        msg = make_message(
            raw_text="Hello",
            channel=ChannelType.SLACK,
        )
        msg.external_message_id = "1710000000.000100"
        db_session.add(msg)
        await db_session.commit()

        # Slack edit payload structure
        event = {
            "type": "message",
            "subtype": "message_changed",
            "channel": "C99999",
            "message": {
                "user": "U123",
                "text": "Hello Edited",
                "ts": "1710000000.000100",
                "edited": {"user": "U123", "ts": "1710000005.000000"}
            },
            "ts": "1710000005.000000"
        }

        await handle_slack_event(db_session, event, MOCK_USER_ID)

        await db_session.refresh(msg)
        assert msg.raw_text == "Hello Edited"
        assert msg.edited_at is not None

    @pytest.mark.asyncio
    async def test_slack_delete_event_sets_deleted_at(self, db_session) -> None:
        """Slack message deletion event sets deleted_at on the existing message row."""
        msg = make_message(
            raw_text="Soon to be deleted Slack msg",
            channel=ChannelType.SLACK,
        )
        msg.external_message_id = "1710000000.000100"
        db_session.add(msg)
        await db_session.commit()

        # Slack delete event structure
        event = {
            "type": "message",
            "subtype": "message_deleted",
            "channel": "C99999",
            "deleted_ts": "1710000000.000100",
            "ts": "1710000010.000000"
        }

        await handle_slack_event(db_session, event, MOCK_USER_ID)

        await db_session.refresh(msg)
        assert msg.deleted_at is not None
