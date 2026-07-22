"""The text command palette — Phase 1's front door, no brain attached.

    alfred menu                       show the service menu
    alfred act <action> [k=v ...]     one action (values parsed as JSON when possible)
    alfred ask <words...>             match a routine from the house customs
    alfred plan <json | @file>        a full JSON plan
    alfred ledger                     today's page of the butler's book
    alfred burn                       burn the day's page
    alfred web                        local web HUD (127.0.0.1, per-session token)
    alfred hud                        overlay HUD (Tkinter, no extras needed)
    alfred summon [--check]           global hotkey (Ctrl+Alt+C opens the web HUD;
                                      ALFRED_UI=hud for the Tkinter one)
    alfred tray                       system tray icon (needs the [ui] extra)
    alfred voice                      push-to-talk loop (needs the [voice] extra)
    alfred                            REPL — same commands, plus `undo`

Consent on the console scales with the tier: Tiers 0-1 run at once (shown, not
gated); Tier 2 asks a plain yes; Tier 3 (anything reaching your files) needs the
phrase "yes i approve please proceed" typed exactly. --yes pre-answers Tier 2
only — the seal is never pre-answered.
"""

import json
import re
import sys

from .adapters import build_adapters
from .executor import Executor
from .gate import SEAL_PHRASE, Etiquette, clear_plan, is_seal_phrase
from .ledger import Ledger
from .registry import REGISTRY
from .undo import UndoManager
from .validator import Refusal, validate_plan


def _console_etiquette(preapproved: bool) -> Etiquette:
    def confirm(summary: str) -> bool:
        if preapproved:
            print(f"By your leave (pre-approved): {summary}")
            return True
        if not sys.stdin.isatty():
            return False
        return input(f"By your leave, sir — {summary} [y/N] ").strip().lower() == "y"

    def seal(summary: str) -> bool:
        # the top rung: --yes never opens it; only the phrase, typed, does
        if not sys.stdin.isatty():
            return False
        print(f"This is sealed, sir — it reaches your files: {summary}")
        return is_seal_phrase(input(f'Type exactly "{SEAL_PHRASE}" to proceed: '))

    return Etiquette(confirm=confirm, seal=seal)


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
    results = executor.run(steps, intent=raw)
    for result in results:
        mark = "ok" if result.ok else "XX"
        print(f"  [{mark}] {result.action}: {result.detail}")
    if any(r.detail == "aborted by the bell" for r in results):
        done = sum(r.ok for r in results)
        print(f"Shall I put things back, sir? {done} step(s) had run — "
              "'undo' reverts them, most recent first.")
    return all(r.ok for r in results)


# A second order tacked on with "and"/"then". The fast paths each resolve ONE
# intent, so on a compound they answer the first and quietly drop the rest —
# "open my github repos and set volume to 30" opened GitHub and forgot the
# volume. Anything compound goes to the model, which can plan several steps.
# "…and play" is spared: the tab fast path already handles that pairing.
_SECOND_INTENT = re.compile(
    r"\b(?:and|then|also|after that)\s+(?!play\b)"
    r"(open|play|set|turn|mute|unmute|search|google|launch|start|switch|snap|"
    r"make|put|close|minimi[sz]e|maximi[sz]e|volume|copy|read|show|silence|"
    r"pause|skip|dark|light)\b")


def is_compound(utterance: str) -> bool:
    return bool(_SECOND_INTENT.search(utterance.lower()))


def split_clauses(utterance: str) -> list[str]:
    """'open youtube and set the volume to 20' -> the two orders.

    Handing the whole sentence to a 2B model was unreliable — asked for GitHub
    and a volume, it answered with a tab and a search and forgot the volume.
    Split at the conjunction and each half becomes a simple order the fast
    paths and the model both handle well.
    """
    parts, rest = [], utterance
    while True:
        found = _SECOND_INTENT.search(rest.lower())
        if not found:
            break
        parts.append(rest[:found.start()].strip())
        rest = re.sub(r"^(?:and|then|also|after that)\s+", "",
                      rest[found.start():].strip(), flags=re.IGNORECASE)
    parts.append(rest.strip())
    return [p.strip(" ,.") for p in parts if p.strip(" ,.")]


