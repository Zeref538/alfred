"""The text command palette — Phase 1's front door, no brain attached.

    alfred menu                       show the service menu
    alfred act <action> [k=v ...]     one action (values parsed as JSON when possible)
    alfred ask <words...>             match a routine from the house customs
    alfred plan <json | @file>        a full JSON plan
    alfred ledger                     today's page of the butler's book
    alfred burn                       burn the day's page
    alfred summon [--check]           global hotkey (Ctrl+Alt+C opens the palette)
    alfred tray                       system tray icon (needs the [ui] extra)
    alfred voice                      push-to-talk loop (needs the [voice] extra)
    alfred                            REPL — same commands, plus `undo`

Consent on the console: Tier 1 plans are announced; Tier 2 plans require an
explicit yes. Without a terminal to ask, pass --yes or Alfred declines.
"""

import json
import sys

from .adapters import build_adapters
from .executor import Executor
from .gate import Etiquette, clear_plan
from .ledger import Ledger
from .registry import REGISTRY
from .undo import UndoManager
from .validator import Refusal, validate_plan


def _console_etiquette(preapproved: bool) -> Etiquette:
    def announce(summary: str) -> bool:
        print(f"If I may, sir: {summary}")
        return True

    def confirm(summary: str) -> bool:
        if preapproved:
            print(f"By your leave (pre-approved): {summary}")
            return True
        if not sys.stdin.isatty():
            return False
        return input(f"By your leave, sir — {summary} [y/N] ").strip().lower() == "y"

    return Etiquette(announce=announce, confirm=confirm)


def _parse_kv(pairs: list[str]) -> dict:
    args = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise Refusal(f"'{pair}' is not key=value, sir.")
        try:
            args[key] = json.loads(value)
        except json.JSONDecodeError:
            args[key] = value
    return args


def run_plan(raw: str, executor: Executor, preapproved: bool = False) -> bool:
    try:
        steps = validate_plan(raw)
        clear_plan(steps, _console_etiquette(preapproved))
    except Refusal as refusal:
        print(refusal)
        return False
    for result in executor.run(steps, intent=raw):
        mark = "ok" if result.ok else "XX"
        print(f"  [{mark}] {result.action}: {result.detail}")
    return True


def _resolve_utterance(utterance: str, ledger: Ledger) -> str:
    """Customs first (no LLM), planner for novel asks. Raises Refusal."""
    from .customs import HouseCustoms
    plan = HouseCustoms().match(utterance)
    if plan is not None:
        ledger.record(event="plan", source="customs", utterance=utterance)
        return plan
    from .planner import PROMPT_VERSION, Planner
    plan, _ = Planner().plan(utterance)  # raises Refusal on a decline
    ledger.record(event="plan", source="llm",
                  prompt_version=PROMPT_VERSION, utterance=utterance)
    return plan


def _voice_loop(executor: Executor, ledger: Ledger, preapproved: bool) -> int:
    from . import voice
    print("Push-to-talk: Enter, then speak (5s). Say 'Alfred, stop' to ring "
          "the bell. Ctrl+C dismisses me.")
    while True:
        try:
            input("[Enter to speak] ")
        except (EOFError, KeyboardInterrupt):
            voice.speak("Very good, sir.")
            return 0
        transcript = voice.transcribe(voice.record())
        print(f'  heard: "{transcript}"')
        if not transcript:
            continue
        if voice.is_stop(transcript):
            executor.abort.set()
            ledger.record(event="bell", transcript=transcript)
            voice.speak("As you were, sir.")
            executor.abort.clear()
            continue
        try:
            plan = _resolve_utterance(transcript, ledger)
        except Refusal as refusal:
            print(refusal)
            voice.speak(str(refusal))
            continue
        ok = run_plan(plan, executor, preapproved)
        voice.speak("Very good, sir." if ok else "My apologies, sir — see the palette.")


def _menu() -> None:
    print(f"The service menu ({len(REGISTRY)} items):")
    for spec in REGISTRY.values():
        undoable = "undoable" if spec.reversible else "one-way"
        print(f"  tier {int(spec.tier)} | {spec.name:<22} {undoable:<8} - {spec.summary}")


def _dispatch(words: list[str], executor: Executor, undo: UndoManager,
              ledger: Ledger, preapproved: bool) -> None:
    command, rest = words[0], words[1:]
    if command == "menu":
        _menu()
    elif command == "ask" and rest:
        plan = _resolve_utterance(" ".join(rest), ledger)
        run_plan(plan, executor, preapproved)
    elif command == "act" and rest:
        plan = json.dumps({"plan": [{"action": rest[0], "args": _parse_kv(rest[1:])}]})
        run_plan(plan, executor, preapproved)
    elif command == "plan" and rest:
        raw = rest[0]
        if raw.startswith("@"):
            raw = open(raw[1:], encoding="utf-8").read()
        run_plan(raw, executor, preapproved)
    elif command == "undo":
        handle = undo.undo_last()
        if handle is None:
            print("Nothing to undo, sir.")
        else:
            ledger.record(event="undo", action=handle.action, detail=handle.description)
            print(f"Undone: {handle.description}.")
    elif command == "ledger":
        for entry in ledger.today() or [{"ts": "—", "event": "an empty page, sir"}]:
            print("  " + json.dumps(entry, ensure_ascii=False))
    elif command == "burn":
        ledger.burn_today()
        print("The day's page is ash, sir.")
    else:
        raise Refusal(f"I don't recognise '{command}', sir. Try: menu, ask, act, plan, undo, ledger, burn.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    preapproved = "--yes" in argv
    argv = [a for a in argv if a != "--yes"]

    if argv[:1] == ["summon"]:
        from .summon import summon_loop
        try:
            summon_loop(check_only="--check" in argv)
        except RuntimeError as e:
            print(e)
            return 1
        return 0
    if argv[:1] == ["tray"]:
        from .tray import main as tray_main
        return tray_main()

    ledger = Ledger()
    undo = UndoManager()
    executor = Executor(build_adapters(), ledger, undo)

    if argv[:1] == ["voice"]:
        return _voice_loop(executor, ledger, preapproved)

    try:
        if argv:
            _dispatch(argv, executor, undo, ledger, preapproved)
            return 0
        print('At your service, sir. ("menu" to browse, "quit" to dismiss me.)')
        while True:
            try:
                line = input("Alfred> ").strip()
            except (EOFError, KeyboardInterrupt):
                line = "quit"
            if line in ("quit", "exit"):
                print("Very good, sir.")
                return 0
            if not line:
                continue
            try:
                _dispatch(line.split(), executor, undo, ledger, preapproved)
            except Refusal as refusal:
                print(refusal)
    except Refusal as refusal:
        print(refusal)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
