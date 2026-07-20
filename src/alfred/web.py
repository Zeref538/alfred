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
import os
import queue
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters import build_adapters
from .executor import Executor
from .gate import Etiquette, clear_plan, is_seal_phrase
from .ledger import Ledger
from .registry import REGISTRY, Tier
from .undo import UndoManager
from .validator import Refusal, plan_tier, validate_plan
from .webpage import PAGE

# consent already obtained (or not needed) — the tiers don't ask twice
_GRANTED = Etiquette(confirm=lambda s: True, seal=lambda s: True)

GREETING = ("Good evening, sir. All systems are nominal. "
            "Alfred is online and at your service.")
MAX_HOLD_SECONDS = 30  # a stuck key can't hold the mic open forever
IDLE_GRACE_SECONDS = 3.0  # after the last window closes, dismiss himself

_WAKE = re.compile(r"^\s*(?:hey\s+|ok\s+)?alfred[,:.\s]+", re.I)


def _strip_wake(text: str) -> str:
    return _WAKE.sub("", text).strip()


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
        self._gates: dict[str, tuple] = {}
        self._motion = None
        self._pending_steps = None
        self._muted = False       # "mute" silences his voice; "unmute" restores it
        self._recorder = None     # hold-to-talk recorder, when a key is held
        self._hold_timer = None
        self._turn = threading.Lock()  # one command at a time — no overlapping turns
        self._on_idle = None      # called when the last window closes (self-dismiss)
        self._ever_connected = False
        self._idle_timer = None

    # --- events out to the page ---------------------------------------------

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        self._subscribers.append(q)
        self._ever_connected = True
        if self._idle_timer is not None:  # a window reappeared — stay awake
            self._idle_timer.cancel()
            self._idle_timer = None
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)
        # once a window has ever opened, closing the last one dismisses him
        if (self._ever_connected and not self._subscribers
                and self._on_idle and self._idle_timer is None):
            self._idle_timer = threading.Timer(IDLE_GRACE_SECONDS, self._on_idle)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _try_begin(self) -> bool:
        """Claim the single turn slot; refuse politely if he's already busy."""
        if not self._turn.acquire(blocking=False):
            self.say("One moment, sir — I'm still attending to the last request.")
            return False
        return True

    def emit(self, **event) -> None:
        for q in list(self._subscribers):
            q.put(event)

    def say(self, text: str) -> None:
        self.emit(type="say", text=text)

    # --- the etiquette gate over the wire ------------------------------------

    def _ask_page(self, kind: str, summary: str) -> bool:
        gate_id = secrets.token_urlsafe(8)
        answers: queue.Queue = queue.Queue()
        self._gates[gate_id] = (kind, answers)
        self.emit(type="gate", kind=kind, id=gate_id, summary=summary)
        try:
            return answers.get()
        finally:
            self._gates.pop(gate_id, None)
            self.emit(type="gate_done", id=gate_id)

    def answer_gate(self, gate_id: str, go: bool, phrase: str = "") -> bool:
        entry = self._gates.get(gate_id)
        if entry is None:
            return False
        kind, answers = entry
        # a seal is verified here, server-side — the page only carries the text
        answers.put(is_seal_phrase(phrase) if kind == "seal" else bool(go))
        return True

    def etiquette(self) -> Etiquette:
        return Etiquette(
            confirm=lambda s: self._ask_page("confirm", s),
            seal=lambda s: self._ask_page("seal", s),
        )

    # --- doing things ---------------------------------------------------------

    def _plan_for(self, utterance: str):
        if self._resolver is not None:
            plan = self._resolver(utterance, self.ledger)
        else:
            from .palette import _resolve_utterance
            plan = _resolve_utterance(utterance, self.ledger)
        return validate_plan(plan)

    def _execute(self, steps, intent: str, gate: Etiquette,
                 spoken: bool = False) -> None:
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
        if not self._try_begin():
            return
        try:
            self.emit(type="state", state="working")
            self._execute(self._plan_for(utterance), utterance, self.etiquette(), spoken)
        except Refusal as refusal:
            self.say(str(refusal))
            if spoken:
                self._speak(str(refusal))
        except Exception as error:  # the service never dies mid-request
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")
        finally:
            self.emit(type="state", state="idle")
            self._turn.release()

    def _speak(self, text: str) -> None:
        if self._muted:
            return
        from . import voice
        self.emit(type="state", state="speaking")  # the green visualiser
        try:
            voice.speak(text)
        finally:
            self.emit(type="state", state="idle")

    def greet(self) -> None:
        """The boot line — spoken once at startup (the page shows the text)."""
        self._speak(GREETING)

    # --- listening ------------------------------------------------------------

    def hear(self) -> None:
        """Fixed 5-second push-to-talk (the mic button)."""
        from . import voice
        if not self._try_begin():
            return
        self.emit(type="state", state="listening")
        self.say("Listening, sir (5 seconds)…")
        try:
            audio = voice.record()
            self.emit(type="state", state="idle")
            self._process_audio(audio)
        finally:
            self._turn.release()

    def hold_start(self) -> None:
        """Open the mic and hold it — the HUD's hold-to-talk keys (J+K). Holds
        the turn lock until hold_stop, so a new command can't start mid-hold."""
        from . import voice
        if self._recorder is not None:
            return
        if not self._try_begin():
            return
        recorder = voice.Recorder()
        try:
            recorder.start()
        except Exception as error:
            self.say(f"My apologies, sir — the microphone won't open ({error}).")
            self._turn.release()
            return
        self._recorder = recorder
        self.emit(type="state", state="listening")
        self.say("Listening, sir — release to send.")
        self._hold_timer = threading.Timer(MAX_HOLD_SECONDS, self.hold_stop)
        self._hold_timer.daemon = True
        self._hold_timer.start()

    def hold_stop(self) -> None:
        recorder, self._recorder = self._recorder, None  # whoever wins, stops it once
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None
        if recorder is None:
            return  # nothing held — the lock isn't ours to release
        try:
            audio = recorder.stop()
            self.emit(type="state", state="idle")
            self._process_audio(audio)
        finally:
            self._turn.release()

    def _process_audio(self, audio) -> None:
        """The mishear guard, shared by every listening path: transcribe, repair,
        honour the bell and the mute word, then show the plan and gate it by tier
        — nothing for read-only/reversible, a spoken yes for the consequential,
        the typed seal (on the panel) for anything that reaches your files."""
        from . import fieldlog, voice
        raw = voice.transcribe(audio)
        self.emit(type="subtitle", text=raw)  # what he heard, big on the panel
        self.say(f'Heard: "{raw}"')
        if not raw:
            fieldlog.record(outcome="empty", raw="")
            return
        from .planner import correct_transcript
        transcript = correct_transcript(raw)
        if transcript != raw:
            self.emit(type="subtitle", text=transcript)
            self.say(f'Taking that as: "{transcript}"')
        if voice.is_stop(transcript):
            self.ring_bell("spoken")
            self._speak(voice.stand_down())
            fieldlog.record(outcome="bell", raw=raw, corrected=transcript)
            return
        if voice.is_undo(transcript):
            self._undo_spoken()
            fieldlog.record(outcome="undo", raw=raw, corrected=transcript)
            return
        if voice.is_unmute(transcript):
            self._muted = False
            self.say("Voice restored, sir.")
            self._speak("Voice restored, sir.")
            fieldlog.record(outcome="unmute", raw=raw, corrected=transcript)
            return
        if voice.is_mute(transcript):
            self._muted = True
            self.say("Muted, sir — say 'unmute' to bring me back.")
            fieldlog.record(outcome="mute", raw=raw, corrected=transcript)
            return
        # resolve first, so the user approves the PLAN, not just the words
        from .gate import describe
        try:
            self.emit(type="state", state="working")
            self._pending_steps = self._plan_for(transcript)
        except Refusal as refusal:
            self.emit(type="state", state="idle")
            fieldlog.record(outcome="refusal", raw=raw, corrected=transcript,
                            detail=str(refusal))
            self._offer_search_fallback(raw, transcript)  # don't dead-end — ask first
            return
        finally:
            self.emit(type="state", state="idle")
        # show the plan on the panel — never speak it back; the yes scales to tier
        self.say("He would:")
        for step in self._pending_steps:
            self.say("  - " + describe(step))
        fieldlog.record(outcome="plan", raw=raw, corrected=transcript,
                        detail="; ".join(describe(s) for s in self._pending_steps))
        tier = plan_tier(self._pending_steps)
        try:
            if tier <= Tier.ANNOUNCED:  # nothing consequential — just do it
                self.emit(type="state", state="working")
                self._execute(self._pending_steps, transcript, _GRANTED, spoken=True)
            elif tier is Tier.CONFIRM:
                self._speak("Shall I proceed, sir?")
                self.emit(type="state", state="listening")
                try:
                    confirmed = voice.heard_confirmation()
                finally:
                    self.emit(type="state", state="idle")
                if confirmed:
                    self._execute(self._pending_steps, transcript, _GRANTED, spoken=True)
                else:
                    self.ledger.record(event="voice_declined", transcript=transcript)
                    self.say("No confirmation — standing down.")
                    self._speak(voice.stand_down())
            else:  # UNDER_SEAL — voice can't type the seal; the panel takes it
                self._speak("That reaches your files, sir — kindly type your approval below.")
                self._execute(self._pending_steps, transcript, self.etiquette(), spoken=True)
        except Refusal as refusal:
            self.say(str(refusal))
            self._speak(str(refusal))
        except Exception as error:
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")
            fieldlog.record(outcome="error", raw=raw, corrected=transcript,
                            detail=f"{type(error).__name__}: {error}")
        finally:
            self._pending_steps = None
            self.emit(type="state", state="idle")

    def _offer_search_fallback(self, raw: str, transcript: str) -> None:
        """When a spoken command makes no sense on the menu, don't just refuse
        or guess — say so and ask to search it instead, executing only on a yes."""
        from . import fieldlog, voice
        query = _strip_wake(transcript)
        if not query:
            self.say("I didn't catch a command there, sir.")
            self._speak("I didn't catch that, sir.")
            return
        self.say(f'I didn\'t quite follow, sir. Shall I search for "{query}"?')
        self._speak(f"I didn't quite follow, sir. Shall I search for {query}?")
        self.emit(type="state", state="listening")
        try:
            confirmed = voice.heard_confirmation()
        finally:
            self.emit(type="state", state="idle")
        if not confirmed:
            self.say("Very well, sir — I'll leave it.")
            self._speak(voice.stand_down())
            return
        steps = validate_plan(json.dumps(
            {"plan": [{"action": "web_search", "args": {"query": query}}]}))
        fieldlog.record(outcome="fallback", raw=raw, corrected=transcript,
                        detail=f"search: {query}")
        self._execute(steps, transcript, _GRANTED, spoken=True)

    def ring_bell(self, source: str) -> None:
        self.executor.abort.set()
        self.ledger.record(event="bell", source=source)
        self.say("As you were, sir. (the bell)")
        self.executor.abort.clear()

    def _undo_spoken(self) -> None:
        handle = self.undo.undo_last()
        if handle is None:
            self.say("Nothing to undo, sir.")
            self._speak("Nothing to undo, sir.")
        else:
            self.ledger.record(event="undo", action=handle.action,
                               detail=handle.description)
            self.say(f"Undone: {handle.description}.")
            self._speak("Undone, sir.")

    def command(self, name: str) -> None:
        if name == "undo":
            self._undo_spoken()
        elif name == "menu":
            for spec in REGISTRY.values():
                self.say(f"tier {int(spec.tier)} | {spec.name} — {spec.summary}")
        elif name == "ledger":
            for entry in self.ledger.today()[-10:] or [{"note": "an empty page, sir"}]:
                self.say(json.dumps(entry, ensure_ascii=False))
        elif name == "burn":
            self.ledger.burn_today()
            self.say("The day's page is ash, sir.")
        elif name == "fieldlog":
            from . import fieldlog
            for line in fieldlog.summary().splitlines():
                self.say(line)
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
                self.wfile.write(PAGE.replace("__TOKEN__", token)
                                 .replace("__GREETING__", GREETING).encode("utf-8"))
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
                finally:
                    session.unsubscribe(q)  # last window gone → he dismisses himself
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
            elif route == "/api/listen":  # hold-to-talk: on key-down / key-up
                target = session.hold_start if body.get("on") else session.hold_stop
                threading.Thread(target=target, daemon=True).start()
            elif route == "/api/bell":
                session.ring_bell("page")
            elif route == "/api/gate":
                session.answer_gate(str(body.get("id", "")), bool(body.get("go")),
                                    str(body.get("phrase", "")))
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


