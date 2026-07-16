"""Temporal Resolution node in the LangGraph agent pipeline.

Resolves relative or explicit temporal phrases (e.g. "by Friday", "tomorrow")
against an anchor message timestamp into concrete timezone-aware deadlines.

Design decisions:
- Anchor = message send timestamp (sender's local timezone, §6.4)
- Business-day vs calendar-day distinction (§6.4)
- Unresolvable phrases → deadline_confidence low, never silently guessed (§6.4)
- Explicit policy tested against the eval set
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

DAYS_OF_WEEK = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Phrases that imply business days rather than calendar days
BUSINESS_DAY_PHRASES = {
    "business day", "business days", "working day", "working days",
    "eob", "end of business", "close of business", "cob",
}

# Phrases that are inherently unresolvable
VAGUE_PHRASES = {
    "sometime soon", "soon", "later", "when i can",
    "when i'm back", "when i get back", "when things settle",
    "at some point", "eventually", "in a bit", "asap",
    "when possible", "when i have time",
}


def _next_business_day(dt: datetime, days_ahead: int = 1) -> datetime:
    """Advance by N business days (skip weekends)."""
    count = 0
    current = dt
    while count < days_ahead:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            count += 1
    return current


def _ensure_tz(dt: datetime, anchor: datetime) -> datetime:
    """Ensure the datetime has timezone info, defaulting to anchor's timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=anchor.tzinfo or timezone.utc)
    return dt


def resolve_deadline(phrase: str, anchor: datetime) -> dict[str, Any]:
    """Resolve a temporal phrase against an anchor datetime into a concrete deadline.

    Returns:
        dict with 'deadline' (datetime | None) and 'confidence' (float 0-1).
        If the phrase is unresolvable, deadline is None and confidence is low.
    """
    if not phrase:
        return {"deadline": None, "confidence": 0.0}

    # Ensure anchor has timezone
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)

    cleaned = phrase.strip().lower()
    # Remove common prepositions
    cleaned = re.sub(r"^(by|at|on|before|in|for|around)\s+", "", cleaned)

    # ── Vague / unresolvable phrases ──────────────────────────
    for vague in VAGUE_PHRASES:
        if vague in cleaned:
            return {"deadline": None, "confidence": 0.1}

    # ── "today" ───────────────────────────────────────────────
    if cleaned in ("today", "this afternoon", "this evening"):
        deadline = anchor.replace(hour=18, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.85}

    # ── "tomorrow" / "tomorrow morning" ───────────────────────
    if "tomorrow" in cleaned:
        deadline = anchor + timedelta(days=1)
        hour = 10 if "morning" in cleaned else 18
        deadline = deadline.replace(hour=hour, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.9}

    # ── "end of day" / "eod" / "close of business" / "cob" ───
    if cleaned in ("end of day", "eod", "close of business", "cob", "eob", "end of business"):
        deadline = anchor.replace(hour=18, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.9}

    # ── "end of week" ─────────────────────────────────────────
    if cleaned in ("end of week", "eow"):
        # Friday of current week
        weekday = anchor.weekday()
        days_to_friday = (4 - weekday) % 7
        if days_to_friday == 0 and anchor.hour >= 18:
            days_to_friday = 7
        deadline = anchor + timedelta(days=days_to_friday)
        deadline = deadline.replace(hour=18, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.85}

    # ── "end of month" ────────────────────────────────────────
    if cleaned in ("end of month", "eom"):
        next_month = anchor.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        deadline = last_day.replace(hour=18, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.95}

    # ── "next week" ───────────────────────────────────────────
    if cleaned == "next week":
        weekday = anchor.weekday()
        days_ahead = 7 - weekday  # Monday of next week
        deadline = anchor + timedelta(days=days_ahead)
        deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.8}

    # ── "in N days" / "in N business days" ────────────────────
    in_days_match = re.match(r"(\d+)\s+(business\s+)?(days?|working\s+days?)", cleaned)
    if in_days_match:
        n = int(in_days_match.group(1))
        is_business = bool(in_days_match.group(2)) or "working" in cleaned
        if is_business:
            deadline = _next_business_day(anchor, n)
        else:
            deadline = anchor + timedelta(days=n)
        deadline = deadline.replace(hour=18, minute=0, second=0, microsecond=0)
        return {"deadline": deadline, "confidence": 0.85}

    # ── "in N hours" ──────────────────────────────────────────
    in_hours_match = re.match(r"(\d+)\s+hours?", cleaned)
    if in_hours_match:
        n = int(in_hours_match.group(1))
        deadline = anchor + timedelta(hours=n)
        return {"deadline": deadline, "confidence": 0.9}

    # ── Day of week (e.g. "friday", "by monday") ──────────────
    for day_name, day_idx in DAYS_OF_WEEK.items():
        if day_name in cleaned:
            weekday = anchor.weekday()
            days_ahead = (day_idx - weekday) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week's day if sent on that day
            deadline = anchor + timedelta(days=days_ahead)
            deadline = deadline.replace(hour=18, minute=0, second=0, microsecond=0)
            return {"deadline": deadline, "confidence": 0.85}

    # ── Explicit month & day (e.g., "october 17th", "oct 17") ─
    for month_name, month_num in MONTHS.items():
        pattern = rf"\b{month_name}\b\s+(\d+)"
        match = re.search(pattern, cleaned)
        if match:
            day = int(match.group(1))
            year = anchor.year
            if month_num < anchor.month or (month_num == anchor.month and day < anchor.day):
                year += 1
            try:
                deadline = datetime(year, month_num, day, 18, 0, 0, tzinfo=anchor.tzinfo)
                return {"deadline": deadline, "confidence": 0.95}
            except ValueError:
                pass

    # ── Numeric date patterns (e.g., "1/15", "01/15/2025") ────
    date_match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", cleaned)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        year_str = date_match.group(3)
        year = int(year_str) if year_str else anchor.year
        if year < 100:
            year += 2000
        try:
            deadline = datetime(year, month, day, 18, 0, 0, tzinfo=anchor.tzinfo)
            return {"deadline": deadline, "confidence": 0.9}
        except ValueError:
            pass

    # ── Unresolvable — explicit about uncertainty ─────────────
    return {"deadline": None, "confidence": 0.1}
