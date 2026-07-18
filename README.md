# Carson — A Proper Butler for Your PC

A local agentic AI butler for Windows: summon it by hotkey or voice, ask in
plain language, and it opens your tabs, runs your searches, and adjusts your
settings — governed by strict house rules enforced by deterministic code, so a
misheard command is caught at the gate instead of acted upon.

**Status: Phase 1 — hands, no brain.** Typed action registry, argument
validator, ledger, undo, and a text command palette. No LLM or voice yet.

## The trust architecture

The AI never gets free control:

1. **Service menu** — actions come from a typed, versioned registry; the
   planner emits strict JSON over that menu, never keystrokes or shell.
2. **Argument validation** — a deterministic validator checks every argument
   against per-action policy (URL schemes, path containment, typed value
   ranges) before any adapter runs.
3. **Etiquette tiers** — read-only acts run at liberty; state changes are
   announced; settings and files require explicit consent.
4. **Butler's book** — every act is written to an append-only JSONL ledger
   with a revert handle; reversible actions are undoable.
5. **The bell** — a kill switch aborts any in-flight plan between steps.

See [PLAN.md](PLAN.md) for the full design, tier table, and roadmap.

## Using the palette

```
carson menu                  the service menu (12 actions, tiers, undoability)
carson act web_search query="AI-102 study guide"
carson plan @routine.json    a multi-step JSON plan
carson ledger | carson burn  read or burn the day's page
carson summon                Ctrl+Alt+C anywhere opens the palette
carson tray                  tray icon (pip install -e .[ui])
carson                       REPL, with in-session undo
```

## Development

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m pytest
```
