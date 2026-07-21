"""The global J+K chord: only a true simultaneous hold fires, so ordinary
typing (keys down and up one at a time) never triggers it."""

from alfred.globalkeys import Chord


def _chord():
    events = []
    return Chord(("j", "k"), lambda: events.append("start"),
                 lambda: events.append("stop")), events


def test_simultaneous_hold_starts_then_release_stops():
    chord, events = _chord()
    chord.press("j")
    assert events == []          # one key alone does nothing
    chord.press("k")
    assert events == ["start"]   # both down — fire
    chord.release("k")
    assert events == ["start", "stop"]  # hold broken — stop


def test_sequential_typing_never_triggers():
    chord, events = _chord()
    for key in ("j", "k"):       # typed one at a time: down, up, down, up
        chord.press(key)
        chord.release(key)
    assert events == []


def test_extra_presses_do_not_refire():
    chord, events = _chord()
    chord.press("j")
    chord.press("k")
    chord.press("j")   # auto-repeat while held
    chord.press("k")
    assert events == ["start"]   # only one start
    chord.release("j")
    chord.release("k")
    assert events == ["start", "stop"]


def test_tap_debounces_autorepeat_but_rearms():
    from alfred.globalkeys import Tap
    now = [100.0]
    taps = []
    tap = Tap(lambda: taps.append(1), interval=0.6, clock=lambda: now[0])
    assert tap.tap() and len(taps) == 1      # first press counts
    now[0] += 0.05
    assert not tap.tap() and len(taps) == 1  # auto-repeat while held: ignored
    now[0] += 0.05
    assert not tap.tap() and len(taps) == 1
    now[0] += 1.0
    assert tap.tap() and len(taps) == 2      # a genuine second press re-arms


def test_toggle_reads_real_state_not_a_remembered_flag(tmp_path):
    # the live failure: a remembered flag desynced and the chord stuck forever.
    # toggle_listening must decide from whether the recorder actually exists.
    from alfred.executor import Executor
    from alfred.ledger import Ledger
    from alfred.undo import UndoManager
    from alfred.web import Session
    session = Session(executor=Executor({}, Ledger(root=tmp_path), UndoManager()))
    calls = []
    session.hold_start = lambda: calls.append("start")
    session.hold_stop = lambda: calls.append("stop")
    assert not session.listening()
    session.toggle_listening()
    assert calls == ["start"]
    session._recorder = object()          # the mic is genuinely open now
    assert session.listening()
    session.toggle_listening()
    assert calls == ["start", "stop"]


def test_other_keys_are_ignored():
    chord, events = _chord()
    chord.press("a")
    chord.press("j")
    chord.press("k")
    chord.release("a")
    assert events == ["start"]
