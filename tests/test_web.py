"""The web HUD's locks, tried for real: token, host check, gate flow.

A live server on a random port, fake adapters, a canned resolver — no
model, no browser, no real machine-touching."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from alfred.executor import Executor
from alfred.ledger import Ledger
from alfred.undo import UndoManager
from alfred.web import Session, make_server

TOKEN = "test-token-123"


@pytest.fixture
def server(tmp_path):
    hits = []
    executor = Executor(
        {"web_search": lambda a: hits.append(a.query),
         "set_volume": lambda a: hits.append(a.level),
         "settings_change": lambda a: hits.append(a.value),
         "open_file": lambda a: hits.append("opened")},
        Ledger(root=tmp_path), UndoManager())
    resolver = lambda utterance, ledger: json.dumps(
        {"plan": [{"action": "web_search", "args": {"query": utterance}}]})
    session = Session(executor=executor, resolver=resolver)
    httpd = make_server(session, TOKEN)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    yield {"port": port, "session": session, "hits": hits}
    httpd.shutdown()


def call(port, path, body=None, token=TOKEN, host=None):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if host:
        request.remove_header("Host")
        request.add_header("Host", host)
    return urllib.request.urlopen(request, timeout=5)


def test_no_token_is_401(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server["port"], "/", token=None)
    assert error.value.code == 401


def test_wrong_token_is_401(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server["port"], "/api/ask", body={"text": "hi"}, token="stolen")
    assert error.value.code == 401


def test_dns_rebinding_host_is_403(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server["port"], "/", host="evil.example.com")
    assert error.value.code == 403


def test_page_serves_with_token_and_embeds_it(server):
    page = call(server["port"], "/").read().decode()
    assert "ALFRED" in page and TOKEN in page


def test_ask_flows_through_executor(server):
    call(server["port"], "/api/ask", body={"text": "weather in manila"})
    deadline = time.time() + 5
    while not server["hits"] and time.time() < deadline:
        time.sleep(0.05)
    assert server["hits"] == ["weather in manila"]


def _await_gate(events):
    gate = events.get(timeout=5)
    while gate["type"] != "gate":  # state events may precede the gate card
        gate = events.get(timeout=5)
    return gate


def test_tier1_runs_without_a_gate(server):
    # a reversible state change just happens — no card, no yes
    session = server["session"]
    session._resolver = lambda u, l: json.dumps(
        {"plan": [{"action": "set_volume", "args": {"level": 5}}]})
    call(server["port"], "/api/ask", body={"text": "volume 5"})
    deadline = time.time() + 5
    while 5 not in server["hits"] and time.time() < deadline:
        time.sleep(0.05)
    assert 5 in server["hits"]


def test_tier2_confirm_can_be_declined_over_the_wire(server):
    session = server["session"]
    session._resolver = lambda u, l: json.dumps(
        {"plan": [{"action": "settings_change",
                   "args": {"key": "app_theme", "value": "dark"}}]})
    events = session.subscribe()
    threading.Thread(target=session.ask, args=("dark mode",), daemon=True).start()
    gate = _await_gate(events)
    assert gate["kind"] == "confirm"
    call(server["port"], "/api/gate", body={"id": gate["id"], "go": False})
    deadline = time.time() + 5
    said = []
    while time.time() < deadline:
        event = events.get(timeout=5)
        if event.get("type") == "say":
            said.append(event["text"])
            break
    assert any("shan't" in s for s in said)
    assert "dark" not in server["hits"]  # the declined action never ran


def test_tier3_seal_needs_the_exact_phrase(server, tmp_path, monkeypatch):
    import alfred.config as config
    target = tmp_path / "notes.txt"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "ALLOWED_FOLDERS", (tmp_path,))
    session = server["session"]
    session._resolver = lambda u, l: json.dumps(
        {"plan": [{"action": "open_file", "args": {"path": str(target)}}]})

    # wrong phrase → withheld, nothing opens
    events = session.subscribe()
    threading.Thread(target=session.ask, args=("open notes",), daemon=True).start()
    gate = _await_gate(events)
    assert gate["kind"] == "seal"
    call(server["port"], "/api/gate", body={"id": gate["id"], "phrase": "yes"})
    time.sleep(0.3)
    assert "opened" not in server["hits"]

    # exact phrase → it runs
    threading.Thread(target=session.ask, args=("open notes",), daemon=True).start()
    gate = _await_gate(events)
    call(server["port"], "/api/gate",
         body={"id": gate["id"], "phrase": "yes i approve please proceed"})
    deadline = time.time() + 5
    while "opened" not in server["hits"] and time.time() < deadline:
        time.sleep(0.05)
    assert "opened" in server["hits"]


def test_second_command_is_refused_while_busy(server):
    session = server["session"]
    session._turn.acquire()  # pretend a turn is already in flight
    events = session.subscribe()
    session.ask("volume 5")  # runs synchronously here, should bounce off the lock
    session._turn.release()
    said = []
    while not events.empty():
        e = events.get_nowait()
        if e.get("type") == "say":
            said.append(e["text"])
    assert any("One moment" in s for s in said)
    assert 5 not in server["hits"]  # the busy command never ran


def test_last_window_closing_dismisses_him(monkeypatch, tmp_path):
    import alfred.web as web
    from alfred.executor import Executor
    from alfred.ledger import Ledger
    from alfred.undo import UndoManager
    monkeypatch.setattr(web, "IDLE_GRACE_SECONDS", 0.05)
    session = web.Session(executor=Executor({}, Ledger(root=tmp_path), UndoManager()))
    dismissed = threading.Event()
    session._on_idle = dismissed.set
    q = session.subscribe()      # a window opens
    session.unsubscribe(q)       # and closes — the last one
    assert dismissed.wait(2), "closing the last window should dismiss him"


def test_strip_wake_word():
    from alfred.web import _strip_wake
    assert _strip_wake("alfred open youtube") == "open youtube"
    assert _strip_wake("Hey Alfred, search cats") == "search cats"
    assert _strip_wake("open youtube") == "open youtube"
    # the live failure: his name rode into the query as the object
    assert _strip_wake("alfred open, spotify, and play a post malone music") == \
        "open, spotify, and play a post malone music"
    assert _strip_wake("Alfred. volume 30") == "volume 30"
    assert _strip_wake("alfred") == ""          # addressed, no order given
    assert _strip_wake("alfredo pasta recipe") == "alfredo pasta recipe"  # not the name


def test_unknown_route_is_404(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server["port"], "/api/shell", body={"cmd": "dir"})
    assert error.value.code == 404
