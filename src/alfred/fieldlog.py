"""The field log: what actually happened when you tested Alfred out loud.

Every spoken turn is appended to ~/.alfred/fieldlog.jsonl — the raw transcript,
what the corrector took it as, and how it ended (a plan, a refusal, an error, an
empty hearing, the bell, mute, undo). It exists so real mishears and failures
are *captured* rather than lost, and can be reviewed and fortified against later:

    alfred fieldlog          the recent turns, worst-first hints
    alfred fieldlog clear     wipe the log and start a fresh testing run

This is a diagnostic side-channel, not the butler's book — it never gates or
drives an action, and it holds only your own words, never page or file contents.
"""

import datetime
import json

from . import config

FIELDLOG_FILE = config.DATA_DIR / "fieldlog.jsonl"

# outcomes worth a second look when reviewing a testing run
WEAK = {"empty", "refusal", "error", "mishear"}


def record(**fields) -> None:
    """Append one turn. Best-effort — logging must never break a command."""
    try:
        FIELDLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **fields}
        with FIELDLOG_FILE.open("a", encoding="utf-8") as page:
            page.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read() -> list[dict]:
    if not FIELDLOG_FILE.exists():
        return []
    entries = []
    for line in FIELDLOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def clear() -> None:
    FIELDLOG_FILE.unlink(missing_ok=True)


def summary() -> str:
    """A short readout: totals, the weak turns, and the mishears (raw != heard)."""
    entries = read()
    if not entries:
        return "The field log is empty, sir — nothing tested yet."
    weak = [e for e in entries if e.get("outcome") in WEAK]
    mishears = [e for e in entries
                if e.get("corrected") and e.get("raw") != e.get("corrected")]
    lines = [f"{len(entries)} turns logged · {len(weak)} weak · {len(mishears)} corrected mishears"]
    for e in entries[-20:]:
        raw = e.get("raw", "")
        heard = e.get("corrected")
        shown = f'"{raw}"' + (f' -> "{heard}"' if heard and heard != raw else "")
        detail = f" — {e['detail']}" if e.get("detail") else ""
        lines.append(f"  [{e.get('outcome', '?'):<8}] {shown}{detail}")
    return "\n".join(lines)
