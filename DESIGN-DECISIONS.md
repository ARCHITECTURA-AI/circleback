# Circle Back — Design Decisions

This document captures the hardest architectural and product calls made during the development of Circle Back, focusing on *why* these decisions were made rather than just what the outcome was.

## 1. Biasing Hard Toward Precision Over Recall

**The Decision:** The extraction LLM is explicitly prompted to be conservative. Commitments with a confidence score below 0.5 are routed to a secondary "Review Queue" rather than the main digest. 

**The Reasoning:** In the agentic space, trust is asymmetrical. If Circle Back misses a commitment (false negative), the user is no worse off than they were before using the tool. However, if the tool consistently flags non-commitments—like past-tense statements, sarcastic remarks, or hypotheticals (false positives)—the user will experience notification fatigue and quickly abandon the product. We decided that keeping the primary digest high-signal was worth the cost of occasionally missing a vague promise.

## 2. "Absence of Evidence" vs. "Evidence of Absence"

**The Decision:** When a deadline passes without a matching semantic fulfillment message in the thread, the status engine transitions the commitment to `overdue`. However, the UI and internal audit trail strictly frame this as: *"No evidence found — please confirm."* It never says, *"You failed to complete this."*

**The Reasoning:** An agent reading email and Slack is not omniscient. A user might promise to "send the deck by Friday" in an email, but then hand a physical printout to their colleague, or drop the link in a Zoom chat. The system cannot definitively know if a task was skipped. Claiming false certainty when the system is actually just blind to the fulfillment channel fundamentally breaks user trust. 

## 3. Manual Cross-Channel Identity Resolution (v1)

**The Decision:** Circle Back does not attempt to automatically link a user's Slack ID (`@john.doe`) with their Gmail address (`jdoe@company.com`). Instead, users must manually map these identities in the Settings tab.

**The Reasoning:** Automatic identity resolution is a notoriously difficult NLP problem. A false positive here—grouping a commitment meant for an external client with an internal colleague who shares a similar name—would leak context and create confusing digests. For a personal-use v1, a manual "seed list" mapping provides a perfectly safe cold-start. We prioritized data integrity over onboarding friction.

## 4. The Append-Only Audit Trail (CommitmentEvent)

**The Decision:** We used PostgreSQL with an append-only `CommitmentEvent` table to log every state transition. We explicitly disabled hard-deletes on `Message` rows, using `deleted_at` instead.

**The Reasoning:** LLM pipelines can feel like black boxes. When a commitment unexpectedly transitions from `open` to `renegotiated`, the user needs to know *why*. By forcing every pipeline node (Extraction, Temporal Resolution, Fulfillment Matching) to write a discrete `CommitmentEvent` with a confidence score and a reference to the source message, the system becomes an inspectable, deterministic state machine. If the LLM makes a mistake, the evidence trail proves exactly where the logic diverged.

## 5. Deferring Deadlines for Conditional Commitments

**The Decision:** The extractor detects recurring ("every Monday") and conditional ("if the build fails, I'll ping you") commitments, but the temporal node intentionally leaves their `resolved_deadline` as `null`.

**The Reasoning:** Early prototypes attempted to force-fit every commitment into a strict datetime deadline. This caused Claude to hallucinate dates for conditional logic (e.g., guessing a date for when the build might fail). We realized that not all promises are temporal. Flagging them as `conditional` and leaving them open indefinitely is a far more honest representation of the data than fabricating a due date.
