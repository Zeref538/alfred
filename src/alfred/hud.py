"""The overlay HUD: a small always-on-top window over the same one door.

Pure stdlib Tkinter — no web server, no sockets, no new dependencies, and
therefore none of the localhost attack surface THREATMODEL.md warns about.

The pipeline (customs → planner → validator → gate → executor) runs on a
worker thread; the etiquette gate renders as UI: Tier 1 is a cancelable
countdown banner, Tier 2 is an explicit pair of consent buttons. Typed
input is an `ask` utterance; /commands mirror the palette.
"""

import queue
import threading
import tkinter as tk

from .adapters import build_adapters
from .executor import Executor
from .gate import Etiquette, clear_plan
from .ledger import Ledger
from .registry import REGISTRY
from .undo import UndoManager
from .validator import Refusal, validate_plan

ANNOUNCE_SECONDS = 2.0

_BG, _FG, _ACCENT, _DIM = "#16161e", "#e6e0cf", "#e0c060", "#8a8677"


def route(text: str) -> tuple[str, str]:
    """'/undo' → ('undo', ''), '/menu' → ('menu', ''), anything else → ask."""
    text = text.strip()
    if text.startswith("/"):
        command, _, rest = text[1:].partition(" ")
        return command.lower(), rest.strip()
    return "ask", text


class Hud:
    def __init__(self) -> None:
        self.ledger = Ledger()
        self.undo = UndoManager()
        self.executor = Executor(build_adapters(), self.ledger, self.undo)

        self.root = tk.Tk()
        self.root.title("Alfred")
        self.root.attributes("-topmost", True)
        self.root.configure(bg=_BG)
        self.root.geometry("+80+80")
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        tk.Label(self.root, text="ALFRED — at your service",
                 bg=_BG, fg=_ACCENT, font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(10, 2))

        self.entry = tk.Entry(self.root, width=52, bg="#22222e", fg=_FG,
                              insertbackground=_FG, relief="flat",
                              font=("Segoe UI", 11))
        self.entry.pack(fill="x", padx=12, ipady=6)
        self.entry.bind("<Return>", self._submit)
        self.entry.focus_set()

        self.out = tk.Text(self.root, width=52, height=9, bg=_BG, fg=_FG,
                           relief="flat", font=("Consolas", 9), wrap="word",
                           state="disabled")
        self.out.pack(fill="both", expand=True, padx=12, pady=(6, 4))

        self.banner = tk.Frame(self.root, bg=_BG)
        self.banner.pack(fill="x", padx=12, pady=(0, 10))

        self.say(f'Good day, sir. Ask, or /menu /undo /ledger /burn. '
                 f'Esc dismisses me. ({len(REGISTRY)} services)')

    # --- UI plumbing ---------------------------------------------------------

    def ui(self, fn) -> None:
        self.root.after(0, fn)

    def say(self, text: str) -> None:
        def append() -> None:
            self.out.configure(state="normal")
            self.out.insert("end", text + "\n")
            self.out.see("end")
            self.out.configure(state="disabled")
        self.ui(append)

    def _clear_banner(self) -> None:
        for child in self.banner.winfo_children():
            child.destroy()

    # --- etiquette rendered as UI (called from the worker thread) ------------

    def _announce(self, summary: str) -> bool:
        answer: queue.Queue[bool] = queue.Queue()

        def show() -> None:
            self._clear_banner()
            label = tk.Label(self.banner, bg=_BG, fg=_DIM, font=("Segoe UI", 9))
            label.pack(side="left")
            tk.Button(self.banner, text="Belay that", relief="flat",
                      bg="#3a2a2a", fg=_FG,
                      command=lambda: answer.put(False)).pack(side="right")

            def tick(remaining: float) -> None:
                if not answer.empty():
                    return
                if remaining <= 0:
                    answer.put(True)
                    return
                label.configure(text=f"If I may ({remaining:.0f}s): {summary}")
                self.root.after(250, tick, remaining - 0.25)

            tick(ANNOUNCE_SECONDS)

        self.ui(show)
        result = answer.get()
        self.ui(self._clear_banner)
        return result

    def _confirm(self, summary: str) -> bool:
        answer: queue.Queue[bool] = queue.Queue()

        def show() -> None:
            self._clear_banner()
            tk.Label(self.banner, text=f"By your leave, sir: {summary}",
                     bg=_BG, fg=_ACCENT, font=("Segoe UI", 9),
                     wraplength=340, justify="left").pack(side="left")
            tk.Button(self.banner, text="Not now", relief="flat", bg="#3a2a2a",
                      fg=_FG, command=lambda: answer.put(False)).pack(side="right", padx=2)
            tk.Button(self.banner, text="Go ahead", relief="flat", bg="#2a3a2a",
                      fg=_FG, command=lambda: answer.put(True)).pack(side="right", padx=2)

        self.ui(show)
        result = answer.get()
        self.ui(self._clear_banner)
        return result

    # --- the work ------------------------------------------------------------

    def _submit(self, _event) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.say(f"> {text}")
        threading.Thread(target=self._work, args=(text,), daemon=True).start()

    def _work(self, text: str) -> None:
        command, rest = route(text)
        try:
            if command == "ask":
                self._ask(rest)
            elif command == "undo":
                handle = self.undo.undo_last()
                if handle is None:
                    self.say("Nothing to undo, sir.")
                else:
                    self.ledger.record(event="undo", action=handle.action,
                                       detail=handle.description)
                    self.say(f"Undone: {handle.description}.")
            elif command == "menu":
                for spec in REGISTRY.values():
                    self.say(f"  tier {int(spec.tier)} | {spec.name} - {spec.summary}")
            elif command == "ledger":
                for entry in self.ledger.today()[-8:] or [{"note": "an empty page, sir"}]:
                    self.say(f"  {entry}")
            elif command == "burn":
                self.ledger.burn_today()
                self.say("The day's page is ash, sir.")
            else:
                self.say(f"I don't recognise /{command}, sir.")
        except Refusal as refusal:
            self.say(str(refusal))
        except Exception as error:  # the HUD must never die mid-service
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")

    def _ask(self, utterance: str) -> None:
        from .palette import _resolve_utterance
        self.say("Very good, sir — one moment.")
        plan = _resolve_utterance(utterance, self.ledger)  # may raise Refusal
        steps = validate_plan(plan)
        clear_plan(steps, Etiquette(announce=self._announce, confirm=self._confirm))
        results = self.executor.run(steps, intent=utterance)
        for result in results:
            self.say(f"  [{'ok' if result.ok else 'XX'}] {result.action}: {result.detail}")
        if all(r.ok for r in results):
            self.say("Done, sir.")

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    return Hud().run()
