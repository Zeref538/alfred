"""The HUD page itself — presentation only, no power.

Everything the page can do goes through the token-guarded API in web.py;
restyling this file can never widen the attack surface.
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALFRED</title>
<style>
 :root { --cy:#39d7ff; --cy-dim:#1a7fa0; --cy-glow:rgba(57,215,255,.45);
         --amber:#ffb02e; --red:#ff5a49; --ink:#04080f; }
 * { box-sizing:border-box; margin:0; }
 body { background:
        radial-gradient(1200px 700px at 50% -10%, #0a1a2b 0%, var(--ink) 60%),
        var(--ink);
        color:var(--cy); font:14px Consolas, 'Cascadia Mono', monospace;
        min-height:100vh; display:flex; align-items:center; justify-content:center;
        padding:2rem 1rem; }
 body::before { content:""; position:fixed; inset:0; pointer-events:none;
        background:repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 1px,
        transparent 1px 3px); mix-blend-mode:overlay; }
 body::after { content:""; position:fixed; inset:0; pointer-events:none;
        background:
        linear-gradient(rgba(57,215,255,.05) 1px, transparent 1px) 0 0/100% 48px,
        linear-gradient(90deg, rgba(57,215,255,.05) 1px, transparent 1px) 0 0/48px 100%; }

 #frame { width:min(720px, 100%); position:relative; padding:1.6rem;
        border:1px solid rgba(57,215,255,.25);
        background:rgba(4,10,18,.85); backdrop-filter:blur(2px);
        box-shadow:0 0 40px rgba(57,215,255,.08), inset 0 0 60px rgba(57,215,255,.04); }
 .corner { position:absolute; width:22px; height:22px; border:2px solid var(--cy);
        filter:drop-shadow(0 0 4px var(--cy-glow)); }
 .tl { top:-2px; left:-2px; border-right:0; border-bottom:0; }
 .tr { top:-2px; right:-2px; border-left:0; border-bottom:0; }
 .bl { bottom:-2px; left:-2px; border-right:0; border-top:0; }
 .br { bottom:-2px; right:-2px; border-left:0; border-top:0; }

 header { display:flex; align-items:center; gap:1rem; margin-bottom:1.1rem; }
 #reactor { width:44px; height:44px; border-radius:50%; position:relative; flex:none;
        background:radial-gradient(circle, #eaffff 0%, #9feaff 18%, #2bb7e0 45%,
        rgba(9,40,60,.9) 70%);
        box-shadow:0 0 14px var(--cy-glow), 0 0 40px rgba(57,215,255,.25),
        inset 0 0 10px rgba(255,255,255,.7);
        animation:pulse 2.4s ease-in-out infinite; }
 #reactor::before { content:""; position:absolute; inset:-7px; border-radius:50%;
        border:1px dashed rgba(57,215,255,.5); animation:spin 14s linear infinite; }
 #reactor.working { animation:pulse .7s ease-in-out infinite; }
 #reactor.listening { background:radial-gradient(circle, #fff8ea 0%, #ffd79f 18%,
        #e0a12b 45%, rgba(60,40,9,.9) 70%);
        box-shadow:0 0 14px rgba(255,176,46,.5), 0 0 40px rgba(255,176,46,.3); }
 @keyframes pulse { 0%,100% { transform:scale(1); } 50% { transform:scale(1.07); } }
 @keyframes spin { to { transform:rotate(360deg); } }

 h1 { font-size:1.05rem; letter-spacing:.55em; color:#d9f6ff;
      text-shadow:0 0 8px var(--cy-glow); font-weight:600; }
 #status { font-size:.7rem; color:var(--cy-dim); letter-spacing:.25em;
      margin-top:.35rem; text-transform:uppercase; }
 #status b { color:var(--cy); }

 #log { border:1px solid rgba(57,215,255,.2); background:rgba(2,6,11,.9);
      height:300px; overflow-y:auto; padding:.8rem .9rem; white-space:pre-wrap;
      font-size:12px; line-height:1.55; color:#a8e6ff;
      text-shadow:0 0 5px rgba(57,215,255,.35);
      scrollbar-color:var(--cy-dim) transparent; }
 #log .me { color:#e9fbff; }
 #log .act { animation:landed .9s ease-out; }
 @keyframes landed { 0% { background:rgba(57,215,255,.35); text-shadow:0 0 14px var(--cy); }
                     100% { background:transparent; } }
 #reactor.blip { animation:pulse .25s ease-in-out 3; }

 .gate { border:1px solid var(--amber); background:rgba(40,28,6,.5);
      padding:.6rem .8rem; margin:.6rem 0; display:flex; gap:.8rem;
      align-items:center; justify-content:space-between; color:var(--amber);
      text-shadow:0 0 6px rgba(255,176,46,.4); font-size:12px;
      box-shadow:0 0 18px rgba(255,176,46,.12); }
 .gate::before { content:"⚠ AUTHORIZATION"; letter-spacing:.2em; font-size:.65rem;
      border-right:1px solid rgba(255,176,46,.4); padding-right:.8rem; flex:none; }
 .gate button { border-color:var(--amber); color:var(--amber); }
 .gate button:hover { box-shadow:0 0 12px rgba(255,176,46,.5); }

 #bar, #cmds { display:flex; gap:.55rem; margin-top:.8rem; align-items:center;
      flex-wrap:wrap; }
 input[type=text] { flex:1; min-width:200px; background:rgba(6,14,24,.9);
      color:#e9fbff; border:1px solid rgba(57,215,255,.35); padding:.65rem .8rem;
      font:inherit; outline:none; caret-color:var(--cy);
      clip-path:polygon(10px 0, 100% 0, 100% calc(100% - 10px),
                        calc(100% - 10px) 100%, 0 100%, 0 10px); }
 input[type=text]:focus { box-shadow:0 0 14px rgba(57,215,255,.25);
      border-color:var(--cy); }
 button { background:transparent; color:var(--cy); font:inherit; cursor:pointer;
      border:1px solid rgba(57,215,255,.45); padding:.6rem .9rem;
      letter-spacing:.12em; text-transform:uppercase; font-size:.72rem;
      clip-path:polygon(8px 0, 100% 0, 100% calc(100% - 8px),
                        calc(100% - 8px) 100%, 0 100%, 0 8px);
      transition:box-shadow .15s, background .15s; }
 button:hover { background:rgba(57,215,255,.08); box-shadow:0 0 14px var(--cy-glow); }
 #bell { color:var(--red); border-color:rgba(255,90,73,.6); }
 #bell:hover { background:rgba(255,90,73,.08); box-shadow:0 0 14px rgba(255,90,73,.5); }
 label { color:var(--cy-dim); font-size:.7rem; letter-spacing:.12em;
      text-transform:uppercase; display:flex; gap:.4rem; align-items:center; }
 accent-color: var(--cy);
 #hint { margin-top:.9rem; font-size:.65rem; color:var(--cy-dim);
      letter-spacing:.18em; text-transform:uppercase; }
</style></head><body>
<div id="frame">
 <span class="corner tl"></span><span class="corner tr"></span>
 <span class="corner bl"></span><span class="corner br"></span>
 <header>
  <div id="reactor"></div>
  <div>
   <h1>ALFRED</h1>
   <div id="status">systems <b id="state">nominal</b> · the gate is watching</div>
  </div>
 </header>
 <div id="log"></div><div id="gates"></div>
 <div id="bar">
  <input id="text" type="text" placeholder="your word is my command, sir…" autofocus>
  <button id="mic" title="push-to-talk, 5 seconds">◉ mic</button>
  <button id="bell" title="the bell — abort everything">◼ stop</button>
 </div>
 <div id="cmds">
  <button data-cmd="menu">menu</button><button data-cmd="undo">undo</button>
  <button data-cmd="ledger">ledger</button><button data-cmd="burn">burn</button>
  <label title="webcam rings the stop bell on a big wave — never commands">
   <input type="checkbox" id="motion"> &#128247; motion bell</label>
  <span style="color:var(--cy-dim);font-size:.7rem;letter-spacing:.12em">
   &#9000; CTRL+ALT+C summons this HUD anywhere</span>
  <button id="cog" style="margin-left:auto" title="settings">&#9881; settings</button>
 </div>
 <div id="hint">inputs: type here · &#9673; mic (5s push-to-talk) · &#128247; motion (stop only) · global hotkey — one validated door</div>
</div>
<script>
const TOKEN = "__TOKEN__";
const log = document.getElementById("log");
const reactor = document.getElementById("reactor");
const stateEl = document.getElementById("state");
function say(t, me, flash){ const line = document.createElement("div");
  if (me) line.className = "me";
  if (flash){ line.className = "act";
    if (!reactor.className){ reactor.className = "blip";
      setTimeout(()=>{ if(reactor.className==="blip") reactor.className=""; }, 800); } }
  line.textContent = (me ? "› " : "") + t;
  log.append(line); log.scrollTop = log.scrollHeight; }
function post(path, body){ return fetch(path, {method:"POST",
  headers:{"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}); }
function setState(s){
  reactor.className = s === "idle" ? "" : s;
  stateEl.textContent = s === "idle" ? "nominal" : s; }
const gates = document.getElementById("gates");
function gateCard(e){
  const card = document.createElement("div"); card.className = "gate"; card.id = "g"+e.id;
  const label = document.createElement("span");
  const buttons = document.createElement("span");
  buttons.style.display = "flex"; buttons.style.gap = ".4rem";
  if (e.kind === "announce"){
    let left = e.seconds;
    label.textContent = `${e.summary} — engaging in ${left.toFixed(0)}s`;
    const timer = setInterval(()=>{ left -= 0.25;
      if(left <= 0){ clearInterval(timer); card.remove(); }
      else label.textContent = `${e.summary} — engaging in ${Math.ceil(left)}s`; }, 250);
    const cancel = document.createElement("button"); cancel.textContent = "belay";
    cancel.onclick = ()=>{ clearInterval(timer); post("/api/gate",{id:e.id,go:false}); card.remove(); };
    buttons.append(cancel);
  } else {
    label.textContent = e.summary;
    for (const [text, go] of [["engage", true], ["negative", false]]){
      const b = document.createElement("button"); b.textContent = text;
      b.onclick = ()=>{ post("/api/gate",{id:e.id,go}); card.remove(); };
      buttons.append(b);
    }
  }
  card.append(label, buttons); gates.append(card);
}
const events = new EventSource("/api/events?t="+TOKEN);
events.onmessage = (m)=>{ const e = JSON.parse(m.data);
  if (e.type === "say") say(e.text, false, e.flash);
  else if (e.type === "state") setState(e.state);
  else if (e.type === "gate") gateCard(e);
  else if (e.type === "gate_done"){ const c = document.getElementById("g"+e.id); if(c) c.remove(); } };
const text = document.getElementById("text");
text.addEventListener("keydown",(k)=>{ if(k.key==="Enter" && text.value.trim()){
  say(text.value.trim(), true); post("/api/ask",{text:text.value.trim()}); text.value=""; }});
document.getElementById("mic").onclick = ()=>post("/api/voice");
document.getElementById("bell").onclick = ()=>post("/api/bell");
document.querySelectorAll("[data-cmd]").forEach(b=>b.onclick=()=>post("/api/command",{name:b.dataset.cmd}));
document.getElementById("motion").onchange = (e)=>post("/api/motion",{enable:e.target.checked});
document.getElementById("cog").onclick = ()=>{ location.href = "/settings?t="+TOKEN; };
say("Good day, sir. All systems at your disposal.");
</script></body></html>"""


