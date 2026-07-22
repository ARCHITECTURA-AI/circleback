"""SQLAlchemy ORM models for Circle Back.

Implements the full data model from the technical specification:
User, Person, Message, Thread, Commitment, CommitmentEvent, EvalLabel.

Design decisions:
- JSONB arrays for email_addresses/slack_user_ids (flexible, queryable in Postgres)
- Enums as Python enums mapped to Postgres ENUMs (type safety at both layers)
- Soft deletes via deleted_at on Message (never lose data)
- CommitmentEvent is append-only (immutable audit trail)
- All timestamps are timezone-aware UTC
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from datetime import datetime

# ── Helpers ───────────────────────────────────────────────────

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


# ── Base ──────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Shared base class for all ORM models."""

    pass


# ── Enums ─────────────────────────────────────────────────────


class ChannelType(str, enum.Enum):
    """Communication channel source."""

    EMAIL = "email"
    SLACK = "slack"


class CommitmentDirection(str, enum.Enum):
    """Whether the user made the commitment or is owed it."""

    MADE_BY_USER = "made_by_user"
    OWED_TO_USER = "owed_to_user"


class CommitmentType(str, enum.Enum):
    """Classification of commitment type."""

    SIMPLE = "simple"
    DELEGATED = "delegated"
    CONDITIONAL = "conditional"
    RECURRING = "recurring"


class CommitmentStatus(str, enum.Enum):
    """Current lifecycle status of a commitment."""

    OPEN = "open"
    AT_RISK = "at_risk"
    OVERDUE = "overdue"
    FULFILLED = "fulfilled"
    RENEGOTIATED = "renegotiated"
    DISMISSED = "dismissed"
    NEEDS_CLARIFICATION = "needs_clarification"


class CommitmentEventType(str, enum.Enum):
    """Type of event in a commitment's audit trail."""

    EXTRACTED = "extracted"
    RENEGOTIATED = "renegotiated"
    FULFILLMENT_SIGNAL = "fulfillment_signal"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    EDITED_SOURCE = "edited_source"
    RETRACTED_SOURCE = "retracted_source"


# ── Models ────────────────────────────────────────────────────


class User(Base):
    """User account model for multi-tenancy."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Person(Base):
    """A person who sends or receives commitments.

    Cross-channel identity is resolved manually in v1: the user
    maintains a mapping of email addresses and Slack user IDs
    to Person records.
    """

    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_addresses: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=list,
        server_default="[]",
        doc="List of email addresses associated with this person",
    )
    slack_user_ids: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=list,
        server_default="[]",
        doc="List of Slack user IDs associated with this person",
    )
    is_self: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="True if this Person is the account owner",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
    sent_messages: Mapped[list[Message]] = relationship(
        back_populates="sender",
        foreign_keys="Message.sender_person_id",
    )
    commitments_made: Mapped[list[Commitment]] = relationship(
        back_populates="committer",
        foreign_keys="Commitment.committer_person_id",
    )


class Thread(Base):
    """A conversation thread grouping related messages.

    Email threads use Gmail thread IDs; Slack threads use thread_ts.
    """

    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type", create_constraint=True),
        nullable=False,
    )
    external_thread_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Gmail thread ID or Slack thread_ts",
    )
    participant_person_ids: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=list,
        server_default="[]",
    )
    subject_or_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
    messages: Mapped[list[Message]] = relationship(back_populates="thread")
    commitments: Mapped[list[Commitment]] = relationship(back_populates="thread")


class Message(Base):
    """A normalized message from Gmail or Slack.

    Both channels are normalized into this single shape. Edits and
    deletes are tracked via edited_at/deleted_at — rows are never
    hard-deleted to preserve the evidence trail.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("user_id", "external_message_id", name="uq_user_external_message"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type", create_constraint=True),
        nullable=False,
    )
    external_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=False,
        index=True,
        doc="Original Gmail message ID or Slack message ts",
    )
    thread_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("threads.id"),
        nullable=True,
    )
    sender_person_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("persons.id"),
        nullable=True,
    )
    sender_handle: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Raw email address or Slack user ID of the sender",
    )
    recipient_person_ids: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=list,
        server_default="[]",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    permalink: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
    thread: Mapped[Thread | None] = relationship(back_populates="messages")
    sender: Mapped[Person | None] = relationship(
        back_populates="sent_messages",
        foreign_keys=[sender_person_id],
    )
    commitments: Mapped[list[Commitment]] = relationship(
        back_populates="source_message",
        foreign_keys="Commitment.source_message_id",
    )


