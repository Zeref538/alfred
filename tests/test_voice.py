"""The bell phrase must be caught generously but not greedily; the loopback
test (SAPI speaks into a WAV, whisper reads it back) runs locally only —
CI has no need to download a speech model."""

import os

import pytest

from alfred.voice import is_stop


@pytest.mark.parametrize("heard", [
    "Alfred, stop.", "alfred stop", "Stop, Alfred!", "Stop!", "stop",
    "Alfred... stop that",
])
def test_stop_phrases_ring_the_bell(heard):
    assert is_stop(heard)


@pytest.mark.parametrize("heard", [
    "search for bus stops near me",
    "open the stopwatch website",
    "when does the music stop playing in that film",
    "set the volume to twenty",
    "",
])
def test_ordinary_speech_does_not_ring_the_bell(heard):
    assert not is_stop(heard)


@pytest.mark.parametrize("heard", [
    "Yes.", "yes please", "Confirm.", "go ahead", "do it", "Aye, proceed.",
])
def test_spoken_yes_confirms(heard):
    from alfred.voice import is_yes
    assert is_yes(heard)


@pytest.mark.parametrize("heard", [
    "", "no", "not yet", "don't do it", "yes... no, cancel that",
    "stop", "negative", "set the volume to twenty",
])
def test_anything_else_stands_down(heard):
    from alfred.voice import is_yes
    assert not is_yes(heard)


@pytest.mark.parametrize("heard", ["mute", "Mute.", "mute yourself", "mute please"])
def test_mute_word_is_caught(heard):
    from alfred.voice import is_mute, is_unmute
    assert is_mute(heard) and not is_unmute(heard)


@pytest.mark.parametrize("heard", ["unmute", "Un-mute.", "unmute please", "un mute"])
def test_unmute_word_is_caught_and_never_reads_as_mute(heard):
    from alfred.voice import is_mute, is_unmute
    assert is_unmute(heard) and not is_mute(heard)


@pytest.mark.parametrize("heard", ["set the volume to twenty", "commute to work", ""])
def test_ordinary_speech_is_not_a_mute(heard):
    from alfred.voice import is_mute, is_unmute
    assert not is_mute(heard) and not is_unmute(heard)


def test_greeting_varies_and_matches_the_hour(monkeypatch):
    from alfred.voice import _GREETINGS, greeting, time_of_day
    assert len(_GREETINGS) >= 20, "the boot line should not get stale"
    seen = {greeting() for _ in range(200)}
    assert len(seen) >= 10, "greetings should actually vary"
    assert all("{tod}" not in g for g in seen), "the time token must be filled"
    assert time_of_day() in ("morning", "afternoon", "evening")
    # every greeting renders cleanly for every half of the day
    for phrase in _GREETINGS:
        assert phrase.format(tod="morning")


def test_confidence_gate():
    from alfred.voice import is_confident
    assert is_confident(-0.3, 0.05)       # a clear hearing
    assert not is_confident(-2.4, 0.05)   # words, but whisper was guessing
    assert not is_confident(-0.3, 0.95)   # confident-sounding noise: no speech
    assert not is_confident(0.0, 1.0)     # nothing decoded at all


@pytest.mark.parametrize("heard", ["undo", "Undo.", "undo that", "undo the last one"])
def test_undo_word_is_caught(heard):
    from alfred.voice import is_undo
    assert is_undo(heard)


@pytest.mark.parametrize("heard", [
    "open my undo folder in the browser", "search how to undo a git commit", ""])
def test_ordinary_speech_is_not_an_undo(heard):
    from alfred.voice import is_undo
    assert not is_undo(heard)


def test_muted_session_stays_silent(monkeypatch, tmp_path):
    import alfred.voice as voice_mod
    from alfred.executor import Executor
    from alfred.ledger import Ledger
    from alfred.undo import UndoManager
    from alfred.web import Session
    spoken = []
    monkeypatch.setattr(voice_mod, "speak", lambda t: spoken.append(t))
    session = Session(executor=Executor({}, Ledger(root=tmp_path), UndoManager()))
    session._speak("audible")
    session._muted = True
    session._speak("silenced")
    assert spoken == ["audible"]


@pytest.mark.skipif(os.environ.get("CI") is not None, reason="no model downloads in CI")
def test_piper_british_voice_is_intelligible(tmp_path):
    from alfred.voice import _piper_model, piper_to_wav, transcribe

    if _piper_model() is None:
        pytest.skip("no piper voice model installed")
    wav = str(tmp_path / "alfred.wav")
    assert piper_to_wav("Very good, sir. The study session is prepared.", wav)
    heard = transcribe(wav).lower()
    assert "very good" in heard and "study session" in heard


@pytest.mark.skipif(os.environ.get("CI") is not None, reason="no model downloads in CI")
def test_loopback_tts_to_whisper(tmp_path):
    from alfred.voice import speak_to_wav, transcribe

    wav = str(tmp_path / "loopback.wav")
    speak_to_wav("set the volume to twenty five", wav)
    heard = transcribe(wav).lower()
    assert "volume" in heard and ("twenty five" in heard or "25" in heard)


@pytest.mark.parametrize("heard", [
    "thank you", "Thanks!", "thank you alfred", "that will be all",
    "that's all", "no thanks", "nothing else",
])
def test_thanks_closes_the_conversation(heard):
    from alfred.voice import is_thanks
    assert is_thanks(heard)


@pytest.mark.parametrize("heard", [
    "open youtube", "set the volume to twenty", "play thanks for the memories",
    "", "search for thanksgiving recipes",
])
def test_ordinary_speech_keeps_it_open(heard):
    from alfred.voice import is_thanks
    assert not is_thanks(heard)
