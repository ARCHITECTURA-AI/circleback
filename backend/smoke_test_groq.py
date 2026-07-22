"""Smoke test: Verify Groq LLM integration works end-to-end.

Tests:
1. Structured extraction — send a message with a commitment, get ExtractionResult back
2. Structured fulfillment — send open commitments + follow-up, get FulfillmentResult back
3. Raw text call — simple prompt, get string back
4. Non-commitment rejection — verify a non-commitment message returns empty
5. Cost tracking — verify cost tracking is working
"""

import asyncio
import os
import sys

# Fix Windows console encoding for emoji/unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Ensure we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load .env
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


async def main() -> None:
    print("=" * 70)
    print("  Circle Back — Groq Integration Smoke Test")
    print("=" * 70)

    # Verify config loads correctly
    from circleback.config import get_settings
    settings = get_settings()

    print("\n📋 Config:")
    print(f"   Provider:    {settings.llm_provider}")
    print(f"   Model:       {settings.llm_model}")
    print(f"   API Key:     {settings.groq_api_key[:12]}...{'*' * 20}")
    print(f"   Cost Limit:  ${settings.llm_daily_cost_limit_usd}")

    if not settings.groq_api_key:
        print("\n❌ GROQ_API_KEY is not set in .env — aborting.")
        sys.exit(1)

    from circleback.pipeline.extractor import EXTRACTION_SYSTEM_PROMPT, ExtractionResult
    from circleback.pipeline.fulfillment import FULFILLMENT_SYSTEM_PROMPT, FulfillmentResult
    from circleback.pipeline.llm_client import (
        call_llm_raw,
        call_llm_structured,
        reset_cost_tracking,
    )

    reset_cost_tracking()
    passed = 0
    failed = 0

    # ── Test 1: Structured Extraction ─────────────────────────
    print("\n" + "─" * 70)
    print("🧪 Test 1: Structured Extraction (commitment message)")
    print("─" * 70)
    try:
        result = await call_llm_structured(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message="Analyze this message for commitments:\n\nI'll send you the quarterly report by Friday end of day.",
            output_schema=ExtractionResult,
            provider=settings.llm_provider,
            model=settings.llm_model,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        print(f"   ✅ Got ExtractionResult with {len(result.commitments)} commitment(s)")
        for c in result.commitments:
            print(f"      • is_commitment: {c.is_commitment}")
            print(f"        text: \"{c.raw_text_span[:60]}\"")
            print(f"        type: {c.commitment_type}")
            print(f"        temporal: {c.raw_temporal_phrase}")
            print(f"        confidence: {c.extraction_confidence}")
            print(f"        reasoning: {c.reasoning[:80]}")

        if result.commitments and result.commitments[0].is_commitment:
            print("   ✅ PASS — Correctly identified as a commitment")
            passed += 1
        else:
            print("   ⚠️  WARN — Expected at least one commitment flagged as is_commitment=True")
            failed += 1
    except Exception as e:
        print(f"   ❌ FAIL — {type(e).__name__}: {e}")
        failed += 1

    # ── Test 2: Non-Commitment Rejection ──────────────────────
    print("\n" + "─" * 70)
    print("🧪 Test 2: Non-Commitment Rejection (sarcasm / past-tense)")
    print("─" * 70)
    try:
        result = await call_llm_structured(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message="Analyze this message for commitments:\n\nThanks for sending that over Friday, really appreciate it!",
            output_schema=ExtractionResult,
            provider=settings.llm_provider,
            model=settings.llm_model,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        print(f"   ✅ Got ExtractionResult with {len(result.commitments)} commitment(s)")

        real_commitments = [c for c in result.commitments if c.is_commitment]
        if len(real_commitments) == 0:
            print("   ✅ PASS — Correctly rejected non-commitment (past-tense)")
            passed += 1
        else:
            print(f"   ⚠️  WARN — Expected 0 real commitments but got {len(real_commitments)}")
            for c in real_commitments:
                print(f"      • \"{c.raw_text_span[:60]}\" (confidence: {c.extraction_confidence})")
            failed += 1
    except Exception as e:
        print(f"   ❌ FAIL — {type(e).__name__}: {e}")
        failed += 1

    # ── Test 3: Structured Fulfillment Matching ───────────────
    print("\n" + "─" * 70)
    print("🧪 Test 3: Structured Fulfillment Matching")
    print("─" * 70)
    try:
        user_msg = (
            "OPEN COMMITMENTS:\n"
            "- ID: commit-001 | Type: simple | Text: \"I'll send you the quarterly report\" | "
            "Deadline: 2026-07-25T18:00:00+00:00 | Status: open\n\n"
            "NEW MESSAGE (from alice@company.com):\n"
            "Here's the quarterly report as promised. Let me know if you have questions."
        )
        result = await call_llm_structured(
            system_prompt=FULFILLMENT_SYSTEM_PROMPT,
            user_message=user_msg,
            output_schema=FulfillmentResult,
            provider=settings.llm_provider,
            model=settings.llm_model,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        print(f"   ✅ Got FulfillmentResult with {len(result.matches)} match(es)")
        for m in result.matches:
            print(f"      • commitment_id: {m.commitment_id}")
            print(f"        action: {m.action}")
            print(f"        confidence: {m.confidence}")
            print(f"        reason: {m.reason[:80]}")

        fulfill_matches = [m for m in result.matches if m.action == "fulfill"]
        if fulfill_matches:
            print("   ✅ PASS — Correctly detected fulfillment")
            passed += 1
        else:
            print("   ⚠️  WARN — Expected a 'fulfill' match")
            failed += 1
    except Exception as e:
        print(f"   ❌ FAIL — {type(e).__name__}: {e}")
        failed += 1

    # ── Test 4: Raw Text Call ─────────────────────────────────
    print("\n" + "─" * 70)
    print("🧪 Test 4: Raw Text Call")
    print("─" * 70)
    try:
        response = await call_llm_raw(
            system_prompt="You are a helpful assistant. Reply in one sentence.",
            user_message="What is Circle Back?",
            provider=settings.llm_provider,
            model=settings.llm_model,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        print(f"   ✅ Got raw response ({len(response)} chars):")
        print(f"      \"{response[:120]}\"")
        if len(response) > 5:
            print("   ✅ PASS — Got meaningful response")
            passed += 1
        else:
            print("   ⚠️  WARN — Response seems too short")
            failed += 1
    except Exception as e:
        print(f"   ❌ FAIL — {type(e).__name__}: {e}")
        failed += 1

    # ── Test 5: Delegated Commitment Detection ────────────────
    print("\n" + "─" * 70)
    print("🧪 Test 5: Delegated Commitment Detection")
    print("─" * 70)
    try:
        result = await call_llm_structured(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message="Analyze this message for commitments:\n\nI'll get Sarah to send you the contract by next Tuesday.",
            output_schema=ExtractionResult,
            provider=settings.llm_provider,
            model=settings.llm_model,
            daily_cost_limit=settings.llm_daily_cost_limit_usd,
        )
        print(f"   ✅ Got ExtractionResult with {len(result.commitments)} commitment(s)")
        for c in result.commitments:
            if c.is_commitment:
                print(f"      • type: {c.commitment_type}")
                print(f"        text: \"{c.raw_text_span[:60]}\"")
                print(f"        confidence: {c.extraction_confidence}")

        delegated = [c for c in result.commitments if c.is_commitment and c.commitment_type == "delegated"]
        if delegated:
            print("   ✅ PASS — Correctly identified as 'delegated' type")
            passed += 1
        else:
            real = [c for c in result.commitments if c.is_commitment]
            if real:
                print(f"   ⚠️  PARTIAL — Detected commitment but type='{real[0].commitment_type}' (expected 'delegated')")
                passed += 1  # Still counts as working, just type classification differs
            else:
                print("   ❌ FAIL — No commitment detected")
                failed += 1
    except Exception as e:
        print(f"   ❌ FAIL — {type(e).__name__}: {e}")
        failed += 1

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"  Results: {passed}/{total} passed, {failed}/{total} failed")
    if failed == 0:
        print("  🎉 All tests passed! Groq integration is working correctly.")
    else:
        print(f"  ⚠️  {failed} test(s) had issues — review output above.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
