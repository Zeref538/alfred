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
    # isolate BOTH files — the real ~/.alfred/shortcuts.yaml must never leak
    # into a test and change what site_lookup resolves to
    monkeypatch.setattr(vocab, "VOCAB_FILE", tmp_path / "vocabulary.yaml")
    monkeypatch.setattr(vocab, "SHORTCUTS_FILE", tmp_path / "shortcuts.yaml")
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


@pytest.mark.parametrize("junk", [
    "IDLE (Python 3.14 64-bit)", "ImageMagick Web Pages", "Python 3.12 Manuals",
    "AMD Software: Adrenalin Edition", "Application Verifier (x64)",
    "MSI Afterburner Localization Reference", "b1", "x",
])
def test_unspeakable_start_menu_junk_is_rejected(junk):
    # this is what whisper hallucinated back at us: version numbers and
    # multi-word technical names must never become hotwords
    assert vocab.speakable(junk) is None


@pytest.mark.parametrize("good", ["Notepad", "Discord", "Google Chrome", "youtube"])
def test_real_names_survive(good):
    assert vocab.speakable(good) == good.lower()


def test_hotwords_are_short_and_free_of_digits(vocab_file, monkeypatch):
    vocab.VOCAB_FILE.write_text(
        "sites:\n  youtube: https://youtube.com\n  netflix: https://netflix.com\n",
        encoding="utf-8")
    words = vocab.hotwords()
    assert "youtube" in words and "netflix" in words
    assert not any(ch.isdigit() for ch in words)
    assert len(words.split(", ")) <= vocab.MAX_HOTWORDS


def test_common_sites_open_without_the_model(vocab_file, monkeypatch):
    # no bookmarks — well-known sites still resolve deterministically
    vocab.VOCAB_FILE.write_text("sites: {}\n", encoding="utf-8")
    assert vocab.site_lookup("open youtube") == "https://youtube.com"
    assert vocab.site_lookup("go to reddit") == "https://reddit.com"
    assert vocab.site_lookup("open youtub") == "https://youtube.com"  # small mishear
    assert vocab.site_lookup("open nature") is None       # unknown -> planner decides
    assert vocab.site_lookup("what time is it") is None   # not an open phrase


def test_spoken_url_only_for_hosts_we_know(tmp_path, monkeypatch):
    monkeypatch.setattr(vocab, "SHORTCUTS_FILE", tmp_path / "shortcuts.yaml")
    monkeypatch.setattr(vocab, "VOCAB_FILE", tmp_path / "vocabulary.yaml")
    # github is in the well-known table, so a spoken domain resolves
    assert vocab.url_lookup("go to github dot com") == "https://github.com"
    assert vocab.url_lookup("set the volume to twenty") is None
    # THE LIVE FAILURE: whisper heard "chess" as "chest" and we opened
    # https://chest.com — a squatter's page. A host we cannot vouch for must
    # never be fabricated from speech; it falls through to a search instead.
    assert vocab.url_lookup("open zorblatt-widgets.com now") is None
    # chess.com is in the well-known table, so the mishearing lands correctly
    # without the master having to teach it
    assert vocab.url_lookup("open chest.com daily puzzles") == \
        "https://www.chess.com"
    # his own entry, path and all, outranks the built-in one
    vocab.remember("chess", "https://www.chess.com/daily")
    assert vocab.url_lookup("open chest.com") == "https://www.chess.com/daily"
    assert vocab.url_lookup("open chess.com slash daily puzzles") == \
        "https://chess.com/daily-puzzles"


def test_shortcuts_beat_everything_and_ignore_filler(tmp_path, monkeypatch):
    # the live failure: "my go trade tab" is an open TAB, never a bookmark
    monkeypatch.setattr(vocab, "SHORTCUTS_FILE", tmp_path / "shortcuts.yaml")
    monkeypatch.setattr(vocab, "VOCAB_FILE", tmp_path / "vocabulary.yaml")
    vocab.remember("go trade", "https://ultra.heygotrade.com/portfolio")
    for said in ("open my go trade investment tab", "open my go trade tab",
                 "open go trade"):
        assert vocab.site_lookup(said) == "https://ultra.heygotrade.com/portfolio"
    # a shortcut also outranks the built-in table
    vocab.remember("youtube", "https://my.private.tube")
    assert vocab.site_lookup("open my youtube tab") == "https://my.private.tube"


def test_correct_never_runs_away(tmp_path, monkeypatch):
    # THE LIVE FAILURE: with a shortcut "go trade", the word "trade" fuzzy-matched
    # it, became "go go trade", matched again, and recursed into
    # "open go go go go go ..." hundreds of words long.
    monkeypatch.setattr(vocab, "SHORTCUTS_FILE", tmp_path / "shortcuts.yaml")
    monkeypatch.setattr(vocab, "VOCAB_FILE", tmp_path / "vocabulary.yaml")
    vocab.remember("go trade", "https://ultra.heygotrade.com/portfolio")
    out = vocab.correct("open go trade tab")
    assert out.split().count("go") == 1
    assert len(out.split()) <= len("open go trade tab".split()) + 1


def test_play_keeps_prepositions_inside_titles():
    # stripping every "on" turned "attack on titan" into "attack titan"
    assert vocab.play_lookup("play attack on titan on crunchyroll") == \
        "https://www.crunchyroll.com/search?q=attack%20on%20titan"
    assert vocab.play_lookup("play malcolm in the middle on disney plus") == \
        "https://www.disneyplus.com/search?q=malcolm%20in%20the%20middle"
    # and the service's OWN search, not a web search for the title
    assert vocab.play_lookup("play stranger things on netflix") == \
        "https://www.netflix.com/search?q=stranger%20things"


def test_shortcuts_reject_non_http(tmp_path, monkeypatch):
    monkeypatch.setattr(vocab, "SHORTCUTS_FILE", tmp_path / "shortcuts.yaml")
    (tmp_path / "shortcuts.yaml").write_text(
        "shortcuts:\n  evil: javascript:alert(1)\n  fine: https://ok.example\n",
        encoding="utf-8")
    assert vocab.load_shortcuts() == {"fine": "https://ok.example"}


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