SETTINGS_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALFRED — settings</title>
<style>
 :root { --cy:#39d7ff; --cy-dim:#1a7fa0; --cy-glow:rgba(57,215,255,.45);
         --amber:#ffb02e; --ink:#04080f; }
 * { box-sizing:border-box; margin:0; }
 body { background:radial-gradient(1200px 700px at 50% -10%, #0a1a2b 0%, var(--ink) 60%),
        var(--ink); color:var(--cy); font:14px Consolas, monospace;
        display:flex; justify-content:center; padding:2rem 1rem; }
 #frame { width:min(720px,100%); border:1px solid rgba(57,215,255,.25);
        background:rgba(4,10,18,.85); padding:1.6rem;
        box-shadow:0 0 40px rgba(57,215,255,.08); }
 h1 { font-size:1rem; letter-spacing:.45em; color:#d9f6ff;
        text-shadow:0 0 8px var(--cy-glow); margin-bottom:1rem; }
 h2 { font-size:.75rem; letter-spacing:.3em; color:var(--cy-dim);
        margin:1.2rem 0 .5rem; text-transform:uppercase; }
 .row { display:flex; gap:.6rem; align-items:center; margin:.4rem 0; }
 .row label { width:180px; color:var(--cy-dim); font-size:.75rem;
        letter-spacing:.1em; text-transform:uppercase; }
 input, select, textarea { background:rgba(6,14,24,.9); color:#e9fbff;
        border:1px solid rgba(57,215,255,.35); padding:.45rem .6rem;
        font:inherit; outline:none; flex:1; }
 textarea { width:100%; height:260px; white-space:pre; font-size:12px; }
 button { background:transparent; color:var(--cy); font:inherit; cursor:pointer;
        border:1px solid rgba(57,215,255,.45); padding:.55rem .9rem;
        letter-spacing:.12em; text-transform:uppercase; font-size:.72rem;
        clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),
                          calc(100% - 8px) 100%,0 100%,0 8px); }
 button:hover { background:rgba(57,215,255,.08); box-shadow:0 0 14px var(--cy-glow); }
 #status { margin-top:.8rem; color:var(--amber); font-size:.75rem; min-height:1.2em;
        text-shadow:0 0 6px rgba(255,176,46,.4); }
 .hintline { color:var(--cy-dim); font-size:.65rem; margin:.3rem 0 0;
        letter-spacing:.08em; }
