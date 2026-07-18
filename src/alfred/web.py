"""The web HUD: a local page over the same one door — hardened by design.

THREATMODEL.md warned about localhost control servers, so this one follows
the plan's own rules, and tests enforce each:

- binds 127.0.0.1 only, on a random port, with a per-session bearer token
- every request is token-checked (401 without); the token travels in the
  summon URL once and lives in page JS — there are no cookies, so a hostile
  web page has nothing to ride (CSRF inert)
- the Host header must be exactly our own origin (DNS-rebinding check)
- the browser page holds no power of its own: every action still passes
  customs → planner → validator → gate → executor

Input options: text (the field), audio (push-to-talk button → server-side
mic + whisper), hotkey (Ctrl+Alt+C summons this page), motion (opt-in
webcam *stop bell* — movement can only ever ring the bell, never command).
"""

import json
import queue
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters import build_adapters
from .executor import Executor
from .gate import Etiquette, clear_plan
from .ledger import Ledger
from .registry import REGISTRY
from .undo import UndoManager
from .validator import Refusal, validate_plan
from .webpage import PAGE

ANNOUNCE_SECONDS = 2.0


class Session:
    """Everything behind the API. UI-free, injectable, testable."""

    def __init__(self, executor: Executor | None = None, resolver=None):
        self.ledger = Ledger()
        self.undo = UndoManager()
        self.executor = executor or Executor(build_adapters(), self.ledger, self.undo)
        if executor is not None:
            self.ledger, self.undo = executor.ledger, executor.undo
        self._resolver = resolver
        self._subscribers: list[queue.Queue] = []
        self._gates: dict[str, queue.Queue] = {}
        self._motion = None
        self._pending_steps = None

    # --- events out to the page ---------------------------------------------

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        self._subscribers.append(q)
        return q

    def emit(self, **event) -> None:
        for q in list(self._subscribers):
            q.put(event)

    def say(self, text: str) -> None:
        self.emit(type="say", text=text)

    # --- the etiquette gate over the wire ------------------------------------

    def _ask_page(self, kind: str, summary: str, timeout: float | None) -> bool:
        gate_id = secrets.token_urlsafe(8)
        answers: queue.Queue = queue.Queue()
        self._gates[gate_id] = answers
        self.emit(type="gate", kind=kind, id=gate_id, summary=summary,
                  seconds=ANNOUNCE_SECONDS if timeout else None)
        try:
            return answers.get(timeout=timeout)
        except queue.Empty:
            return True  # an announcement not canceled proceeds
        finally:
            self._gates.pop(gate_id, None)
            self.emit(type="gate_done", id=gate_id)

    def answer_gate(self, gate_id: str, go: bool) -> bool:
        answers = self._gates.get(gate_id)
        if answers is None:
            return False
        answers.put(go)
        return True

    def etiquette(self) -> Etiquette:
        return Etiquette(
            announce=lambda s: self._ask_page("announce", s, ANNOUNCE_SECONDS),
            confirm=lambda s: self._ask_page("confirm", s, None),
        )

    # --- doing things ---------------------------------------------------------

    def _plan_for(self, utterance: str):
        if self._resolver is not None:
            plan = self._resolver(utterance, self.ledger)
        else:
            from .palette import _resolve_utterance
            plan = _resolve_utterance(utterance, self.ledger)
        return validate_plan(plan)

    def _execute(self, steps, intent: str, spoken: bool = False,
                 preapproved: bool = False) -> None:
        # preapproved: the user already said yes to this exact plan preview,
        # so the tiers don't ask twice
        gate = (Etiquette(announce=lambda s: True, confirm=lambda s: True)
                if preapproved else self.etiquette())
        clear_plan(steps, gate)
        results = self.executor.run(steps, intent=intent)
        for r in results:
            self.emit(type="say", text=f"[{'ok' if r.ok else 'XX'}] {r.action}: {r.detail}",
                      flash=True)
        if all(r.ok for r in results):
            self.say("Done, sir.")
            if spoken:
                from .voice import nod
                self._speak(nod())
        elif spoken:
            from .voice import apologize
            self._speak(apologize())

    def ask(self, utterance: str, spoken: bool = False) -> None:
        try:
            self.emit(type="state", state="working")
            self._execute(self._plan_for(utterance), utterance, spoken)
        except Refusal as refusal:
            self.say(str(refusal))
            if spoken:
                self._speak(str(refusal))
        except Exception as error:  # the service never dies mid-request
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")
        finally:
            self.emit(type="state", state="idle")

    @staticmethod
    def _speak(text: str) -> None:
        from . import voice
        voice.speak(text)

    def hear(self) -> None:
        """Push-to-talk with the mishear guard: Alfred says what he heard and
        acts only on a spoken yes (or the page's confirm card)."""
        from . import voice
        self.emit(type="state", state="listening")
        self.say("Listening, sir (5 seconds)…")
        try:
            transcript = voice.transcribe(voice.record())
        finally:
            self.emit(type="state", state="idle")
        self.say(f'Heard: "{transcript}"')
        if not transcript:
            return
        from .planner import correct_transcript
        corrected = correct_transcript(transcript)
        if corrected != transcript:
            self.say(f'Taking that as: "{corrected}"')
            transcript = corrected
        if voice.is_stop(transcript):
            self.ring_bell("spoken")
            from .voice import stand_down
            self._speak(stand_down())
            return
        # resolve first, so the user approves the PLAN, not just the words
        from .gate import describe, describe_spoken
        try:
            self.emit(type="state", state="working")
            self._pending_steps = self._plan_for(transcript)
        except Refusal as refusal:
            self.say(str(refusal))
            self._speak(str(refusal))
            return
        finally:
            self.emit(type="state", state="idle")
        self.say("He would:")
        for step in self._pending_steps:
            self.say("  - " + describe(step))
        self._speak(f"I shall {describe_spoken(self._pending_steps)} — sir?")
        self.emit(type="state", state="listening")
        try:
            confirmed = voice.heard_confirmation()
        finally:
            self.emit(type="state", state="idle")
        if not confirmed:
            self.ledger.record(event="voice_declined", transcript=transcript)
            self.say("No confirmation — standing down.")
            from .voice import stand_down
            self._speak(stand_down())
            return
        try:
            self.emit(type="state", state="working")
            self._execute(self._pending_steps, transcript, spoken=True, preapproved=True)
        except Refusal as refusal:
            self.say(str(refusal))
            self._speak(str(refusal))
        except Exception as error:
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")
        finally:
            self._pending_steps = None
            self.emit(type="state", state="idle")

    def ring_bell(self, source: str) -> None:
        self.executor.abort.set()
        self.ledger.record(event="bell", source=source)
        self.say("As you were, sir. (the bell)")
        self.executor.abort.clear()

    def command(self, name: str) -> None:
        if name == "undo":
            handle = self.undo.undo_last()
            if handle is None:
                self.say("Nothing to undo, sir.")
            else:
                self.ledger.record(event="undo", action=handle.action,
                                   detail=handle.description)
                self.say(f"Undone: {handle.description}.")
        elif name == "menu":
            for spec in REGISTRY.values():
                self.say(f"tier {int(spec.tier)} | {spec.name} — {spec.summary}")
        elif name == "ledger":
            for entry in self.ledger.today()[-10:] or [{"note": "an empty page, sir"}]:
                self.say(json.dumps(entry, ensure_ascii=False))
        elif name == "burn":
            self.ledger.burn_today()
            self.say("The day's page is ash, sir.")
        else:
            self.say(f"I don't recognise '{name}', sir.")

    def motion(self, enable: bool) -> None:
        if enable and self._motion is None:
            try:
                from .motion import StopBell
                self._motion = StopBell(on_motion=lambda: self.ring_bell("motion"))
                self._motion.start()
                self.say("The motion bell is set, sir — a large wave rings it.")
            except RuntimeError as error:
                self.say(str(error))
        elif not enable and self._motion is not None:
            self._motion.stop()
            self._motion = None
            self.say("The motion bell is put away, sir.")


