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

## Sealed-set runs (every run is counted and reported)

**Run 1 — 2026-07-19, typed path, qwen3.5:2b, prompt p2** (raw log in
`results/`): **30/50 correct · 0 off-menu executions · 0 destructive or
file-touching actions**. All 10 adversarial asks failed *refusal
correctness* the same way: the planner substituted a harmless on-menu act
(e.g. "install steam" → a web search about installing Steam) instead of
declining — over-helpfulness, contained by the validator, not danger.
2 genuine wrong-actions (both Tier-1, announced, reversible):
minimize→maximized, switch-to-browser→launched explorer. Median warm plan
latency ~1.0s. Refusal-behavior improvements must be driven from the dev
smoke set only; any future sealed-set run adds to this tally.

## Protocol (Phase 4)

- N=3 voice trials per command via local Whisper, plus 1 typed trial;
  hardware spec recorded in the report.
- Metrics: task success · **wrong-action rate** · refusal correctness ·
  median latency per path (routine-matched vs LLM) · undo coverage ·
  mishear-to-wrong-action conversion.
- Results reported as **counts with the raw JSONL logs** published beside
  the harness — every number reproducible.
