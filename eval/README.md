# The examination — frozen eval set

Carson's headline numbers come from **one** benchmark, defined here, and the
methodology is the point: the test set is written *before* any planner
prompt exists, so the planner can never be tuned to its own exam.

## Status: DRAFT — not yet sealed

`frozen_set.draft.jsonl` was authored before Phase 2 (no planner prompt
exists at time of writing; see git history). Before sealing:

1. Collect **at least 15 utterances verbatim from 2–3 other people** (ask
   "how would you tell an assistant to _X_?" — do not show them the draft)
   and swap them in, keeping the expected outcomes.
2. Rename to `frozen_set.jsonl` and add `SEAL.md` recording the commit hash
   and date. After the seal commit, the file is never edited — fixes go in
   an errata section of the final report, not in the set.

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
