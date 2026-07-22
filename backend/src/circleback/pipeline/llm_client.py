"""Centralized LLM client for Circle Back.

Wraps langchain-anthropic to provide:
- Shared Claude initialization
- Daily cost tracking and enforcement (llm_daily_cost_limit_usd)
- Structured output helpers via Pydantic models
- Configurable model selection
"""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Cost tracking ─────────────────────────────────────────────

_daily_cost_cents: float = 0.0
_cost_reset_day: int = 0

# Approximate token pricing for Claude Sonnet 4 (per 1M tokens)
INPUT_COST_PER_M = 3.00   # $3 per 1M input tokens
OUTPUT_COST_PER_M = 15.00  # $15 per 1M output tokens


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts."""
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_M
    return input_cost + output_cost


def _check_and_update_cost(input_tokens: int, output_tokens: int, daily_limit: float) -> None:
    """Track daily cost and raise if limit exceeded."""
    global _daily_cost_cents, _cost_reset_day

    today = time.gmtime().tm_yday
    if today != _cost_reset_day:
        _daily_cost_cents = 0.0
        _cost_reset_day = today

    cost = _estimate_cost(input_tokens, output_tokens)
    _daily_cost_cents += cost

    if _daily_cost_cents > daily_limit:
        raise RuntimeError(
            f"Daily LLM cost limit exceeded: ${_daily_cost_cents:.2f} > ${daily_limit:.2f}. "
            "Pipeline halted to prevent runaway bills."
        )

    logger.info("LLM call cost: $%.4f (daily total: $%.4f / $%.2f limit)",
                cost, _daily_cost_cents, daily_limit)


def reset_cost_tracking() -> None:
    """Reset cost tracking — useful for tests."""
    global _daily_cost_cents, _cost_reset_day
    _daily_cost_cents = 0.0
    _cost_reset_day = 0


# ── Structured LLM calls ─────────────────────────────────────

T = TypeVar("T", bound=BaseModel)


async def call_claude_structured(
    system_prompt: str,
    user_message: str,
    output_schema: type[T],
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    daily_cost_limit: float = 10.0,
) -> T:
    """Call Claude with structured output, returning a validated Pydantic model.

    Uses langchain-anthropic's with_structured_output for reliable JSON extraction.
    Tracks costs and enforces the daily spend limit.
    """
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    structured_llm = llm.with_structured_output(output_schema)

    messages = [
        ("system", system_prompt),
        ("human", user_message),
    ]

    from typing import cast
    result = cast(T, structured_llm.invoke(messages))

    # Estimate token usage (rough: 4 chars ≈ 1 token)
    input_tokens = (len(system_prompt) + len(user_message)) // 4
    output_tokens = len(result.model_dump_json()) // 4
    _check_and_update_cost(input_tokens, output_tokens, daily_cost_limit)

    return result


async def call_claude_raw(
    system_prompt: str,
    user_message: str,
    model: str = "claude-sonnet-4-20250514",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    daily_cost_limit: float = 10.0,
) -> str:
    """Call Claude and return raw text response."""
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    messages = [
        ("system", system_prompt),
        ("human", user_message),
    ]

    response = llm.invoke(messages)
    content_raw = response.content if hasattr(response, "content") else str(response)

    if isinstance(content_raw, list):
        text_parts = []
        for block in content_raw:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(str(block["text"]))
        content = "".join(text_parts)
    else:
        content = content_raw

    # Cost tracking
    input_tokens = (len(system_prompt) + len(user_message)) // 4
    output_tokens = len(content) // 4
    _check_and_update_cost(input_tokens, output_tokens, daily_cost_limit)

    return content
