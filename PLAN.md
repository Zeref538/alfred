# Alfred — A Proper Butler for Your PC

> A local agentic AI butler that lives on your machine: summon it by hotkey or
> voice, ask in plain language, and it opens your tabs, runs your searches,
> and adjusts your settings — governed by strict house rules enforced by
> deterministic code, so a misheard command is caught at the gate instead of
> acted upon.
>
> Theme: an impeccable British butler. Discreet, precise, asks before
> presuming, keeps a meticulous diary, and never touches what he wasn't
> invited to touch.
>
> **Slot: capstone, November–December 2026** (takes Ipon's slot; Ipon moves to
> backlog/2027 — revisit when Tipid ships). ~6 weeks part-time.

## The pitch

Everyone builds a "Jarvis" that is a voice loop glued to `webbrowser.open()`.
Alfred's differentiator is the part employers actually respect: **the safety
architecture for an agent with hands on a real computer.** The AI never gets
free control — it plans over a fixed menu of vetted actions, every argument is
validated before any adapter runs, big actions require consent, reversible
actions are undoable, and every act is written in the butler's book. YODA's
trust pattern (AI proposes, deterministic code executes, human gates,
everything audited), promoted from one dataset to the whole PC.

Headline demo: press the hotkey, say *"Alfred, set up my study session"* —
it opens the AI-102 guide, your notes repo, and a Pomodoro timer, mutes
notifications, and announces *"Very good, sir."* Then show the published
eval: exact counts of correct plans, wrong actions, and refused off-menu
asks, straight from the harness logs.

## House rules (the trust architecture)

1. **The service menu (action allowlist).** Alfred can only perform actions
   from a typed, versioned registry — `open_url`, `web_search`, `focus_app`,
   `launch_app`, `media_control`, `set_volume`, `toggle_do_not_disturb`,
   `open_file` (whitelisted folders), `clipboard_read/write`, `window_layout`,
   `settings_change` (whitelisted keys only). The LLM emits strict JSON
   picking from this menu; it can never emit raw keystrokes, mouse events, or
   shell commands. Unknown request → polite refusal + suggestion.
