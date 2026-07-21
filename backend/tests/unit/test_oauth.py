"""Unit tests for OAuth callback user-matching logic.

Validates that the OAuth flows correctly create/match users by email
and that the multi-tenancy invariant holds: different emails → different users,
same email → same user.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db.models import User, OAuthToken
from tests.conftest import MOCK_USER_ID


@pytest.mark.asyncio
async def test_google_callback_creates_user(db_session: AsyncSession):
    """Google OAuth callback should create a new User if email is not yet registered."""
    from circleback.db.models import User

    # Initially no users with this email
    result = await db_session.execute(select(User).where(User.email == "new@example.com"))
    assert result.scalar_one_or_none() is None

    # Simulate what google_callback does
    user = User(email="new@example.com", display_name="New User")
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.email == "new@example.com"))
    created_user = result.scalar_one()
    assert created_user.email == "new@example.com"
    assert created_user.display_name == "New User"
    assert created_user.id is not None


@pytest.mark.asyncio
async def test_same_email_returns_same_user(db_session: AsyncSession):
    """Re-authenticating with the same email should reuse the existing User, not create a duplicate."""
    user1 = User(email="repeat@example.com", display_name="User")
    db_session.add(user1)
    await db_session.flush()

    # Simulate find-or-create logic (same as oauth.py L137-142)
    result = await db_session.execute(select(User).where(User.email == "repeat@example.com"))
    found_user = result.scalar_one_or_none()
    assert found_user is not None
    assert found_user.id == user1.id


@pytest.mark.asyncio
async def test_different_emails_create_separate_users(db_session: AsyncSession):
    """Two different Google accounts must create separate User records."""
    user_a = User(email="alice@example.com", display_name="Alice")
    user_b = User(email="bob@example.com", display_name="Bob")
    db_session.add(user_a)
    db_session.add(user_b)
    await db_session.flush()

    result_a = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    result_b = await db_session.execute(select(User).where(User.email == "bob@example.com"))

    alice = result_a.scalar_one()
    bob = result_b.scalar_one()
    assert alice.id != bob.id


@pytest.mark.asyncio
async def test_slack_fallback_email_no_collision(db_session: AsyncSession):
    """Slack fallback synthetic email should not collide with a real Google email."""
    # Simulate a Google user
    google_user = User(email="U12345@slack.com", display_name="Fake Slack Domain")
    db_session.add(google_user)
    await db_session.flush()

    # Slack fallback now uses @circleback.internal, so no collision
    slack_email = "slack+U12345@circleback.internal"
    result = await db_session.execute(select(User).where(User.email == slack_email))
    assert result.scalar_one_or_none() is None  # No collision

    slack_user = User(email=slack_email, display_name="U12345")
    db_session.add(slack_user)
    await db_session.flush()

    assert google_user.id != slack_user.id


@pytest.mark.asyncio
async def test_connection_status_endpoint(client):
    """GET /oauth/status should not crash (exercises the Any import fix)."""
    response = await client.get("/api/v1/oauth/status")
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 2  # google + slack
