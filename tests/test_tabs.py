"""The browser bridge, and the limits on what it may know.

These are the tests that matter most in the whole suite: the bridge is the
largest amount of sight Alfred has, so each restriction is asserted rather
than trusted."""

import pytest

from alfred import tabs


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.setattr(tabs, "PRIVACY_FILE", tmp_path / "tab_privacy.yaml")
    tabs.VIEW.forget()
    yield
    tabs.VIEW.forget()


REPORT = [
    {"id": 1, "title": "GoTrade — Portfolio", "url": "https://ultra.heygotrade.com/portfolio?session=SECRET"},
    {"id": 2, "title": "YouTube", "url": "https://www.youtube.com/watch?v=abc123"},
    {"id": 3, "title": "My Bank — Accounts", "url": "https://mybank.com/accounts"},
]


def test_paths_and_queries_never_survive_the_door():
    tabs.VIEW.update(REPORT)
    for tab in tabs.VIEW.all():
        assert "?" not in tab.host and "/" not in tab.host
        # the session token in the first URL must be gone entirely
        assert "SECRET" not in repr(tab)
        assert "abc123" not in repr(tab)


def test_hosts_are_reduced_to_a_bare_name():
    tabs.VIEW.update(REPORT)
    hosts = {t.host for t in tabs.VIEW.all()}
    assert "ultra.heygotrade.com" in hosts
    assert "youtube.com" in hosts       # www. stripped


def test_banking_is_blinded_by_default():
    tabs.VIEW.update(REPORT)
    assert all("bank" not in t.host for t in tabs.VIEW.all())
    assert len(tabs.VIEW.all()) == 2    # the bank tab never arrived


def test_master_can_blind_his_own_hosts(tmp_path):
    tabs.PRIVACY_FILE.write_text("never_see:\n  - '*heygotrade*'\n", encoding="utf-8")
    tabs.VIEW.update(REPORT)
    assert all("heygotrade" not in t.host for t in tabs.VIEW.all())


def test_match_finds_a_tab_by_name_or_host():
    tabs.VIEW.update(REPORT)
    assert tabs.VIEW.match("go trade").id == 1
    assert tabs.VIEW.match("gotrade").id == 1
    assert tabs.VIEW.match("youtube").id == 2
    assert tabs.VIEW.match("something never opened") is None


def test_a_stale_view_is_not_used(monkeypatch):
    tabs.VIEW.update(REPORT)
    assert tabs.VIEW.fresh()
    monkeypatch.setattr(tabs, "STALE_SECONDS", -1)  # everything is now old
    assert not tabs.VIEW.fresh()
    assert tabs.VIEW.all() == []
    assert tabs.VIEW.match("go trade") is None


def test_forget_is_immediate():
    tabs.VIEW.update(REPORT)
    tabs.VIEW.forget()
    assert tabs.VIEW.all() == [] and not tabs.VIEW.fresh()


def test_spoken_tab_name_requires_the_word_tab():
    assert tabs.spoken_tab_name("switch to my go trade tab") == "go trade"
    assert tabs.spoken_tab_name("open my youtube tab") == "youtube"
    # without "tab" this must NOT reach into the browser — it opens a page
    assert tabs.spoken_tab_name("open youtube") is None
    assert tabs.spoken_tab_name("volume 30") is None


def test_play_media_degrades_to_opening_without_the_bridge(monkeypatch):
    # no extension: he should still land you on the page, not fail outright
    import alfred.adapters.browser as browser_mod
    from alfred import schemas
    opened = []
    monkeypatch.setattr(browser_mod, "webbrowser",
                        type("W", (), {"open": staticmethod(opened.append)}))
    monkeypatch.setattr(tabs, "_emit", None)
    browser_mod.play_media(schemas.PlayMedia(url="https://youtube.com/results?q=x"))
    assert opened == ["https://youtube.com/results?q=x"]


def test_play_media_asks_the_bridge_when_connected(monkeypatch):
    from alfred import schemas
    from alfred.adapters.browser import play_media
    sent = []
    monkeypatch.setattr(tabs, "_emit", lambda **e: sent.append(e))
    play_media(schemas.PlayMedia(url="https://open.spotify.com/search/x"))
    assert sent == [{"type": "play_request", "url": "https://open.spotify.com/search/x"}]


def test_play_media_is_http_only():
    import pytest as _pytest
    from alfred import schemas
    with _pytest.raises(Exception):
        schemas.PlayMedia(url="javascript:alert(1)")


def test_focus_tab_refuses_when_the_bridge_is_quiet():
    from alfred import schemas
    from alfred.adapters.browser import focus_tab
    with pytest.raises(RuntimeError, match="can't see your tabs"):
        focus_tab(schemas.FocusTab(name="anything"))


def test_tab_titles_never_reach_the_planner_prompt():
    # the data-flow rule: a page can title itself anything, so no tab text may
    # ever appear in the menu the model is shown
    from alfred.planner import menu_text
    tabs.VIEW.update(REPORT)
    menu = menu_text()
    assert "focus_tab" in menu                 # the action exists
    for leak in ("GoTrade", "heygotrade", "YouTube", "youtube.com"):
        assert leak not in menu
