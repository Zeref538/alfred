"""House customs: the fast path must match generously but never bypass the gate."""

import json

import pytest

from alfred.customs import DEFAULT_CUSTOMS, HouseCustoms
from alfred.validator import validate_plan


@pytest.fixture
def customs(tmp_path):
    return HouseCustoms(path=tmp_path / "customs.yaml")


def test_default_customs_created_on_first_use(customs, tmp_path):
    assert (tmp_path / "customs.yaml").read_text(encoding="utf-8") == DEFAULT_CUSTOMS
    assert customs.names() == ["at_ease", "investment_mode", "quiet_hours",
                               "school_mode", "study_session", "work_mode"]


def test_exact_match_ignores_case_and_punctuation(customs):
    plan = customs.match("Set up my Study Session!")
    assert plan is not None
    actions = [s["action"] for s in json.loads(plan)["plan"]]
    assert actions == ["open_url", "web_search", "toggle_do_not_disturb"]


def test_fuzzy_match_catches_near_misses(customs):
    # a plausible STT slip on "set up my study session"
    assert customs.match("set up my study sesion") is not None


def test_unrelated_utterances_do_not_match(customs):
    assert customs.match("delete all my files") is None
    assert customs.match("") is None


def test_matched_plans_pass_the_real_validator(customs):
    for name in customs.names():
        phrase = customs.routines[name]["phrases"][0]
        validate_plan(customs.match(phrase))  # Refusal here means bad defaults


def test_user_customs_still_face_the_validator(tmp_path):
    # a mischievous routine matches fine — and dies at the gate, not in customs
    (tmp_path / "customs.yaml").write_text(
        "routines:\n  evil:\n    phrases: [do the thing]\n"
        "    plan:\n      - action: run_shell\n        args: {cmd: format c}\n",
        encoding="utf-8")
    plan = HouseCustoms(path=tmp_path / "customs.yaml").match("do the thing")
    assert plan is not None
    from alfred.validator import Refusal
    with pytest.raises(Refusal):
        validate_plan(plan)
