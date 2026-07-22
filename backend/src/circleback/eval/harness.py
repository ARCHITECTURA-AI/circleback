"""Evaluation Harness implementation for measuring commitment extraction quality.

Loads labeled test fixtures, runs prefiltering and LLM extraction,
compares results, and computes Precision, Recall, and F1 metrics.

Design decisions:
- Tracks binary commitment detection PLUS committer accuracy and type accuracy
- Generates a detailed eval report with example successes/failures
- Exposed via /metrics API endpoint (spec §7)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from circleback.db.models import ChannelType, Message
from circleback.eval.metrics import calculate_metrics
from circleback.pipeline.extractor import extract_commitments_from_message
from circleback.pipeline.prefilter import should_process_message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def load_fixtures() -> list[dict[str, Any]]:
    """Load labeled evaluation fixtures from JSON file."""
    fixtures_path = Path(__file__).parent / "fixtures" / "eval_fixtures.json"
    with open(fixtures_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


async def run_evaluation(db: AsyncSession, limit: int | None = None, user_id: str | None = None) -> dict[str, Any]:
    """Run extraction pipeline on labeled fixtures and return performance metrics.

    Returns comprehensive metrics including:
    - Binary detection: precision, recall, F1
    - Committer accuracy (when commitment is correctly detected)
    - Type accuracy (when commitment is correctly detected)
    - Example successes and failures for honest reporting (spec §12)
    """
    from sqlalchemy import select

    from circleback.db.models import User

    resolved_user_id = user_id
    if not resolved_user_id:
        # Check if any user exists, otherwise create one
        result = await db.execute(select(User))
        user_record = result.scalar_one_or_none()
        if user_record:
            resolved_user_id = user_record.id
        else:
            user_record = User(email="eval@company.com", display_name="Eval User")
            db.add(user_record)
            await db.flush()
            resolved_user_id = user_record.id

    fixtures = load_fixtures()
    if limit is not None:
        fixtures = fixtures[:limit]

    tp = 0  # True positives: correctly detected as commitment
    fp = 0  # False positives: flagged as commitment but isn't
    fn = 0  # False negatives: missed a real commitment
    tn = 0  # True negatives: correctly rejected as non-commitment

    type_correct = 0
    type_total = 0

    examples_success: list[dict[str, Any]] = []
    examples_failure: list[dict[str, Any]] = []
    prefilter_false_negatives: list[str] = []

    for index, fixture in enumerate(fixtures):
        text = fixture["text"]
        expected_commitment = fixture["is_commitment"]
        expected_type = fixture.get("commitment_type")

        # Create dummy message (not persisted)
        from datetime import datetime, timezone
        msg = Message(
            id=f"eval_msg_{index}",
            user_id=resolved_user_id,
            channel=ChannelType.EMAIL,
            raw_text=text,
            timestamp=datetime.now(timezone.utc),
            recipient_person_ids=[],
        )

        # Run prefilter
        passed_prefilter = should_process_message(text)

        commitments = []
        if passed_prefilter:
            commitments = await extract_commitments_from_message(
                db, msg, self_email="self@company.com", user_id=resolved_user_id
            )

        actual_commitment = len(commitments) > 0

        # Track prefilter false negatives separately
        if expected_commitment and not passed_prefilter:
            prefilter_false_negatives.append(text[:80])

        # Binary classification
        if expected_commitment and actual_commitment:
            tp += 1
            # Check type accuracy
            if expected_type and commitments:
                actual_type = commitments[0].commitment_type.value
                type_total += 1
                if actual_type == expected_type:
                    type_correct += 1
                else:
                    examples_failure.append({
                        "text": text[:100],
                        "issue": "wrong_type",
                        "expected_type": expected_type,
                        "actual_type": actual_type,
                    })

            examples_success.append({
                "text": text[:100],
                "confidence": commitments[0].extraction_confidence if commitments else 0.0,
            })

        elif not expected_commitment and actual_commitment:
            fp += 1
            examples_failure.append({
                "text": text[:100],
                "issue": "false_positive",
                "confidence": commitments[0].extraction_confidence if commitments else 0.0,
            })

        elif expected_commitment and not actual_commitment:
            fn += 1
            examples_failure.append({
                "text": text[:100],
                "issue": "false_negative",
                "passed_prefilter": passed_prefilter,
            })

        else:
            tn += 1

    metrics_dict: dict[str, Any] = dict(calculate_metrics(tp, fp, fn))
    metrics_dict["total_tested"] = len(fixtures)
    metrics_dict["tp"] = tp
    metrics_dict["fp"] = fp
    metrics_dict["fn"] = fn
    metrics_dict["tn"] = tn
    metrics_dict["type_accuracy"] = type_correct / type_total if type_total > 0 else None
    metrics_dict["type_evaluated"] = type_total
    metrics_dict["prefilter_false_negatives"] = len(prefilter_false_negatives)
    metrics_dict["example_successes"] = examples_success[:5]  # Show top 5
    metrics_dict["example_failures"] = examples_failure[:5]

    return metrics_dict
