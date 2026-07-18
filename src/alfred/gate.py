"""The etiquette gate: consent before action, per tier.

UI-agnostic: the palette wires these callbacks to the console, the future
tray/HUD wires them to toasts and dialogs. A multi-step plan is gated once,
at its highest tier, before the first step runs.
"""

from dataclasses import dataclass
from typing import Callable

from .registry import Tier
from .validator import PlanStep, Refusal, plan_tier


@dataclass
class Etiquette:
    announce: Callable[[str], bool]  # Tier 1 — may return False to cancel
    confirm: Callable[[str], bool]   # Tier 2 — must return True to proceed


def describe(step: PlanStep) -> str:
    args = step.args.model_dump()
    detail = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{step.spec.name}({detail})" if detail else step.spec.name


def describe_spoken(steps: list[PlanStep]) -> str:
    """A plan as the butler would say it: summaries, not signatures."""
    parts = []
    for step in steps:
        args = step.args.model_dump()
        value = next(iter(args.values()), None)
        parts.append(step.spec.summary if value is None
                     else f"{step.spec.summary} — {value}")
    return "; then ".join(parts)


def clear_plan(steps: list[PlanStep], etiquette: Etiquette) -> None:
    """Raise Refusal unless the plan's tier is satisfied. Tier 0 passes silently."""
    tier = plan_tier(steps)
    summary = "; ".join(describe(s) for s in steps)
    if tier is Tier.ANNOUNCED and not etiquette.announce(summary):
        raise Refusal("As you wish — canceled, sir.")
    if tier is Tier.BY_YOUR_LEAVE and not etiquette.confirm(summary):
        raise Refusal("Very good — I shan't, sir.")
