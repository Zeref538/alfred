"""The household vocabulary: bookmark parsing, hotwords, the site fast path."""

import json

import pytest

from alfred import vocab

BOOKMARKS = {
    "roots": {
        "bookmark_bar": {"type": "folder", "children": [
            {"type": "url", "name": "GitHub", "url": "https://github.com"},
            {"type": "folder", "name": "study", "children": [
                {"type": "url", "name": "AI-102 Guide",
                 "url": "https://learn.microsoft.com/ai-102"},
                {"type": "url", "name": "evil", "url": "javascript:alert(1)"},
            ]},
        ]},
        "other": {"type": "folder", "children": []},
    }
}


@pytest.fixture
def vocab_file(tmp_path, monkeypatch):
    monkeypatch.setattr(vocab, "VOCAB_FILE", tmp_path / "vocabulary.yaml")
    return tmp_path


def test_read_bookmarks_walks_folders_and_keeps_http_only(tmp_path):
    path = tmp_path / "Bookmarks"
    path.write_text(json.dumps(BOOKMARKS), encoding="utf-8")
    marks = vocab.read_bookmarks(path)
    assert marks == {"github": "https://github.com",
                     "ai-102 guide": "https://learn.microsoft.com/ai-102"}


def test_corrupt_bookmarks_file_reads_as_empty(tmp_path):
    path = tmp_path / "Bookmarks"
    path.write_text("not json", encoding="utf-8")
    assert vocab.read_bookmarks(path) == {}


def test_site_lookup_fuzzy_matches_open_phrases(vocab_file, monkeypatch):
    vocab.VOCAB_FILE.write_text(
        "sites:\n  github: https://github.com\n  ai-102 guide: https://learn.microsoft.com\n",
        encoding="utf-8")
    assert vocab.site_lookup("open github") == "https://github.com"
    assert vocab.site_lookup("take me to the ai 102 guide") == "https://learn.microsoft.com"
    assert vocab.site_lookup("open the gith ub") == "https://github.com"
    assert vocab.site_lookup("set the volume to twenty") is None
    assert vocab.site_lookup("open something unbookmarked") is None


def test_common_sites_open_without_the_model(vocab_file, monkeypatch):
    # no bookmarks — well-known sites still resolve deterministically
    vocab.VOCAB_FILE.write_text("sites: {}\n", encoding="utf-8")
    assert vocab.site_lookup("open youtube") == "https://youtube.com"
    assert vocab.site_lookup("go to reddit") == "https://reddit.com"
    assert vocab.site_lookup("open youtub") == "https://youtube.com"  # small mishear
    assert vocab.site_lookup("open nature") is None       # unknown -> planner decides
    assert vocab.site_lookup("what time is it") is None   # not an open phrase


def test_bookmarks_win_over_common_sites(vocab_file, monkeypatch):
    vocab.VOCAB_FILE.write_text(
        "sites:\n  youtube: https://my.private.tube/home\n", encoding="utf-8")
    assert vocab.site_lookup("open youtube") == "https://my.private.tube/home"


def test_deterministic_correction_repairs_split_names(vocab_file, monkeypatch):
    monkeypatch.setattr("alfred.config.ALLOWED_APPS",
                        {"spotify": "x", "notepad": "y"})
    vocab.VOCAB_FILE.write_text("sites:\n  github: https://github.com\n",
                                encoding="utf-8")
    assert "spotify" in vocab.correct("open spot if i")
    assert vocab.correct("launch note pad") == "launch notepad"
    assert vocab.correct("go to get hub") == "go to github"
    assert vocab.correct("set the volume to twenty") == "set the volume to twenty"


def test_hotwords_are_capped_cleaned_and_deduped(vocab_file, monkeypatch):
    sites = {f"site {i}": f"https://x{i}.example" for i in range(200)}
    vocab.VOCAB_FILE.write_text(
        "sites:\n" + "".join(f"  {k}: {v}\n" for k, v in sites.items()),
        encoding="utf-8")
    words = vocab.hotwords().split(", ")
    assert len(words) == vocab.MAX_HOTWORDS
    assert all(w == w.lower() for w in words)