def _lockfile():
    from . import config
    return config.DATA_DIR / "hud.lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:  # Windows: OpenProcess succeeds only for a live PID
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _running_instance():
    """The URL of a live HUD from the lockfile, or None (clearing a stale lock)."""
    lock = _lockfile()
    if not lock.exists():
        return None
    try:
        doc = json.loads(lock.read_text(encoding="utf-8"))
    except Exception:
        lock.unlink(missing_ok=True)
        return None
    if _pid_alive(int(doc.get("pid", 0))):
        return doc.get("url", "an open window")
    lock.unlink(missing_ok=True)  # the process is gone — the lock was stale
    return None


def stop_running() -> int:
    """`alfred stop` — dismiss a HUD left running in the background."""
    running = _running_instance()
    if not running:
        print("Alfred isn't running, sir.")
        return 0
    doc = json.loads(_lockfile().read_text(encoding="utf-8"))
    pid = int(doc["pid"])
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)  # TERMINATE
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    _lockfile().unlink(missing_ok=True)
    print(f"Dismissed Alfred (PID {pid}), sir.")
    return 0


def main() -> int:
    running = _running_instance()
    if running:
        print(f"Alfred is already at your service: {running}", flush=True)
        print("Dismiss that one first — close its window, or run `alfred stop`.",
              flush=True)
        return 1

    token = secrets.token_urlsafe(24)
    session = Session()
    server = make_server(session, token)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?t={token}"
    session._on_idle = lambda: threading.Thread(
        target=server.shutdown, daemon=True).start()  # last window closed → stop

    lock = _lockfile()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": os.getpid(), "url": url}), encoding="utf-8")

    print(f"At your service: {url}", flush=True)
    print("(one instance at a time; closing the window dismisses me, as does `alfred stop`)",
          flush=True)

    from . import globalkeys
    if globalkeys.available():
        try:  # slow work in threads — never block the system-wide keyboard hook
            globalkeys.watch(
                lambda: threading.Thread(target=session.hold_start, daemon=True).start(),
                lambda: threading.Thread(target=session.hold_stop, daemon=True).start())
            print("Global J+K hold-to-talk armed — works from any window.", flush=True)
        except Exception as error:
            print(f"(global J+K unavailable: {error})", flush=True)

    from . import voice

    def _boot() -> None:
        session.greet()   # loads Piper and delivers the spoken boot line
        voice.warm_up()   # then whisper + planner in the background
    threading.Thread(target=_boot, daemon=True).start()
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        lock.unlink(missing_ok=True)
    return 0
