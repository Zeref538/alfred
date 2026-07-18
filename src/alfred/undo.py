"""Undo manager: a LIFO stack of revert handles from reversible actions.

Adapters that change state return a RevertHandle capturing how to put things
back; "Alfred, undo that" pops and runs the most recent one.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class RevertHandle:
    action: str
    description: str  # human-readable, also written to the ledger
    revert: Callable[[], None]


class UndoManager:
    def __init__(self) -> None:
        self._stack: list[RevertHandle] = []

    def push(self, handle: RevertHandle) -> None:
        self._stack.append(handle)

    def undo_last(self) -> RevertHandle | None:
        """Revert and return the most recent reversible act, or None."""
        if not self._stack:
            return None
        handle = self._stack.pop()
        handle.revert()
        return handle

    def __len__(self) -> int:
        return len(self._stack)
