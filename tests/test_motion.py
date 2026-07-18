"""The motion detector's judgment, fed synthetic frames — no camera, no cv2."""

import numpy as np

from alfred.motion import Detector, SUSTAINED_FRAMES

QUIET = np.zeros((120, 160), dtype=np.uint8)
LOUD_A = np.zeros((120, 160), dtype=np.uint8)
LOUD_B = np.full((120, 160), 255, dtype=np.uint8)


def test_stillness_never_rings():
    detector = Detector()
    assert not any(detector.observe(QUIET) for _ in range(50))


def test_one_flicker_is_ignored():
    detector = Detector()
    detector.observe(QUIET)
    assert not detector.observe(LOUD_B)  # single spike, not sustained
    assert not any(detector.observe(QUIET) for _ in range(10))


def test_sustained_wave_rings_once_then_cools_down():
    detector = Detector()
    detector.observe(QUIET)
    rings = []
    frames = [LOUD_A, LOUD_B] * (SUSTAINED_FRAMES + 2)
    for frame in frames:
        rings.append(detector.observe(frame))
    assert rings.count(True) == 1  # rings exactly once, then cooldown holds
