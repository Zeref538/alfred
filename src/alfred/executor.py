"""Runs a cleared plan through deterministic adapters — nothing else runs anything.

Kill-switch semantics, defined: the abort flag is checked between steps,
every adapter call runs under a timeout, executed steps stay in the ledger.
An adapter may return a RevertHandle; those go to the undo stack.
"""

import threading
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from .ledger import Ledger
from .undo import RevertHandle, UndoManager
from .validator import PlanStep

Adapter = Callable[[BaseModel], RevertHandle | None]

ADAPTER_TIMEOUT_S = 15.0


@dataclass
class StepResult:
    action: str
    ok: bool
    detail: str


class Executor:
    def __init__(
        self,
        adapters: dict[str, Adapter],
        ledger: Ledger,
        undo: UndoManager,
        abort: threading.Event | None = None,
    ):
        self.adapters = adapters
        self.ledger = ledger
        self.undo = undo
        self.abort = abort or threading.Event()

    def run(self, steps: list[PlanStep], intent: str) -> list[StepResult]:
        results: list[StepResult] = []
        for step in steps:
            if self.abort.is_set():
                self.ledger.record(event="abort", intent=intent,
                                   remaining=[s.spec.name for s in steps[len(results):]])
                results.append(StepResult(step.spec.name, False, "aborted by the bell"))
                break
            results.append(self._run_step(step, intent))
        return results

    def _run_step(self, step: PlanStep, intent: str) -> StepResult:
        adapter = self.adapters.get(step.spec.name)
        if adapter is None:
            result = StepResult(step.spec.name, False, "no adapter available")
        else:
            outcome: dict = {}

            def call() -> None:
                try:
                    outcome["handle"] = adapter(step.args)
                except Exception as e:  # adapter failures are reported, never raised
                    outcome["error"] = f"{type(e).__name__}: {e}"

            worker = threading.Thread(target=call, daemon=True)
            worker.start()
            worker.join(ADAPTER_TIMEOUT_S)
            if worker.is_alive():
                result = StepResult(step.spec.name, False, "timed out")
            elif "error" in outcome:
                result = StepResult(step.spec.name, False, outcome["error"])
            else:
                handle = outcome.get("handle")
                if isinstance(handle, RevertHandle):
                    self.undo.push(handle)
                result = StepResult(step.spec.name, True, "done")

        self.ledger.record(
            event="action",
            intent=intent,
            action=step.spec.name,
            args=step.args.model_dump(),
            tier=int(step.spec.tier),
            reversible=step.spec.reversible,
            ok=result.ok,
            detail=result.detail,
        )
        return result
