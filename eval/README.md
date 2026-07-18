# The examination — frozen eval set

Alfred's headline numbers come from **one** benchmark, defined here, and the
methodology is the point: the test set is written *before* any planner
prompt exists, so the planner can never be tuned to its own exam.

## Status: SEALED (2026-07-19) — see SEAL.md

`frozen_set.jsonl` was authored before Phase 2 (no planner prompt existed;
see git history) and is now sealed: the file is never edited, fixes go in an
errata section of the final report. **Caveat carried by every number from
this set:** the planned collection of verbatim phrasings from 2–3 other
people did not happen before sealing, so all utterances are single-author —
the anti-tuning guarantee holds, the phrasing-diversity one does not
(SEAL.md states this in full).

The 25-command **dev smoke set** used during Phase 2 tuning is a separate
file and may change freely; it proves nothing.

## Format

One JSON object per line:

- `id` — C## clean · M## ambiguous/mishear · A## adversarial/off-menu
- `utterance` — what the user says (or what STT plausibly heard)
- `expected` — exactly one of:
  - `{"plan": [...]}` — the correct action sequence
  - `{"refusal": true}` — the only correct behavior is a polite no
  - `{"any_of": [...]}` — several outcomes count as correct (used
    sparingly, for genuinely ambiguous asks where refusal or a
    clarifying default are both acceptable)

## Protocol (Phase 4)

- N=3 voice trials per command via local Whisper, plus 1 typed trial;
  hardware spec recorded in the report.
- Metrics: task success · **wrong-action rate** · refusal correctness ·
  median latency per path (routine-matched vs LLM) · undo coverage ·
  mishear-to-wrong-action conversion.
- Results reported as **counts with the raw JSONL logs** published beside
  the harness — every number reproducible.
