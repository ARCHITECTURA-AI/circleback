"""LangGraph pipeline definition and compilation.

Implements the full pipeline from the technical specification as individual,
independently-testable nodes in a StateGraph:

  Ingestion → Prefilter → Extraction → Temporal Resolution
     → Thread/Entity Linking → Fulfillment Matching → Status Engine
     → Digest Generation

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
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id))
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
    msg_id = state["message_id"]
    self_email = state["self_email"]

    result = await db.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {"commitments_extracted": 0}

    commitments = await extract_commitments_from_message(db, msg, self_email=self_email)
    return {"commitments_extracted": len(commitments)}


async def temporal_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Temporal resolution node: resolve relative dates to concrete deadlines.

    Anchors against message send timestamp with explicit timezone/business-day policy.
    """
    db: AsyncSession = config["configurable"]["db"]
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {}

    # Find commitments from this message that need temporal resolution
    from circleback.db.models import Commitment
    c_result = await db.execute(
        select(Commitment).where(Commitment.source_message_id == msg_id)
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
    msg_id = state["message_id"]
    ext_thread_id = state.get("external_thread_id")

    result = await db.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return {}

    await link_thread_and_entities(db, msg, external_thread_id=ext_thread_id)
    return {}


async def fulfill_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Fulfillment matching node: semantic matching against specific open commitments.

    Handles fulfillment, renegotiation, and delegation independently.
    """
    db: AsyncSession = config["configurable"]["db"]
    msg_id = state["message_id"]

    result = await db.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one_or_none()
    if not msg or not msg.thread_id:
        return {}

    await process_thread_fulfillment(db, msg.thread_id, msg)
    return {}


async def status_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Status engine node: evaluate and transition commitment statuses.

    Every transition is logged as a CommitmentEvent with evidence.
    """
    db: AsyncSession = config["configurable"]["db"]
    await update_commitment_statuses(db)
    return {"processing_complete": True}


async def digest_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Digest generation node: compile active commitments into grouped lists."""
    from circleback.pipeline.digest import generate_digest
    db: AsyncSession = config["configurable"]["db"]
    digest_data = await generate_digest(db)
    return {"digest_data": digest_data}


def correction_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Human correction loop node using LangGraph interrupt.
    
    Pauses execution to allow user to provide corrections for any commitments.
    When resumed with a correction payload, applies the correction.
    """
    # Wait for human input. The frontend/API will resume this graph with correction data.
    correction_data = interrupt({"pending_corrections": state.get("digest_data", {})})
    
    # We will handle the database application in the API endpoint before resuming,
    # or we can do it here if we make this node async.
    # For now, simply record the response in state.
    return {"correction_response": correction_data}


# ── Router Logic ──────────────────────────────────────────────


def route_after_prefilter(state: PipelineState) -> str:
    """Decide whether to execute full extraction or skip to link+fulfill+status."""
    if state.get("should_extract"):
        return "extract"
    # Even if no extraction needed, still check fulfillment and update statuses
    return "link"


# ── Graph Compilation ─────────────────────────────────────────


def compile_pipeline_graph(checkpointer: Any | None = None) -> Any:
    """Compile and return the LangGraph state machine.

    Each pipeline stage is a separate node — independently unit-testable
    and independently loggable, as required by the spec.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                     Defaults to MemorySaver for in-process persistence.
    """
    workflow = StateGraph(PipelineState)

    # Add individual nodes (spec §6: "each stage is a LangGraph node")
    workflow.add_node("prefilter", prefilter_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("temporal", temporal_node)
    workflow.add_node("link", link_node)
    workflow.add_node("fulfill", fulfill_node)
    workflow.add_node("status", status_node)
    workflow.add_node("digest", digest_node)
    workflow.add_node("correction", correction_node)

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

    # After extraction, resolve temporal phrases
    workflow.add_edge("extract", "temporal")
    # After temporal, link threads and entities
    workflow.add_edge("temporal", "link")
    # After linking, check for fulfillment signals
    workflow.add_edge("link", "fulfill")
    # After fulfillment, update all statuses
    workflow.add_edge("fulfill", "status")
    # After status, generate digest
    workflow.add_edge("status", "digest")
    # After digest, allow human correction via interrupt
    workflow.add_edge("digest", "correction")
    # Done
    workflow.add_edge("correction", END)

    if checkpointer is None:
        checkpointer = global_checkpointer

    return workflow.compile(checkpointer=checkpointer)


async def run_pipeline_for_message(
    db: AsyncSession,
    message_id: str,
    external_thread_id: str | None = None,
    self_email: str = "",
) -> None:
    """Helper to invoke the compiled LangGraph pipeline for a specific message."""
    graph = compile_pipeline_graph()
    initial_state = {
        "message_id": message_id,
        "external_thread_id": external_thread_id,
        "self_email": self_email,
        "should_extract": False,
        "commitments_extracted": 0,
        "processing_complete": False,
    }
    await graph.ainvoke(
        initial_state,
        {"configurable": {"thread_id": message_id, "db": db}}
    )

