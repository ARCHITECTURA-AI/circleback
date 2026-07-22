# Circle Back — Product Specification

**A personal agent that tracks commitments made across email and Slack — yours and others' — and surfaces what's at risk before it becomes a broken promise.**

---

## 1. Problem Statement

People make and receive dozens of small commitments a week buried inside email threads and Slack messages — "I'll send this by Friday," "let me get back to you on that," "I'll loop in legal and follow up." None of this lives in a task manager. It gets lost in scroll, and the two failure modes are both costly:

- You forget something you promised, and someone else notices before you do.
- You're waiting on something someone else promised, and you don't realize it's overdue until it blocks you.

Circle Back is not a summarizer and not a to-do list. It is a state machine that extracts commitments from real conversation, resolves vague temporal language into real deadlines, watches for evidence of fulfillment, and tells you — with appropriate uncertainty — what's actually at risk.

**Core design commitment:** the system must never claim false certainty. Absence of evidence that something was done is surfaced as "no evidence found, please confirm" — never as a verdict that something was missed.

---

## 2. Scope (v1)

- **Personal use only.** Tracks commitments the user makes and commitments made *to* the user — symmetric tracking, both directions, from day one.
- **Two channels from day one:** Gmail and Slack, normalized into a single pipeline.
- **Public-facing product.** Real users will connect their own Gmail/Slack via OAuth. This means OAuth verification, a privacy policy, and real security practices are in scope for v1, not deferred.
- **Cross-channel identity resolution is manual** in v1 (user maintains a person-mapping list). Automatic identity resolution across channels is explicitly out of scope — the false-positive risk isn't worth it yet.
- **Recurring and conditional commitments are detected but not deadline-tracked** in v1 (flagged separately, not force-fit into the deadline model).

### Explicitly out of scope for v1
- Team/multi-user shared commitment tracking
- Automatic cross-channel person resolution
- Calendar integration for resolving relative dates against actual availability
- Mobile app (web-responsive only)
- Any channel beyond Gmail and Slack (SMS, other chat tools, etc.)

---

## 3. Product Name

**Circle Back** — deliberately ironic. "Circle back" is the most-mocked phrase in corporate speak for a commitment that will quietly never happen. This tool actually circles back.

---

## 4. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Agent pipeline | **LangGraph** (Python) | Pipeline is a deterministic, inspectable state machine — not autonomous agent negotiation. Native support for human-in-the-loop interrupts and checkpointed state across sessions, both required for the correction loop and multi-day commitment tracking. |
| Backend API | **FastAPI** (Python) | Pairs naturally with LangGraph, async-friendly for webhook ingestion from Gmail/Slack. |
| Database | **PostgreSQL** | Relational model fits the evidence-trail/audit-log requirement (Commitment → CommitmentEvent) far better than a document store. |
| Frontend | **Next.js + TypeScript + Tailwind** | Needs a real public-facing UI (onboarding, digest, commitment detail, settings) — not just an API demo. |
| Auth | OAuth 2.0 (Google, Slack) + session-based app auth | Standard, and required for the verification processes below. |
| LLM provider | Groq (Llama 3.1 8B, default) / Anthropic Claude (fallback) | Dual-provider support via config toggle. Groq for cost efficiency; Anthropic for structured output reliability. |
| Hosting | Backend: Fly.io or Render. Frontend: Vercel. DB: managed Postgres (Neon/Supabase/RDS). | Reasonable default for a solo-maintained public project — revisit if cost or scale demands change this. |

> Pin LangGraph's version explicitly at project start — its API has changed across versions. Verify current best practices for the interrupt/checkpoint patterns before scaffolding, rather than relying on possibly-stale documentation.

---

## 5. Data Model

```
Person
  id, display_name
  email_addresses[]        -- manually seeded/confirmed by user
  slack_user_ids[]
  is_self                  -- flags which Person row is the account owner

Message
  id, channel (email | slack), thread_id, sender_person_id,
  recipient_person_ids[], timestamp, raw_text, permalink,
  edited_at (nullable), deleted_at (nullable)

Thread
  id, channel, participant_person_ids[], subject_or_topic

Commitment
  id, source_message_id, thread_id
  committer_person_id, recipient_person_id(s)
  direction                -- 'made_by_user' | 'owed_to_user'
  raw_text_span
  commitment_type           -- 'simple' | 'delegated' | 'conditional' | 'recurring'
  raw_temporal_phrase
  resolved_deadline (nullable), deadline_confidence (0-1)
  extraction_confidence (0-1)
  status                    -- open | at_risk | overdue | fulfilled | renegotiated | dismissed | needs_clarification
  created_at, last_updated_at

CommitmentEvent
  id, commitment_id, type   -- extracted | renegotiated | fulfillment_signal
                             -- | confirmed | dismissed | edited_source | retracted_source
  evidence_message_id (nullable)
  timestamp, note

EvalLabel   (internal QA tool, not user-facing)
  id, message_id, is_commitment (human-labeled), correct_committer,
  correct_deadline, notes  -- powers the precision/recall eval harness
```

