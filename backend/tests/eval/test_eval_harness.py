"""Tests for the Evaluation Harness.

TDD: These tests verify that the evaluation harness loads labeled fixtures,
runs extraction against them, computes precision, recall, and F1 metrics correctly,
and reports regressions if quality drops.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from circleback.eval.harness import run_evaluation, load_fixtures
from circleback.db.models import CommitmentType


def test_eval_harness_loads_fixtures() -> None:
    """Eval harness correctly loads labeled messages from fixtures file."""
    fixtures = load_fixtures()
    assert len(fixtures) > 0
    # Verify shape of first fixture
    f = fixtures[0]
    assert "text" in f
    assert "is_commitment" in f
    assert "correct_committer" in f


def test_eval_computes_metrics_correctly() -> None:
    """Metrics calculations (Precision, Recall, F1) are mathematically correct."""
    from circleback.eval.metrics import calculate_metrics

    # TP = 3, FP = 1, FN = 2
    metrics = calculate_metrics(tp=3, fp=1, fn=2)
    assert metrics["precision"] == pytest.approx(3 / (3 + 1))
    assert metrics["recall"] == pytest.approx(3 / (3 + 2))
    assert metrics["f1"] == pytest.approx(2 * 0.75 * 0.6 / (0.75 + 0.6))


@pytest.mark.asyncio
@patch("circleback.pipeline.extractor.call_llm_for_extraction")
async def test_eval_harness_run_evaluation(mock_call_llm, db_session) -> None:
    """Running evaluation compiles precision, recall, and F1 across the loaded set."""
    # Mock LLM to return commitment for every input
    mock_call_llm.return_value = {
        "commitments": [
            {
                "raw_text_span": "test span",
                "commitment_type": "simple",
                "raw_temporal_phrase": "",
                "extraction_confidence": 0.9,
                "committer_identifier": "sender",
                "recipient_identifiers": [],
                "is_commitment": True
            }
        ]
    }

    # Run eval with a subset of fixtures
    results = await run_evaluation(db_session, limit=5)
    assert "precision" in results
    assert "recall" in results
    assert "f1" in results
    assert results["total_tested"] == 5
