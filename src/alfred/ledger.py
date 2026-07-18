"""The butler's book: append-only JSONL, one page (file) per day.

Every act Alfred performs lands here — intent, action, tier, result, revert
note. Entries are never edited in place; "Alfred, burn the day's page"
removes the page entirely, which is the supported way to forget.
"""

import datetime
import json
from pathlib import Path

from . import config


RETENTION_DAYS = 30


class Ledger:
    def __init__(self, root: Path | None = None):
        self.root = (root or config.DATA_DIR) / "ledger"
        self.root.mkdir(parents=True, exist_ok=True)
        self._expire_old_pages()

    def _expire_old_pages(self) -> None:
        cutoff = datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS)
        for page in self.root.glob("*.jsonl"):
            try:
                if datetime.date.fromisoformat(page.stem) < cutoff:
                    page.unlink()
            except ValueError:
                continue  # not one of our pages; leave it be

    def _page(self) -> Path:
        return self.root / f"{datetime.date.today().isoformat()}.jsonl"

    def record(self, **entry: object) -> None:
        entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **entry}
        with self._page().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def today(self) -> list[dict]:
        page = self._page()
        if not page.exists():
            return []
        return [json.loads(line) for line in page.read_text(encoding="utf-8").splitlines() if line]

    def burn_today(self) -> None:
        self._page().unlink(missing_ok=True)
