"""Tests for Temporal Resolution logic.

TDD: These tests define how relative date phrases (e.g., 'by Friday', 'tomorrow')
are resolved into timezone-aware datetime deadlines against message send timestamp anchor.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from circleback.pipeline.temporal import resolve_deadline


def test_resolve_explicit_date() -> None:
    """Explicit dates resolve with high confidence."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("by October 17th", anchor)
    assert res["deadline"].year == 2026
    assert res["deadline"].month == 10
    assert res["deadline"].day == 17
    assert res["confidence"] >= 0.8


def test_resolve_relative_friday() -> None:
    """Relative 'Friday' sent on Monday Oct 14 resolves to Friday Oct 18."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)  # Monday Oct 12 actually (let's check calendar)
    # 2026-10-14 is a Wednesday.
    # Wednesday Oct 14 -> Friday is Oct 16.
    res = resolve_deadline("by Friday", anchor)
    assert res["deadline"].day == 16
    assert res["deadline"].month == 10


def test_resolve_relative_friday_sent_on_friday() -> None:
    """Relative 'Friday' sent on Friday Oct 16 resolves to next Friday Oct 23."""
    anchor = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)  # Friday
    res = resolve_deadline("by Friday", anchor)
    assert res["deadline"].day == 23
    assert res["deadline"].month == 10


def test_resolve_next_week() -> None:
    """'next week' resolves to Monday of next week."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)  # Wednesday Oct 14
    res = resolve_deadline("next week", anchor)
    # Next week Monday should be Oct 19.
    assert res["deadline"].day == 19
    assert res["deadline"].month == 10


def test_resolve_end_of_day() -> None:
    """'end of day' resolves to 18:00 (6 PM) of the anchor day."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("by end of day", anchor)
    assert res["deadline"].day == 14
    assert res["deadline"].hour == 18


def test_resolve_end_of_month() -> None:
    """'end of month' resolves to the last day of the current month."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("end of month", anchor)
    assert res["deadline"].day == 31
    assert res["deadline"].month == 10


def test_resolve_tomorrow() -> None:
    """'tomorrow' resolves to the next day."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("tomorrow", anchor)
    assert res["deadline"].day == 15
    assert res["deadline"].month == 10


def test_unresolvable_sometime_soon() -> None:
    """Vague phrases like 'sometime soon' yield low confidence and null deadline."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("sometime soon", anchor)
    assert res["deadline"] is None
    assert res["confidence"] < 0.2


def test_unresolvable_when_im_back() -> None:
    """Vague phrases like 'when I'm back' yield low confidence and null deadline."""
    anchor = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    res = resolve_deadline("when I'm back", anchor)
    assert res["deadline"] is None
    assert res["confidence"] < 0.2
