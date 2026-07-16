"""Normalization logic for email and Slack messages into the Message ORM model.

Extracts sender, recipients, timestamp, raw body content, thread grouping IDs,
and link information, formatting them consistently.
"""

from __future__ import annotations

import base64
import email.utils
import re
from datetime import datetime, timezone
from typing import Any

from circleback.db.models import ChannelType, Message


def parse_email_address(raw_header: str) -> list[str]:
    """Parse email headers like 'Alice <alice@co.com>, Bob <bob@co.com>' into pure emails."""
    if not raw_header:
        return []
    emails = []
    # Split by comma but be careful of commas inside quotes
    parts = email.utils.getaddresses([raw_header])
    for _, addr in parts:
        if addr:
            emails.append(addr.strip().lower())
    return emails


def get_gmail_header(headers: list[dict[str, str]], name: str) -> str:
    """Retrieve header value by name (case-insensitive)."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def decode_gmail_body(payload: dict[str, Any]) -> str:
    """Recursively decode Gmail message body parts (plain text preferred)."""
    body = payload.get("body", {})
    data = body.get("data", "")
    if data:
        try:
            # Gmail uses urlsafe base64
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8")
        except Exception:
            pass

    # If multipart, check parts
    parts = payload.get("parts", [])
    text_content = []
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            part_body = part.get("body", {})
            part_data = part_body.get("data", "")
            if part_data:
                try:
                    text_content.append(
                        base64.urlsafe_b64decode(part_data.encode("utf-8")).decode("utf-8")
                    )
                except Exception:
                    pass
        elif part.get("parts"):
            text_content.append(decode_gmail_body(part))

    return "\n".join(text_content) if text_content else payload.get("snippet", "")


def normalize_gmail_message(raw_gmail: dict[str, Any]) -> Message:
    """Normalize a raw Gmail API message resource into a Message ORM model."""
    msg_id = raw_gmail["id"]
    thread_id = raw_gmail.get("threadId")
    internal_date = int(raw_gmail.get("internalDate", 0)) / 1000.0
    timestamp = datetime.fromtimestamp(internal_date, tz=timezone.utc)

    payload = raw_gmail.get("payload", {})
    headers = payload.get("headers", [])

    from_header = get_gmail_header(headers, "From")
    sender_emails = parse_email_address(from_header)
    # The first email is the sender's email
    sender_email = sender_emails[0] if sender_emails else ""

    to_header = get_gmail_header(headers, "To")
    cc_header = get_gmail_header(headers, "Cc")
    recipients = parse_email_address(to_header) + parse_email_address(cc_header)

    body_text = decode_gmail_body(payload)
    if not body_text:
        body_text = raw_gmail.get("snippet", "")

    # For Gmail, subject is useful metadata
    subject = get_gmail_header(headers, "Subject")

    # In normalizer, we populate recipient_person_ids with the raw email strings.
    # The Entity Linker phase will resolve these to Person foreign keys later.
    return Message(
        channel=ChannelType.EMAIL,
        external_message_id=msg_id,
        timestamp=timestamp,
        raw_text=body_text,
        sender_handle=sender_email,
        recipient_person_ids=recipients,
        permalink=f"https://mail.google.com/mail/u/0/#inbox/{thread_id}" if thread_id else None,
    )


def normalize_slack_message(
    raw_slack: dict[str, Any],
    team_members: list[str] | None = None,
    permalink: str | None = None,
) -> Message:
    """Normalize a raw Slack message event into a Message ORM model."""
    # Slack timestamps are like "1710000000.000100"
    ts = raw_slack.get("ts", "")
    timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)

    text = raw_slack.get("text", "")
    sender_slack_id = raw_slack.get("user", "")

    # For Slack, the thread_ts groups replies. If no thread_ts, it's just ts.
    thread_ts = raw_slack.get("thread_ts", ts)

    # In Slack, recipients are the other participants in the channel or conversation.
    recipients = list(team_members) if team_members else []
    if sender_slack_id in recipients:
        recipients.remove(sender_slack_id)

    # We store the raw Slack user IDs in recipient_person_ids first.
    # Entity Linker will map them to Person records.
    return Message(
        channel=ChannelType.SLACK,
        external_message_id=ts,
        timestamp=timestamp,
        raw_text=text,
        sender_handle=sender_slack_id,
        recipient_person_ids=recipients,
        permalink=permalink,
    )
