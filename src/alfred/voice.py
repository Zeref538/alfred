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

_GREETINGS = [
    "Good {tod}, sir. All systems are nominal.",
    "Good {tod}, sir. Alfred is online and at your service.",
    "Good {tod}, sir. Everything is in order.",
    "Good {tod}, sir. The house is in order and I am listening.",
    "At your service, sir. All systems nominal this {tod}.",
    "Good {tod}, sir. Standing by.",
    "Good {tod}, sir. Awaiting your instruction.",
    "Alfred online, sir. Systems nominal.",
    "Good {tod}, sir. Ready when you are.",
    "Good {tod}, sir. All quiet, and all working.",
    "Systems nominal, sir. A very good {tod} to you.",
    "Good {tod}, sir. Shall we begin?",
    "Good {tod}, sir. The service menu is open.",
    "Back at your side, sir. Good {tod}.",
    "Good {tod}, sir. Everything checks out.",
    "Alfred reporting, sir. All systems nominal this {tod}.",
    "Good {tod}, sir. I have the house well in hand.",
    "Good {tod}, sir. Whenever you're ready.",
    "At your service this {tod}, sir. Nothing amiss.",
    "Good {tod}, sir. All stations green.",
    "Good {tod}, sir. I'm listening.",
    "Good {tod}, sir. The bell is answered.",
]


def time_of_day() -> str:
    import datetime
    hour = datetime.datetime.now().hour
    return "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


def greeting() -> str:
    """A fresh boot line each summoning, and the right half of the day —
    'good evening' at ten in the morning rather gives the game away."""
    return random.choice(_GREETINGS).format(tod=time_of_day())


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
    subprocess.run(_SPEAK, input=text.encode("utf-8"), capture_output=True, timeout=60,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def speak_to_wav(text: str, wav_path: str) -> None:
    """Render speech to a WAV file — used by the loopback tests as a stand-in
    for a human at the microphone."""
    subprocess.run(_SPEAK_TO_WAV, input=text.encode("utf-8"), capture_output=True,
                   timeout=60, env={**os.environ, "ALFRED_TTS_WAV": wav_path},
                   creationflags=subprocess.CREATE_NO_WINDOW)


# Whisper's own doubt. Below this mean log-probability, or above this
# no-speech probability, a hearing is not to be acted on without asking —
# this is what catches noise decoded as confident-sounding nonsense.
CONFIDENT_LOGPROB = -0.9
MAX_NO_SPEECH = 0.6


def transcribe_with_quality(audio):
    """(text, mean avg_logprob, max no_speech_prob).

    audio: a WAV path or a float32 numpy array at SAMPLE_RATE. Known app and
    bookmark names bias the decoding (whisper hotwords). The two numbers let a
    caller decline to act on a hearing whisper itself wasn't sure of."""
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
    found = list(segments)
    text = " ".join(segment.text.strip() for segment in found).strip()
    if not found:
        return text, 0.0, 1.0
    mean_logprob = sum(s.avg_logprob for s in found) / len(found)
    return text, mean_logprob, max(s.no_speech_prob for s in found)


def transcribe(audio) -> str:
    return transcribe_with_quality(audio)[0]


def is_confident(mean_logprob: float, no_speech: float) -> bool:
    return mean_logprob >= CONFIDENT_LOGPROB and no_speech <= MAX_NO_SPEECH


def record(seconds: float = RECORD_SECONDS):
    import sounddevice as sd
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                    channels=1, dtype="float32")
    sd.wait()
    return frames[:, 0]


# Waiting for a pause is what lets a conversation run without a key for every
# sentence: he listens until you stop, rather than for a fixed five seconds.
SILENCE_RMS = 0.012      # below this a block counts as quiet
SILENCE_HANG = 1.1       # this much quiet, after speech, ends the turn
LEAD_IN = 4.0            # but wait this long for a first word before giving up
MAX_UTTERANCE = 16.0


def record_until_silence(max_seconds: float = MAX_UTTERANCE):
    """Record until the master stops speaking. Returns whatever was said, or an
    empty array if he never started."""
    import numpy as np
    import sounddevice as sd
    block = int(0.1 * SAMPLE_RATE)
    frames, quiet, spoke, elapsed = [], 0.0, False, 0.0
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=block) as stream:
        while elapsed < max_seconds:
            chunk, _ = stream.read(block)
            frames.append(chunk.copy())
            elapsed += 0.1
            loud = float(np.sqrt(np.mean(np.square(chunk))))
            if loud > SILENCE_RMS:
                spoke, quiet = True, 0.0
            else:
                quiet += 0.1
                if spoke and quiet >= SILENCE_HANG:
                    break
                if not spoke and elapsed >= LEAD_IN:
                    return np.zeros(0, dtype="float32")
    return np.concatenate(frames)[:, 0] if frames else np.zeros(0, dtype="float32")


_THANKS = ("thank you", "thanks", "thank u", "that will be all", "thats all",
           "that is all", "that would be all", "no thanks", "nothing else",
           "thats it", "that is it")


