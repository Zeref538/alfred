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
    {"id": 1, "title": "Ledger — Portfolio", "url": "https://ledger.example.com/portfolio?session=SECRET"},
    {"id": 2, "title": "YouTube", "url": "https://www.youtube.com/watch?v=abc123"},
    {"id": 3, "title": "My Bank — Accounts", "url": "https://mybank.com/accounts"},
]


def test_credentials_never_survive_the_door():
    tabs.VIEW.update(REPORT)
    for tab in tabs.VIEW.all():
        assert "?" not in tab.host and "/" not in tab.host
        assert "SECRET" not in repr(tab)      # ?session=SECRET is dropped
    # the path is kept — it says WHICH page — but the credential is not
    trade = next(t for t in tabs.VIEW.all() if "example" in t.host)
    assert trade.path == "/portfolio"


@pytest.mark.parametrize("url, expected", [
    # navigation: keep. these are what tell two tabs on a site apart
    ("https://github.com/me?tab=repositories", "/me?tab=repositories"),
    ("https://www.youtube.com/watch?v=dQw4w9Wg", "/watch?v=dQw4w9Wg"),
    ("https://site.com/docs/page", "/docs/page"),
    # credentials: drop, by name...
    ("https://site.com/a?session=abc&tab=x", "/a?tab=x"),
    ("https://site.com/a?access_token=xyz", "/a"),
    ("https://site.com/reset?code=123456", "/reset"),
    # ...and by shape, whatever they are called
    ("https://site.com/a?r=" + "A1b2C3d4" * 8, "/a"),
    # fragments never survive
    ("https://site.com/a#deep-section", "/a"),
])
def test_paths_are_kept_but_credentials_filtered(url, expected):
    tabs.VIEW.forget()
    tabs.VIEW.update([{"id": 9, "title": "t", "url": url}])
    assert tabs.VIEW.all()[0].path == expected


def test_hosts_are_reduced_to_a_bare_name():
    tabs.VIEW.update(REPORT)
    hosts = {t.host for t in tabs.VIEW.all()}
    assert "ledger.example.com" in hosts
    assert "youtube.com" in hosts       # www. stripped


def test_path_lets_him_tell_two_tabs_on_one_site_apart():
    tabs.VIEW.update([
        {"id": 1, "title": "octocat", "url": "https://github.com/octocat"},
        {"id": 2, "title": "Repositories",
         "url": "https://github.com/octocat?tab=repositories"},
    ])
    assert tabs.VIEW.match("github repositories").id == 2


def test_banking_is_blinded_by_default():
    tabs.VIEW.update(REPORT)
    assert all("bank" not in t.host for t in tabs.VIEW.all())
    assert len(tabs.VIEW.all()) == 2    # the bank tab never arrived


def test_master_can_blind_his_own_hosts(tmp_path):
    tabs.PRIVACY_FILE.write_text("never_see:\n  - '*example*'\n", encoding="utf-8")
    tabs.VIEW.update(REPORT)
    assert all("example" not in t.host for t in tabs.VIEW.all())


def test_match_finds_a_tab_by_name_or_host():
    tabs.VIEW.update(REPORT)
    assert tabs.VIEW.match("ledger portfolio").id == 1
    assert tabs.VIEW.match("ledger").id == 1
    assert tabs.VIEW.match("youtube").id == 2
    assert tabs.VIEW.match("something never opened") is None


def test_a_stale_view_is_not_used(monkeypatch):
    tabs.VIEW.update(REPORT)
    assert tabs.VIEW.fresh()
    monkeypatch.setattr(tabs, "STALE_SECONDS", -1)  # everything is now old
    assert not tabs.VIEW.fresh()
    assert tabs.VIEW.all() == []
    assert tabs.VIEW.match("ledger") is None


def test_forget_is_immediate():
    tabs.VIEW.update(REPORT)
    tabs.VIEW.forget()
    assert tabs.VIEW.all() == [] and not tabs.VIEW.fresh()


def test_spoken_tab_name_requires_the_word_tab():
    assert tabs.spoken_tab_name("switch to my go ledger tab") == "go ledger"
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
    for leak in ("Ledger", "example", "YouTube", "youtube.com"):
        assert leak not in menu
