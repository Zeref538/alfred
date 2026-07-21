"""The browser bridge: knowing which tabs are open, without learning too much.

Alfred cannot see tabs from the operating system, so a small extension in the
browser reports them. That is a large amount of new sight — the tabs a person
has open are among the most revealing things on their machine — so the limits
are built into the data structure rather than promised in prose:

- **Nothing is stored but a name and a host.** The extension sends a title and
  a URL; only the title and the hostname survive the door. Paths and query
  strings — where session tokens, document ids and search terms live — are
  discarded on arrival and never held at all.
- **Nothing touches the disk.** The view lives in memory, dies with the
  process, and is never written to the ledger or the field log (which the
  master may well send to someone else).
- **Nothing goes to the model.** The data-flow rule is absolute: a tab title is
  attacker-controlled text — any web page can name itself "ignore previous
  instructions". Matching is deterministic and local, and no tab title or host
  ever enters a planner prompt.
- **The master can blind it.** Hosts listed in ~/.alfred/tab_privacy.yaml are
  dropped on arrival, so a banking tab is never even momentarily known.
- **It goes stale on purpose.** A view older than STALE_SECONDS is not used, so
  Alfred never acts on a browser he may no longer be looking at.
- **It is off unless asked for.** No extension, no sight.
"""

import re
import threading
import time
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from . import config

PRIVACY_FILE = config.DATA_DIR / "tab_privacy.yaml"
STALE_SECONDS = 90
MAX_TABS = 200
MATCH_THRESHOLD = 0.62

# Hosts never worth knowing about by default. The master may add his own.
DEFAULT_BLIND = [
    "*bank*", "*paypal*", "*wellsfargo*", "*chase.com*",
    "accounts.google.com", "*login*", "*signin*", "*password*",
]


def _blind_patterns() -> list[str]:
    import yaml
    patterns = list(DEFAULT_BLIND)
    if PRIVACY_FILE.exists():
        try:
            doc = yaml.safe_load(PRIVACY_FILE.read_text(encoding="utf-8")) or {}
            extra = doc.get("never_see") or []
            patterns += [str(p).lower() for p in extra]
        except Exception:
            pass
    return patterns


def _blinded(host: str, patterns: list[str]) -> bool:
    host = host.lower()
    for pattern in patterns:
        body = pattern.strip().lower()
        if not body:
            continue
        if body.startswith("*") and body.endswith("*"):
            if body.strip("*") in host:
                return True
        elif body.startswith("*"):
            if host.endswith(body.lstrip("*")):
                return True
        elif body.endswith("*"):
            if host.startswith(body.rstrip("*")):
                return True
        elif body == host:
            return True
    return False


# Query parameters that carry credentials rather than meaning. Dropped by name,
# and anything long or high-entropy is dropped by shape regardless of its name —
# a reset link is no less dangerous for being called "r".
_SECRET_PARAMS = frozenset("""
    token access_token id_token refresh refresh_token session sessionid sid auth
    authorization key api_key apikey password pwd pass secret code state nonce
    signature sig hash otp jwt bearer credential login email phone
""".split())
MAX_PARAM_VALUE = 40
MAX_PATH = 120


def _safe_query(query: str) -> str:
    """Keep the parts of a query that say WHICH page; drop the parts that are
    credentials. "?tab=repositories" is navigation; "?session=..." is a key."""
    from urllib.parse import parse_qsl, urlencode
    kept = []
    for name, value in parse_qsl(query, keep_blank_values=False):
        if name.lower() in _SECRET_PARAMS:
            continue
        if len(value) > MAX_PARAM_VALUE:      # long values are tokens, not words
            continue
        if len(value) > 24 and not any(c in value for c in " -_") \
                and any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
            continue                          # base64/hex-looking: treat as secret
        kept.append((name, value))
    return urlencode(kept[:6])


class Tab:
    """A tab as Alfred is permitted to know it: an id, a name, a host, and the
    path that says WHICH page. Never a credential, never page content."""

    __slots__ = ("id", "title", "host", "path")

    def __init__(self, tab_id, title: str, host: str, path: str = ""):
        self.id = tab_id
        self.title = title
        self.host = host
        self.path = path

    @property
    def where(self) -> str:
        return self.host + self.path

    def __repr__(self) -> str:
        return f"Tab({self.title!r} @ {self.where})"


