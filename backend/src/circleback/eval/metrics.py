"""Metrics calculation utilities for the Circle Back evaluation harness.

Computes Precision, Recall, and F1 scores based on true positives,
false positives, and false negatives.
"""

from __future__ import annotations


def calculate_metrics(tp: int, fp: int, fn: int) -> dict[str, float]:
    """Calculate Precision, Recall, and F1 score from raw counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
