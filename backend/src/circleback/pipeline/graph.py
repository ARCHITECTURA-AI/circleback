"""LangGraph pipeline definition and compilation.

Implements the split pipeline from the technical specification:
- Ingestion graph (per-message, non-blocking)
- Digest+Correction graph (scheduled or on-demand, with human-in-the-loop interrupt)

Each node has explicit typed state in/out. The graph uses MemorySaver
checkpointing for persistence across sessions.
"""

from __future__ import annotations

from typing import TypedDict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# Global checkpointer so state is preserved across API requests for interrupt/resume
global_checkpointer = MemorySaver()

from langchain_core.runnables import RunnableConfig

from circleback.db.models import Message
from circleback.pipeline.prefilter import should_process_message
from circleback.pipeline.extractor import extract_commitments_from_message
from circleback.pipeline.temporal import resolve_deadline
from circleback.pipeline.linker import link_thread_and_entities
from circleback.pipeline.fulfillment import process_thread_fulfillment
from circleback.pipeline.status import update_commitment_statuses


# ── Pipeline State Definition ─────────────────────────────────


class PipelineState(TypedDict):
    """Internal state passed between nodes in the pipeline.

    Each field is populated or updated by the corresponding node.
    """

    user_id: str
    message_id: str
    external_thread_id: str | None
    self_email: str
    should_extract: bool
    commitments_extracted: int
    processing_complete: bool
    digest_data: dict[str, Any]
    correction_response: dict[str, Any]


# ── Node Implementations ──────────────────────────────────────


async def prefilter_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Prefilter node: cheap heuristic to determine if message might contain commitments.

    This avoids expensive LLM calls for messages that clearly contain no commitment language.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id, Message.user_id == user_id))
    msg = result.scalar_one_or_none()

    if not msg or msg.deleted_at is not None:
        return {"should_extract": False}

    passed = should_process_message(msg.raw_text)
    return {"should_extract": passed}