2. **The measure of every request (argument validation).** The menu constrains
   action *names*; a deterministic validator constrains the *arguments*, where
   the real danger lives. Every action has a typed pydantic schema with
   unknown fields forbidden, and per-action policy on top:
   - `open_url`: `http`/`https` schemes only — no `file:`, no `javascript:`.
   - `open_file`: path canonicalized first, then containment-checked against
     the whitelisted folders (no `..\` traversal).
   - `settings_change`: exact-match key allowlist **with typed value ranges**
     per key — an allowed key with an out-of-range value is still refused.
   - `clipboard_write`: snapshots the previous clipboard first, so even this
     is undoable.
   Off-menu action names and out-of-policy arguments are rejected by the
   validator before any adapter runs — enforced by an automated red-team
   suite that runs in CI, not by trusting the model.
3. **Etiquette tiers (consent model).**
   - **Tier 0 — at liberty:** read-only/reversible-instantly (open tab, search,
     focus window). Executes immediately.
   - **Tier 1 — announced:** state changes (volume, DND, window layout,
     launching apps). Shows a 2-second cancelable toast before acting.
   - **Tier 2 — by your leave:** settings changes, anything file-touching.
     Preview shown as a diff; explicit confirmation required; auto-revert
     snapshot taken first. In voice mode, confirmation is a spoken phrase —
     *"go ahead, Alfred"* — never a bare "yes," so a mishear can't confirm
     itself.
   - Multi-step plans gate at the **highest** tier present in the plan,
     before the first step executes.
   - Nothing in the registry is destructive (no delete, no install, no
     shutdown) in v1 — the tier table is published in the README.
4. **The butler's book (audit + undo).** Every action → JSONL entry (intent,
   transcript, action JSON, tier, planner prompt version, result, revert
   handle). Each registry entry declares `reversible: true/false`; every
   reversible action has a tested revert, and irreversible ones (a search
   already run, a phrase already spoken) are labeled as such and tier-gated
   accordingly — the README publishes the per-action undo table rather than
   claiming everything is undoable. `Ctrl+Alt+Z` or "Alfred, undo that"
   reverts the last reversible action. A "day's ledger" view lists everything
   he did. The book is append-only per day, transcripts are redactable, and
   entries expire after 30 days by default — or immediately on "Alfred, burn
   the day's page."
5. **The bell (kill switch).** Global hotkey and the wake-word "Alfred, stop"
   abort any in-flight plan. Defined semantics, not vibes: the executor
   checks the abort flag between plan steps, every adapter call runs under a
   timeout, already-executed steps remain in the ledger, and Alfred offers
   *"shall I put things back, sir?"* — a plan-level revert of the completed
   reversible steps.
6. **Discretion (privacy).** Wake word + STT + LLM all local (Whisper +
   Ollama). Audio never leaves the machine; no always-on cloud mic. Azure
   OpenAI is an optional per-request brain for complex plans — never for
   audio. And a strict data-flow rule for the planner: its prompt may contain
   only the user's command (typed or transcribed) and the static service
   menu — never clipboard contents, page titles, window titles, or file
   contents. In v1 the clipboard is something Alfred moves, never something
   Alfred reads aloud to the model; that is the prompt-injection boundary,
   stated as a rule rather than a hope.

## Non-goals (v1)

Scope discipline, in writing: no free-form shell, keyboard, or mouse control;
no file writes or deletes; no software installs; no cloud audio; no always-on
microphone by default (push-to-talk is the default, wake word is opt-in); no
autonomous or unattended operation — Alfred acts only on an explicit summons.

## Architecture

```
  hotkey (global)          voice (local Whisper, push-to-talk
      │                     or local wake word "Alfred")
      └───────┬─────────────┘
              ▼
   intent → plan
     ├─ routine matcher (exact/fuzzy match on known routines —
     │   no LLM round-trip for the common case)
     └─ local LLM planner (novel requests: schema-constrained JSON
         over the service menu; multi-step plans allowed)
              ▼
   validator (deterministic: action names + argument policy)
              ▼
   etiquette gate (tier check → toast / confirm / immediate)
              ▼
   executor (deterministic adapters, per-call timeouts, abort
   flag checked between steps):
     browser (Playwright/CDP profile) · apps & windows (pywinauto/Win32) ·
     system settings (whitelisted PowerShell/registry adapters w/ snapshots) ·
     media/volume (pycaw / OS APIs)
              ▼
   butler's book (JSONL) ── undo manager ── tray UI + minimal overlay HUD
     (HUD talks to the core over a local named pipe — no open localhost
      HTTP port with action-triggering endpoints; if HTTP is ever needed,
      it binds 127.0.0.1 with a per-session bearer token)
```

## Phases

### Phase 1 — Hands, no brain (weeks 1–2)
- [ ] Action registry schema (typed, versioned, `reversible` flag) + 10 core
      actions with deterministic adapters, each unit-tested and
      revert-capable where applicable.
- [ ] Validator with per-action argument policy + pytest suite of adversarial
      fixtures: traversal paths, `javascript:`/`file:` URLs, off-menu names,
      malformed and oversized JSON, out-of-range setting values.
- [ ] CI from day one: GitHub Actions on a Windows runner, adapters mocked.
- [ ] Global hotkey summon + text command palette (no voice yet).
- [ ] Butler's book (JSONL) + undo manager + tray icon.
- [ ] **Frozen eval set authored now** — before any prompt tuning — 50
      commands (clean + adversarial/ambiguous), with phrasings solicited from
      2–3 other people to limit author bias. Sealed until Phase 4.
- **Exit gate:** 10 actions scriptable from the palette, ledger records all,
      undo works for every reversible action, validator suite green in CI.

### Phase 2 — The brain (week 3)
- [ ] Local LLM planner: natural language → strict-JSON plan over the menu.
      Reliability by construction: JSON-schema-constrained decoding (Ollama
      structured outputs) as the primary path; parse → one bounded repair
      attempt → deterministic refusal as the fallback; temperature 0; planner
      prompt versioned, version recorded in every ledger entry.
- [ ] Routine matcher fast path: known routines ("study session") execute
      with no LLM round-trip; the LLM handles novel requests only.
      User-defined routines in a YAML "house customs" file.
- [ ] Etiquette gate: tier enforcement (highest-tier gating for multi-step
      plans) + toasts + confirm dialogs.
- [ ] Red-team set wired into CI as a permanent regression suite.
- **Exit gate:** 25-command **dev smoke set** (distinct from the frozen eval)
      ≥ 90% correct plans; 0 off-menu executions across the red-team suite.

### Phase 3 — The voice (week 4)
- [ ] Push-to-talk voice via local Whisper (small/int8, CPU); optional local
      wake word (openWakeWord).
- [ ] Spoken confirmations/responses (local TTS, butler persona, brief);
      Tier-2 spoken confirm requires the explicit phrase, per house rule 3.
- [ ] Kill switch: hotkey + "Alfred, stop," with the defined abort semantics.
- **Exit gate:** voice-to-action median latency < 2.5s on my laptop for
      routine-matched and Tier-0 commands; LLM-path latency measured and
      reported (not promised).

### Phase 4 — Proof (weeks 5–6)
- [ ] **The eval, published:** unseal the frozen 50-command set. N=3 voice
      trials per command. Metrics: task success · wrong-action rate (the
      false-fix twin) · refusal correctness on off-menu asks · median latency
      per path · undo coverage · mishear-to-wrong-action conversion. The
      harness, raw JSONL results, and hardware spec ship in the repo — every
      number reproducible. Results reported as **counts, not just
      percentages**: "0 off-menu executions in 150 adversarial trials;
      47/50 correct plans" says more than a headline rate a single error
      could move by two points.
- [ ] **THREATMODEL.md** (one page): assets, trust-boundary diagram, attacker
      capabilities (mishearing, clipboard-borne injection, a hostile web page
      probing the local HUD), and the mitigation table mapping each to a
      house rule.
- [ ] Red-team section in README: prompt-injection attempts, mishearing
      tests, and how the validator + tiers contained each — backed by the CI
      suite, not a one-time anecdote.
- [ ] Polish: minimal overlay HUD, demo video, portfolio card (count-based
      framing from the eval), RAG index update.
- **Stretch (only if ahead):** per-app volume.

## Success criteria

| outcome | bar |
|---|---|
| Minimum ship | hotkey+text palette, 10 actions, validator + tiers, ledger, undo, CI red-team suite, eval published with harness |
| Good | + local voice loop under 2.5s on the fast path, routines, 0 off-menu executions across all recorded trials |
| Headline | + full demo video, THREATMODEL.md, and a clean eval report an interviewer can rerun |

## Risks

- **Scope explosion (the Jarvis graveyard)** → the service menu is the scope.
  New capabilities = new registry entries, nothing else. v1 menu is frozen at
  ~12 actions; palm-gesture stop and a "morning briefing" routine are
  explicitly parked beyond v1 to pay for the guardrail work.
- **Windows API fiddliness** → adapter risk is graded up front:
  `toggle_do_not_disturb` (Focus Assist has no clean public API) and UWP
  `settings_change` keys are marked **at-risk**, with named fallbacks (DND →
  mute + suppress toasts via a stable registry key). Prefer stable adapters
  (CDP for browser, pycaw for audio); drop any adapter that can't be made
  reliable rather than shipping flaky — and say so in the README instead of
  silently shrinking the menu.
- **Argument-level attacks** → the allowlist alone doesn't help if
  `open_url` will take `file://` or `open_file` will take `..\` — hence the
  validator (house rule 2) and its adversarial fixture suite in CI.
- **STT mishears** → that's what the tiers and the explicit spoken-confirm
  phrase are for; the eval measures mishear-to-wrong-action conversion and
  shows the gate catching them.
- **Wake-word false triggers** → default to push-to-talk; wake word opt-in.
- **Prompt injection** → bounded by the data-flow rule in house rule 6: the
  planner never sees page text, titles, clipboard, or file contents in v1 —
  commands and menu only. Documented explicitly, tested in the red-team
  suite.
- **Local HUD as attack surface** → no unauthenticated localhost endpoint may
  trigger actions, ever; IPC over a named pipe by default (see Architecture).
- **Latency vs. local models** → the routine-matcher fast path keeps common
  commands off the LLM entirely; the < 2.5s promise applies to that path,
  and LLM-path latency is reported honestly from the eval.

## Stack

Python · faster-whisper · openWakeWord · Piper/Windows TTS · Ollama with a
small local instruct model (qwen3.5 family — 0.8b/2b/4b pulled locally;
final pick benchmarked on this laptop at build time) + optional Azure OpenAI ·
Playwright/CDP · pywinauto + Win32 · pycaw (Core Audio) · named-pipe IPC for
the HUD · pystray · pydantic · JSONL ledger · pytest + GitHub Actions.
