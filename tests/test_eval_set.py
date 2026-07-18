"""The exam must itself be well-formed: every line parses, ids are unique,
and every gold plan passes the real validator — an off-menu gold answer
would mean the exam is wrong, not the butler."""

import json
from pathlib import Path

from alfred.validator import validate_plan

DRAFT = Path(__file__).parent.parent / "eval" / "frozen_set.jsonl"


def load():
    return [json.loads(line) for line in DRAFT.read_text(encoding="utf-8").splitlines() if line]


def gold_plans(expected: dict):
    if "plan" in expected:
        yield expected["plan"]
    for option in expected.get("any_of", []):
        if "plan" in option:
            yield option["plan"]


def test_draft_set_shape():
    entries = load()
    assert len(entries) == 50
    ids = [e["id"] for e in entries]
    assert len(set(ids)) == 50
    assert all(e["category"] in ("clean", "ambiguous", "adversarial") for e in entries)


def test_every_gold_plan_is_on_the_menu():
    for entry in load():
        for plan in gold_plans(entry["expected"]):
            validate_plan(json.dumps({"plan": plan}))  # raises Refusal if the exam is wrong


def test_every_adversarial_case_expects_refusal():
    for entry in load():
        if entry["category"] == "adversarial":
            assert entry["expected"] == {"refusal": True}
