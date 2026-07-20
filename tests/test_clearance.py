"""Clearance: only 'I confirm Alfred, ...' unlocks self-config, and only for
the two hotkey settings — parsing is deterministic and bounded."""

from alfred import clearance


def test_phrase_is_required():
    assert clearance.clearance_instruction("set the hold keys to g and h") is None
    assert clearance.clearance_instruction("please set hold keys") is None


def test_phrase_unlocks_the_instruction():
    assert clearance.clearance_instruction(
        "I confirm Alfred, set the hold keys to g and h") == "set the hold keys to g and h"


def test_parse_hold_keys():
    assert clearance.parse_self_config("set the hold keys to g and h") == ("hold_keys", "g+h")
    assert clearance.parse_self_config("hold to talk keys f j") == ("hold_keys", "f+j")


def test_parse_summon_hotkey():
    assert clearance.parse_self_config(
        "set the summon hotkey to ctrl alt j") == ("summon_hotkey", "ctrl+alt+j")
    assert clearance.parse_self_config(
        "summon shortcut control shift m") == ("summon_hotkey", "ctrl+shift+m")


def test_unparseable_self_config_is_none():
    assert clearance.parse_self_config("do a barrel roll") is None
    assert clearance.parse_self_config("set the hold keys to only one") is None  # <2 letters


def test_end_to_end_over_the_wire(tmp_path, monkeypatch):
    import alfred.settings as settings
    from alfred.executor import Executor
    from alfred.ledger import Ledger
    from alfred.undo import UndoManager
    from alfred.web import Session
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.yaml")
    settings._cache = None
    session = Session(executor=Executor({}, Ledger(root=tmp_path), UndoManager()))
    handled = session._maybe_clearance("I confirm Alfred, set the hold keys to g and h")
    assert handled
    assert settings.get("hold_keys") == "g+h"
