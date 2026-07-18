"""The household vocabulary: names Alfred should recognise on first hearing.

`alfred learn` sweeps two local sources — the registered apps and the
browser's bookmarks (Chromium format: Chrome, Edge, Opera/GX, Brave) — into
~/.alfred/vocabulary.yaml. The names then serve two purposes:

- whisper *hotwords*: transcription is biased toward words you actually
  say, which is the honest fix for "spotify" becoming "spot if I"
- a deterministic "open <bookmark name>" fast path: a known site opens
  without an LLM round-trip, and still through the validator

Everything stays on the machine. Nothing here ever enters a planner prompt
except the user's own (possibly corrected) utterance — the data-flow rule
holds.
"""

import json
import os
import re
from difflib import get_close_matches
from pathlib import Path

import yaml

from . import config

VOCAB_FILE = config.DATA_DIR / "vocabulary.yaml"
MAX_HOTWORDS = 100

_CHROMIUM_BOOKMARK_FILES = [
    r"Google\Chrome\User Data\Default\Bookmarks",
    r"Microsoft\Edge\User Data\Default\Bookmarks",
    r"BraveSoftware\Brave-Browser\User Data\Default\Bookmarks",
]
_OPERA_BOOKMARK_FILES = [
    r"Opera Software\Opera GX Stable\Bookmarks",
    r"Opera Software\Opera Stable\Bookmarks",
]


def bookmark_files() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming = Path(os.environ.get("APPDATA", ""))
    candidates = [local / rel for rel in _CHROMIUM_BOOKMARK_FILES]
    candidates += [roaming / rel for rel in _OPERA_BOOKMARK_FILES]
    return [p for p in candidates if p.is_file()]


def read_bookmarks(path: Path) -> dict[str, str]:
    """name -> url from one Chromium-format bookmarks file."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    found: dict[str, str] = {}

    def walk(node: dict) -> None:
        if node.get("type") == "url":
            name = str(node.get("name", "")).strip().lower()
            url = str(node.get("url", ""))
            if name and url.startswith(("http://", "https://")):
                found.setdefault(name, url)
        for child in node.get("children", []):
            walk(child)

    for root in (doc.get("roots") or {}).values():
        if isinstance(root, dict):
            walk(root)
    return found


def build_vocabulary() -> dict:
    sites: dict[str, str] = {}
    for path in bookmark_files():
        sites.update(read_bookmarks(path))
    vocabulary = {"sites": sites}
    VOCAB_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOCAB_FILE.write_text(yaml.safe_dump(vocabulary, sort_keys=True,
                                         allow_unicode=True), encoding="utf-8")
    return vocabulary


def load() -> dict:
    if not VOCAB_FILE.exists():
        return {"sites": {}}
    try:
        return yaml.safe_load(VOCAB_FILE.read_text(encoding="utf-8")) or {"sites": {}}
    except Exception:
        return {"sites": {}}


def hotwords() -> str:
    """A biasing string for whisper: app names + bookmark names, capped."""
    terms = list(config.ALLOWED_APPS) + list(load().get("sites", {}))
    seen: list[str] = []
    for term in terms:
        cleaned = re.sub(r"[^a-z0-9 ]", " ", term.lower()).strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
        if len(seen) >= MAX_HOTWORDS:
            break
    return ", ".join(seen)


def _terms() -> list[str]:
    cleaned = []
    for term in list(config.ALLOWED_APPS) + list(load().get("sites", {})):
        term = re.sub(r"[^a-z0-9 ]", " ", term.lower()).strip()
        if 3 <= len(term) <= 30:
            cleaned.append(term)
    return cleaned


def correct(utterance: str) -> str:
    """Deterministic mishear repair: sliding word-windows fuzzy-matched
    against the household vocabulary ('spot if i' → 'spotify'). No model,
    no surprises — only known names are ever substituted."""
    from difflib import SequenceMatcher
    words = utterance.split()
    terms = _terms()
    if not terms:
        return utterance
    for size in (1, 2, 3):  # smallest windows first, so command words survive
        for start in range(len(words) - size + 1):
            window = " ".join(words[start:start + size])
            cleaned = re.sub(r"[^a-z0-9 ]", "", window.lower()).strip()
            squashed = cleaned.replace(" ", "")
            if len(squashed) < 4:
                continue
            for term in terms:
                score = max(SequenceMatcher(None, cleaned, term).ratio(),
                            SequenceMatcher(None, squashed, term.replace(" ", "")).ratio())
                if score >= 0.82 and term not in cleaned:
                    return correct(" ".join(words[:start] + [term] + words[start + size:]))
    return utterance


_OPEN_VERBS = re.compile(r"^(?:open|go to|visit|show me|take me to)\s+(?:the\s+)?(.+)$")


def site_lookup(utterance: str) -> str | None:
    """'open my portfolio' -> the bookmarked URL, if the name is close enough."""
    said = re.sub(r"[^a-z0-9 ]", "", utterance.lower()).strip()
    match = _OPEN_VERBS.match(said)
    if not match:
        return None
    wanted = match.group(1).strip()
    sites = load().get("sites", {})
    hit = get_close_matches(wanted, list(sites), n=1, cutoff=0.8)
    return sites[hit[0]] if hit else None
