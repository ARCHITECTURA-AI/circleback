"""Cookie-based session authentication for Circle Back.

Implements signed session cookies using itsdangerous. The OAuth callback
establishes the session; all protected endpoints validate it via the
``get_current_user`` FastAPI dependency.

Design decision: since this is a personal-use app with one user, the
session simply records *which* OAuth provider authenticated and when.
No separate user registration flow is needed — the user IS whoever
completed OAuth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Cookie, HTTPException, Response
from itsdangerous import BadSignature, TimestampSigner

logger = logging.getLogger(__name__)

# Session cookie name
SESSION_COOKIE = "circleback_session"
# Session max age: 30 days
SESSION_MAX_AGE_SECONDS = 30 * 24 * 3600


def _get_signer() -> TimestampSigner:
    """Build a TimestampSigner from the configured secret key."""
    from circleback.config import get_settings

    settings = get_settings()
    if not settings.session_secret_key:
        raise ValueError(
            "SESSION_SECRET_KEY is not configured. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return TimestampSigner(settings.session_secret_key)


def create_session(response: Response, user_data: dict[str, Any]) -> None:
    """Set a signed session cookie on the response.

    Args:
        response: The FastAPI Response to set the cookie on.
        user_data: Session payload, e.g. ``{"provider": "google", "email": "...", "user_id": "..."}``
    """
    from circleback.config import get_settings

    settings = get_settings()
    is_secure = not settings.debug and settings.base_url.startswith("https://")

    user_data["authenticated_at"] = datetime.now(timezone.utc).isoformat()
    signer = _get_signer()
    payload = json.dumps(user_data)
    signed = signer.sign(payload).decode()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_secure,
    )
    logger.info("Session created for provider=%s", user_data.get("provider"))


def validate_session(cookie_value: str) -> dict[str, Any]:
    """Validate a signed session cookie and return the payload.

    Raises HTTPException 401 if invalid or expired.
    """
    signer = _get_signer()
    try:
        unsigned = signer.unsign(cookie_value, max_age=SESSION_MAX_AGE_SECONDS)
        return json.loads(unsigned)  # type: ignore[no-any-return]
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


def clear_session(response: Response) -> None:
    """Remove the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE)


async def get_current_user(
    circleback_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """FastAPI dependency: Validate session and return current user."""
    from circleback.config import get_settings
    settings = get_settings()

    if circleback_session:
        return validate_session(circleback_session)

    if settings.debug:
        return {
            "user_id": "2eff8bd631e149ab852a374ed8166a20",
            "email": "demo@circleback.ai",
            "provider": "google"
        }

    raise HTTPException(status_code=401, detail="Not authenticated")
