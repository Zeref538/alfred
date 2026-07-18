"""The butler's ears and voice.

- Ears: push-to-talk recording (sounddevice) transcribed by faster-whisper,
  entirely local — audio never leaves the machine.
- Voice: Windows SAPI via a fixed PowerShell argv; text travels over stdin,
  never through string interpolation (same discipline as the clipboard).
- The bell, spoken: any transcript that is essentially "Alfred, stop" sets
  the abort event and nothing else happens.

Requires the [voice] extra (faster-whisper, sounddevice) for the ears; the
voice itself needs nothing beyond Windows.
"""

import os
import random
import re
import subprocess
import tempfile
from pathlib import Path

from . import config

SAMPLE_RATE = 16_000
RECORD_SECONDS = 5
CONFIRM_SECONDS = 3.5

# The butler's voice: a local Piper model (British, JARVIS-adjacent) when
# present, Windows SAPI otherwise. ALFRED_TTS=sapi forces the fallback.
# Pace, loudness, and model names live in settings (env still wins).
VOICES_DIR = config.DATA_DIR / "voices"

_DONE = ["Very good, sir.", "Done, sir.", "As you wish.",
         "Consider it done, sir.", "At once, sir.", "All handled, sir."]
_STAND_DOWN = ["As you were, sir.", "Very well, sir.", "Standing down, sir.",
               "Of course — not a finger lifted."]
_SORRY = ["My apologies, sir — do see the panel.",
          "Something went sideways, sir.", "That one got away from me, sir."]


def nod() -> str:
    return random.choice(_DONE)


def stand_down() -> str:
    return random.choice(_STAND_DOWN)


def apologize() -> str:
    return random.choice(_SORRY)

_SPEAK = ["powershell", "-NoProfile", "-Command",
          "Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.Speak([Console]::In.ReadToEnd())"]

_SPEAK_TO_WAV = ["powershell", "-NoProfile", "-Command",
                 "Add-Type -AssemblyName System.Speech; "
                 "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                 "$s.SetOutputToWaveFile($env:ALFRED_TTS_WAV); "
                 "$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()"]

_model = None


def _piper_model() -> Path | None:
    if os.environ.get("ALFRED_TTS") == "sapi":
        return None
    from . import settings
    model = VOICES_DIR / f"{settings.get('piper_voice')}.onnx"
    return model if model.exists() else None


_piper = None


def piper_to_wav(text: str, wav_path: str) -> bool:
    """Synthesize with the local Piper voice (cached in-process — ~0.1s a
    line after the one-time model load). False if Piper isn't set up."""
    global _piper
    model = _piper_model()
    if model is None:
        return False
    if _piper is None:
        from piper import PiperVoice
        _piper = PiperVoice.load(str(model))
    import wave

    from piper import SynthesisConfig

    from . import settings
    style = SynthesisConfig(length_scale=1.0 / float(settings.get("voice_pace")),
                            volume=float(settings.get("voice_volume")))
    with wave.open(wav_path, "wb") as wav:
        _piper.synthesize_wav(text, wav, syn_config=style)
    return True


def speak(text: str) -> None:
    wav_path = Path(tempfile.gettempdir()) / "alfred_says.wav"
    if piper_to_wav(text, str(wav_path)):
        import winsound
        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        return
    subprocess.run(_SPEAK, input=text.encode("utf-8"), capture_output=True, timeout=60)


def speak_to_wav(text: str, wav_path: str) -> None:
    """Render speech to a WAV file — used by the loopback tests as a stand-in
    for a human at the microphone."""
    subprocess.run(_SPEAK_TO_WAV, input=text.encode("utf-8"), capture_output=True,
                   timeout=60, env={**os.environ, "ALFRED_TTS_WAV": wav_path})


def transcribe(audio) -> str:
    """audio: a WAV path or a float32 numpy array at SAMPLE_RATE. Known app
    and bookmark names bias the decoding (whisper hotwords)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        from . import settings
        _model = WhisperModel(settings.get("whisper"), device="cpu",
                              compute_type="int8")
    from . import vocab
    known = vocab.hotwords() or None
    segments, _ = _model.transcribe(audio, language="en", beam_size=1,
                                    hotwords=known)
    return " ".join(segment.text.strip() for segment in segments).strip()


def record(seconds: float = RECORD_SECONDS):
    import sounddevice as sd
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                    channels=1, dtype="float32")
    sd.wait()
    return frames[:, 0]


def is_stop(transcript: str) -> bool:
    words = re.sub(r"[^a-z ]", "", transcript.lower()).split()
    return "stop" in words and (len(words) <= 3 or "alfred" in words)


def is_yes(transcript: str) -> bool:
    """A spoken confirmation. Anything negative wins over anything positive —
    a mishear must never confirm itself."""
    text = re.sub(r"[^a-z ]", "", transcript.lower())
    words = set(text.split())
    if words & {"no", "not", "dont", "stop", "negative", "cancel", "belay", "never"}:
        return False
    return bool(words & {"yes", "yeah", "confirm", "proceed", "aye", "engage"}) \
        or "go ahead" in text or "do it" in text


def heard_confirmation() -> bool:
    """Listen briefly for a spoken yes."""
    return is_yes(transcribe(record(CONFIRM_SECONDS)))
