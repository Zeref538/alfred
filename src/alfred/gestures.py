"""Hand gestures: a camera the master opens, never one that watches him.

Two hard rules, both structural:

- **On demand only.** The webcam is opened when a gesture watch is explicitly
  started and released the moment it stops. Nothing here runs at startup, and
  no frame is ever stored, uploaded, or fed to the planner.
- **No shortcut past the gate.** A recognised gesture does not *do* anything.
  It resolves its bound phrase through the ordinary pipeline — customs or
  planner, then the validator, then the etiquette gate — and because a gesture
  is a low-precision input, the plan is always confirmed before it runs.

The classifier is a pure function of 21 hand landmarks, so it is testable
without a camera; `alfred gestures` is a live preview that recognises and
prints, executing nothing.

Needs the [vision] extra (mediapipe, opencv-python) and a one-time model:
    alfred gestures setup
"""

import math

from . import config

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_FILE = config.DATA_DIR / "models" / "hand_landmarker.task"
BINDINGS_FILE = config.DATA_DIR / "gestures.yaml"

# a gesture must persist this many frames before it counts, then rest —
# the same debounce discipline as the motion bell
STEADY_FRAMES = 6
COOLDOWN_FRAMES = 45

DEFAULT_BINDINGS = {
    "bindings": {
        "open_palm": "at ease",
        "fist": "quiet hours",
        "peace": "study session",
        "thumbs_up": "work mode",
    }
}

# The hand as a skeleton: which landmarks are joined by a bone. Wrist 0, then
# thumb, index, middle, ring, pinky outward, with the palm strung across.
HAND_BONES = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (9, 10), (10, 11), (11, 12),               # middle
    (13, 14), (14, 15), (15, 16),              # ring
    (0, 17), (17, 18), (18, 19), (19, 20),     # pinky
    (5, 9), (9, 13), (13, 17),                 # across the palm
]

_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
_PIPS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}


def _extended(points) -> dict:
    """Which fingers stand proud, from 21 (x, y) landmarks."""
    out = {}
    for name, tip in _TIPS.items():
        out[name] = points[tip][1] < points[_PIPS[name]][1]  # y grows downward
    # the thumb splays sideways: its tip sits farther from the index knuckle
    out["thumb"] = (math.dist(points[4], points[5]) > math.dist(points[3], points[5]))
    return out


def classify(points) -> str | None:
    """21 landmarks -> a gesture name, or None when it reads as nothing."""
    if points is None or len(points) != 21:
        return None
    up = _extended(points)
    fingers = [up["index"], up["middle"], up["ring"], up["pinky"]]
    if all(fingers) and up["thumb"]:
        return "open_palm"
    if fingers == [True, True, False, False]:
        return "peace"
    if fingers == [True, False, False, False]:
        return "point"
    if not any(fingers):
        return "thumbs_up" if up["thumb"] else "fist"
    return None


def load_bindings() -> dict:
    import yaml
    if not BINDINGS_FILE.exists():
        BINDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        BINDINGS_FILE.write_text(yaml.safe_dump(DEFAULT_BINDINGS, sort_keys=True),
                                 encoding="utf-8")
        return dict(DEFAULT_BINDINGS)
    try:
        doc = yaml.safe_load(BINDINGS_FILE.read_text(encoding="utf-8")) or {}
        bindings = doc.get("bindings")
        return {"bindings": {str(k): str(v) for k, v in bindings.items()}} \
            if isinstance(bindings, dict) else dict(DEFAULT_BINDINGS)
    except Exception:
        return dict(DEFAULT_BINDINGS)


def phrase_for(gesture: str) -> str | None:
    return load_bindings()["bindings"].get(gesture)


def model_ready() -> bool:
    return MODEL_FILE.exists()


def download_model() -> None:
    import urllib.request
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)


def available() -> bool:
    try:
        import cv2  # noqa: F401
        from mediapipe.tasks.python import vision  # noqa: F401
        return True
    except Exception:
        return False


