"""House customs: the routines Carson knows by heart.

A YAML file of named routines with trigger phrases and fixed plans. Matching
is exact-or-fuzzy on normalized text (stdlib difflib — no LLM round-trip),
which is the latency fast path: common commands never wait on a model.

Customs are user-authored and therefore untrusted: a matched plan still goes
through the validator and the etiquette gate like anything else.
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from . import config

DEFAULT_CUSTOMS = """\
# Carson's house customs — routines he knows by heart.
# Each routine: trigger phrases and a fixed plan over the service menu.
# Plans are validated and tier-gated like any other request.
routines:
  study_session:
    phrases:
      - set up my study session
      - study time
      - let's study
    plan:
      - action: open_url
        args: {url: "https://learn.microsoft.com/credentials/certifications/exams/ai-102/"}
      - action: web_search
        args: {query: "pomodoro timer online"}
      - action: toggle_do_not_disturb
        args: {enabled: true}
  quiet_hours:
    phrases:
      - quiet hours
      - make it quiet
      - wind down
    plan:
      - action: toggle_do_not_disturb
        args: {enabled: true}
      - action: set_volume
        args: {level: 10}
"""

_FUZZY_CUTOFF = 0.85


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


class HouseCustoms:
    def __init__(self, path: Path | None = None):
        self.path = path or (config.DATA_DIR / "customs.yaml")
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(DEFAULT_CUSTOMS, encoding="utf-8")
        doc = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.routines: dict[str, dict] = doc.get("routines") or {}

    def match(self, utterance: str) -> str | None:
        """Return the matched routine's plan as JSON, or None. Never raises
        on a bad customs file entry — the validator downstream will rule."""
        spoken = _normalize(utterance)
        if not spoken:
            return None
        best: tuple[float, dict | None] = (0.0, None)
        for routine in self.routines.values():
            for phrase in routine.get("phrases", []):
                candidate = _normalize(str(phrase))
                if candidate == spoken:
                    return json.dumps({"plan": routine.get("plan", [])})
                score = SequenceMatcher(None, spoken, candidate).ratio()
                if score > best[0]:
                    best = (score, routine)
        if best[0] >= _FUZZY_CUTOFF and best[1] is not None:
            return json.dumps({"plan": best[1].get("plan", [])})
        return None

    def names(self) -> list[str]:
        return sorted(self.routines)