def _resolve_utterance(utterance: str, ledger: Ledger) -> str:
    """Customs, then the deterministic fast paths, then the planner.

    The fast paths are exact but each resolves a SINGLE intent, so anything
    compound is handed to the model instead — it is the only part of Alfred
    that can plan several steps. Raises Refusal.
    """
    from .customs import HouseCustoms
    plan = HouseCustoms().match(utterance)
    if plan is not None:
        ledger.record(event="plan", source="customs", utterance=utterance)
        return plan
    if is_compound(utterance):
        from . import config
        steps, refused = [], []
        for clause in split_clauses(utterance):
            try:  # each clause gets the whole pipeline, model included
                steps.extend(json.loads(_resolve_utterance(clause, ledger)).get("plan", []))
            except Refusal as refusal:
                refused.append(f"{clause} ({refusal})")
        if not steps:
            raise Refusal("I couldn't make sense of any of that, sir.")
        if refused:  # never drop part of an order silently
            print(f"  (I can't do: {'; '.join(refused)})")
        ledger.record(event="plan", source="compound", utterance=utterance,
                      clauses=len(steps))
        return json.dumps({"plan": steps[:config.MAX_PLAN_STEPS]})
    # an already-open tab beats opening a second copy of the same page.
    # Deliberately deterministic and local: no tab title ever reaches the model.
    from . import tabs
    wanted_tab = tabs.spoken_tab_name(utterance)
    if wanted_tab and tabs.VIEW.match(wanted_tab) is not None:
        ledger.record(event="plan", source="tab", utterance=utterance)
        steps = [{"action": "focus_tab", "args": {"name": wanted_tab}}]
        if tabs.wants_play_after(utterance):  # "...tab and play"
            steps.append({"action": "media_control", "args": {"command": "play_pause"}})
        return json.dumps({"plan": steps})
    from . import vocab
    # a spoken domain is unambiguous — never let the model search around it
    url = vocab.url_lookup(utterance)
    if url is not None:
        ledger.record(event="plan", source="spoken-url", utterance=utterance)
        return json.dumps({"plan": [{"action": "open_url", "args": {"url": url}}]})
    # "play X on spotify" is exact enough to resolve without the model guessing
    url = vocab.play_lookup(utterance)
    if url is not None:
        ledger.record(event="plan", source="play", utterance=utterance)
        return json.dumps({"plan": [{"action": "play_media", "args": {"url": url}}]})
    url = vocab.site_lookup(utterance)
    if url is not None:
        ledger.record(event="plan", source="bookmark", utterance=utterance)
        return json.dumps({"plan": [{"action": "open_url", "args": {"url": url}}]})
    from .planner import PROMPT_VERSION, Planner
    plan, _ = Planner().plan(utterance)  # raises Refusal on a decline
    ledger.record(event="plan", source="llm",
                  prompt_version=PROMPT_VERSION, utterance=utterance)
    return plan


