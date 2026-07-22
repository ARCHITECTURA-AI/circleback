"""Commitments API endpoints.

Handles listing high-confidence commitments, manual correction requests,
the low-confidence review queue, and evaluation metrics.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import select

from circleback.api.session import get_current_user
from circleback.db import get_db
from circleback.db.models import Commitment, CommitmentDirection, CommitmentStatus
from circleback.eval.harness import run_evaluation
from circleback.pipeline.digest import apply_commitment_correction
from circleback.pipeline.graph import compile_digest_graph

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["commitments"])


# ── Request/Response schemas ──────────────────────────────────


class CommitmentResponse(BaseModel):
    """Serialized commitment for API responses."""

    id: str
    direction: str
    raw_text_span: str
    commitment_type: str
    status: str
    extraction_confidence: float
    deadline_confidence: float
    raw_temporal_phrase: str | None = None
    resolved_deadline: str | None = None

    model_config = {"from_attributes": True}


class CommitmentListResponse(BaseModel):
    """Paginated list of commitments."""

    items: list[CommitmentResponse]
    total: int


class CorrectionRequest(BaseModel):
    """Request schema for manual user correction."""

    action: str
    params: dict[str, Any] | None = None


class EventResponse(BaseModel):
    """Serialized commitment event trail entry."""

    id: str
    type: str
    timestamp: str
    note: str | None = None

    model_config = {"from_attributes": True}


class CommitmentDetailResponse(BaseModel):
    """Detailed commitment response including event trail and source message context."""

    id: str
    direction: str
    raw_text_span: str
    commitment_type: str
    status: str
    extraction_confidence: float
    deadline_confidence: float
    raw_temporal_phrase: str | None = None
    resolved_deadline: str | None = None
    source_message_text: str | None = None
    source_message_sender: str | None = None
    events: list[EventResponse] = []

    model_config = {"from_attributes": True}



# ── Endpoints ─────────────────────────────────────────────────


@router.get("/commitments", response_model=CommitmentListResponse)
async def list_commitments(
    status: CommitmentStatus | None = Query(None, description="Filter by status"),
    direction: CommitmentDirection | None = Query(None, description="Filter by direction"),
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> CommitmentListResponse:
    """List all high-confidence commitments for the current user (extraction_confidence >= 0.5)."""
    # Precision over recall: borderline elements go to review queue
    query = select(Commitment).where(
        Commitment.extraction_confidence >= 0.5,
        Commitment.user_id == user["user_id"]
    )

    if status is not None:
        query = query.where(Commitment.status == status)
    if direction is not None:
        query = query.where(Commitment.direction == direction)

    result = await db.execute(query)
    commitments = result.scalars().all()

    items = [
        CommitmentResponse(
            id=c.id,
            direction=c.direction.value,
            raw_text_span=c.raw_text_span,
            commitment_type=c.commitment_type.value,
            status=c.status.value,
            extraction_confidence=c.extraction_confidence,
            deadline_confidence=c.deadline_confidence,
            raw_temporal_phrase=c.raw_temporal_phrase,
            resolved_deadline=(
                c.resolved_deadline.isoformat() if c.resolved_deadline else None
            ),
        )
        for c in commitments
    ]

    return CommitmentListResponse(items=items, total=len(items))


@router.get("/review-queue", response_model=CommitmentListResponse)
async def list_review_queue(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> CommitmentListResponse:
    """List all low-confidence commitments for the current user (extraction_confidence < 0.5)."""
    query = select(Commitment).where(
        Commitment.extraction_confidence < 0.5,
        Commitment.user_id == user["user_id"]
    )
    result = await db.execute(query)
    commitments = result.scalars().all()

    items = [
        CommitmentResponse(
            id=c.id,
            direction=c.direction.value,
            raw_text_span=c.raw_text_span,
            commitment_type=c.commitment_type.value,
            status=c.status.value,
            extraction_confidence=c.extraction_confidence,
            deadline_confidence=c.deadline_confidence,
            raw_temporal_phrase=c.raw_temporal_phrase,
            resolved_deadline=(
                c.resolved_deadline.isoformat() if c.resolved_deadline else None
            ),
        )
        for c in commitments
    ]

    return CommitmentListResponse(items=items, total=len(items))


@router.post("/commitments/{commitment_id}/correct")
async def correct_commitment(
    commitment_id: str,
    body: CorrectionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Apply manual user correction (e.g. done, dismiss, postpone) to a commitment.

    This also resumes the LangGraph correction node if it was interrupted (spec §6.9).
    """
    # 1. Lookup commitment to get the source message ID (which is the LangGraph thread_id)
    result = await db.execute(
        select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.user_id == user["user_id"]
        )
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    # 2. Apply the correction to the database directly
    try:
        await apply_commitment_correction(
            db,
            commitment_id=commitment_id,
            action=body.action,
            params=body.params,
            user_id=user["user_id"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 3. Resume the LangGraph execution for the digest graph
    graph = compile_digest_graph()
    correction_data = {
        "commitment_id": commitment_id,
        "action": body.action,
        "params": body.params,
    }
    digest_thread_id = f"digest_{user['user_id']}"
    try:
        await graph.ainvoke(
            Command(resume=correction_data),
            {"configurable": {"thread_id": digest_thread_id, "db": db, "user_id": user["user_id"]}}
        )
    except Exception as e:
        logger.warning("Could not resume LangGraph digest thread for %s: %s", digest_thread_id, e)

    return {"status": "success"}


@router.get("/commitments/{commitment_id}", response_model=CommitmentDetailResponse)
async def get_commitment_detail(
    commitment_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> CommitmentDetailResponse:
    """Retrieve detailed information about a single commitment, including its history."""
    from sqlalchemy.orm import selectinload

    query = (
        select(Commitment)
        .where(
            Commitment.id == commitment_id,
            Commitment.user_id == user["user_id"]
        )
        .options(
            selectinload(Commitment.events),
            selectinload(Commitment.source_message)
        )
    )
    result = await db.execute(query)
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")

    events_list = [
        EventResponse(
            id=ev.id,
            type=ev.type.value,
            timestamp=ev.timestamp.isoformat(),
            note=ev.note
        )
        for ev in c.events
    ]

    return CommitmentDetailResponse(
        id=c.id,
        direction=c.direction.value,
        raw_text_span=c.raw_text_span,
        commitment_type=c.commitment_type.value,
        status=c.status.value,
        extraction_confidence=c.extraction_confidence,
        deadline_confidence=c.deadline_confidence,
        raw_temporal_phrase=c.raw_temporal_phrase,
        resolved_deadline=c.resolved_deadline.isoformat() if c.resolved_deadline else None,
        source_message_text=c.source_message.raw_text if c.source_message else None,
        source_message_sender=c.source_message.sender_handle if c.source_message else None,
        events=events_list
    )


import time  # noqa: E402

# Module-level metrics cache keyed by user_id (Phase 4)
_metrics_cache: dict[str, dict[str, Any]] = {}
_metrics_cache_timestamps: dict[str, float] = {}
_METRICS_CACHE_TTL = 3600  # 1 hour cache TTL


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve scores computed by the evaluation harness from cache."""
    uid = user["user_id"]
    now = time.time()

    # Return cache if valid for this user
    if uid in _metrics_cache and (now - _metrics_cache_timestamps.get(uid, 0)) < _METRICS_CACHE_TTL:
        return _metrics_cache[uid]

    return {
        "status": "no_cached_results",
        "message": "No cached metrics available or cache expired. Run POST /api/v1/metrics/refresh to generate."
    }


def _run_evaluation_sync(user_id: str) -> None:
    """Run evaluation in background and cache results."""
    import asyncio

    from circleback.db import async_session_factory

    async def _inner() -> None:
        async with async_session_factory() as db:
            try:
                metrics = await run_evaluation(db, limit=50, user_id=user_id)
                _metrics_cache[user_id] = metrics
                _metrics_cache_timestamps[user_id] = time.time()
                await db.commit()
            except Exception:
                await db.rollback()

    asyncio.run(_inner())


@router.post("/metrics/refresh")
async def refresh_metrics(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Queue evaluation harness to run in background and cache the results."""
    uid = user["user_id"]
    background_tasks.add_task(_run_evaluation_sync, uid)
    return {"status": "running", "message": "Metrics refresh queued. Poll GET /api/v1/metrics for results."}


@router.post("/digest/generate")
async def generate_user_digest(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger digest generation for the current user (runs the digest graph)."""
    graph = compile_digest_graph()
    digest_thread_id = f"digest_{user['user_id']}"
    try:
        initial_state = {
            "user_id": user["user_id"],
            "message_id": "",
            "external_thread_id": None,
            "self_email": "",
            "should_extract": False,
            "commitments_extracted": 0,
            "processing_complete": False,
        }
        result = await graph.ainvoke(
            initial_state,
            {"configurable": {"thread_id": digest_thread_id, "db": db, "user_id": user["user_id"]}}
        )
        return result.get("digest_data", {})  # type: ignore[no-any-return]
    except Exception as e:
        logger.error("Failed to generate digest: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate digest: {str(e)}")