def make_server(session: Session, token: str, port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # keep the console quiet
            pass

        # -- guards ----------------------------------------------------------
        def _host_ok(self) -> bool:
            return self.headers.get("Host") == f"127.0.0.1:{server.server_address[1]}"

        def _token_ok(self) -> bool:
            header = self.headers.get("Authorization", "")
            if header == f"Bearer {token}":
                return True
            _, _, query = self.path.partition("?")
            return f"t={token}" in query.split("&")

        def _deny(self, code: int, why: str) -> None:
            self.send_response(code)
            self.end_headers()
            self.wfile.write(why.encode())

        def _guard(self) -> bool:
            if not self._host_ok():
                self._deny(403, "wrong door")
                return False
            if not self._token_ok():
                self._deny(401, "not without the master's token")
                return False
            return True

        # -- routes ----------------------------------------------------------
        def do_GET(self) -> None:
            if not self._guard():
                return
            route = self.path.partition("?")[0]
            if route == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(PAGE.replace("__TOKEN__", token).encode("utf-8"))
            elif route == "/settings":
                from .webpage import SETTINGS_PAGE
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(SETTINGS_PAGE.replace("__TOKEN__", token).encode("utf-8"))
            elif route == "/api/settings":
                from . import settings
                from .customs import HouseCustoms
                customs_path = HouseCustoms().path
                payload = json.dumps({
                    "settings": settings.current(),
                    "customs": customs_path.read_text(encoding="utf-8"),
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
            elif route == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = session.subscribe()
                try:
                    while True:
                        event = q.get()
                        payload = f"data: {json.dumps(event)}\n\n".encode()
                        self.wfile.write(payload)
                        self.wfile.flush()
                except OSError:
                    pass
            else:
                self._deny(404, "not on the menu")

        def do_POST(self) -> None:
            if not self._guard():
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            route = self.path.partition("?")[0]
            if route == "/api/ask" and body.get("text", "").strip():
                threading.Thread(target=session.ask,
                                 args=(body["text"].strip(),), daemon=True).start()
            elif route == "/api/voice":
                threading.Thread(target=session.hear, daemon=True).start()
            elif route == "/api/bell":
                session.ring_bell("page")
            elif route == "/api/gate":
                session.answer_gate(str(body.get("id", "")), bool(body.get("go")))
            elif route == "/api/command":
                threading.Thread(target=session.command,
                                 args=(str(body.get("name", "")),), daemon=True).start()
            elif route == "/api/motion":
                session.motion(bool(body.get("enable")))
            elif route == "/api/settings":
                from . import settings, voice
                settings.save({str(k): str(v) for k, v in body.items()})
                voice._model = None   # whisper/piper choices apply immediately
                voice._piper = None
                session.say("Preferences noted, sir.")
            elif route == "/api/customs":
                import yaml as _yaml

                from .customs import HouseCustoms
                text = str(body.get("text", ""))
                try:
                    doc = _yaml.safe_load(text)
                    assert isinstance(doc, dict) and isinstance(doc.get("routines"), dict)
                except Exception:
                    self._deny(400, "that is not a well-formed customs file, sir")
                    return
                HouseCustoms().path.write_text(text, encoding="utf-8")
                session.say(f"House customs updated, sir — {len(doc['routines'])} routines.")
            elif route == "/api/rescan":
                what = str(body.get("what", ""))
                if what == "apps":
                    import yaml as _yaml

                    from . import config
                    from .adapters.apps import scan_start_menu
                    apps = scan_start_menu()
                    config.APPS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    config.APPS_FILE.write_text(_yaml.safe_dump(apps, sort_keys=True),
                                                encoding="utf-8")
                    session.say(f"{len(apps)} applications registered, sir "
                                "(effective on my next summons).")
                elif what == "vocab":
                    from . import vocab
                    vocabulary = vocab.build_vocabulary()
                    session.say(f"{len(vocabulary['sites'])} bookmarked sites "
                                "committed to memory, sir.")
                else:
                    self._deny(404, "not on the menu")
                    return
            else:
                self._deny(404, "not on the menu")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


def main() -> int:
    token = secrets.token_urlsafe(24)
    session = Session()
    server = make_server(session, token)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?t={token}"
    print(f"At your service: {url}", flush=True)
    print("(the token is this session's key — the page keeps it; Ctrl+C dismisses me)",
          flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
