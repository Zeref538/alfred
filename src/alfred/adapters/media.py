"""Media keys via the OS virtual-key interface.

These are Alfred's *own* deterministic key taps for the four media controls —
the planner still cannot emit arbitrary keystrokes; only these fixed codes
exist, chosen by validated enum.

set_volume needs pycaw (the `[media]` extra); without it the adapter reports
itself unavailable rather than approximating.
"""

import ctypes

from .. import schemas
from ..undo import RevertHandle

_KEYEVENTF_KEYUP = 0x0002
_MEDIA_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
}


def _tap(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def media_control(args: schemas.MediaControl) -> None:
    _tap(_MEDIA_KEYS[args.command])


def _endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def set_volume(args: schemas.SetVolume) -> RevertHandle:
    try:
        volume = _endpoint()
    except ImportError:
        raise RuntimeError("set_volume requires the [media] extra (pycaw)") from None
    previous = volume.GetMasterVolumeLevelScalar()
    volume.SetMasterVolumeLevelScalar(args.level / 100, None)
    return RevertHandle(
        "set_volume",
        f"restore volume to {round(previous * 100)}",
        lambda: _endpoint().SetMasterVolumeLevelScalar(previous, None),
    )
