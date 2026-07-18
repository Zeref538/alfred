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
import re
import subprocess

SAMPLE_RATE = 16_000
RECORD_SECONDS = 5
WHISPER_MODEL = os.environ.get("ALFRED_WHISPER", "base")

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


def speak(text: str) -> None:
    subprocess.run(_SPEAK, input=text.encode("utf-8"), capture_output=True, timeout=60)


def speak_to_wav(text: str, wav_path: str) -> None:
    """Render speech to a WAV file — used by the loopback tests as a stand-in
    for a human at the microphone."""
    subprocess.run(_SPEAK_TO_WAV, input=text.encode("utf-8"), capture_output=True,
                   timeout=60, env={**os.environ, "ALFRED_TTS_WAV": wav_path})


def transcribe(audio) -> str:
    """audio: a WAV path or a float32 numpy array at SAMPLE_RATE."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(audio, language="en", beam_size=1)
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
