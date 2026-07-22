"""Tests for the message Normalizer.

TDD: These tests define how raw data from Gmail and Slack are normalized
into the unified Message model.
"""

from __future__ import annotations

from circleback.db.models import ChannelType
from circleback.ingestion.normalizer import normalize_gmail_message, normalize_slack_message


def test_normalizer_sets_channel_correctly() -> None:
    """Gmail source maps to channel='email', Slack source maps to channel='slack'."""
    raw_gmail = {
        "id": "gmail_123",
        "threadId": "thread_abc",
        "internalDate": "1710000000000",
        "snippet": "Hello world",
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@company.com"},
                {"name": "To", "value": "bob@company.com"},
                {"name": "Subject", "value": "Meeting tomorrow"},
            ],
            "body": {"data": "SGVsbG8gd29ybGQ="},  # base64 for "Hello world"
        },
    }
    msg = normalize_gmail_message(raw_gmail)
    assert msg.channel == ChannelType.EMAIL
    assert msg.external_message_id == "gmail_123"

    raw_slack = {
        "client_msg_id": "slack_123",
        "type": "message",
        "text": "Hello Slack",
        "user": "U12345",
        "ts": "1710000000.000100",
        "channel": "C99999",
    }
    msg_slack = normalize_slack_message(raw_slack, team_members=["U12345", "U67890"])
    assert msg_slack.channel == ChannelType.SLACK
    assert msg_slack.external_message_id == "1710000000.000100"


def test_normalizer_extracts_recipients() -> None:
    """All To/CC recipients or channel participants become recipient_person_ids."""
    raw_gmail = {
        "id": "gmail_123",
        "threadId": "thread_abc",
        "internalDate": "1710000000000",
        "snippet": "Hello",
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@company.com"},
                {"name": "To", "value": "bob@company.com, charlie@company.com"},
                {"name": "Cc", "value": "david@company.com"},
            ],
            "body": {"data": "SGVsbG8="},
        },
    }
    msg = normalize_gmail_message(raw_gmail)
    # The normalizer returns recipients as raw strings/emails, which the entity linker will map to Person IDs.
    # So the normalizer should extract raw email list.
    assert len(msg.recipient_person_ids) == 3
    assert "bob@company.com" in msg.recipient_person_ids
    assert "charlie@company.com" in msg.recipient_person_ids
    assert "david@company.com" in msg.recipient_person_ids


def test_normalizer_preserves_permalink() -> None:
    """Permalink to original message is stored for later UI linking."""
    raw_slack = {
        "client_msg_id": "slack_123",
        "type": "message",
        "text": "Hello Slack",
        "user": "U12345",
        "ts": "1710000000.000100",
        "channel": "C99999",
    }
    msg = normalize_slack_message(
        raw_slack,
        team_members=["U12345"],
        permalink="https://workspace.slack.com/archives/C99999/p1710000000000100",
    )
    assert msg.permalink == "https://workspace.slack.com/archives/C99999/p1710000000000100"