</style></head><body><div id="frame">
 <h1>ALFRED — SETTINGS</h1>
 <h2>Voice &amp; hearing</h2>
 <div class="row"><label>voice pace (0.7–1.6)</label>
  <input id="voice_pace" type="number" step="0.02" min="0.7" max="1.6"></div>
 <div class="row"><label>voice volume (0–1)</label>
  <input id="voice_volume" type="number" step="0.05" min="0" max="1"></div>
 <div class="row"><label>hearing (whisper)</label>
  <select id="whisper"><option>tiny</option><option>base</option><option>small</option></select></div>
 <div class="row"><label>voice model (piper)</label><input id="piper_voice"></div>
 <h2>Brain &amp; web</h2>
 <div class="row"><label>planner model</label><input id="model"></div>
 <div class="row"><label>search engine url</label><input id="search"></div>
 <div class="row"><button id="save">save preferences</button>
  <button id="apps">rescan apps</button><button id="vocab">relearn bookmarks</button>
  <button id="back">back to the hud</button></div>
 <h2>House customs — routines &amp; modes</h2>
 <p class="hintline">phrases trigger the plan; every plan still faces the validator and the tiers.</p>
 <textarea id="customs" spellcheck="false"></textarea>
 <div class="row"><button id="saveCustoms">save customs</button></div>
 <div id="status"></div>
