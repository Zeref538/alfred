"""The brain on its leash — all with a scripted generate, no Ollama needed."""

import json

import pytest

from alfred.planner import Planner, menu_text, response_schema
from alfred.registry import REGISTRY
from alfred.validator import Refusal

GOOD = json.dumps({"plan": [{"action": "set_volume", "args": {"level": 20}}]})
DECLINE = json.dumps({"plan": []})
OFF_MENU = json.dumps({"plan": [{"action": "run_shell", "args": {"cmd": "dir"}}]})


def scripted(*replies: str):
    queue = list(replies)
    calls = []

    def generate(messages):
        calls.append(messages)
        return queue.pop(0)

    return generate, calls


def test_valid_first_reply_needs_no_repair():
    generate, calls = scripted(GOOD)
    raw, steps = Planner(generate=generate).plan("volume to twenty")
    assert steps[0].spec.name == "set_volume" and steps[0].args.level == 20
    assert len(calls) == 1


def test_malformed_reply_gets_one_repair_with_the_error_quoted():
    generate, calls = scripted(OFF_MENU, GOOD)
    _, steps = Planner(generate=generate).plan("volume to twenty")
    assert steps[0].spec.name == "set_volume"
    assert len(calls) == 2
    assert "rejected" in calls[1][-1]["content"]


def test_two_bad_replies_end_in_refusal():
    generate, _ = scripted(OFF_MENU, "still not json")
    with pytest.raises(Refusal):
        Planner(generate=generate).plan("volume to twenty")


def test_a_decline_is_final_not_repaired():
    generate, calls = scripted(DECLINE)
    with pytest.raises(Refusal, match="service menu"):
        Planner(generate=generate).plan("delete system32")
    assert len(calls) == 1  # no repair attempt for a polite no


def test_prompt_contains_only_utterance_and_static_menu():
    generate, calls = scripted(GOOD)
    Planner(generate=generate).plan("volume to twenty")
    system, user = calls[0][0], calls[0][1]
    assert user["content"] == "volume to twenty"
    for spec_name in REGISTRY:
        assert spec_name in system["content"]
    # the data-flow rule: nothing beyond system+user goes in
    assert [m["role"] for m in calls[0]] == ["system", "user"]


def test_response_schema_covers_every_action_in_the_enum():
    schema = response_schema()
    enum = schema["properties"]["plan"]["items"]["properties"]["action"]["enum"]
    assert set(enum) == set(REGISTRY)


def test_menu_text_names_every_action():
    text = menu_text()
    assert all(name in text for name in REGISTRY)
