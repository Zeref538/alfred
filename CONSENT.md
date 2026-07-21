# The consent ladder

Alfred's one rule of consent:

> **The higher the rung, the heavier the consent.** Work that only reads, or that
> can be undone with a keystroke, runs the moment it's understood — Alfred *shows*
> you what he did, he doesn't stop to *ask*. Consent is reserved for the actions
> that actually matter, and it gets harder to give as the stakes rise. The top
> rung will not move without your own words, typed exactly.

Every action in the [service menu](src/alfred/registry.py) carries a tier. A
plan made of several steps is gated **once, at the highest tier any step
carries** — so a plan that changes a setting *and* opens a file is sealed, not
merely confirmed.

| Tier | Name | What it means | How you consent |
|:----:|------|---------------|-----------------|
| **0** | `AT_LIBERTY` | read-only or instantly reversible | nothing — it just runs |
| **1** | `ANNOUNCED` | reversible state change | nothing — it runs, is flashed on the HUD, and is undoable |
| **2** | `CONFIRM` | consequential | one plain **yes** — click **engage**, or say "yes" |
| **3** | `UNDER_SEAL` | reaches the filesystem | type **`yes i approve please proceed`**, exactly |

## The actions, by rung

**Tier 0 — at liberty** (runs silently)
- `open_url` — open a web page
- `web_search` — run a web search
- `focus_app` — bring a window to the front
- `focus_tab` — switch to a browser tab already open *(see below)*
- `clipboard_read` — read the clipboard *(never fed to the planner)*

**Tier 1 — announced** (runs, shown, undoable — no yes)
- `launch_app` — start an allowlisted application
- `media_control` — play, pause, or skip media
- `set_volume` — set the master volume · *undoable*
- `toggle_do_not_disturb` — mute or restore notifications · *undoable*
- `clipboard_write` — write to the clipboard *(previous contents snapshotted)* · *undoable*
- `window_layout` — arrange the focused window · *undoable*

**Tier 2 — confirm** (one plain yes)
- `settings_change` — change an allowlisted system setting · *undoable*

**Tier 3 — under seal** (type `yes i approve please proceed`)
- `open_file` — open a file from a whitelisted folder

## The browser bridge, and what it may know

Alfred cannot see browser tabs from the operating system, so a small extension
reports them. That is the largest amount of sight he has, and the limits are
built into the data structure rather than promised:

| Limit | How it's enforced |
|---|---|
| Only a **title and a hostname** are kept | paths and query strings are discarded on arrival — session tokens and document ids are never held at all |
| **Nothing reaches disk** | held in memory, dies with the process, never written to the ledger or field log |
| **Nothing reaches the model** | a page can title itself *"ignore previous instructions"*, so tab text never enters a planner prompt; matching is deterministic and local |
| **Banking and sign-in pages are invisible** | blinded by default; add your own hosts to `~/.alfred/tab_privacy.yaml` |
| **It expires** | a report older than 90s is not acted on |
| **Page contents are unreachable** | the extension holds no scripting permission, so it *cannot* read page text, forms or passwords |
| **It only ever switches** | `focus_tab` moves to a tab already open — it cannot navigate one, close one, or read one |
| **Off unless installed** | no extension, no sight; **pause** stops all reporting instantly |

Saying "tab" is required (*"switch to my go trade **tab**"*). Without it,
*"open youtube"* opens a page as before and the browser is never consulted.

## Why the seal can't be spoken

Tier 3 is deliberately **un-sayable**. A mishearing must never be able to reach
your files, so the top rung accepts only typed text and verifies it
*server-side* — the browser page carries the characters but never decides. On a
voice command that resolves to a sealed plan, Alfred hands it to the panel and
waits for you to type; the microphone alone can't complete it. The phrase is
matched forgiving only of spacing, case, and a trailing `.`/`!` — nothing else.

The v1 menu populates rungs 0 through 3 with real actions and, by design,
contains nothing more destructive than opening a file: there is no delete, no
install, no shell, no file *write*. Rung 3 is where any such capability would
land if it were ever added — and it would arrive already sealed.