---

## 6. Pipeline Architecture (LangGraph)

```
Ingestion → Cheap Prefilter → Extraction → Temporal Resolution
   → Thread/Entity Linking → Fulfillment Matching → Status Engine
   → Digest Generation → Human Correction Loop (interrupt) → feeds back into Extraction confidence
```

Each stage is a LangGraph node with explicit typed state in/out — independently unit-testable, independently loggable.

### 6.1 Ingestion
- Gmail: incremental sync via history API (cursor-based, not full re-fetch)
- Slack: Events API subscription + backfill on connect
- Normalizes both into `Message` rows
- Handles `edited_at`/`deleted_at`: on edit, re-run extraction on that message; on delete, mark linked commitments' source as `retracted_source` — never silently drop commitment history

### 6.2 Cheap Prefilter
- Lightweight heuristic (keyword/regex pass: "I'll", "will send", "by [day/date]", "let me", etc.) before the expensive LLM call
- Purpose: cost and latency control at inbox scale — most messages contain no commitment at all
- Tunable, tracked against the eval set for false-negative rate (must not filter out real commitments)

### 6.3 Extraction (LLM, structured output)
- Input: prefiltered message + surrounding thread context
- Output: candidate `Commitment` objects with `extraction_confidence`
- Must distinguish: real commitments vs. hedges ("I could probably..."), hypotheticals, group commitments with no individual owner ("we'll circle back" — flagged no-owner, excluded), past-tense references to others' actions, delegated commitments, conditional commitments
- **Bias hard toward precision over recall.** Borderline confidence → route to low-priority review queue, never the main digest.

