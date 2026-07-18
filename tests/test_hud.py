"""Routing and (locally) a real-window smoke test. CI runners get no Tk."""

import os

import pytest

from alfred.hud import route


def test_plain_text_routes_to_ask():
    assert route("silence the notifications") == ("ask", "silence the notifications")


def test_slash_commands_route_by_name():
    assert route("/undo") == ("undo", "")
    assert route("/Menu") == ("menu", "")
    assert route("/ledger today") == ("ledger", "today")
    assert route("  /burn  ") == ("burn", "")


@pytest.mark.skipif(os.environ.get("CI") is not None, reason="no display in CI")
def test_hud_window_builds_and_dies_cleanly():
    from alfred.hud import Hud

    hud = Hud()
    hud.root.update()  # one pump proves the widgets laid out
    assert hud.entry.winfo_exists()
    hud.root.destroy()
