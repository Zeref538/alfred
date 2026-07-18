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

    def ask(self, utterance: str) -> None:
        try:
            if self._resolver is not None:
                plan = self._resolver(utterance, self.ledger)
            else:
                from .palette import _resolve_utterance
                plan = _resolve_utterance(utterance, self.ledger)
            steps = validate_plan(plan)
            clear_plan(steps, self.etiquette())
            results = self.executor.run(steps, intent=utterance)
            for r in results:
                self.say(f"[{'ok' if r.ok else 'XX'}] {r.action}: {r.detail}")
            if all(r.ok for r in results):
                self.say("Done, sir.")
        except Refusal as refusal:
            self.say(str(refusal))
        except Exception as error:  # the service never dies mid-request
            self.say(f"My apologies, sir — {type(error).__name__}: {error}")

    def hear(self) -> None:
        from . import voice
        self.say("Listening, sir (5 seconds)…")
        transcript = voice.transcribe(voice.record())
        self.say(f'Heard: "{transcript}"')
        if not transcript:
            return
        if voice.is_stop(transcript):
            self.ring_bell("spoken")
            return
        self.ask(transcript)

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
    print(f"At your service: {url}")
    print("(the token is this session's key — the page keeps it; Ctrl+C dismisses me)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Alfred</title>
<style>
 body { background:#16161e; color:#e6e0cf; font:14px 'Segoe UI',sans-serif;
        max-width:640px; margin:2rem auto; padding:0 1rem; }
 h1 { color:#e0c060; font-size:1rem; letter-spacing:.2em; }
 #log { background:#101018; border:1px solid #2a2a38; border-radius:8px;
        padding:.8rem; height:300px; overflow-y:auto; font:12px Consolas,monospace;
        white-space:pre-wrap; }
 #bar { display:flex; gap:.5rem; margin:.8rem 0; }
 input[type=text] { flex:1; background:#22222e; color:#e6e0cf; border:1px solid #2a2a38;
        border-radius:6px; padding:.6rem; font-size:14px; }
 button { background:#2a2a38; color:#e6e0cf; border:0; border-radius:6px;
        padding:.6rem .9rem; cursor:pointer; }
 button:hover { background:#3a3a4c; }
 #bell { background:#4a2a2a; }
 .gate { background:#221e14; border:1px solid #e0c060; border-radius:8px;
        padding:.6rem .8rem; margin:.6rem 0; display:flex; gap:.6rem;
        align-items:center; justify-content:space-between; }
 .dim { color:#8a8677; } label { color:#8a8677; font-size:12px; }
</style></head><body>
<h1>ALFRED — AT YOUR SERVICE</h1>
<div id="log"></div><div id="gates"></div>
<div id="bar">
 <input id="text" type="text" placeholder="Ask, sir… (Enter)" autofocus>
 <button id="mic" title="push-to-talk (5s)">&#127908;</button>
 <button id="bell" title="the bell — abort">&#128276;</button>
</div>
<div id="bar">
 <button data-cmd="menu">menu</button><button data-cmd="undo">undo</button>
 <button data-cmd="ledger">ledger</button><button data-cmd="burn">burn</button>
 <label><input type="checkbox" id="motion"> motion stop-bell (webcam rings the bell on a big wave — never commands)</label>
</div>
<p class="dim">text · audio (mic button) · hotkey (Ctrl+Alt+C summons this page) · motion (opt-in bell)</p>
<script>
const TOKEN = "__TOKEN__";
const log = document.getElementById("log");
function say(t){ log.textContent += t + "\\n"; log.scrollTop = log.scrollHeight; }
function post(path, body){ return fetch(path, {method:"POST",
  headers:{"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}); }
const gates = document.getElementById("gates");
function gateCard(e){
  const card = document.createElement("div"); card.className = "gate"; card.id = "g"+e.id;
  const label = document.createElement("span");
  const buttons = document.createElement("span");
  if (e.kind === "announce"){
    let left = e.seconds;
    label.textContent = `If I may (${left.toFixed(0)}s): ${e.summary}`;
    const timer = setInterval(()=>{ left -= 0.25;
      if(left <= 0){ clearInterval(timer); card.remove(); }
      else label.textContent = `If I may (${Math.ceil(left)}s): ${e.summary}`; }, 250);
    const cancel = document.createElement("button"); cancel.textContent = "Belay that";
    cancel.onclick = ()=>{ clearInterval(timer); post("/api/gate",{id:e.id,go:false}); card.remove(); };
    buttons.append(cancel);
  } else {
    label.textContent = `By your leave, sir: ${e.summary}`;
    for (const [text, go] of [["Go ahead", true], ["Not now", false]]){
      const b = document.createElement("button"); b.textContent = text;
      b.onclick = ()=>{ post("/api/gate",{id:e.id,go}); card.remove(); };
      buttons.append(b);
    }
  }
  card.append(label, buttons); gates.append(card);
}
const events = new EventSource("/api/events?t="+TOKEN);
events.onmessage = (m)=>{ const e = JSON.parse(m.data);
  if (e.type === "say") say(e.text);
  else if (e.type === "gate") gateCard(e);
  else if (e.type === "gate_done"){ const c = document.getElementById("g"+e.id); if(c) c.remove(); } };
const text = document.getElementById("text");
text.addEventListener("keydown",(k)=>{ if(k.key==="Enter" && text.value.trim()){
  say("> "+text.value.trim()); post("/api/ask",{text:text.value.trim()}); text.value=""; }});
document.getElementById("mic").onclick = ()=>post("/api/voice");
document.getElementById("bell").onclick = ()=>post("/api/bell");
document.querySelectorAll("[data-cmd]").forEach(b=>b.onclick=()=>post("/api/command",{name:b.dataset.cmd}));
document.getElementById("motion").onchange = (e)=>post("/api/motion",{enable:e.target.checked});
say("Good day, sir. The services are at your disposal.");
</script></body></html>"""
