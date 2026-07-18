"""The motion stop bell: a webcam that can only ever say "stop".

Deliberately powerless — motion is a noisy sensor, so it gets exactly one
capability: ringing the bell (abort). It cannot form or confirm commands.
Opt-in per session from the web HUD, off by default, and the frames never
leave the process.

Requires the [motion] extra (opencv-python).
"""

import threading

# a sustained, large change between frames counts as a deliberate wave
MOTION_THRESHOLD = 28.0   # mean absolute gray delta (0-255)
SUSTAINED_FRAMES = 4
COOLDOWN_FRAMES = 60


def frame_delta(previous, current) -> float:
    """Mean absolute difference between two grayscale frames (numpy arrays)."""
    if previous is None or previous.shape != current.shape:
        return 0.0
    diff = abs(current.astype("int16") - previous.astype("int16"))
    return float(diff.mean())


class Detector:
    """Pure decision logic — testable with synthetic frames, no camera."""

    def __init__(self) -> None:
        self._previous = None
        self._hot = 0
        self._cooldown = 0

    def observe(self, gray_frame) -> bool:
        """Feed one grayscale frame; True means ring the bell."""
        delta = frame_delta(self._previous, gray_frame)
        self._previous = gray_frame
        if self._cooldown > 0:
            self._cooldown -= 1
            return False
        self._hot = self._hot + 1 if delta >= MOTION_THRESHOLD else 0
        if self._hot >= SUSTAINED_FRAMES:
            self._hot = 0
            self._cooldown = COOLDOWN_FRAMES
            return True
        return False


class StopBell(threading.Thread):
    def __init__(self, on_motion) -> None:
        try:
            import cv2  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "The motion bell needs the [motion] extra (opencv-python), sir."
            ) from None
        super().__init__(daemon=True)
        self.on_motion = on_motion
        self._stop = threading.Event()

    def run(self) -> None:
        import cv2

        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            self.on_motion = None
            return
        detector = Detector()
        try:
            while not self._stop.is_set():
                ok, frame = camera.read()
                if not ok:
                    break
                gray = cv2.cvtColor(cv2.resize(frame, (160, 120)),
                                    cv2.COLOR_BGR2GRAY)
                if detector.observe(gray) and self.on_motion is not None:
                    self.on_motion()
        finally:
            camera.release()

    def stop(self) -> None:
        self._stop.set()