async def extract_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Extraction node: call Claude for structured commitment extraction.

    Produces candidate Commitment objects with extraction_confidence scores.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    msg_id = state["message_id"]
    self_email = state["self_email"]

    result = await db.execute(select(Message).where(Message.id == msg_id, Message.user_id == user_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {"commitments_extracted": 0}

    commitments = await extract_commitments_from_message(db, msg, self_email=self_email, user_id=user_id)
    return {"commitments_extracted": len(commitments)}


async def temporal_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Temporal resolution node: resolve relative dates to concrete deadlines.

    Anchors against message send timestamp with explicit timezone/business-day policy.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id, Message.user_id == user_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {}

    # Find commitments from this message that need temporal resolution
    from circleback.db.models import Commitment
    c_result = await db.execute(
        select(Commitment).where(
            Commitment.source_message_id == msg_id,
            Commitment.user_id == user_id
        )
    )
    commitments = c_result.scalars().all()

    for c in commitments:
        if c.raw_temporal_phrase and not c.resolved_deadline:
            res = resolve_deadline(c.raw_temporal_phrase, msg.timestamp)
            c.resolved_deadline = res["deadline"]
            c.deadline_confidence = res["confidence"]

            # If unresolvable, mark needs_clarification
            if res["deadline"] is None and res["confidence"] <= 0.1:
                from circleback.db.models import CommitmentStatus
                c.status = CommitmentStatus.NEEDS_CLARIFICATION

    await db.flush()
    return {}


async def link_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Thread/entity linking node: groups messages and maps identities.

    Maps sender handles to Person records using the manual seed list.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    msg_id = state["message_id"]
    ext_thread_id = state.get("external_thread_id")

    result = await db.execute(select(Message).where(Message.id == msg_id, Message.user_id == user_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {}

    await link_thread_and_entities(db, msg, external_thread_id=ext_thread_id, user_id=user_id)
    return {}


async def fulfill_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Fulfillment matching node: semantic matching against specific open commitments.

    Handles fulfillment, renegotiation, and delegation independently.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id, Message.user_id == user_id))
    msg = result.scalar_one_or_none()
    if not msg or not msg.thread_id:
        return {}

    await process_thread_fulfillment(db, msg.thread_id, msg, user_id=user_id)
    return {}


async def status_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Status engine node: evaluate and transition commitment statuses.

    Every transition is logged as a CommitmentEvent with evidence.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    
    from circleback.config import get_settings
    at_risk_hours = get_settings().at_risk_hours_before_deadline
    
    await update_commitment_statuses(db, at_risk_hours=at_risk_hours, user_id=user_id)
    return {"processing_complete": True}


async def digest_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Digest generation node: compile active commitments into grouped lists."""
    from circleback.pipeline.digest import generate_digest
    db: AsyncSession = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id") or state.get("user_id")
    digest_data = await generate_digest(db, user_id=user_id)
    return {"digest_data": digest_data}


def correction_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Human correction loop node using LangGraph interrupt.
    
    Pauses execution to allow user to provide corrections for any commitments.
    When resumed with a correction payload, applies the correction.
    """
    # Wait for human input. The frontend/API will resume this graph with correction data.
    correction_data = interrupt({"pending_corrections": state.get("digest_data", {})})
    return {"correction_response": correction_data}


# ── Router Logic ──────────────────────────────────────────────


def route_after_prefilter(state: PipelineState) -> str:
    """Decide whether to execute full extraction or skip to link+fulfill+status."""
    if state.get("should_extract"):
        return "extract"
    # Even if no extraction needed, still check fulfillment and update statuses
    return "link"


# ── Graph Compilation ─────────────────────────────────────────


def compile_ingestion_graph(checkpointer: Any | None = None) -> Any:
    """Compile and return the LangGraph ingestion pipeline state machine."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("prefilter", prefilter_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("temporal", temporal_node)
    workflow.add_node("link", link_node)
    workflow.add_node("fulfill", fulfill_node)
    workflow.add_node("status", status_node)

    # Wire the edges
    workflow.add_edge(START, "prefilter")

    workflow.add_conditional_edges(
        "prefilter",
        route_after_prefilter,
        {
            "extract": "extract",
            "link": "link",
        }
    )

    workflow.add_edge("extract", "temporal")
    workflow.add_edge("temporal", "link")
    workflow.add_edge("link", "fulfill")
    workflow.add_edge("fulfill", "status")
    workflow.add_edge("status", END)

    if checkpointer is None:
        checkpointer = global_checkpointer

    return workflow.compile(checkpointer=checkpointer)


def compile_digest_graph(checkpointer: Any | None = None) -> Any:
    """Compile and return the LangGraph digest/correction pipeline state machine."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("status", status_node)
    workflow.add_node("digest", digest_node)
    workflow.add_node("correction", correction_node)

    workflow.add_edge(START, "status")
    workflow.add_edge("status", "digest")
    workflow.add_edge("digest", "correction")
    workflow.add_edge("correction", END)

    if checkpointer is None:
        checkpointer = global_checkpointer

    return workflow.compile(checkpointer=checkpointer)


# Backward compatibility alias
compile_pipeline_graph = compile_ingestion_graph


async def run_pipeline_for_message(
    db: AsyncSession,
    message_id: str,
    user_id: str,
    external_thread_id: str | None = None,
    self_email: str = "",
) -> None:
    """Helper to invoke the compiled LangGraph ingestion pipeline for a specific message."""
    graph = compile_ingestion_graph()
    initial_state = {
        "user_id": user_id,
        "message_id": message_id,
        "external_thread_id": external_thread_id,
        "self_email": self_email,
        "should_extract": False,
        "commitments_extracted": 0,
        "processing_complete": False,
    }
    await graph.ainvoke(
        initial_state,
        {"configurable": {"thread_id": message_id, "db": db, "user_id": user_id}}
    )
