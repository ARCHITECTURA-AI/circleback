"""Authentication, session management, and data deletion endpoints.

Handles:
- Session info (GET /auth/me)
- Logout (POST /auth/logout)
- Absolute data purge (DELETE /auth/data) — spec §10
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db import get_db
from circleback.db.models import (
    Commitment,
    CommitmentEvent,
    EvalLabel,
    Message,
    OAuthToken,
    Person,
    Thread,
    UnrecognizedSender,
)
from circleback.api.session import get_current_user, clear_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_session_info(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the current session information."""
    return {"authenticated": True, **user}


@router.post("/logout")
async def logout(
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Clear the session cookie and log out."""
    clear_session(response)
    return {"status": "logged_out"}


@router.delete("/data")
async def delete_all_user_data(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Absolutely delete all user-related data in the database.

    This is the "disconnect and delete my data" action from spec §10.
    It purges stored tokens AND all derived data — not just a soft delete.
    Deletion order respects foreign key constraints.
    """
    # Delete in dependency order (children first)
    await db.execute(delete(CommitmentEvent))
    await db.execute(delete(EvalLabel))
    await db.execute(delete(Commitment))
    await db.execute(delete(UnrecognizedSender))
    await db.execute(delete(Message))
    await db.execute(delete(Thread))
    await db.execute(delete(Person))
    await db.execute(delete(OAuthToken))

    await db.flush()

    # Also clear the session since tokens are gone
    clear_session(response)

    return {
        "status": "success",
        "message": "All data has been permanently deleted — tokens, messages, commitments, and person mappings.",
    }
