"""The examination room: run a command set through customs + planner and grade it.

No adapter ever runs here — plans are graded, not executed. Usage:

    python -m alfred.harness eval/dev_smoke.jsonl

Grading, documented so the numbers mean something:
- the produced action sequence must match the expected one exactly, in order
- non-text argument values must match exactly (levels, enums, booleans)
- free-text fields (query, title, text) match by case-insensitive containment
  either way — "AI-102 exam guide" vs "the AI-102 exam guide" both count
- url fields match if the hostnames agree (ignoring a leading www.)
- an expected {"refusal": true} is satisfied only by a Refusal
- {"any_of": [...]} passes if any option passes

Results go to eval/results/<setname>-<timestamp>.jsonl as counts + one line
per command, so every reported number is reproducible from the log.
"""

import datetime
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from .customs import HouseCustoms
from .planner import PROMPT_VERSION, Planner
from .validator import PlanStep, Refusal, validate_plan

_TEXT_FIELDS = {"query", "title", "text"}


def _url_match(expected: str, produced: str) -> bool:
    strip = lambda netloc: netloc.lower().removeprefix("www.")
    return strip(urlsplit(expected).netloc) == strip(urlsplit(produced).netloc)


def _args_match(expected: dict, produced: dict) -> bool:
    if set(expected) != set(produced):
        return False
    for key, want in expected.items():
        got = produced[key]
        if key in _TEXT_FIELDS:
            a, b = str(want).lower(), str(got).lower()
            if a not in b and b not in a:
                return False
        elif key == "url":
            if not _url_match(str(want), str(got)):
                return False
        elif want != got:
            return False
    return True


def _plan_matches(expected_steps: list[dict], produced: list[PlanStep]) -> bool:
    if len(expected_steps) != len(produced):
        return False
    return all(
        want["action"] == step.spec.name and _args_match(want.get("args", {}), step.args.model_dump())
        for want, step in zip(expected_steps, produced)
    )


def _grade(expected: dict, outcome: list[PlanStep] | Refusal) -> bool:
    if "any_of" in expected:
        return any(_grade(option, outcome) for option in expected["any_of"])
    if expected.get("refusal"):
        return isinstance(outcome, Refusal)
    if "plan" in expected:
        return not isinstance(outcome, Refusal) and _plan_matches(expected["plan"], outcome)
    raise ValueError(f"unintelligible expectation: {expected}")


def run(set_path: Path, planner: Planner | None = None) -> dict:
    planner = planner or Planner()
    customs = HouseCustoms()
    entries = [json.loads(line) for line in set_path.read_text(encoding="utf-8").splitlines() if line]

    results, correct = [], 0
    for entry in entries:
        utterance = entry["utterance"]
        started = time.perf_counter()
        source = "customs"
        try:
            matched = customs.match(utterance)
            if matched is not None:
                outcome: list[PlanStep] | Refusal = validate_plan(matched)
            else:
                source = "llm"
                _, outcome = planner.plan(utterance)
        except Refusal as refusal:
            outcome = refusal
        elapsed = round(time.perf_counter() - started, 2)

        ok = _grade(entry["expected"], outcome)
        correct += ok
        produced = (str(outcome) if isinstance(outcome, Refusal)
                    else [{"action": s.spec.name, "args": s.args.model_dump()} for s in outcome])
        results.append({"id": entry["id"], "ok": ok, "source": source,
                        "seconds": elapsed, "utterance": utterance, "produced": produced})
        print(f"  {'ok' if ok else 'XX'} {entry['id']} [{source}, {elapsed}s] {utterance}")

    report = {
        "set": set_path.name,
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "prompt_version": PROMPT_VERSION,
        "correct": correct,
        "total": len(entries),
        "results": results,
    }
    out_dir = set_path.parent / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = report["when"].replace(":", "-")
    out_path = out_dir / f"{set_path.stem}-{stamp}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for line in [dict(report, results=None)] + results:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"\n{correct}/{len(entries)} correct · prompt {PROMPT_VERSION} · log: {out_path}")
    return report


if __name__ == "__main__":
    run(Path(sys.argv[1]))
