# Alfred — A Proper Butler for Your PC

A local agentic AI butler for Windows: summon it by hotkey or voice, ask in
plain language, and it opens your tabs, runs your searches, and adjusts your
settings — governed by strict house rules enforced by deterministic code, so a
misheard command is caught at the gate instead of acted upon.

**Status:** Phases 1–3 built — hands (validated adapters), brain (local LLM
planner), and voice (local whisper + SAPI). The sealed 50-command evaluation
(Phase 4) is pending; numbers below are from the *development* smoke set and
say so.

<!-- demo: drop a short screen recording (`alfred web`, ask it something,
     show a gate firing) in as `docs/demo.gif` and swap the line below for
     `![Alfred demo](docs/demo.gif)` -->

## The trust architecture

The AI never gets free control. There is exactly one door between anything
untrusted (speech, typed text, LLM output, user-authored routines) and the
machine: a deterministic validator, with a consent gate behind it.

1. **Service menu** — actions come from a typed, versioned registry; the
   planner emits strict JSON over that menu, never keystrokes or shell.
2. **Argument validation** — per-action policy before any adapter runs:
   http(s)-only URLs, resolve-then-contain file paths, exact-match app and
   settings allowlists with typed value ranges.
3. **Etiquette tiers** — read-only acts run at liberty; state changes are
   announced; settings and files require explicit consent. Multi-step plans
   gate once, at their highest tier, before anything executes.
4. **Butler's book** — every act in an append-only daily JSONL ledger with
   tier, arguments, result, and planner prompt version. Pages expire after
   30 days; "burn the day's page" purges immediately.
5. **The bell** — hotkey or "Alfred, stop": an abort flag checked between
   steps, adapter timeouts, and an offer to put reversible steps back.

Full analysis in [THREATMODEL.md](THREATMODEL.md); design and roadmap in
[PLAN.md](PLAN.md).

## The service menu (v1 — frozen at 12 actions)

| action | tier | undoable | notes |
|---|---|---|---|
| `open_url` | 0 | — | http/https with a host, nothing else |
| `web_search` | 0 | — | single-line query, length-capped |
| `focus_app` | 0 | — | window title substring |
| `clipboard_read` | 0 | — | shown to the user, never fed to the planner |
| `launch_app` | 1 | — | exact-match app allowlist, no shell |
| `media_control` | 1 | — | play_pause / next / previous / stop |
| `set_volume` | 1 | ✓ | 0–100; previous level snapshotted |
| `toggle_do_not_disturb` | 1 | ✓ | parked as at-risk: refuses honestly for now |
| `clipboard_write` | 1 | ✓ | previous contents snapshotted first |
| `window_layout` | 1 | ✓ | previous rect snapshotted |
| `open_file` | 2 | — | resolve-then-contain against whitelisted folders |
| `settings_change` | 2 | ✓ | exact keys with typed values; registry snapshot |

Tier 0 = at liberty · Tier 1 = announced (cancelable) · Tier 2 = by your
leave (explicit consent).

## Using Alfred

```
alfred web                   local web HUD — text · mic · bell · motion toggle
alfred hud                   Tkinter overlay (no extras, no sockets)
alfred menu                  the service menu
alfred ask silence the notifications
alfred act set_volume level=30
alfred plan @routine.json    a multi-step JSON plan
alfred voice                 push-to-talk loop ([voice] extra)
alfred summon                Ctrl+Alt+C anywhere opens the web HUD (ALFRED_UI=hud
                             for the Tkinter one)
alfred tray                  tray icon ([ui] extra)
alfred ledger | alfred burn  read or burn the day's page
alfred                       REPL, with in-session undo
```

Four ways in, one door out: **text** (any UI), **audio** (mic button or
`alfred voice` — local whisper), **hotkey** (global summon), **motion**
(opt-in webcam *stop bell*, `[motion]` extra — movement can only abort,
never command). Everything reaches the machine through the same
validator → gate → executor path. The web HUD binds 127.0.0.1 with a
per-session token and a Host check; see THREATMODEL.md row 6.

`ask` matches your routines and modes first (`~/.alfred/customs.yaml` —
work/school/investment modes ship as defaults), then bookmarked sites
("open github"), then a local model via Ollama — structured outputs,
temperature 0, one repair attempt, a polite refusal for anything off-menu,
and a 30-minute keep-alive so the model stays warm.

**Voice flow, guarded:** speak → whisper (biased toward your app and
bookmark names via `alfred learn`) → a two-layer mishear corrector (fuzzy
vocabulary repair, then the LLM with a never-change-numbers rule) → Alfred
*shows and speaks the exact plan* → nothing runs until your spoken yes.

**Settings** live in the web HUD's ⚙ page (`/settings`) and persist to
`~/.alfred/settings.yaml`: voice pace, Alfred's own volume, whisper model
(default `small`), planner model, search engine, plus the routines/modes
editor and rescan buttons. Environment variables (`ALFRED_MODEL`,
`ALFRED_WHISPER`, `ALFRED_VOICE_PACE`, …) always win over the file.

**The voice.** Alfred speaks with a local British Piper voice when one is
installed (one-time, ~60 MB, fully offline):

```
pip install -e .[voice]
python -m piper.download_voices en_GB-alan-medium --data-dir %USERPROFILE%\.alfred\voices
```

Falls back to Windows SAPI otherwise. `ALFRED_PIPER_VOICE` picks a
different Piper voice; `ALFRED_TTS=sapi` forces the fallback.

## Numbers so far (dev smoke set — not the sealed eval)

From `eval/results/`, reproducible via `python -m alfred.harness
eval/dev_smoke.jsonl` (qwen3.5:2b, this repo's grading rules):

- prompt p1: 12/25 correct, 0 off-menu — failure log committed
- prompt p2: **25/25 correct, 0 off-menu**, ~1s median warm plan latency
- voice loopback (TTS→WAV→whisper): STT 0.8s + plan 0–1s warm

The 50-command eval set was frozen in draft *before* any prompt existed and
stays untouched until it is sealed with phrasings from other people
(`eval/README.md` has the protocol). Headline numbers come only from that.

## Development

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]          # +[ui,media,voice] as needed
.venv\Scripts\python -m pytest                          # 102 tests; adapters mocked in CI
```
