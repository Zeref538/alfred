"""The gesture classifier is a pure function of 21 landmarks, so the computer
vision is testable with no camera and no model — synthetic hands only."""

import pytest

from alfred import gestures


def hand(index=False, middle=False, ring=False, pinky=False, thumb=False):
    """Build 21 (x, y) landmarks. y grows downward, so an extended finger puts
    its tip ABOVE (smaller y than) its PIP joint."""
    points = [(0.5, 0.9)] * 21          # wrist-ish default
    points[0] = (0.5, 0.9)              # wrist
    points[5] = (0.5, 0.6)              # index knuckle, the thumb reference
    # thumb: extended = tip (4) farther from knuckle (5) than IP (3) is
    points[3] = (0.45, 0.7)
    points[4] = (0.20, 0.5) if thumb else (0.47, 0.68)
    for name, extended in (("index", index), ("middle", middle),
                           ("ring", ring), ("pinky", pinky)):
        tip, pip = gestures._TIPS[name], gestures._PIPS[name]
        points[pip] = (0.5, 0.6)
        points[tip] = (0.5, 0.4) if extended else (0.5, 0.7)
    return points


def test_open_palm():
    assert gestures.classify(
        hand(index=True, middle=True, ring=True, pinky=True, thumb=True)) == "open_palm"


def test_fist():
    assert gestures.classify(hand()) == "fist"


def test_thumbs_up_is_a_fist_with_the_thumb_out():
    assert gestures.classify(hand(thumb=True)) == "thumbs_up"


def test_peace_and_point():
    assert gestures.classify(hand(index=True, middle=True)) == "peace"
    assert gestures.classify(hand(index=True)) == "point"


def test_unreadable_hands_are_none():
    assert gestures.classify(None) is None
    assert gestures.classify([(0.5, 0.5)] * 5) is None          # too few landmarks
    assert gestures.classify(hand(middle=True, ring=True)) is None  # no such sign


def test_bindings_default_and_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(gestures, "BINDINGS_FILE", tmp_path / "gestures.yaml")
    loaded = gestures.load_bindings()
    assert loaded["bindings"]["open_palm"] == "at ease"
    assert (tmp_path / "gestures.yaml").exists()   # written out for editing
    assert gestures.phrase_for("fist") == "quiet hours"
    assert gestures.phrase_for("nonesuch") is None


def test_bad_bindings_fall_back_to_defaults(tmp_path, monkeypatch):
    bad = tmp_path / "gestures.yaml"
    bad.write_text("bindings: not-a-mapping\n", encoding="utf-8")
    monkeypatch.setattr(gestures, "BINDINGS_FILE", bad)
    assert gestures.load_bindings()["bindings"] == gestures.DEFAULT_BINDINGS["bindings"]


def test_watch_refuses_without_the_model(tmp_path, monkeypatch):
    monkeypatch.setattr(gestures, "MODEL_FILE", tmp_path / "absent.task")
    monkeypatch.setattr(gestures, "available", lambda: True)
    with pytest.raises(RuntimeError, match="gestures setup"):
        gestures.Watch(lambda g: None).start()
