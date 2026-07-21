"""Authentication, session management, and data deletion endpoints.

Handles:
- Session info (GET /auth/me)
- Logout (POST /auth/logout)
- Absolute data purge (DELETE /auth/data) — spec §10
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
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
    """Absolutely delete all user-related data in the database for the current user.

    This is the "disconnect and delete my data" action from spec §10.
    It purges stored tokens AND all derived data — not just a soft delete.
    Deletion order respects foreign key constraints.
    """
    from circleback.db.models import User

    user_id = user["user_id"]

    # Delete in dependency order (children first)
    await db.execute(
        delete(CommitmentEvent).where(
            CommitmentEvent.commitment_id.in_(
                select(Commitment.id).where(Commitment.user_id == user_id)
            )
        )
    )
    await db.execute(delete(EvalLabel).where(EvalLabel.user_id == user_id))
    await db.execute(delete(Commitment).where(Commitment.user_id == user_id))
    await db.execute(delete(UnrecognizedSender).where(UnrecognizedSender.user_id == user_id))
    await db.execute(delete(Message).where(Message.user_id == user_id))
    await db.execute(delete(Thread).where(Thread.user_id == user_id))
    await db.execute(delete(Person).where(Person.user_id == user_id))
    await db.execute(delete(OAuthToken).where(OAuthToken.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))

    await db.flush()

    # Also clear the session since tokens are gone
    clear_session(response)

    return {
        "status": "success",
        "message": "All data has been permanently deleted — tokens, messages, commitments, and person mappings.",
    }
