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
MAX_HOTWORDS = 40  # a short, speakable list; a long one hallucinates itself back

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


_cache: tuple | None = None  # ((path, mtime), parsed)


def load() -> dict:
    global _cache
    if not VOCAB_FILE.exists():
        return {"sites": {}}
    key = (str(VOCAB_FILE), VOCAB_FILE.stat().st_mtime)
    if _cache is not None and _cache[0] == key:
        return _cache[1]
    try:
        parsed = yaml.safe_load(VOCAB_FILE.read_text(encoding="utf-8")) or {"sites": {}}
    except Exception:
        parsed = {"sites": {}}
    _cache = (key, parsed)
    return parsed


# Words that betray a Start Menu entry nobody says out loud. Feeding these to
# whisper as hotwords is actively harmful: on silence or noise it hallucinates
# them back ("4 64 bit, idle python 3 14, imagemagick web"), so they are cut.
_NOISE_WORDS = frozenset(
    "documentation manual manuals docs tools tool verifier prompt uninstall "
    "readme sdk cmd gui cli x64 x86 wow bit edition release notes reference "
    "localization diagnostics initiator configuration management legacy "
    "preview installer kit samples sample".split())


def speakable(term: str) -> str | None:
    """A name a human would actually say, or None. Digits, version numbers and
    long technical strings are rejected — they poison the decoder."""
    cleaned = re.sub(r"[^a-z ]", " ", term.lower())  # digits out entirely
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()
    if not 1 <= len(words) <= 2:
        return None
    if any(len(w) < 2 for w in words) or any(w in _NOISE_WORDS for w in words):
        return None
    return cleaned if 3 <= len(cleaned) <= 20 else None


def _speakable_terms() -> list[str]:
    """Bookmarked site names first — those are what the master actually says."""
    terms, seen = list(load().get("sites", {})) + list(config.ALLOWED_APPS), []
    for term in terms:
        name = speakable(term)
        if name and name not in seen:
            seen.append(name)
    return seen


def hotwords() -> str:
    """A biasing string for whisper — curated and capped. A short list of names
    the master really says beats a long list of everything installed."""
    return ", ".join(_speakable_terms()[:MAX_HOTWORDS])


def _terms() -> list[str]:
    return _speakable_terms()


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

# Well-known destinations, so "open youtube" opens reliably and instantly
# without asking the small local model to remember a domain. The user's own
# bookmarks always take precedence over these.
_COMMON_SITES = {
    "youtube": "https://youtube.com", "github": "https://github.com",
    "google": "https://google.com", "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com", "drive": "https://drive.google.com",
    "reddit": "https://reddit.com", "twitter": "https://twitter.com",
    "x": "https://x.com", "facebook": "https://facebook.com",
    "instagram": "https://instagram.com", "linkedin": "https://linkedin.com",
    "netflix": "https://netflix.com", "spotify": "https://open.spotify.com",
    "twitch": "https://twitch.tv", "amazon": "https://amazon.com",
    "wikipedia": "https://wikipedia.org", "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com", "chatgpt": "https://chatgpt.com",
    "discord": "https://discord.com/app", "whatsapp": "https://web.whatsapp.com",
}


def site_lookup(utterance: str) -> str | None:
    """'open my portfolio' / 'open youtube' -> a URL. The user's bookmarks are
    tried first (their names win), then a table of well-known sites — both
    fuzzy, so a small mishear still lands."""
    said = re.sub(r"[^a-z0-9 ]", "", utterance.lower()).strip()
    match = _OPEN_VERBS.match(said)
    if not match:
        return None
    wanted = match.group(1).strip()
    sites = load().get("sites", {})
    hit = get_close_matches(wanted, list(sites), n=1, cutoff=0.8)
    if hit:
        return sites[hit[0]]
    if wanted in _COMMON_SITES:
        return _COMMON_SITES[wanted]
    near = get_close_matches(wanted, list(_COMMON_SITES), n=1, cutoff=0.85)
    return _COMMON_SITES[near[0]] if near else None
