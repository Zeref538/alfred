"""The etiquette gate: consent before action, graded by tier.

The rule, in one line: *the higher the rung, the heavier the consent.* Read-only
and reversible work runs unbidden; only the consequential rungs stop to ask, and
the top rung will not move without the master's own words, typed exactly.

    Tier 0  AT_LIBERTY   runs at once, silently
    Tier 1  ANNOUNCED    runs at once, flashed and undoable — no yes asked
    Tier 2  CONFIRM      one plain yes (a click, a spoken "yes")
    Tier 3  UNDER_SEAL   the phrase "yes i approve please proceed", typed exactly

UI-agnostic: the palette wires these callbacks to the console, the web HUD to
cards over the wire. A multi-step plan is gated once, at its highest tier.
"""

from dataclasses import dataclass
from typing import Callable

from .registry import Tier
from .validator import PlanStep, Refusal, plan_tier

SEAL_PHRASE = "yes i approve please proceed"


def is_seal_phrase(text: str) -> bool:
    """The sealed approval, forgiving only of spacing, case, and trailing marks."""
    return " ".join(str(text).lower().split()).strip(" .!") == SEAL_PHRASE


@dataclass
class Etiquette:
    confirm: Callable[[str], bool]  # Tier 2 — a plain yes; True proceeds
    seal: Callable[[str], bool]     # Tier 3 — the typed approval phrase; True proceeds


def describe(step: PlanStep) -> str:
    args = step.args.model_dump()
    detail = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{step.spec.name}({detail})" if detail else step.spec.name


def clear_plan(steps: list[PlanStep], etiquette: Etiquette) -> None:
    """Raise Refusal unless the plan's tier is satisfied. Tiers 0 and 1 pass
    without asking — they run and are shown, never gated behind a yes."""
    tier = plan_tier(steps)
    summary = "; ".join(describe(s) for s in steps)
    if tier is Tier.CONFIRM and not etiquette.confirm(summary):
        raise Refusal("Very good — I shan't, sir.")
    if tier is Tier.UNDER_SEAL and not etiquette.seal(summary):
        raise Refusal("Left untouched, sir — the seal was withheld.")