</div>
<script>
const TOKEN = "__TOKEN__";
const status = (t)=>{ document.getElementById("status").textContent = t; };
const FIELDS = ["voice_pace","voice_volume","whisper","piper_voice","model","search"];
function post(path, body){ return fetch(path, {method:"POST",
  headers:{"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}); }
fetch("/api/settings?t="+TOKEN).then(r=>r.json()).then(d=>{
  for (const f of FIELDS) document.getElementById(f).value = d.settings[f];
  document.getElementById("customs").value = d.customs; });
document.getElementById("save").onclick = async ()=>{
  const body = {}; for (const f of FIELDS) body[f] = document.getElementById(f).value;
  await post("/api/settings", body); status("Preferences saved — applied immediately."); };
document.getElementById("saveCustoms").onclick = async ()=>{
  const r = await post("/api/customs", {text: document.getElementById("customs").value});
  status(r.ok ? "Customs saved — live on the next ask." : "Rejected: " + await r.text()); };
document.getElementById("apps").onclick = async ()=>{
  await post("/api/rescan", {what:"apps"}); status("Start Menu rescanned."); };
document.getElementById("vocab").onclick = async ()=>{
  await post("/api/rescan", {what:"vocab"}); status("Bookmarks relearned."); };
document.getElementById("back").onclick = ()=>{ location.href = "/?t="+TOKEN; };
</script></body></html>"""
