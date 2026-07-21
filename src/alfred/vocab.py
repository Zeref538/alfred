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
SHORTCUTS_FILE = config.DATA_DIR / "shortcuts.yaml"  # the master's own, never rescanned
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
    terms = (list(load_shortcuts()) + list(load().get("sites", {}))
             + list(config.ALLOWED_APPS))
    seen = []
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


MAX_REPAIRS = 3


def _one_repair(text: str, terms: list[str]) -> str | None:
    from difflib import SequenceMatcher
    words = text.split()
    whole = re.sub(r"[^a-z0-9 ]", "", text.lower())
    for size in (1, 2, 3):  # smallest windows first, so command words survive
        for start in range(len(words) - size + 1):
            window = " ".join(words[start:start + size])
            cleaned = re.sub(r"[^a-z0-9 ]", "", window.lower()).strip()
            squashed = cleaned.replace(" ", "")
            if len(squashed) < 4:
                continue
            for term in terms:
                if term in whole:
                    continue  # already said — never insert it a second time
                score = max(SequenceMatcher(None, cleaned, term).ratio(),
                            SequenceMatcher(None, squashed, term.replace(" ", "")).ratio())
                if score >= 0.82:
                    return " ".join(words[:start] + [term] + words[start + size:])
    return None


def correct(utterance: str) -> str:
    """Deterministic mishear repair: sliding word-windows fuzzy-matched against
    the household vocabulary ('spot if i' -> 'spotify'). Only known names are
    ever substituted.

    This ran away once, spectacularly. The old guard asked whether the term was
    in the *window*, so with a shortcut named "go trade", the word "trade"
    fuzzy-matched it, became "go go trade", matched again, and recursed into
    "open go go go go ..." forever. Three defences now: a term already present
    anywhere in the sentence is never re-inserted, repairs are capped, and a
    repair may never balloon the sentence.
    """
    terms = _terms()
    if not terms:
        return utterance
    text, original = utterance, len(utterance.split())
    for _ in range(MAX_REPAIRS):
        repaired = _one_repair(text, terms)
        if repaired is None or repaired == text:
            break
        if len(repaired.split()) > original + 1:
            break
        text = repaired
    return text


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
    # streaming — named constantly, and worth knowing without being taught
    "disney plus": "https://www.disneyplus.com", "disneyplus": "https://www.disneyplus.com",
    "disney": "https://www.disneyplus.com", "hbo max": "https://www.max.com",
    "max": "https://www.max.com", "crunchyroll": "https://www.crunchyroll.com",
    "prime video": "https://www.primevideo.com", "primevideo": "https://www.primevideo.com",
    "hulu": "https://www.hulu.com", "soundcloud": "https://soundcloud.com",
    "apple music": "https://music.apple.com", "tiktok": "https://www.tiktok.com",
    "chess": "https://www.chess.com", "pinterest": "https://www.pinterest.com",
}


_SPOKEN_DOMAIN = re.compile(
    r"\b([a-z0-9][a-z0-9-]{1,30})\s*(?:\.|\bdot\b)\s*"
    r"(com|net|org|io|gg|tv|co|dev|ph|uk)\b")
_PATH_FILLER = re.compile(r"^(?:and|then|the|a|an)\s+")


def known_hosts() -> dict[str, str]:
    """Hosts we can vouch for: the master's shortcuts, his bookmarks, and the
    well-known table. Nothing else is a place we are willing to send him."""
    from urllib.parse import urlsplit
    hosts: dict[str, str] = {}
    for url in (list(load_shortcuts().values())
                + list(load().get("sites", {}).values())
                + list(_COMMON_SITES.values())):
        host = urlsplit(url).netloc.lower().removeprefix("www.")
        if host:
            hosts.setdefault(host, url)
    return hosts


def url_lookup(utterance: str) -> str | None:
    """'open chess.com slash daily puzzles' -> https://chess.com/daily-puzzles,
    but ONLY for a host we already know.

    Speech is not a reliable way to spell a domain. "chess" came through as
    "chest", and happily opening https://chest.com sent the master to a
    squatter's page — a mishearing became a navigation to an attacker-friendly
    address. So a spoken domain must match something we can vouch for; anything
    else falls through to a search, where the engine's own spelling correction
    is far better at this than we are.
    """
    said = re.sub(r"[^a-z0-9 .-]", " ", utterance.lower())
    said = re.sub(r"\s+", " ", said)
    match = _SPOKEN_DOMAIN.search(said)
    if not match:
        return None
    host = f"{match.group(1)}.{match.group(2)}"
    known = known_hosts()
    if host not in known:
        near = get_close_matches(host, list(known), n=1, cutoff=0.82)
        if not near:
            return None  # never fabricate a destination out of a mishearing
        host = near[0]
    rest = said[match.end():]
    # "slash daily puzzles" -> /daily-puzzles ; a slug, joined as one usually is
    slashed = re.split(r"\bslash\b|/", rest, maxsplit=1)
    if len(slashed) > 1:
        tail = _PATH_FILLER.sub("", slashed[1].strip())
        words = [w for w in re.split(r"[ .]+", tail) if w]
        if words:
            return f"https://{host}/" + "-".join(words)
    return known[host]  # no path spoken — his own entry, path and all


