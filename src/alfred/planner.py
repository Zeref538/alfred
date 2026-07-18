"""The brain, kept on a leash.

A local LLM turns a novel request into a plan over the service menu — and
that is *all* it can do. Reliability by construction, not hope:

- structured outputs: Ollama is handed a JSON schema built from the registry
  (action names as constants, argument schemas from the same pydantic models
  the validator enforces), temperature 0
- the reply still goes through the deterministic validator; on Refusal there
  is exactly one repair attempt with the error quoted back, then a refusal
- an empty plan is the model's way of declining — off-menu asks end politely
- data-flow rule: the prompt contains the user's utterance and the static
  menu, nothing else — no clipboard, no titles, no file contents
- every planner call is ledgered with PROMPT_VERSION for reproducibility
"""

import json
import os
import urllib.request

from . import config
from .registry import REGISTRY
from .validator import PlanStep, Refusal, validate_plan

PROMPT_VERSION = "p2"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
# small non-thinking default: on this hardware the 4b variant refuses
# think=false and reasons for minutes; override via ALFRED_MODEL
DEFAULT_MODEL = os.environ.get("ALFRED_MODEL", "qwen3.5:2b")
TIMEOUT_S = 120

_SYSTEM = """You are Alfred, a butler who controls a PC only through a fixed service menu.
Convert the user's request into a JSON plan using ONLY the actions below.
Rules:
- Use the fewest steps that honestly fulfil the request.
- A search is exactly one web_search step. NEVER invent URLs — use open_url
  only when the user names a site (then use its https:// domain).
- "skip"/"next song" means media_control next; "pause"/"play" means
  play_pause; "previous" means previous.
- If the request names something the menu can do, do it. Return {"plan": []}
  ONLY when the menu truly cannot fulfil it (deleting, installing, shutting
  down, typing, closing apps) or the request is too vague to act on safely.

Examples:
user: launch notepad
{"plan": [{"action": "launch_app", "args": {"app": "notepad"}}]}
user: search for cheap flights to cebu
{"plan": [{"action": "web_search", "args": {"query": "cheap flights to cebu"}}]}
user: dark mode and volume to 40
{"plan": [{"action": "settings_change", "args": {"key": "app_theme", "value": "dark"}},
          {"action": "set_volume", "args": {"level": 40}}]}
user: delete my downloads folder
{"plan": []}

The service menu (argument values shown are the ONLY ones allowed):
"""


def _field_hint(name: str, prop: dict) -> str:
    if "enum" in prop:
        return f"{name}: {'|'.join(map(str, prop['enum']))}"
    if prop.get("type") == "integer":
        low, high = prop.get("minimum"), prop.get("maximum")
        bounds = f" {low}-{high}" if low is not None and high is not None else ""
        return f"{name}: integer{bounds}"
    return f"{name}: {prop.get('type', 'value')}"


# allowlists live in validators, not schema properties — spell them out
_MENU_OVERRIDES = {
    "launch_app": lambda: (
        f"app: {'|'.join(sorted(config.ALLOWED_APPS))}"
        if len(config.ALLOWED_APPS) <= 12
        else f"app: one of {len(config.ALLOWED_APPS)} registered app names "
             "(use the app's plain name, e.g. "
             + ", ".join(sorted(config.ALLOWED_APPS)[:8]) + ", ...)"),
    "settings_change": lambda: "; ".join(
        f"key: {key}, value: {'|'.join(sorted(values))}"
        for key, values in config.SETTINGS_POLICY.items()),
}


def menu_text() -> str:
    lines = []
    for spec in REGISTRY.values():
        override = _MENU_OVERRIDES.get(spec.name)
        if override:
            args = override()
        else:
            props = spec.args.model_json_schema().get("properties", {})
            args = ", ".join(_field_hint(k, v) for k, v in props.items())
        lines.append(f"- {spec.name}({args}) — {spec.summary}")
    return "\n".join(lines)


def response_schema() -> dict:
    """A JSON schema for structured decoding: action names as an enum from
    the registry, args as a free object. Kept simple on purpose — richer
    constructs (const/anyOf) break llama.cpp's grammar conversion, and
    argument policing belongs to the deterministic validator anyway."""
    return {
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": sorted(REGISTRY)},
                        "args": {"type": "object"},
                    },
                    "required": ["action", "args"],
                },
                "maxItems": config.MAX_PLAN_STEPS,
            }
        },
        "required": ["plan"],
    }


def _ollama_generate(messages: list[dict], model: str) -> str:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,  # qwen3.5 reasons for hundreds of tokens otherwise — latency, not accuracy
        "format": response_schema(),
        "options": {"temperature": 0, "seed": 7},
    }).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read())["message"]["content"]
    except OSError as e:
        raise Refusal(f"My thinking cap is unavailable, sir ({e}).") from None


class Planner:
    def __init__(self, generate=None, model: str = DEFAULT_MODEL):
        self._generate = generate or (lambda messages: _ollama_generate(messages, model))

    def plan(self, utterance: str) -> tuple[str, list[PlanStep]]:
        """Return (raw plan JSON, validated steps) or raise Refusal."""
        messages = [
            {"role": "system", "content": _SYSTEM + menu_text()},
            {"role": "user", "content": utterance},
        ]
        raw = self._generate(messages)
        self._refuse_if_declined(raw)
        try:
            return raw, validate_plan(raw)
        except Refusal as first_error:
            # one repair attempt for malformed plans — a decline is final
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content":
                             f"That plan was rejected: {first_error} "
                             "Reply with a corrected plan, or {\"plan\": []} to decline."})
            raw = self._generate(messages)
            self._refuse_if_declined(raw)
            return raw, validate_plan(raw)

    @staticmethod
    def _refuse_if_declined(raw: str) -> None:
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(doc, dict) and doc.get("plan") == []:
            raise Refusal("I'm afraid that isn't on the service menu, sir.")