class Watch:
    """A webcam gesture watch. Opens the camera on start(), releases on stop().

    on_gesture(name) fires once per steady gesture, then rests for a cooldown so
    a held hand doesn't machine-gun the butler.
    """

    def __init__(self, on_gesture, camera: int = 0, preview: bool = True,
                 stream: bool = False):
        self.on_gesture = on_gesture
        self.camera = camera
        self.preview = preview  # an OpenCV window, for the CLI test harness
        self.stream = stream    # keep the latest frame for the HUD to show
        self._stop = False
        self._thread = None
        self._jpeg = None

    def latest_jpeg(self):
        """The most recent annotated frame, or None. Held for exactly as long
        as it takes the next one to replace it."""
        return self._jpeg

    def _annotate(self, frame, points, gesture):
        """Draw the hand as a skeleton — the joints and the bones between them
        — so what the camera makes of you is plain to see, not merely asserted."""
        import cv2
        height, width = frame.shape[:2]
        if points:
            at = lambda i: (int(points[i][0] * width), int(points[i][1] * height))
            for a, b in HAND_BONES:
                cv2.line(frame, at(a), at(b), (255, 170, 90), 2, cv2.LINE_AA)
            for index in range(len(points)):
                tip = index in (4, 8, 12, 16, 20)
                cv2.circle(frame, at(index), 6 if tip else 4,
                           (120, 255, 200) if tip else (255, 220, 140), -1,
                           cv2.LINE_AA)
            label, colour = (gesture or "hand — no known sign"), (120, 255, 200)
        else:
            label, colour = "no hand in view", (150, 150, 150)
        cv2.rectangle(frame, (0, 0), (width, 34), (18, 8, 30), -1)
        cv2.putText(frame, f"ALFRED  |  {label}", (12, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, colour, 2, cv2.LINE_AA)
        return frame

    def _draw(self, frame, points, gesture):
        """The CLI preview window. False once Esc is pressed."""
        import cv2
        cv2.imshow("Alfred - gesture preview", frame)
        return (cv2.waitKey(1) & 0xFF) != 27

    def _loop(self) -> None:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_FILE)),
            num_hands=1)
        capture = cv2.VideoCapture(self.camera)
        steady, last, resting = 0, None, 0
        try:
            with vision.HandLandmarker.create_from_options(options) as landmarker:
                while not self._stop:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = landmarker.detect(image)
                    points = ([(p.x, p.y) for p in result.hand_landmarks[0]]
                              if result.hand_landmarks else None)
                    gesture = classify(points)
                    # annotate through the cooldown too, so the picture never
                    # freezes while he's resting
                    if self.preview or self.stream:
                        shown = self._annotate(frame, points, gesture)
                        if self.stream:
                            ok, buffer = cv2.imencode(
                                ".jpg", shown, [cv2.IMWRITE_JPEG_QUALITY, 72])
                            if ok:
                                self._jpeg = buffer.tobytes()
                        if self.preview and not self._draw(shown, points, gesture):
                            break
                    if resting > 0:
                        resting -= 1
                        continue
                    steady = steady + 1 if (gesture and gesture == last) else 0
                    last = gesture
                    if gesture and steady >= STEADY_FRAMES:
                        steady, resting = 0, COOLDOWN_FRAMES
                        self.on_gesture(gesture)
        finally:
            capture.release()  # the eye closes the moment we're done
            if self.preview:
                try:
                    cv2.destroyWindow("Alfred - gesture preview")
                except Exception:
                    pass

    def _guard(self) -> None:
        if not available():
            raise RuntimeError("The [vision] extra isn't installed, sir "
                               "(pip install -e .[vision]).")
        if not model_ready():
            raise RuntimeError("The hand model isn't here yet, sir — "
                               "run `alfred gestures setup`.")

    def run(self) -> None:
        """Blocking watch on the calling thread — right for the CLI preview,
        where OpenCV's window wants the main thread."""
        self._guard()
        self._stop = False
        self._loop()

    def start(self) -> None:
        import threading
        self._guard()
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
