"""Centralized LLM client for Circle Back.

Wraps langchain-groq and langchain-anthropic to provide:
- Dual-provider support (Groq default, Anthropic fallback) via LLM_PROVIDER config
- Shared LLM initialization
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

# Approximate token pricing per provider (per 1M tokens)
PRICING: dict[str, dict[str, float]] = {
    "groq": {
        "input": 0.05,   # $0.05 per 1M input tokens (llama-3.1-8b-instant)
        "output": 0.08,  # $0.08 per 1M output tokens
    },
    "anthropic": {
        "input": 3.00,   # $3 per 1M input tokens (Claude Sonnet 4)
        "output": 15.00,  # $15 per 1M output tokens
    },
}

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.1-8b-instant",
    "anthropic": "claude-sonnet-4-20250514",
}


def _estimate_cost(input_tokens: int, output_tokens: int, provider: str = "groq") -> float:
    """Estimate cost in USD from token counts."""
    pricing = PRICING.get(provider, PRICING["groq"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def _check_and_update_cost(
    input_tokens: int, output_tokens: int, daily_limit: float, provider: str = "groq"
) -> None:
    """Track daily cost and raise if limit exceeded."""
    global _daily_cost_cents, _cost_reset_day

    today = time.gmtime().tm_yday
    if today != _cost_reset_day:
        _daily_cost_cents = 0.0
        _cost_reset_day = today

    cost = _estimate_cost(input_tokens, output_tokens, provider)
    _daily_cost_cents += cost

    if _daily_cost_cents > daily_limit:
        raise RuntimeError(
            f"Daily LLM cost limit exceeded: ${_daily_cost_cents:.2f} > ${daily_limit:.2f}. "
            "Pipeline halted to prevent runaway bills."
        )

    logger.info("LLM call cost: $%.4f (daily total: $%.4f / $%.2f limit) [%s]",
                cost, _daily_cost_cents, daily_limit, provider)


def reset_cost_tracking() -> None:
    """Reset cost tracking — useful for tests."""
    global _daily_cost_cents, _cost_reset_day
    _daily_cost_cents = 0.0
    _cost_reset_day = 0


# ── Provider initialization ──────────────────────────────────

def _get_llm(
    provider: str = "groq",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> Any:
    """Create an LLM instance for the given provider.

    Supports 'groq' and 'anthropic' providers.
    """
    resolved_model = model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS["groq"])

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model_name=resolved_model,  # type: ignore[call-arg]
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # Default: Groq
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=resolved_model,  # type: ignore[call-arg]
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ── Structured LLM calls ─────────────────────────────────────

T = TypeVar("T", bound=BaseModel)


async def call_llm_structured(
    system_prompt: str,
    user_message: str,
    output_schema: type[T],
    provider: str = "groq",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    daily_cost_limit: float = 1.0,
) -> T:
    """Call the LLM with structured output, returning a validated Pydantic model.

    Uses with_structured_output for reliable JSON extraction.
    Tracks costs and enforces the daily spend limit.
    Supports both Groq and Anthropic providers.
    """
    llm = _get_llm(provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(output_schema)

    messages = [
        ("system", system_prompt),
        ("human", user_message),
    ]

    from typing import cast

    # Retry once on parse failure (open-source models occasionally produce malformed JSON)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            result = cast("T", await structured_llm.ainvoke(messages))
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.warning("LLM structured output failed (attempt 1), retrying: %s", e)
                continue
            raise last_error from e

    # Estimate token usage (rough: 4 chars ≈ 1 token)
    input_tokens = (len(system_prompt) + len(user_message)) // 4
    output_tokens = len(result.model_dump_json()) // 4
    _check_and_update_cost(input_tokens, output_tokens, daily_cost_limit, provider)

    return result


async def call_llm_raw(
    system_prompt: str,
    user_message: str,
    provider: str = "groq",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    daily_cost_limit: float = 1.0,
) -> str:
    """Call the LLM and return raw text response.

    Supports both Groq and Anthropic providers.
    """
    llm = _get_llm(provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)

    messages = [
        ("system", system_prompt),
        ("human", user_message),
    ]

    response = await llm.ainvoke(messages)
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
    _check_and_update_cost(input_tokens, output_tokens, daily_cost_limit, provider)

    return content


# ── Backward-compatible aliases ───────────────────────────────
# These map the old call_claude_* names for any callers that haven't been updated yet.

call_claude_structured = call_llm_structured
call_claude_raw = call_llm_raw
