"""The deterministic gatekeeper between any planner and any adapter.

Input is untrusted text (from an LLM, the palette, or anywhere else). Output
is either a fully-typed plan or a Refusal — there is no third state, and no
adapter can be reached except through here.
"""

import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from . import config
from .registry import REGISTRY, ActionSpec, Tier


class Refusal(Exception):
    """A polite no. The message is safe to show (or speak) to the user."""


@dataclass(frozen=True)
class PlanStep:
    spec: ActionSpec
    args: BaseModel


def validate_plan(raw: str) -> list[PlanStep]:
    """Parse untrusted JSON into a typed plan, or raise Refusal.

    Expected shape: {"plan": [{"action": "...", "args": {...}}, ...]}
    """
    if len(raw.encode("utf-8", errors="replace")) > config.MAX_PLAN_BYTES:
        raise Refusal("I'm afraid that request is rather too long, sir.")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        raise Refusal("I couldn't make sense of that plan, sir.") from None

    if not isinstance(doc, dict) or set(doc) != {"plan"} or not isinstance(doc["plan"], list):
        raise Refusal("A plan must be exactly {\"plan\": [...]}, sir.")
    steps_raw = doc["plan"]
    if not 1 <= len(steps_raw) <= config.MAX_PLAN_STEPS:
        raise Refusal(
            f"I can manage between 1 and {config.MAX_PLAN_STEPS} steps at a time, sir."
        )

    steps: list[PlanStep] = []
    for i, item in enumerate(steps_raw, 1):
        if not isinstance(item, dict) or set(item) - {"action", "args"} or "action" not in item:
            raise Refusal(f"Step {i} is not a proper request, sir.")
        name = item["action"]
        spec = REGISTRY.get(name) if isinstance(name, str) else None
        if spec is None:
            raise Refusal(
                f"I'm afraid '{name}' is not on the service menu, sir. "
                "Might I suggest asking what I can do?"
            )
        args_raw = item.get("args", {})
        if not isinstance(args_raw, dict):
            raise Refusal(f"Step {i}: arguments must be an object, sir.")
        try:
            args = spec.args.model_validate(args_raw)
        except ValidationError as e:
            detail = "; ".join(err["msg"] for err in e.errors())
            raise Refusal(f"Step {i} ({name}): {detail}, sir.") from None
        steps.append(PlanStep(spec, args))
    return steps


def plan_tier(steps: list[PlanStep]) -> Tier:
    """A plan is gated at the highest tier present, before the first step runs."""
    return max(step.spec.tier for step in steps)
