"""Palette wiring: kv parsing, adapter table completeness, refusals surface politely."""

import pytest

from carson.adapters import build_adapters
from carson.executor import Executor
from carson.ledger import Ledger
from carson.palette import _parse_kv, run_plan
from carson.registry import REGISTRY
from carson.undo import UndoManager
from carson.validator import Refusal


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
