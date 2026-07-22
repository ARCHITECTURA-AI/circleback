"""Tests for the Cheap Prefilter.

TDD: These tests define the regex/keyword matching contract for the cheap prefilter.
The prefilter blocks obvious non-commitments to save LLM costs and latency.
"""

from __future__ import annotations

from circleback.pipeline.prefilter import should_process_message


def test_prefilter_passes_clear_commitment() -> None:
    """Clear commitments containing I'll/will/send/deadline keywords pass the filter."""
    assert should_process_message("I'll send you the deck by Friday") is True
    assert should_process_message("I will deliver the reports tomorrow") is True
    assert should_process_message("let me get back to you on that by next week") is True


def test_prefilter_passes_delegated_commitment() -> None:
    """Delegation phrases pass the filter."""
    assert should_process_message("I'll get Sarah to send the document") is True
    assert should_process_message("I will have Sarah review it") is True


def test_prefilter_skips_no_commitment() -> None:
    """Phrases without any commitment indicators are skipped."""
    assert should_process_message("Thanks, sounds good!") is False
    assert should_process_message("Are we still meeting at 3 PM?") is False
    assert should_process_message("The weather is nice today.") is False


def test_prefilter_passes_conditional() -> None:
    """Conditional commitment phrases pass the filter."""
    assert should_process_message("If the budget is approved, I will start the project") is True


def test_prefilter_passes_quoted_commitment() -> None:
    """Forwarded or quoted emails containing commitments pass the filter."""
    email_body = (
        "---------- Forwarded message ---------\n"
        "From: Alice <alice@co.com>\n"
        "Date: Mon, Oct 14, 2026\n"
        "Subject: Project deck\n\n"
        "I will send you the deck by Friday."
    )
    assert should_process_message(email_body) is True
