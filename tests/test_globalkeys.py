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


def test_other_keys_are_ignored():
    chord, events = _chord()
    chord.press("a")
    chord.press("j")
    chord.press("k")
    chord.release("a")
    assert events == ["start"]
