"""Shared test fixtures for Circle Back backend tests.

Provides:
- In-memory SQLite async engine for fast, isolated DB tests
- Test DB session factory
- FastAPI test client with dependency overrides
- Common test data factories
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from circleback.db.models import (
    Base,
    ChannelType,
    Commitment,
    CommitmentDirection,
    CommitmentEvent,
    CommitmentEventType,
    CommitmentStatus,
    CommitmentType,
    Message,
    Person,
    Thread,
    User,
)
from circleback.main import create_app
from circleback.db import get_db
from circleback.api.session import get_current_user


# ── Async engine for tests (SQLite in-memory) ────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
MOCK_USER_ID = "00000000-0000-0000-0000-00000000000a"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create a fresh async engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh DB session for each test, seeded with a default User."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Seed the default user
        user = make_user()
        session.add(user)
        await session.commit()
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client with test DB and authenticated session injected."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user() -> dict[str, Any]:
        return {
            "provider": "google",
            "email": "test@company.com",
            "user_id": MOCK_USER_ID,
        }

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Test Data Factories ──────────────────────────────────────


def make_user(
    email: str = "test@company.com",
    display_name: str = "Test User",
    id: str = MOCK_USER_ID,
) -> User:
    """Create a User instance for testing."""
    return User(
        id=id,
        email=email,
        display_name=display_name,
    )


def make_person(
    display_name: str = "Test User",
    email_addresses: list[str] | None = None,
    slack_user_ids: list[str] | None = None,
    is_self: bool = False,
    user_id: str = MOCK_USER_ID,
) -> Person:
    """Create a Person instance for testing."""
    return Person(
        user_id=user_id,
        display_name=display_name,
        email_addresses=email_addresses or [],
        slack_user_ids=slack_user_ids or [],
        is_self=is_self,
    )


def make_message(
    raw_text: str = "Test message",
    channel: ChannelType = ChannelType.EMAIL,
    timestamp: datetime | None = None,
    sender_person_id: str | None = None,
    thread_id: str | None = None,
    user_id: str = MOCK_USER_ID,
) -> Message:
    """Create a Message instance for testing."""
    return Message(
        user_id=user_id,
        channel=channel,
        raw_text=raw_text,
        timestamp=timestamp or datetime.now(timezone.utc),
        sender_person_id=sender_person_id,
        thread_id=thread_id,
    )


def make_commitment(
    raw_text_span: str = "I'll send you the deck by Friday",
    direction: CommitmentDirection = CommitmentDirection.MADE_BY_USER,
    commitment_type: CommitmentType = CommitmentType.SIMPLE,
    status: CommitmentStatus = CommitmentStatus.OPEN,
    extraction_confidence: float = 0.9,
    deadline_confidence: float = 0.8,
    source_message_id: str | None = None,
    committer_person_id: str | None = None,
    thread_id: str | None = None,
    user_id: str = MOCK_USER_ID,
) -> Commitment:
    """Create a Commitment instance for testing."""
    return Commitment(
        user_id=user_id,
        raw_text_span=raw_text_span,
        direction=direction,
        commitment_type=commitment_type,
        status=status,
        extraction_confidence=extraction_confidence,
        deadline_confidence=deadline_confidence,
        source_message_id=source_message_id,
        committer_person_id=committer_person_id,
        thread_id=thread_id,
    )


def make_commitment_event(
    commitment_id: str,
    event_type: CommitmentEventType = CommitmentEventType.EXTRACTED,
    evidence_message_id: str | None = None,
    note: str | None = None,
) -> CommitmentEvent:
    """Create a CommitmentEvent instance for testing."""
    return CommitmentEvent(
        commitment_id=commitment_id,
        type=event_type,
        evidence_message_id=evidence_message_id,
        note=note,
    )
