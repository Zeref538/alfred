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
         "set_volume": lambda a: hits.append(a.level)},
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


def test_tier1_gate_can_be_belayed_over_the_wire(server, tmp_path):
    session = server["session"]
    session._resolver = lambda u, l: json.dumps(
        {"plan": [{"action": "set_volume", "args": {"level": 5}}]})
    events = session.subscribe()
    threading.Thread(target=session.ask, args=("volume 5",), daemon=True).start()
    gate = events.get(timeout=5)
    assert gate["type"] == "gate" and gate["kind"] == "announce"
    call(server["port"], "/api/gate", body={"id": gate["id"], "go": False})
    deadline = time.time() + 5
    said = []
    while time.time() < deadline:
        event = events.get(timeout=5)
        if event.get("type") == "say":
            said.append(event["text"])
            break
    assert any("canceled" in s for s in said)
    assert 5 not in server["hits"]  # the belayed action never ran


def test_unknown_route_is_404(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server["port"], "/api/shell", body={"cmd": "dir"})
    assert error.value.code == 404