def is_thanks(transcript: str) -> bool:
    """'thank you' closes the conversation — politer than reaching for a key.

    It must come at the END of what was said, and stand as its own words.
    Merely containing the letters is not enough: "play thanks for the memories"
    is an order, and "search for thanksgiving recipes" is a question, and
    hanging up on either would be a small betrayal.
    """
    text = re.sub(r"['’]", "", transcript.lower())
    text = " ".join(re.sub(r"[^a-z ]", " ", text).split())
    # "thank you alfred" and "thanks, please" end with courtesies, not orders
    text = re.sub(r"(?:\s+(?:alfr\w*|unfr\w*|elfr\w*|please|sir|now|then))+$",
                  "", text).strip()
    return any(text == phrase or text.endswith(" " + phrase)
               for phrase in _THANKS)


def strip_thanks(transcript: str) -> str:
    """The command spoken before a trailing sign-off, if any.

    "system check, thank you" is a command that happens to end politely, not
    an empty pleasantry — is_thanks() alone can't tell those apart from a
    bare "thank you sir", so callers that want to still act on the order
    should check this instead of discarding the whole utterance.
    """
    text = re.sub(r"['’]", "", transcript.lower())
    text = " ".join(re.sub(r"[^a-z ]", " ", text).split())
    text = re.sub(r"(?:\s+(?:alfr\w*|unfr\w*|elfr\w*|please|sir|now|then))+$",
                  "", text).strip()
    for phrase in _THANKS:
        if text == phrase:
            return ""
        if text.endswith(" " + phrase):
            return text[: -len(phrase) - 1].strip()
    return transcript


class Recorder:
    """Hold-to-talk: open the mic on key-down, close it on key-up, keep the
    frames in between. Used by the HUD's push-to-talk keys."""

    def __init__(self):
        self._frames: list = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=lambda indata, frames, t, status: self._frames.append(indata.copy()))
        self._stream.start()

    def stop(self):
        import numpy as np
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        return (np.concatenate(self._frames)[:, 0] if self._frames
                else np.zeros(0, dtype="float32"))


def warm_up() -> None:
    """Load whisper and the piper voice ahead of the first request, and nudge
    Ollama to page the planner model in. Meant for a background thread at
    HUD start — first mic press then answers in ~1s instead of ~40."""
    try:
        import numpy as np
        transcribe(np.zeros(SAMPLE_RATE // 2, dtype="float32"))
    except Exception:
        pass
    try:
        piper_to_wav("Ready.", str(Path(tempfile.gettempdir()) / "alfred_warm.wav"))
    except Exception:
        pass
    try:
        from .planner import Planner
        Planner().plan("warm up")
    except Exception:  # a Refusal is fine — the model is loaded either way
        pass


def is_stop(transcript: str) -> bool:
    words = re.sub(r"[^a-z ]", "", transcript.lower()).split()
    return "stop" in words and (len(words) <= 3 or "alfred" in words)


def is_unmute(transcript: str) -> bool:
    words = set(re.sub(r"[^a-z ]", "", transcript.lower()).split())
    return bool(words & {"unmute", "unmuted"}) or "un mute" in transcript.lower()


def is_mute(transcript: str) -> bool:
    """'mute' means silence Alfred's own voice — but never when it's 'unmute'."""
    if is_unmute(transcript):
        return False
    return "mute" in set(re.sub(r"[^a-z ]", "", transcript.lower()).split())


def is_shutdown(transcript: str) -> bool:
    """'shutdown' / 'stand down' — put down everything he is doing at once.

    This closes ALFRED's own work: the running plan, the conversation, the
    microphone, the camera. It does not touch the master's machine — that
    remains off the menu, whatever the word sounds like.
    """
    words = re.sub(r"[^a-z ]", " ", transcript.lower()).split()
    if not words or len(words) > 4:
        return False
    joined = " ".join(words)
    return any(phrase in joined for phrase in
               ("shutdown", "shut down", "stand down", "stand everything down",
                "close everything", "power down"))


def is_undo(transcript: str) -> bool:
    """'undo' / 'undo that' / 'undo the last one' — revert the last command."""
    words = re.sub(r"[^a-z ]", "", transcript.lower()).split()
    return "undo" in words and len(words) <= 4


_SYSTEM_CHECK = ("system check", "check system", "run a system check",
                  "run system check", "check the system", "how are you doing",
                  "how is the system", "check your vitals", "run diagnostics",
                  "run a diagnostic", "check vitals")


def is_system_check(transcript: str) -> bool:
    """'system check' — CPU/GPU/disk/memory and the rest of `alfred doctor`,
    same as the HUD's chip. Short and fixed, like the other meta-commands
    above, so it's answered directly rather than sent through the planner,
    which has no matching action in the service menu."""
    text = " ".join(re.sub(r"[^a-z ]", " ", transcript.lower()).split())
    return text in _SYSTEM_CHECK


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
