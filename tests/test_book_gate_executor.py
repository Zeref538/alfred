"""Ledger, undo, gate, and executor — all with fake adapters, nothing real runs."""

import json
import threading
import time

import pytest

import alfred.executor as executor_mod
from alfred.executor import Executor, StepResult
from alfred.gate import Etiquette, clear_plan
from alfred.ledger import Ledger
from alfred.undo import RevertHandle, UndoManager
from alfred.validator import Refusal, validate_plan


def steps_for(*items: dict):
    return validate_plan(json.dumps({"plan": list(items)}))


SEARCH = {"action": "web_search", "args": {"query": "hello"}}          # tier 0
VOLUME = {"action": "set_volume", "args": {"level": 30}}               # tier 1, reversible
THEME = {"action": "settings_change",
         "args": {"key": "app_theme", "value": "dark"}}                # tier 2


@pytest.fixture
def ledger(tmp_path):
    return Ledger(root=tmp_path)


# --- butler's book -----------------------------------------------------------

def test_ledger_appends_and_reads_back(ledger):
    ledger.record(event="action", action="web_search", ok=True)
    ledger.record(event="action", action="set_volume", ok=False)
    page = ledger.today()
    assert [e["action"] for e in page] == ["web_search", "set_volume"]
    assert all("ts" in e for e in page)


def test_burn_the_days_page(ledger):
    ledger.record(event="action", action="web_search")
    ledger.burn_today()
    assert ledger.today() == []


def test_pages_expire_after_retention(tmp_path):
    import datetime

    from alfred.ledger import RETENTION_DAYS

    book = tmp_path / "ledger"
    book.mkdir()
    old_day = datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS + 1)
    stale = book / f"{old_day.isoformat()}.jsonl"
    stale.write_text('{"event": "action"}\n', encoding="utf-8")
    fresh = book / f"{datetime.date.today().isoformat()}.jsonl"
    fresh.write_text('{"event": "action"}\n', encoding="utf-8")
    keepsake = book / "notes.jsonl"  # not a dated page — never touched
    keepsake.write_text("mine\n", encoding="utf-8")

    Ledger(root=tmp_path)

    assert not stale.exists()
    assert fresh.exists() and keepsake.exists()


# --- undo manager ------------------------------------------------------------

def test_undo_is_lifo_and_runs_the_revert():
    undone = []
    undo = UndoManager()
    for name in ("first", "second"):
        undo.push(RevertHandle(name, name, lambda n=name: undone.append(n)))
    assert undo.undo_last().action == "second"
    assert undone == ["second"]
    assert len(undo) == 1


def test_undo_on_empty_stack_is_a_shrug():
    assert UndoManager().undo_last() is None


# --- etiquette gate ----------------------------------------------------------

def gate(confirm=True, seal=True, log=None):
    log = log if log is not None else []
    return Etiquette(
        confirm=lambda s: (log.append(("confirm", s)), confirm)[1],
        seal=lambda s: (log.append(("seal", s)), seal)[1],
    ), log


def test_tier0_passes_without_asking():
    etiquette, log = gate()
    clear_plan(steps_for(SEARCH), etiquette)
    assert log == []


def test_tier1_runs_without_a_yes():
    # reversible state changes are shown, never gated behind a confirmation
    etiquette, log = gate(confirm=False, seal=False)
    clear_plan(steps_for(VOLUME), etiquette)  # no raise
    assert log == []


def test_seal_phrase_forgives_only_spacing_and_case():
    from alfred.gate import is_seal_phrase
    assert is_seal_phrase("Yes I approve please proceed.")
    assert is_seal_phrase("  yes   i approve please proceed  ")
    assert not is_seal_phrase("yes i approve")
    assert not is_seal_phrase("yes")


def test_tier2_gates_whole_plan_once_at_highest_tier():
    etiquette, log = gate(confirm=False)
    with pytest.raises(Refusal):
        clear_plan(steps_for(SEARCH, THEME), etiquette)
    assert [kind for kind, _ in log] == ["confirm"]  # asked once, as a plain yes


def test_tier3_requires_the_typed_seal(tmp_path, monkeypatch):
    import alfred.config as config
    target = tmp_path / "notes.txt"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "ALLOWED_FOLDERS", (tmp_path,))
    steps = steps_for({"action": "open_file", "args": {"path": str(target)}})

    withheld, _ = gate(seal=False)
    with pytest.raises(Refusal):
        clear_plan(steps, withheld)

    granted, log = gate(seal=True)
    clear_plan(steps, granted)  # no raise
    assert [kind for kind, _ in log] == ["seal"]  # the top rung, not a plain confirm


# --- executor ----------------------------------------------------------------

def test_executor_runs_ledgers_and_collects_reverts(ledger):
    undo = UndoManager()
    calls = []
    adapters = {
        "web_search": lambda args: calls.append(args.query),
        "set_volume": lambda args: RevertHandle("set_volume", "back to 50", lambda: None),
    }
    results = Executor(adapters, ledger, undo).run(steps_for(SEARCH, VOLUME), intent="test")
    assert all(r.ok for r in results)
    assert calls == ["hello"]
    assert len(undo) == 1
    entries = ledger.today()
    assert [e["action"] for e in entries] == ["web_search", "set_volume"]
    assert entries[1]["reversible"] is True and entries[1]["tier"] == 1


def test_adapter_exception_is_reported_not_raised(ledger):
    def boom(args):
        raise RuntimeError("no browser")
    results = Executor({"web_search": boom}, ledger, UndoManager()).run(
        steps_for(SEARCH), intent="test")
    assert results == [StepResult("web_search", False, "RuntimeError: no browser")]
    assert ledger.today()[0]["ok"] is False


def test_missing_adapter_is_reported(ledger):
    results = Executor({}, ledger, UndoManager()).run(steps_for(SEARCH), intent="test")
    assert not results[0].ok and "no adapter" in results[0].detail


def test_the_bell_aborts_between_steps(ledger):
    abort = threading.Event()
    ex = Executor({"web_search": lambda args: abort.set(),
                   "set_volume": lambda args: None}, ledger, UndoManager(), abort=abort)
    results = ex.run(steps_for(SEARCH, VOLUME), intent="test")
    assert results[0].ok is True
    assert results[1].detail == "aborted by the bell"
    assert ledger.today()[-1]["event"] == "abort"


def test_slow_adapter_times_out(ledger, monkeypatch):
    monkeypatch.setattr(executor_mod, "ADAPTER_TIMEOUT_S", 0.05)
    def slow(args):
        time.sleep(1)
    results = Executor({"web_search": slow}, ledger, UndoManager()).run(
        steps_for(SEARCH), intent="test")
    assert results[0].detail == "timed out"
