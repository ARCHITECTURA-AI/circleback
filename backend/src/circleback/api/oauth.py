"""OAuth 2.0 endpoints for Google (Gmail) and Slack.

Implements the auth flows required by spec §9:
- Google OAuth with read-only Gmail scope
- Slack OAuth for Events API access
- Token encryption at rest
- Connected accounts status check
- Session creation on successful OAuth (spec §4: session-based app auth)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.config import get_settings
from circleback.db import get_db
from circleback.db.models import OAuthToken
from circleback.encryption import encrypt_token, decrypt_token
from circleback.api.session import create_session, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


# ── Schemas ───────────────────────────────────────────────────


class ConnectedAccount(BaseModel):
    """Status of a connected OAuth account."""

    provider: str
    connected: bool
    scope: str | None = None
    connected_at: str | None = None


class ConnectionStatus(BaseModel):
    """Overall connection status."""

    accounts: list[ConnectedAccount]


# ── Google OAuth ──────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "email",
    "profile",
]


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    """Initiate Google OAuth flow for Gmail read-only access."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    redirect_uri = f"{settings.base_url}/api/v1/oauth/google/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google OAuth callback — exchange code for tokens, store encrypted, and create session."""
    import httpx
    from circleback.db.models import User

    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    redirect_uri = f"{settings.base_url}/api/v1/oauth/google/callback"

    # Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if response.status_code != 200:
        logger.error("Google token exchange failed: %s", response.text)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    token_data = response.json()
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    scope = token_data.get("scope", "")

    # Fetch user info using the access token
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            logger.error("Failed to fetch Google userinfo: %s", userinfo_resp.text)
            raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
        userinfo = userinfo_resp.json()
        email = userinfo.get("email", "")
        display_name = userinfo.get("name", "")

    if not settings.token_encryption_key:
        raise HTTPException(status_code=500, detail="Token encryption key not configured")

    # Find or create User
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(email=email, display_name=display_name)
        db.add(user)
        await db.flush()

    # Delete existing Google token for this user if present
    await db.execute(delete(OAuthToken).where(OAuthToken.provider == "google", OAuthToken.user_id == user.id))

    # Store encrypted tokens
    oauth_token = OAuthToken(
        user_id=user.id,
        provider="google",
        encrypted_access_token=encrypt_token(access_token, settings.token_encryption_key),
        encrypted_refresh_token=encrypt_token(refresh_token, settings.token_encryption_key) if refresh_token else None,
        scope=scope,
        expires_at=datetime.now(timezone.utc),
    )
    db.add(oauth_token)
    await db.flush()

    logger.info("Google OAuth tokens stored successfully")

    # Create session and redirect to frontend onboarding
    redirect = RedirectResponse(url=f"{settings.frontend_url}/onboarding", status_code=302)
    create_session(redirect, {"provider": "google", "email": email, "user_id": user.id})
    return redirect


# ── Slack OAuth ───────────────────────────────────────────────

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_SCOPES = [
    "channels:history",
    "channels:read",
    "groups:history",
    "groups:read",
    "im:history",
    "im:read",
    "mpim:history",
    "mpim:read",
    "users:read",
    "users:read.email",
]


@router.get("/slack/login")
async def slack_login() -> RedirectResponse:
    """Initiate Slack OAuth flow."""
    settings = get_settings()
    if not settings.slack_client_id:
        raise HTTPException(status_code=500, detail="Slack OAuth not configured")

    redirect_uri = f"{settings.base_url}/api/v1/oauth/slack/callback"
    params = {
        "client_id": settings.slack_client_id,
        "scope": ",".join(SLACK_SCOPES),
        "redirect_uri": redirect_uri,
    }
    return RedirectResponse(url=f"{SLACK_AUTH_URL}?{urlencode(params)}")


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Slack OAuth callback — exchange code for token, store encrypted, and create session."""
    import httpx
    from circleback.db.models import User

    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(status_code=500, detail="Slack OAuth not configured")

    redirect_uri = f"{settings.base_url}/api/v1/oauth/slack/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SLACK_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "redirect_uri": redirect_uri,
            },
        )

    if response.status_code != 200:
        logger.error("Slack token exchange failed: %s", response.text)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    token_data = response.json()
    if not token_data.get("ok"):
        raise HTTPException(status_code=400, detail=token_data.get("error", "Unknown Slack error"))

    access_token = token_data.get("access_token", "")
    scope = token_data.get("scope", "")

    # Retrieve Slack user ID to fetch email from Slack API
    authed_user = token_data.get("authed_user", {})
    slack_user_id = authed_user.get("id") or token_data.get("bot_user_id")

    email = ""
    display_name = ""
    if slack_user_id:
        async with httpx.AsyncClient() as client:
            info_resp = await client.get(
                "https://slack.com/api/users.info",
                params={"user": slack_user_id},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_resp.status_code == 200:
                info_data = info_resp.json()
                if info_data.get("ok"):
                    slack_user = info_data.get("user", {})
                    profile = slack_user.get("profile", {})
                    email = profile.get("email", "")
                    display_name = slack_user.get("real_name") or slack_user.get("name")

    if not email and slack_user_id:
        email = f"{slack_user_id}@slack.com"
        display_name = slack_user_id

    if not email:
        raise HTTPException(status_code=400, detail="Failed to obtain user identity from Slack")

    if not settings.token_encryption_key:
        raise HTTPException(status_code=500, detail="Token encryption key not configured")

    # Find or create User
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(email=email, display_name=display_name)
        db.add(user)
        await db.flush()

    # Delete existing Slack token for this user if present
    await db.execute(delete(OAuthToken).where(OAuthToken.provider == "slack", OAuthToken.user_id == user.id))

    oauth_token = OAuthToken(
        user_id=user.id,
        provider="slack",
        encrypted_access_token=encrypt_token(access_token, settings.token_encryption_key),
        scope=scope,
        expires_at=None,  # Slack tokens don't expire
    )
    db.add(oauth_token)
    await db.flush()

    logger.info("Slack OAuth tokens stored successfully")

    # Create session and redirect to frontend onboarding
    redirect = RedirectResponse(url=f"{settings.frontend_url}/onboarding", status_code=302)
    create_session(redirect, {"provider": "slack", "email": email, "user_id": user.id})
    return redirect


# ── Status Check ──────────────────────────────────────────────


@router.get("/status", response_model=ConnectionStatus)
async def connection_status(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> ConnectionStatus:
    """Check which OAuth accounts are connected for the current user."""
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user["user_id"]))
    tokens = result.scalars().all()

    providers_connected = {t.provider: t for t in tokens}

    accounts = []
    for provider in ("google", "slack"):
        token = providers_connected.get(provider)
        accounts.append(
            ConnectedAccount(
                provider=provider,
                connected=token is not None,
                scope=token.scope if token else None,
                connected_at=token.created_at.isoformat() if token else None,
            )
        )

    return ConnectionStatus(accounts=accounts)
