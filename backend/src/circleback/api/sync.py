"""Sync API endpoints.

Handles triggering background syncs for connected OAuth accounts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select

from circleback.api.session import get_current_user
from circleback.db import get_db
from circleback.db.models import OAuthToken

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger background sync for all connected accounts.

    Used primarily right after onboarding to populate the initial database state.
    """
    result = await db.execute(select(OAuthToken).where(OAuthToken.user_id == user["user_id"]))
    tokens = result.scalars().all()

    if not tokens:
        raise HTTPException(
            status_code=400,
            detail="No connected accounts found. Please connect an account first."
        )

    # Note: In a real implementation, we would decode the tokens and pass them
    # to the respective sync tasks (e.g. sync_gmail, sync_slack).
    # For now, this is a stub that represents triggering the background task.
    logger.info("Triggered background sync for providers: %s", [t.provider for t in tokens])

    # We would do: background_tasks.add_task(sync_all_accounts, tokens)

    return {
        "status": "sync_started",
        "channels": [t.provider for t in tokens]
    }
