"""Settings precedence and the settings API's locks and validation."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from alfred import settings
from alfred.executor import Executor
from alfred.ledger import Ledger
from alfred.undo import UndoManager
from alfred.web import Session, make_server

TOKEN = "settings-test-token"


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.yaml")
    return settings.SETTINGS_FILE


def test_defaults_when_nothing_is_set(settings_file):
    assert settings.get("voice_pace") == "1.18"
    assert settings.get("search").startswith("https://www.google.com")


def test_file_overrides_default_and_env_overrides_file(settings_file, monkeypatch):
    settings.save({"voice_pace": "1.4"})
    assert settings.get("voice_pace") == "1.4"
    monkeypatch.setenv("ALFRED_VOICE_PACE", "0.9")
    assert settings.get("voice_pace") == "0.9"


def test_unknown_keys_are_not_persisted(settings_file):
    settings.save({"voice_pace": "1.3", "run_shell": "yes please"})
    assert "run_shell" not in settings.load()


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.yaml")
    import alfred.customs as customs_mod
    monkeypatch.setattr(customs_mod.config, "DATA_DIR", tmp_path)
    executor = Executor({}, Ledger(root=tmp_path), UndoManager())
    session = Session(executor=executor, resolver=lambda u, l: "{}")
    httpd = make_server(session, TOKEN)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()


def call(port, path, body=None, token=TOKEN):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(request, timeout=5)


def test_settings_roundtrip_over_the_api(server):
    call(server, "/api/settings", body={"voice_pace": "1.30"})
    doc = json.loads(call(server, "/api/settings").read())
    assert doc["settings"]["voice_pace"] == "1.30"
    assert "routines" in doc["customs"]


def test_settings_page_requires_token(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server, "/settings", token=None)
    assert error.value.code == 401


def test_bad_customs_yaml_is_rejected(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server, "/api/customs", body={"text": "routines: ["})
    assert error.value.code == 400


def test_good_customs_yaml_is_saved(server):
    text = ("routines:\n  tea_time:\n    phrases: [tea time]\n"
            "    plan:\n      - action: web_search\n        args: {query: tea}\n")
    call(server, "/api/customs", body={"text": text})
    doc = json.loads(call(server, "/api/settings").read())
    assert "tea_time" in doc["customs"]