### 6.4 Temporal Resolution
- Anchor = message send timestamp (sender's local timezone)
- Explicit policy, tested: relative phrases resolve to calendar days unless language implies business days; ambiguous timezone defaults to sender's
- Unresolvable phrases ("sometime soon," "when I'm back") → `deadline_confidence` low, status `needs_clarification` — never silently guessed

### 6.5 Thread/Entity Linking
- Groups messages into commitment-relevant threads
- Maps people across channels via the manual seed list
- Logs (does not silently drop) messages from unrecognized senders/handles that resemble a known person, for later manual mapping

### 6.6 Fulfillment Matching
- Scans later messages in the same thread for evidence matching a *specific* open commitment (semantic match against commitment content, not "any positive follow-up closes the oldest open item")
- Handles multiple concurrent open commitments in one thread independently
- Renegotiation detection: deadline changes update the existing commitment, they do not create a new one
- Delegation detection: "I'll get Sarah to send it" flagged as `delegated`, matching logic checks for Sarah's fulfillment message if she's a mapped Person, otherwise flagged ambiguous

### 6.7 Status Engine
- State transitions per the enum above, every transition logged as a `CommitmentEvent` with evidence
- `at_risk` threshold: configurable window before deadline with no fulfillment signal
- Deadline passed + no evidence anywhere → `overdue`, framed internally and in UI as "no evidence found — confirm?" not "you failed"

### 6.8 Digest Generation
- Daily/weekly summary, at-risk and overdue items, both directions (owed by user / owed to user)
- Framing designed deliberately: lead with upcoming, not overdue, to avoid the digest reading as an indictment

### 6.9 Human Correction Loop (LangGraph interrupt)
- One-tap responses per commitment: **Done** / **Not actually a commitment** / **Still in progress, new deadline**
- Every correction is a `CommitmentEvent` and a labeled data point — feeds the eval set and, over time, confidence calibration for extraction

---

## 7. Evaluation Harness (build alongside Phase 1, not after)

- Labeled set of 100–200 real or realistic synthetic messages (both channels), hand-labeled: is this a commitment, who's the committer, what's the true deadline
- Standing precision/recall/F1 metrics computed against this set on every extraction-prompt or model change
- User corrections from the live product feed back into this set over time
- Exposed as a visible artifact (`/metrics` page or generated eval report in the repo) — this is a deliberate showcase decision, proving the system was validated, not just built

---

## 8. UI / Screens

1. **Landing / marketing page** — problem statement, how it works, connect CTA
2. **Onboarding flow**
   - Connect Gmail → Connect Slack → explain first sync will take a few minutes
   - Person-mapping confirmation step before first digest is shown (cold-start trust: don't show anything until identity mapping is sane)
3. **Main digest** — at-risk / overdue, grouped by direction (owed by you / owed to you), source links
4. **Commitment detail view** (primary showcase surface)
   - Extracted text span, extraction confidence
   - Resolved deadline **with stated reasoning** ("resolved 'Friday' → Oct 17, based on message sent Oct 14")
   - Full evidence/event trail, human-readable
5. **Correction UI** — Done / Not a commitment / New deadline, inline on each item
6. **Review queue** — low-confidence extractions that didn't make the main digest, for manual triage
7. **Settings** — connected accounts, person-mapping list, disconnect + delete-all-data action
8. **Empty / loading / error states** for every screen above

---

## 9. Compliance & Legal (start in parallel with development — do not defer)

- **Google OAuth verification**: Gmail read access is a sensitive/restricted scope. Requires a published privacy policy URL, a demo video showing exact data use, and possibly a CASA security assessment past 100 users. Review can take weeks — submit as soon as the app is minimally functional, not after it's finished.
- **Slack app review**: required for public distribution, faster than Google's but not instant.
- **Privacy policy**: must state what's stored, retention period, encryption at rest, that message content is sent to a third-party LLM API (explicit disclosure), and a clear data-deletion mechanism.
- **Terms of service**: short, honest statement this is a personal/portfolio project, with appropriate liability language. (Not legal advice — have a template reviewed before publishing.)
- **Demo video**: script it to satisfy both the Google verification requirement and the portfolio showcase — same asset, two purposes.

---

## 10. Security

- OAuth refresh tokens encrypted at rest, never logged, minimally scoped (read-only, nothing broader than required)
- Visible "disconnect and delete my data" action that actually purges stored tokens and derived data
- HTTPS everywhere — non-negotiable given real OAuth tokens are in play
- Rate limiting / hard cost caps on LLM API calls (protects against a runaway bill if the demo gets shared widely)
- Structured logging and error monitoring from day one — not for scale, but because a stranger's real inbox will hit cases the eval set didn't cover

---

## 11. Build Plan — Phased, PR-Sized, TDD

Each phase ships independently, tested before merge, failing tests written first.

**Phase 0 — Ingestion skeleton**
Gmail + Slack read-only fetch → normalized `Message` rows, incremental sync, handles edits/deletes.

**Phase 1 — Extraction (with eval harness built alongside)**
Prefilter + LLM extraction → candidate `Commitment` objects, symmetric direction (made_by_user / owed_to_user) from the start. Eval set and metrics live from this phase on.

*Sample test cases:*
- "I'll send you the deck by Friday" → detected, committer=sender, `made_by_user` or `owed_to_user` depending on who's "self"
- "I could probably get this done by Friday if things go well" → low confidence / hedge, review queue not digest
- "We'll circle back on this" → no individual owner, excluded from personal tracking
- "Thanks for sending that over Friday" → past tense, not a commitment
- "I'll get Sarah to send it" → `commitment_type = delegated`

**Phase 2 — Temporal resolution**
Anchor-based relative-date resolution with explicit timezone/business-day policy, confidence scoring, unresolvable phrases flagged not guessed.

**Phase 3 — Thread/entity linking**
Manual person-mapping, thread grouping, unrecognized-sender logging.

**Phase 4 — Fulfillment matching**
Semantic matching against specific commitments (not thread-wide), renegotiation handling, delegation matching.

**Phase 5 — Status engine**
Full state machine, `at_risk` threshold logic, audit trail via `CommitmentEvent`.

**Phase 6 — Digest + correction loop**
Digest generation with deliberate framing, LangGraph interrupt-based correction UI, corrections feeding back into eval set.

**Phase 7 — Product shell**
Onboarding, settings, empty/error states, landing page.

**Phase 8 — Compliance & launch prep**
Privacy policy, ToS, OAuth verification submission, demo video, rate limiting, monitoring.

### Cross-cutting test suite (run against every phase)
- Adversarial: sarcasm ("sure, I'll get right on that"), commitments buried in quoted reply chains or forwards
- Silent fulfillment: system reports absence of evidence, never asserts evidence of absence
- Cross-channel: commitment made in Slack, fulfilled via email attachment
- Renegotiation chains: multiple deadline changes on one thread
- Recurring/conditional commitments: detected and flagged, not force-fit into single-deadline model

---

## 12. Documentation Deliverables

- **README**: problem statement, architecture diagram, key agentic-design decisions and *why* (precision-over-recall bias, evidence-first over silent guessing, why cross-channel identity resolution was deliberately deferred)
- **Architecture diagram**: the pipeline above, visualized
- **Design decisions doc**: short write-ups of the hardest calls made and the reasoning, not just the outcome
- **Demo video**: doubles as OAuth verification asset and portfolio piece
- **Eval report**: precision/recall on the labeled set, with example successes and failures shown honestly

---

## 13. Success Criteria for v1

- Extraction precision ≥ a defined threshold on the held-out eval set before anything ships to the main digest (exact threshold to be set once the eval set exists — don't guess a number before you have real data)
- Zero silent data loss on message edit/delete
- Every status transition has a traceable evidence chain
- A new user can connect both accounts, confirm their identity mapping, and see a sane first digest within one sync cycle
- OAuth verification submitted before Phase 6 is complete, given the multi-week review lag