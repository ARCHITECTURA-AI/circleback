"""Cheap prefilter node in the LangGraph agent pipeline.

Filters out obvious non-commitment messages using regex/keywords to reduce LLM API
costs and latency at inbox scale.
"""

from __future__ import annotations

import re

# Common commitment keywords and relative date patterns
COMMITMENT_PATTERNS = [
    r"\bi'll\b",
    r"\bi will\b",
    r"\blet me\b",
    r"\bi'm going to\b",
    r"\bi'm planning to\b",
    r"\bwe will\b",
    r"\bwe'll\b",
    r"\bwill send\b",
    r"\bwill deliver\b",
    r"\bwill follow up\b",
    r"\bwill get back\b",
    r"\bwill have \w+ \w+\b",
    r"\bget \w+ to \w+\b",
    r"\bby tomorrow\b",
    r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bby end of (day|week|month)\b",
    r"\bnext week\b",
    r"\bsend you the\b",
    r"\bpromise\b",
]

PATTERNS_RE = [re.compile(p, re.IGNORECASE) for p in COMMITMENT_PATTERNS]


def should_process_message(text: str) -> bool:
    """Evaluate if a message might contain a commitment based on cheap heuristics."""
    if not text:
        return False

    # Check if any pattern matches
    return any(pattern.search(text) for pattern in PATTERNS_RE)
