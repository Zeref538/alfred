# Alfred — threat model

One page: what's at stake, where the trust boundaries sit, what an attacker
(or an accident) can try, and which house rule stops it. Every mitigation
here is enforced in code and covered by tests that run in CI.

## Assets

- The PC itself: files, settings, running applications.
- The user's attention and audio environment (volume, notifications).
- The butler's book: transcripts of what the user said (private by design).

## Trust boundaries

```
 UNTRUSTED                                 │  TRUSTED (deterministic)
                                           │
 user speech ──► whisper transcript ───────┼─► validator ─► gate ─► executor ─► adapters
 typed text ───────────────────────────────┤      ▲
 LLM output (plan JSON) ───────────────────┤      │ the ONLY door
 customs.yaml (user-authored routines) ────┤      │
 clipboard contents (read as data only) ───┘      │
```

Everything on the left is data, never instructions to the trusted side.
There is exactly one door: `validate_plan()`. No adapter is reachable except
through it, and the etiquette gate sits behind it.

## Attacker capabilities and mitigations

| # | Threat | Example | Stopped by |
|---|---|---|---|
| 1 | **Mishearing** — STT turns speech into a different command | "set volume to eleventy" | Typed argument ranges (house rule 2); tiered consent — state changes are announced, settings need an explicit yes (rule 3); everything ledgered and reversible acts undoable (rule 4) |
| 2 | **LLM misplanning** — the model invents an action or argument | `run_shell`, `file:///…/SAM`, volume 200 | Structured decoding constrains action names to the registry enum; the validator rejects off-menu names and out-of-policy arguments before any adapter runs — 30+ adversarial fixtures in CI |
| 3 | **Prompt injection via ambient data** — hostile text in clipboard/titles/pages steers the planner | clipboard contains "ignore previous instructions…" | Data-flow rule (rule 6): the planner prompt contains only the utterance and the static menu. `clipboard_read` output goes to the user, never into a prompt. Tested: prompt messages are exactly `[system, user]` |
| 4 | **Malicious/buggy house customs** — a user-authored routine smuggles an action | `customs.yaml` routine with `run_shell` | Matched routines re-enter through the validator like any other plan (tested: the evil routine dies at the gate) |
| 5 | **Path/URL smuggling** — traversal or scheme abuse inside valid actions | `..\..\Windows\System32`, `javascript:` | Resolve-then-contain path policy; http(s)-with-host-only URL policy; exact-match allowlists with typed values |
| 6 | **Local attack surface** — a web page probes a local control port | classic localhost-CSRF | No listening socket exists. Summon is a hotkey; the tray is in-process. If an HTTP HUD is ever added: 127.0.0.1 + per-session token, no unauthenticated action endpoints (PLAN.md commitment) |
| 7 | **Runaway plan** — a multi-step plan mid-flight after a mistake | wrong routine triggered | The bell: hotkey / "Alfred, stop" sets an abort flag checked between steps; adapters run under timeouts; completed reversible steps offer "shall I put things back" via undo |
| 8 | **Ledger as liability** — transcripts accumulate forever | private utterances on disk | Pages expire after 30 days; "burn the day's page" purges immediately; the book is local JSONL, never transmitted |

## Non-capabilities (by construction, v1)

No shell, no keystrokes/mouse synthesis to arbitrary apps, no file writes or
deletes, no installs, no process kill, no shutdown, no network calls except
opening the user's browser and the local Ollama socket, no cloud audio, no
always-on microphone (push-to-talk only), no autonomous operation.

## Residual risks, stated honestly

- A Tier-0 mishear can still open a wrong (validated, http/https) URL or run
  a wrong search — bounded nuisance, visible in the ledger.
- The registry allowlist is the security perimeter; a careless future
  registry entry (e.g. an over-broad `settings_change` key) widens it. That
  is why the menu is frozen for v1 and every entry carries its own argument
  policy and tests.
- SAPI TTS and whisper run as the user; a compromised *machine* is out of
  scope — Alfred defends against a confused butler, not a rooted house.