_PLAY = re.compile(r"\bplay\b(.+)")
# Longest names first, so "disney plus" wins before "disney". Each lands on the
# service's OWN search, which is what "play X on Y" actually means — a web
# search for the title is not the same thing at all.
_PLAY_SERVICES = {
    "disney plus": "https://www.disneyplus.com/search?q={}",
    "prime video": "https://www.primevideo.com/search/?phrase={}",
    "apple music": "https://music.apple.com/search?term={}",
    "crunchyroll": "https://www.crunchyroll.com/search?q={}",
    "soundcloud": "https://soundcloud.com/search?q={}",
    "disneyplus": "https://www.disneyplus.com/search?q={}",
    "primevideo": "https://www.primevideo.com/search/?phrase={}",
    "netflix": "https://www.netflix.com/search?q={}",
    "spotify": "https://open.spotify.com/search/{}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "twitch": "https://www.twitch.tv/search?term={}",
    "disney": "https://www.disneyplus.com/search?q={}",
    "hulu": "https://www.hulu.com/search?q={}",
    "max": "https://www.max.com/search?q={}",
}
# "the", "in" and "on" stay: titles are full of them ("Malcolm in the Middle",
# "Attack on Titan"). Only the "on <service>" tail is stripped, and separately.
_PLAY_FILLER = re.compile(
    r"\b(a|an|some|any|song|songs|music|track|tracks|video|videos|episode|"
    r"show|movie|playlist|please)\b")


def play_lookup(utterance: str) -> str | None:
    """'open spotify and play a post malone song' -> a Spotify search URL.

    The small local model kept inventing a query the master never said; naming
    a service and something to play is common and exact enough to resolve
    deterministically instead."""
    said = utterance.lower()
    service = next((s for s in _PLAY_SERVICES if s in said), None)
    if service is None:
        return None
    match = _PLAY.search(said)
    if not match:
        return None
    # cut the "... on <service>" tail first, so an "on" inside a title survives
    subject = re.sub(rf"\b(?:on|in|at|with|using)?\s*{re.escape(service)}\b.*$",
                     " ", match.group(1))
    subject = _PLAY_FILLER.sub(" ", subject)
    subject = re.sub(r"[^a-z0-9 ]", " ", subject)
    subject = re.sub(r"\s+", " ", subject).strip()
    if not subject:
        return None
    from urllib.parse import quote
    return _PLAY_SERVICES[service].format(quote(subject))


# Words that describe where a thing is, not which thing it is.
_SITE_FILLER = re.compile(
    r"\b(my|the|a|an|up|tab|tabs|page|pages|site|website|window|link|please)\b")


def load_shortcuts() -> dict[str, str]:
    """The master's own name -> URL pairs (~/.alfred/shortcuts.yaml).

    Bookmarks only cover what he saved; the things he actually says are often
    open *tabs*, which we can't see. So he can name them himself, and
    `alfred learn` never touches this file."""
    import yaml
    if not SHORTCUTS_FILE.exists():
        return {}
    try:
        doc = yaml.safe_load(SHORTCUTS_FILE.read_text(encoding="utf-8")) or {}
        pairs = doc.get("shortcuts", doc)
        return {str(k).lower(): str(v) for k, v in pairs.items()
                if str(v).startswith(("http://", "https://"))}
    except Exception:
        return {}


def remember(name: str, url: str) -> None:
    import yaml
    shortcuts = load_shortcuts()
    shortcuts[name.strip().lower()] = url.strip()
    SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHORTCUTS_FILE.write_text(yaml.safe_dump({"shortcuts": shortcuts}, sort_keys=True),
                              encoding="utf-8")


def _best_name(wanted: str, names) -> str | None:
    """Exact, then containment (the longest name that appears in what was
    said), then fuzzy — so "my go trade investment tab" still finds "go trade"."""
    names = list(names)
    if wanted in names:
        return wanted
    inside = sorted((n for n in names if n and n in wanted), key=len, reverse=True)
    if inside:
        return inside[0]
    hit = get_close_matches(wanted, names, n=1, cutoff=0.8)
    return hit[0] if hit else None


def site_lookup(utterance: str) -> str | None:
    """'open my go trade tab' / 'open youtube' -> a URL. The master's own
    shortcuts win, then his bookmarks, then a table of well-known sites."""
    said = re.sub(r"[^a-z0-9 ]", "", utterance.lower()).strip()
    match = _OPEN_VERBS.match(said)
    if not match:
        return None
    wanted = re.sub(r"\s+", " ", _SITE_FILLER.sub(" ", match.group(1))).strip()
    if not wanted:
        return None
    for table in (load_shortcuts(), load().get("sites", {}), _COMMON_SITES):
        name = _best_name(wanted, table)
        if name:
            return table[name]
    return None
