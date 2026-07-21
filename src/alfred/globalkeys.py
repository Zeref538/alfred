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


REARM_SECONDS = 0.6


class Tap:
    """Debounce for the chord.

    Nothing here may depend on key *releases*: in practice they don't reach us,
    which is what broke both hold-to-talk (nothing closed the mic) and the
    first latch (the chord stayed forever engaged, so a second press did
    nothing). A tap is accepted only once per re-arm window, so a held chord
    that auto-repeats still counts as one press.
    """

    def __init__(self, on_tap, interval: float = REARM_SECONDS, clock=None):
        import time
        self.on_tap = on_tap
        self.interval = interval
        self.clock = clock or time.monotonic
        self.last = float("-inf")

    def tap(self) -> bool:
        now = self.clock()
        if now - self.last < self.interval:
            return False
        self.last = now
        self.on_tap()
        return True


def available() -> bool:
    try:
        import keyboard  # noqa: F401
        return True
    except Exception:
        return False


def diagnose(seconds: int = 15) -> int:
    """`alfred keys` — run this yourself in a terminal and press the chord.

    A global keyboard hook only receives events when the process owns an
    interactive desktop session; a HUD started by some other tool may not.
    This says plainly whether the hook sees your keys, and whether the chord
    fires, without guessing.
    """
    import time
    if not available():
        print("The [hotkey] extra isn't installed, sir (pip install -e .[hotkey]).")
        return 1
    import keyboard
    keys = hold_keys()
    combo = "+".join(keys)
    print(f"Watching for {seconds}s, sir. Tap {combo.upper()} a few times, "
          "and press some other keys too.")
    downs, ups, fired = [], [], []
    keyboard.on_press(lambda e: downs.append((e.name or "").lower()))
    keyboard.on_release(lambda e: ups.append((e.name or "").lower()))
    tap = Tap(lambda: fired.append(1))
    keyboard.add_hotkey(combo, tap.tap, trigger_on_release=False, suppress=False)
    time.sleep(seconds)

    print(f"key-down events seen: {len(downs)}  {sorted(set(downs))[:10]}")
    print(f"key-UP   events seen: {len(ups)}  {sorted(set(ups))[:10]}")
    print(f"{combo.upper()} fired: {len(fired)} time(s)")
    if not downs:
        print("\nVerdict: no global key events at all — this process has no "
              "interactive desktop, or another tool owns the hook.")
        return 1
    if not ups:
        print("\nVerdict: presses arrive but RELEASES do not. That is exactly "
              "what broke hold-to-talk; the chord now avoids depending on them.")
    if fired:
        print("\nVerdict: the chord fires — global press-to-listen works.")
        return 0
    print(f"\nVerdict: keys arrive but {combo.upper()} never fired. Press both "
          "together, sir; if it still never fires the hotkey is being swallowed.")
    return 1


def watch(on_toggle) -> None:
    """Arm the global chord: press it to begin listening, press it again to
    send. `on_toggle` decides which of the two it is by asking what is actually
    happening — never by remembering, which is how the state got stuck before.

    It must return quickly: wrap slow work (recording, transcription) in a
    thread so the system-wide keyboard hook is never blocked.
    """
    import keyboard
    tap = Tap(on_toggle)
    # keyboard's own hotkey machinery owns the key state, so we never depend
    # on receiving releases ourselves
    keyboard.add_hotkey("+".join(hold_keys()), tap.tap,
                        trigger_on_release=False, suppress=False)
