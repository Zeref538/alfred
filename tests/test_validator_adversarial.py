"""Red-team fixtures for the validator.

Every case here is an attack or a mishear that must die at the gate:
off-menu actions, argument smuggling, traversal, scheme abuse, malformed and
oversized payloads. These run in CI on every push — the safety claim is a
regression test, not a README sentence.
"""

import json

import pytest

from alfred import config
from alfred.validator import PlanStep, Refusal, validate_plan


def plan(*steps: dict) -> str:
    return json.dumps({"plan": list(steps)})


def refuse(raw: str) -> str:
    with pytest.raises(Refusal) as exc:
        validate_plan(raw)
    return str(exc.value)


@pytest.fixture
def sandbox_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_FOLDERS", [tmp_path / "docs"])
    return tmp_path


# --- off-menu action names ---------------------------------------------------

@pytest.mark.parametrize("name", [
    "delete_file", "run_shell", "install_package", "shutdown",
    "keystroke", "OPEN_URL", "", 7, None,
])
def test_off_menu_actions_refused(name):
    assert "menu" in refuse(plan({"action": name, "args": {}}))


# --- argument smuggling ------------------------------------------------------

def test_unknown_arg_fields_refused():
    refuse(plan({"action": "open_url",
                 "args": {"url": "https://example.com", "shell": "rm -rf /"}}))


def test_extra_step_keys_refused():
    refuse(plan({"action": "open_url", "args": {"url": "https://example.com"},
                 "on_error": "retry"}))


def test_args_must_be_object():
    refuse(plan({"action": "open_url", "args": "https://example.com"}))


# --- URL scheme abuse --------------------------------------------------------

@pytest.mark.parametrize("url", [
    "file:///C:/Windows/System32/config/SAM",
    "javascript:alert(1)",
    "ftp://example.com/x",
    "chrome://settings",
    "//example.com",          # scheme-relative
    "https://",               # no host
    "example.com",            # no scheme
    "https://" + "a" * 3000,  # oversized
])
def test_bad_urls_refused(url):
    refuse(plan({"action": "open_url", "args": {"url": url}}))


# --- path traversal / containment --------------------------------------------

@pytest.mark.parametrize("path", [
    "..\\..\\Windows\\System32\\config\\SAM",
    "C:\\Windows\\System32\\cmd.exe",
    "docs\\..\\..\\secrets.txt",
])
def test_paths_outside_whitelist_refused(sandbox_folders, path):
    refuse(plan({"action": "open_file", "args": {"path": str(sandbox_folders / path)}}))


def test_contained_path_allowed_and_resolved(sandbox_folders):
    inside = sandbox_folders / "docs" / "sub" / ".." / "notes.txt"
    steps = validate_plan(plan({"action": "open_file", "args": {"path": str(inside)}}))
    # the validator stores the canonical path, traversal already collapsed
    assert steps[0].args.path == str((sandbox_folders / "docs" / "notes.txt").resolve())


# --- allowlist membership and value ranges -----------------------------------

@pytest.mark.parametrize("step", [
    {"action": "launch_app", "args": {"app": "powershell"}},
    {"action": "launch_app", "args": {"app": "cmd.exe"}},
    {"action": "set_volume", "args": {"level": 101}},
    {"action": "set_volume", "args": {"level": -1}},
    {"action": "settings_change", "args": {"key": "execution_policy", "value": "bypass"}},
    {"action": "settings_change", "args": {"key": "app_theme", "value": "hotdog"}},
    {"action": "media_control", "args": {"command": "eject"}},
    {"action": "window_layout", "args": {"preset": "close_all"}},
    {"action": "clipboard_write", "args": {"text": "x" * (config.MAX_CLIPBOARD_CHARS + 1)}},
    {"action": "web_search", "args": {"query": "a\nb"}},
])
def test_out_of_policy_arguments_refused(step):
    refuse(plan(step))


# --- malformed / oversized payloads ------------------------------------------

@pytest.mark.parametrize("raw", [
    "not json at all",
    "{}",
    '{"plan": {}}',
    '{"plan": []}',
    '{"plan": [{}]}',
    '{"steps": []}',
    '{"plan": [], "extra": 1}',
    json.dumps({"plan": [{"action": "web_search", "args": {"query": "hi"}}] * 11}),
    "x" * (config.MAX_PLAN_BYTES + 1),
])
def test_malformed_plans_refused(raw):
    refuse(raw)


# --- the happy path still works ----------------------------------------------

def test_valid_multistep_plan_passes():
    steps = validate_plan(plan(
        {"action": "open_url", "args": {"url": "https://example.com/guide"}},
        {"action": "web_search", "args": {"query": "AI-102 study notes"}},
        {"action": "set_volume", "args": {"level": 20}},
    ))
    assert [s.spec.name for s in steps] == ["open_url", "web_search", "set_volume"]
    assert all(isinstance(s, PlanStep) for s in steps)


def test_refusal_messages_are_polite():
    assert refuse(plan({"action": "run_shell", "args": {}})).endswith("do?")
