"""The field log records testing turns and never lets logging break a command."""

import alfred.fieldlog as fieldlog


def test_record_read_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldlog, "FIELDLOG_FILE", tmp_path / "fieldlog.jsonl")
    fieldlog.record(outcome="plan", raw="volume thirty", corrected="volume 30")
    fieldlog.record(outcome="refusal", raw="delete everything", detail="off menu")
    entries = fieldlog.read()
    assert [e["outcome"] for e in entries] == ["plan", "refusal"]
    assert all("ts" in e for e in entries)
    fieldlog.clear()
    assert fieldlog.read() == []


def test_summary_counts_weak_turns_and_mishears(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldlog, "FIELDLOG_FILE", tmp_path / "fieldlog.jsonl")
    fieldlog.record(outcome="plan", raw="spot if I", corrected="spotify")  # mishear
    fieldlog.record(outcome="empty", raw="")                               # weak
    fieldlog.record(outcome="refusal", raw="format c drive", detail="no")  # weak
    text = fieldlog.summary()
    assert "3 turns" in text and "2 weak" in text and "1 corrected mishear" in text


def test_logging_never_raises_on_a_bad_path(tmp_path, monkeypatch):
    # a directory where the file should be — writing must swallow the error
    bad = tmp_path / "wall"
    bad.mkdir()
    monkeypatch.setattr(fieldlog, "FIELDLOG_FILE", bad)
    fieldlog.record(outcome="plan", raw="hello")  # must not raise