class Commitment(Base):
    """A tracked commitment extracted from a message.

    This is the core domain object. It tracks who promised what to whom,
    when it's due, how confident the extraction is, and the current
    lifecycle status.
    """

    __tablename__ = "commitments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("messages.id"),
        nullable=True,
    )
    thread_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("threads.id"),
        nullable=True,
    )
    committer_person_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("persons.id"),
        nullable=True,
    )
    recipient_person_ids: Mapped[list] = mapped_column(
        JSON_TYPE,
        default=list,
        server_default="[]",
    )
    direction: Mapped[CommitmentDirection] = mapped_column(
        Enum(CommitmentDirection, name="commitment_direction", create_constraint=True),
        nullable=False,
    )
    raw_text_span: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The exact text span from the message that contains the commitment",
    )
    commitment_type: Mapped[CommitmentType] = mapped_column(
        Enum(CommitmentType, name="commitment_type", create_constraint=True),
        nullable=False,
        default=CommitmentType.SIMPLE,
    )
    raw_temporal_phrase: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="The original temporal language, e.g. 'by Friday'",
    )
    resolved_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deadline_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        doc="0-1 confidence in the resolved deadline",
    )
    extraction_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        doc="0-1 confidence that this is actually a commitment",
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus, name="commitment_status", create_constraint=True),
        nullable=False,
        default=CommitmentStatus.OPEN,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
    source_message: Mapped[Message | None] = relationship(
        back_populates="commitments",
        foreign_keys=[source_message_id],
    )
    thread: Mapped[Thread | None] = relationship(back_populates="commitments")
    committer: Mapped[Person | None] = relationship(
        back_populates="commitments_made",
        foreign_keys=[committer_person_id],
    )
    events: Mapped[list[CommitmentEvent]] = relationship(
        back_populates="commitment",
        order_by="CommitmentEvent.timestamp",
    )


class CommitmentEvent(Base):
    """An immutable audit-trail entry for a commitment.

    Every state change, correction, fulfillment signal, or source
    modification is recorded here. This is the integrity backbone
    of the product — it proves what happened and why.
    """

    __tablename__ = "commitment_events"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    commitment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("commitments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[CommitmentEventType] = mapped_column(
        Enum(CommitmentEventType, name="commitment_event_type", create_constraint=True),
        nullable=False,
    )
    evidence_message_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("messages.id"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    commitment: Mapped[Commitment] = relationship(back_populates="events")
    evidence_message: Mapped[Message | None] = relationship()


class EvalLabel(Base):
    """Human-labeled ground truth for the evaluation harness.

    Internal QA tool, not user-facing. Powers the precision/recall
    metrics that validate extraction quality.
    """

    __tablename__ = "eval_labels"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("messages.id"),
        nullable=False,
        index=True,
    )
    is_commitment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correct_committer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correct_deadline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
    message: Mapped[Message] = relationship()


class OAuthToken(Base):
    """Encrypted OAuth refresh tokens for connected accounts.

    Tokens are Fernet-encrypted at rest (spec §10). The plaintext
    is never logged or exposed in API responses.
    """

    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="OAuth provider: 'google' or 'slack'",
    )
    encrypted_access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Fernet-encrypted access token",
    )
    encrypted_refresh_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Fernet-encrypted refresh token (Google only)",
    )
    token_type: Mapped[str] = mapped_column(
        String(50),
        default="Bearer",
    )
    scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="OAuth scopes granted",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()


class UnrecognizedSender(Base):
    """Persisted record of unrecognized sender handles for manual review.

    Spec §6.5: "Logs (does not silently drop) messages from unrecognized
    senders/handles that resemble a known person, for later manual mapping."
    """

    __tablename__ = "unrecognized_senders"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    handle: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="The raw email or Slack user ID that couldn't be mapped",
    )
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type", create_constraint=True),
        nullable=False,
    )
    sample_message_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("messages.id"),
        nullable=True,
        doc="A sample message from this sender for context",
    )
    mapped_to_person_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("persons.id"),
        nullable=True,
        doc="Once resolved, the Person this was mapped to",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship()
