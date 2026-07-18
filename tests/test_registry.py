import json

from alfred.registry import REGISTRY, Tier
from alfred.validator import plan_tier, validate_plan


def test_menu_is_frozen_at_twelve_actions():
    assert len(REGISTRY) == 12


def test_nothing_destructive_on_the_menu():
    forbidden = {"delete", "install", "shutdown", "shell", "keystroke", "mouse"}
    for name in REGISTRY:
        assert not any(word in name for word in forbidden)


def test_every_spec_declares_tier_and_reversibility():
    for spec in REGISTRY.values():
        assert spec.tier in Tier
        assert isinstance(spec.reversible, bool)
        assert spec.summary


def test_plan_gates_at_highest_tier():
    steps = validate_plan(json.dumps({"plan": [
        {"action": "web_search", "args": {"query": "hello"}},          # tier 0
        {"action": "settings_change",
         "args": {"key": "app_theme", "value": "dark"}},               # tier 2
    ]}))
    assert plan_tier(steps) is Tier.BY_YOUR_LEAVE
