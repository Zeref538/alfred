# The seal

`frozen_set.jsonl` is sealed as of 2026-07-19. From this commit onward the
file is never edited; corrections go in an errata section of the final
report, not in the set.

**What the seal certifies**

- All 50 utterances were authored **before any planner prompt existed**:
  the set landed in PR #6, the first planner prompt in PR #9, and all prompt
  tuning (p1 → p2) used only the separate dev smoke set — verifiable from
  git history.

**Stated limitation, honestly**

- The protocol called for ≥15 utterances collected verbatim from 2–3 other
  people before sealing. Those were **not collected** — every phrasing is
  the project author's. Results from this set therefore carry a
  **single-author phrasing-bias caveat**, and that caveat must appear
  wherever its numbers are reported. The anti-tuning guarantee above is
  unaffected.

**Seal commit:** recorded in the follow-up commit note (the hash cannot
name itself); confirm with `git log --follow eval/frozen_set.jsonl`.
