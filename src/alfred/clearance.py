"""Highest clearance: the master's own voice reconfiguring Alfred.

A command that begins with the phrase **"I confirm Alfred"** is treated as an
authorized self-config instruction — the only way Alfred changes his own hotkeys
by voice or text. Without the phrase he will not touch his configuration.

Parsing is deterministic and *bounded*: only the two hotkey settings can be
changed this way, nothing else. Typed instructions parse cleanly; spoken ones
are best-effort (single spoken letters are what whisper is least sure of).

    "I confirm Alfred, set the hold keys to g and h"   -> hold_keys = "g+h"
    "I confirm Alfred, set the summon hotkey to ctrl alt j" -> summon_hotkey = "ctrl+alt+j"
"""

import re

PHRASE = "i confirm alfred"
_MODIFIERS = ("ctrl", "control", "alt", "shift", "win", "cmd")


def clearance_instruction(text: str) -> str | None:
    """The instruction after the clearance phrase, or None if unauthorized."""
    cleaned = re.sub(r"[^a-z0-9 +]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned.startswith(PHRASE):
        return None
    return cleaned[len(PHRASE):].strip()


def _tokens(rest: str) -> list[str]:
    return [t for t in re.split(r"[ +]|\band\b", rest) if t]


def parse_self_config(instruction: str) -> tuple[str, str] | None:
    """('hold_keys', 'g+h') or ('summon_hotkey', 'ctrl+alt+j'), or None."""
    hold = re.search(r"hold(?:ing)?(?:[ -]?to[ -]?talk)?\s*keys?\s+(?:to\s+)?(.+)",
                     instruction)
    if hold:
        letters = [t for t in _tokens(hold.group(1)) if len(t) == 1 and t.isalnum()]
        if len(letters) >= 2:
            return ("hold_keys", "+".join(letters[:3]))

    summon = re.search(r"(?:summon|wake|hot ?key|shortcut)\s*(?:hotkey|key)?\s*(?:to\s+)?(.+)",
                       instruction)
    if summon:
        tokens = _tokens(summon.group(1))
        mods = [t for t in tokens if t in _MODIFIERS]
        keys = [t for t in tokens if len(t) == 1 and t.isalnum()]
        if mods and keys:
            mods = ["ctrl" if m == "control" else "win" if m == "cmd" else m for m in mods]
            return ("summon_hotkey", "+".join(mods + [keys[-1]]))
    return None
