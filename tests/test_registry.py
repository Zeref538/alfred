import json

from alfred.registry import REGISTRY, Tier
from alfred.validator import plan_tier, validate_plan


def test_menu_is_frozen_at_thirteen_actions():
    # The count is asserted so the menu can never grow by accident — widening
    # Alfred's reach must be a deliberate edit here, with a reason.
    # 12 -> 13: focus_tab, added with the browser bridge. It only switches to a
    # tab already open; it cannot navigate, close, or read one.
    assert len(REGISTRY) == 13


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
    assert plan_tier(steps) is Tier.CONFIRM


def test_unknown_app_error_stays_short():
    import json

    import pytest

    from alfred.validator import Refusal, validate_plan
    with pytest.raises(Refusal) as err:
        validate_plan(json.dumps(
            {"plan": [{"action": "launch_app", "args": {"app": "nonesuch"}}]}))
    message = str(err.value)
    assert "nonesuch" in message and "known apps" not in message and len(message) < 200
