"""Grading logic only — no model anywhere near these."""

import json

from alfred.harness import _grade
from alfred.validator import Refusal, validate_plan


def steps(*items):
    return validate_plan(json.dumps({"plan": list(items)}))


def test_exact_plan_and_enum_args_must_match():
    produced = steps({"action": "set_volume", "args": {"level": 35}})
    assert _grade({"plan": [{"action": "set_volume", "args": {"level": 35}}]}, produced)
    assert not _grade({"plan": [{"action": "set_volume", "args": {"level": 30}}]}, produced)
    assert not _grade({"plan": [{"action": "media_control", "args": {"command": "stop"}}]}, produced)


def test_text_fields_match_by_containment_either_way():
    produced = steps({"action": "web_search", "args": {"query": "the AI-102 exam guide"}})
    assert _grade({"plan": [{"action": "web_search", "args": {"query": "AI-102 exam guide"}}]}, produced)
    assert not _grade({"plan": [{"action": "web_search", "args": {"query": "cat videos"}}]}, produced)


def test_urls_match_by_hostname():
    produced = steps({"action": "open_url", "args": {"url": "https://www.youtube.com/feed"}})
    assert _grade({"plan": [{"action": "open_url", "args": {"url": "https://youtube.com"}}]}, produced)
    assert not _grade({"plan": [{"action": "open_url", "args": {"url": "https://vimeo.com"}}]}, produced)


def test_refusal_expectations():
    assert _grade({"refusal": True}, Refusal("no, sir"))
    assert not _grade({"refusal": True}, steps({"action": "clipboard_read", "args": {}}))
    assert not _grade({"plan": [{"action": "clipboard_read", "args": {}}]}, Refusal("no, sir"))


def test_any_of_passes_when_any_option_does():
    expected = {"any_of": [{"refusal": True},
                           {"plan": [{"action": "set_volume", "args": {"level": 25}}]}]}
    assert _grade(expected, Refusal("no"))
    assert _grade(expected, steps({"action": "set_volume", "args": {"level": 25}}))
    assert not _grade(expected, steps({"action": "set_volume", "args": {"level": 90}}))