def _voice_loop(executor: Executor, ledger: Ledger, preapproved: bool) -> int:
    from . import voice
    print("Push-to-talk: Enter, then speak (5s). Say 'Alfred, stop' to ring "
          "the bell, 'mute'/'unmute' for my voice. Ctrl+C dismisses me.")
    muted = [False]

    def speak(text: str) -> None:  # honours the mute word
        if not muted[0]:
            voice.speak(text)

    while True:
        try:
            input("[Enter to speak] ")
        except (EOFError, KeyboardInterrupt):
            voice.speak("Very good, sir.")
            return 0
        from . import fieldlog
        raw = voice.transcribe(voice.record())
        print(f'  heard: "{raw}"')
        if not raw:
            fieldlog.record(outcome="empty", raw="")
            continue
        # his own name addresses him, it isn't part of the order
        from .web import _strip_wake
        addressed = _strip_wake(raw)
        if not addressed:
            speak("You have my attention, sir.")
            continue
        # second hearing: the LLM repairs likely mishears from the vocabulary
        from .planner import correct_transcript
        transcript = correct_transcript(addressed)
        if transcript != raw:
            print(f'  taking that as: "{transcript}"')
        if voice.is_stop(transcript):
            executor.abort.set()
            ledger.record(event="bell", transcript=transcript)
            speak("As you were, sir.")
            executor.abort.clear()
            fieldlog.record(outcome="bell", raw=raw, corrected=transcript)
            continue
        if voice.is_undo(transcript):
            handle = executor.undo.undo_last()
            if handle is None:
                print("  nothing to undo, sir")
                speak("Nothing to undo, sir.")
            else:
                ledger.record(event="undo", action=handle.action, detail=handle.description)
                print(f"  undone: {handle.description}")
                speak("Undone, sir.")
            fieldlog.record(outcome="undo", raw=raw, corrected=transcript)
            continue
        if voice.is_unmute(transcript):
            muted[0] = False
            voice.speak("Voice restored, sir.")
            fieldlog.record(outcome="unmute", raw=raw, corrected=transcript)
            continue
        if voice.is_mute(transcript):
            muted[0] = True
            print("  (voice muted — say 'unmute' to restore)")
            fieldlog.record(outcome="mute", raw=raw, corrected=transcript)
            continue
        from . import clearance, settings
        instruction = clearance.clearance_instruction(transcript)
        if instruction is not None:  # "I confirm Alfred, ..."
            change = clearance.parse_self_config(instruction)
            if change is None:
                print("  clearance accepted — but no setting caught")
                speak("I didn't catch which setting, sir.")
            else:
                key, value = change
                settings.save({key: value})
                print(f"  {key} = {value} (effective next summons)")
                speak(f"Done, sir — {key.replace('_', ' ')} is now {value}.")
                fieldlog.record(outcome="clearance", raw=raw, detail=f"{key}={value}")
            continue
        # resolve first: the user approves the PLAN, not just the words
        from .gate import describe
        from .registry import Tier
        from .validator import plan_tier
        try:
            steps = validate_plan(_resolve_utterance(transcript, ledger))
        except Refusal as refusal:
            fieldlog.record(outcome="refusal", raw=raw, corrected=transcript,
                            detail=str(refusal))
            from .web import _strip_wake
            query = _strip_wake(transcript)
            if not query:
                print(refusal)
                speak(str(refusal))
                continue
            print(f'  didn\'t follow, sir — shall I search "{query}"?')
            speak(f"I didn't quite follow, sir. Shall I search for {query}?")
            if not voice.heard_confirmation():
                speak(voice.stand_down())
                continue
            steps = validate_plan(json.dumps(
                {"plan": [{"action": "web_search", "args": {"query": query}}]}))
            fieldlog.record(outcome="fallback", raw=raw, corrected=transcript,
                            detail=f"search: {query}")
        print("  he would:")  # shown, never spoken back
        for step in steps:
            print("   - " + describe(step))
        fieldlog.record(outcome="plan", raw=raw, corrected=transcript,
                        detail="; ".join(describe(s) for s in steps))

        def _run() -> None:
            results = executor.run(steps, intent=transcript)
            for result in results:
                print(f"  [{'ok' if result.ok else 'XX'}] {result.action}: {result.detail}")
            speak(voice.nod() if all(r.ok for r in results) else voice.apologize())

        def _decline() -> None:
            speak(voice.stand_down())
            ledger.record(event="voice_declined", transcript=transcript)

        tier = plan_tier(steps)
        if tier <= Tier.ANNOUNCED:  # read-only / reversible — just do it
            _run()
        elif tier is Tier.CONFIRM:
            speak("Shall I proceed, sir?")
            _run() if voice.heard_confirmation() else _decline()
        else:  # UNDER_SEAL — the spoken word can't carry the seal
            speak("That reaches your files, sir — type your approval.")
            typed = input(f'  type exactly "{SEAL_PHRASE}": ') if sys.stdin.isatty() else ""
            _run() if is_seal_phrase(typed) else _decline()


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
    elif command == "apps":
        from . import config
        if rest[:1] == ["scan"]:
            import yaml

            from .adapters.apps import scan_start_menu
            apps = scan_start_menu()
            config.APPS_FILE.parent.mkdir(parents=True, exist_ok=True)
            config.APPS_FILE.write_text(yaml.safe_dump(apps, sort_keys=True),
                                        encoding="utf-8")
            print(f"{len(apps)} applications registered, sir "
                  f"({config.APPS_FILE}) — effective on my next summons.")
        else:
            print(f"Apps on the menu ({len(config.ALLOWED_APPS)}):")
            for name in sorted(config.ALLOWED_APPS):
                print("  " + name)
    elif command == "remember":
        # alfred remember go ledger = https://ledger.example.com/portfolio
        from . import vocab
        phrase = " ".join(rest)
        name, sep, url = phrase.partition("=")
        if not sep or not name.strip() or not url.strip().startswith("http"):
            print('Usage, sir: alfred remember <name> = <https://...>')
        else:
            vocab.remember(name, url)
            print(f'Committed to memory, sir: "{name.strip().lower()}" -> {url.strip()}')
            print('Say "open ' + name.strip().lower() + '" and I shall.')
    elif command == "hear":
        # alfred hear cloud = claude
        from . import vocab
        said, sep, meant = " ".join(rest).partition("=")
        if not sep:
            corrections = vocab.load_hearing()
            if not corrections:
                print("No hearing corrections yet, sir. "
                      "Usage: alfred hear <what I hear> = <what you mean>")
            for k, v in corrections.items():
                print(f'  "{k}" -> "{v}"')
        elif not said.strip() or not meant.strip():
            print('Usage, sir: alfred hear <what I hear> = <what you mean>')
        else:
            vocab.teach_hearing(said, meant)
            print(f'Noted, sir: when I hear "{said.strip().lower()}" '
                  f'I shall take it as "{meant.strip()}".')
    elif command == "forget":
        from . import vocab
        name = " ".join(rest).strip().lower()
        shortcuts = vocab.load_shortcuts()
        if shortcuts.pop(name, None) is None:
            print(f"I have no shortcut called '{name}', sir.")
        else:
            import yaml
            vocab.SHORTCUTS_FILE.write_text(
                yaml.safe_dump({"shortcuts": shortcuts}, sort_keys=True), encoding="utf-8")
            print(f"Forgotten, sir: {name}")
    elif command == "gestures":
        from . import gestures
        if rest[:1] == ["setup"]:
            print("Fetching the hand model, sir…")
            gestures.download_model()
            print(f"Ready: {gestures.MODEL_FILE}")
        elif not gestures.available():
            print("The [vision] extra isn't installed, sir "
                  "(pip install -e .[vision]).")
        else:
            bindings = gestures.load_bindings()["bindings"]
            print("Bound gestures: " + ", ".join(f"{g} -> {p}" for g, p in bindings.items()))
            print("A preview window will open so you can see what I see.")
            print("Esc (or Ctrl+C) closes it. This is a test — nothing is executed.")
            seen = []

            def show(name: str) -> None:
                seen.append(name)
                print(f"  seen: {name:<10} -> {bindings.get(name) or '(unbound)'}")

            watch = gestures.Watch(on_gesture=show, preview=True)
            try:
                watch.run()  # blocking, on the main thread — OpenCV prefers it
            except KeyboardInterrupt:
                pass
            finally:
                watch.stop()
                print(f"\nCamera released, sir. {len(seen)} gesture(s) recognised.")
    elif command == "fieldlog":
        from . import fieldlog
        if rest[:1] == ["clear"]:
            fieldlog.clear()
            print("Field log wiped, sir — a fresh testing run begins.")
        else:
            print(fieldlog.summary())
    elif command == "learn":
        from . import vocab
        vocabulary = vocab.build_vocabulary()
        print(f"Committed to memory, sir: {len(vocabulary['sites'])} bookmarked "
              f"sites (plus the app roster) — my hearing is tuned to them now.")
    else:
        raise Refusal(f"I don't recognise '{command}', sir. Try: menu, ask, act, plan, undo, ledger, burn.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    preapproved = "--yes" in argv
    argv = [a for a in argv if a != "--yes"]

    if argv[:1] == ["web"]:
        from .web import main as web_main
        return web_main()
    if argv[:1] == ["stop"]:
        from .web import stop_running
        return stop_running()
    if argv[:1] == ["install"]:
        from .shortcut import install
        made = install()
        if not made:
            print("I couldn't place a shortcut, sir.")
            return 1
        for link in made:
            print(f"Placed: {link}")
        print("Double-click it and I shall appear — no terminal needed.")
        return 0
    if argv[:1] == ["uninstall"]:
        from .shortcut import uninstall
        gone = uninstall()
        print(f"Removed {len(gone)} shortcut(s), sir." if gone
              else "There was no shortcut to remove, sir.")
        return 0
    if argv[:1] == ["keys"]:
        from .globalkeys import diagnose
        return diagnose()
    if argv[:1] == ["hud"]:
        from .hud import main as hud_main
        return hud_main()
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
    if argv[:1] == ["doctor"]:
        from .doctor import main as doctor_main
        return doctor_main()

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
