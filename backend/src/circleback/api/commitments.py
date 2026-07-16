"""Commitments API endpoints.

Handles listing high-confidence commitments, manual correction requests,
the low-confidence review queue, and evaluation metrics.
"""

from __future__ import annotations

from typing import Any
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circleback.db import get_db
from circleback.db.models import Commitment, CommitmentDirection, CommitmentStatus
from circleback.pipeline.digest import apply_commitment_correction
from circleback.eval.harness import run_evaluation
from circleback.api.session import get_current_user
from circleback.pipeline.graph import compile_pipeline_graph
from langgraph.types import Command

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
    """List all high-confidence commitments (extraction_confidence >= 0.5)."""
    # Precision over recall: borderline elements go to review queue
    query = select(Commitment).where(Commitment.extraction_confidence >= 0.5)

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
    """List all low-confidence commitments (extraction_confidence < 0.5)."""
    query = select(Commitment).where(Commitment.extraction_confidence < 0.5)
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
    result = await db.execute(select(Commitment).where(Commitment.id == commitment_id))
    commitment = result.scalar_one_or_none()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    # 2. Apply the correction to the database directly
    try:
        await apply_commitment_correction(
            db,
            commitment_id=commitment_id,
            action=body.action,
            params=body.params
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 3. Resume the LangGraph execution
    if commitment.source_message_id:
        graph = compile_pipeline_graph()
        correction_data = {
            "commitment_id": commitment_id,
            "action": body.action,
            "params": body.params,
        }
        try:
            await graph.ainvoke(
                Command(resume=correction_data),
                {"configurable": {"thread_id": commitment.source_message_id, "db": db}}
            )
        except Exception as e:
            logger.warning("Could not resume LangGraph thread for %s: %s", commitment.source_message_id, e)

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
        .where(Commitment.id == commitment_id)
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


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve scores computed by the evaluation harness."""
    try:
        # Run evaluation on the first 50 fixtures
        metrics = await run_evaluation(db, limit=50)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
