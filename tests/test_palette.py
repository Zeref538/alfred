"""Palette wiring: kv parsing, adapter table completeness, refusals surface politely."""

import pytest

from alfred.adapters import build_adapters
from alfred.executor import Executor
from alfred.ledger import Ledger
from alfred.palette import _parse_kv, run_plan
from alfred.registry import REGISTRY
from alfred.undo import UndoManager
from alfred.validator import Refusal


def test_every_menu_item_has_an_adapter():
    assert set(build_adapters()) == set(REGISTRY)


def test_kv_parsing_coerces_json_values():
    assert _parse_kv(["level=30", "query=hello world", "enabled=true"]) == {
        "level": 30, "query": "hello world", "enabled": True}


def test_kv_parsing_rejects_non_pairs():
    with pytest.raises(Refusal):
        _parse_kv(["not-a-pair"])


def test_run_plan_refuses_off_menu_without_reaching_adapters(tmp_path, capsys):
    executor = Executor({}, Ledger(root=tmp_path), UndoManager())
    ok = run_plan('{"plan": [{"action": "run_shell", "args": {}}]}', executor)
    assert ok is False
    assert "menu" in capsys.readouterr().out
    assert executor.ledger.today() == []  # refused plans never touch the book


def test_run_plan_executes_and_prints_results(tmp_path, capsys, monkeypatch):
    hits = []
    executor = Executor({"web_search": lambda a: hits.append(a.query)},
                        Ledger(root=tmp_path), UndoManager())
    ok = run_plan('{"plan": [{"action": "web_search", "args": {"query": "hi"}}]}', executor)
    assert ok is True and hits == ["hi"]
    assert "[ok] web_search" in capsys.readouterr().out


def test_compound_is_split_not_dropped():
    # "open my github repos and set volume to 30" opened GitHub and silently
    # forgot the volume: each fast path resolves ONE intent.
    from alfred.palette import is_compound, split_clauses
    assert is_compound("open my github repos and set volume to 30")
    assert split_clauses("open youtube and set the volume to 20") == \
        ["open youtube", "set the volume to 20"]
    assert split_clauses("silence the notifications and snap this window left") == \
        ["silence the notifications", "snap this window left"]


def test_titles_containing_and_are_not_compound():
    from alfred.palette import is_compound
    for single in ("play fire and rain on spotify", "play hide and seek on spotify",
                   "switch to the disney plus tab and play", "open youtube"):
        assert not is_compound(single), single
