"""Global hold-to-talk: press J and K together, from any window, to open the
mic on the running HUD — you don't have to click into the page first.

Letter keys are deliberate (the master's choice). To keep ordinary typing from
firing it, only a *true simultaneous hold* triggers: both keys must be down at
once, which almost never happens while typing (there the keys go down and up one
at a time). The turn lock downstream still guarantees one command at a time.

Needs the [hotkey] extra (the `keyboard` library); absent, the HUD simply runs
without the global chord and the in-page J+K still works.
"""

HOLD_KEYS = ("j", "k")


def hold_keys() -> tuple:
    """The configured hold-to-talk chord, e.g. ('j', 'k'). Falls back to J+K."""
    from . import settings
    parts = [k.strip().lower() for k in settings.get("hold_keys").split("+") if k.strip()]
    return tuple(parts) if len(parts) >= 2 else HOLD_KEYS


class Chord:
    """A simultaneous-hold detector, independent of any input library so it can
    be tested: feed it press()/release() names, it calls on_start when every key
    is held at once and on_stop when the hold breaks."""

    def __init__(self, keys, on_start, on_stop):
        self.keys = set(keys)
        self.on_start = on_start
        self.on_stop = on_stop
        self.held: set = set()
        self.active = False

    def press(self, name: str) -> None:
        if name not in self.keys:
            return
        self.held.add(name)
        if not self.active and self.keys <= self.held:
            self.active = True
            self.on_start()

    def release(self, name: str) -> None:
        if name not in self.keys:
            return
        self.held.discard(name)
        if self.active and not self.keys <= self.held:
            self.active = False
            self.on_stop()


def available() -> bool:
    try:
        import keyboard  # noqa: F401
        return True
    except Exception:
        return False


def watch(on_start, on_stop) -> None:
    """Arm the global J+K chord. on_start/on_stop should return quickly — wrap
    any slow work (recording, transcription) in a thread so the system-wide
    keyboard hook is never blocked."""
    import keyboard
    chord = Chord(hold_keys(), on_start, on_stop)
    keyboard.on_press(lambda e: chord.press((e.name or "").lower()))
    keyboard.on_release(lambda e: chord.release((e.name or "").lower()))
