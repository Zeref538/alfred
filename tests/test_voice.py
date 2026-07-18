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