class TabView:
    """What the browser last reported. In memory only; never persisted."""

    def __init__(self):
        self._tabs: list[Tab] = []
        self._at = 0.0
        self._lock = threading.Lock()

    def update(self, reported) -> int:
        """Take a report from the extension, keeping only what may be kept."""
        patterns = _blind_patterns()
        kept: list[Tab] = []
        for item in list(reported)[:MAX_TABS]:
            try:
                tab_id = item.get("id")
                title = str(item.get("title", "")).strip()[:120]
                split = urlsplit(str(item.get("url", "")))
                host = split.netloc.lower().removeprefix("www.")
                # the path says which page; the query is filtered to the parts
                # that mean something; the fragment is dropped entirely
                path = split.path if split.path != "/" else ""
                query = _safe_query(split.query)
                path = (path + ("?" + query if query else ""))[:MAX_PATH]
            except Exception:
                continue
            if tab_id is None or not host or _blinded(host, patterns):
                continue
            kept.append(Tab(tab_id, title, host, path))
        with self._lock:
            self._tabs, self._at = kept, time.monotonic()
        return len(kept)

    def fresh(self) -> bool:
        return bool(self._tabs) and (time.monotonic() - self._at) < STALE_SECONDS

    def all(self) -> list[Tab]:
        with self._lock:
            return list(self._tabs) if self.fresh() else []

    def forget(self) -> None:
        with self._lock:
            self._tabs, self._at = [], 0.0

    def match(self, wanted: str):
        """The best tab for a spoken name — deterministic, local, no model.

        Scored against the title and the host, so "my go ledger tab" finds
        either "Ledger — Portfolio" or ledger.example.com.
        """
        wanted = re.sub(r"[^a-z0-9 ]", " ", wanted.lower()).strip()
        wanted = re.sub(r"\s+", " ", wanted)
        if not wanted:
            return None
        squashed = wanted.replace(" ", "")
        best, best_score = None, 0.0
        for tab in self.all():
            title = re.sub(r"[^a-z0-9 ]", " ", tab.title.lower())
            # the path distinguishes two tabs on the same site: "github repos"
            # should find github.com/you?tab=repositories, not the bare profile
            where = re.sub(r"[^a-z0-9]", "", tab.where.lower())
            score = max(
                SequenceMatcher(None, wanted, title).ratio(),
                SequenceMatcher(None, squashed, where).ratio(),
                1.0 if wanted and wanted in title else 0.0,
                1.0 if squashed and squashed in where else 0.0,
            )
            if score > best_score:
                best, best_score = tab, score
        return best if best_score >= MATCH_THRESHOLD else None


VIEW = TabView()

# The extension listens on the same guarded event stream the HUD uses, so
# Alfred asks for a switch by emitting; he never reaches into the browser.
_emit = None


def set_emitter(emit) -> None:
    global _emit
    _emit = emit


def request_focus(tab_id) -> None:
    if _emit is None:
        raise RuntimeError("the browser bridge isn't connected, sir")
    _emit(type="tab_focus", id=tab_id)


def request_play(url: str) -> None:
    """Ask the extension to open a media page and press play on it."""
    if _emit is None:
        raise RuntimeError("the browser bridge isn't connected, sir")
    _emit(type="play_request", url=url)


# Requiring the word "tab" keeps this explicit: an ordinary "open youtube"
# still opens a page, and only a deliberate "…tab" reaches into the browser.
_TAB_PHRASE = re.compile(
    r"\b(?:switch to|swap to|go to|open|show me|take me to|bring up|find)\s+"
    r"(?:my\s+|the\s+)?(.+?)\s*\btabs?\b")


_ALSO_PLAY = re.compile(r"\btabs?\b.*\b(?:and\s+|then\s+)?play\b")


def spoken_tab_name(utterance: str) -> str | None:
    match = _TAB_PHRASE.search(utterance.lower())
    if not match:
        return None
    name = re.sub(r"\s+", " ", match.group(1)).strip()
    return name or None


def wants_play_after(utterance: str) -> bool:
    """'switch to the disney plus tab and play' — the switch was obeyed and the
    'and play' quietly dropped. It is a second step, so it becomes one."""
    return bool(_ALSO_PLAY.search(utterance.lower()))
