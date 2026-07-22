"""The HUD page itself — presentation only, no power.

Everything the page can do goes through the token-guarded API in web.py;
restyling this file can never widen the attack surface. Two pages live here,
the HUD and the settings room, sharing one palette:

    violet  structure — frames, rings, the butler's own voice
    blue    information — what he heard, what he knows, what you typed
    gold    attention — consent, warnings, and the first-run invitation

Cool colours carry the ordinary; the warm one is spent only where the master's
judgement is actually wanted, so a gold thing on screen always means the same.
"""

# The crest: a butler's bowtie inside a hex ring — service inside engineering.
# Inline SVG and a data-URI favicon, so the page stays entirely self-contained.
LOGO = ("<svg class='crest' viewBox='0 0 64 64' aria-hidden='true'>"
        "<defs><linearGradient id='cg' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#c9a4ff'/>"
        "<stop offset='100%' stop-color='#3fd0ff'/></linearGradient></defs>"
        "<polygon points='32,3 58,17 58,47 32,61 6,47 6,17' fill='none' "
        "stroke='url(#cg)' stroke-width='2.5'/>"
        "<circle cx='32' cy='32' r='19' fill='none' stroke='url(#cg)' "
        "stroke-width='1' stroke-dasharray='3 4' opacity='.55'/>"
        "<path d='M32 32 L18 23 L18 41 Z' fill='url(#cg)'/>"
        "<path d='M32 32 L46 23 L46 41 Z' fill='url(#cg)'/>"
        "<circle cx='32' cy='32' r='4' fill='#f2eaff'/></svg>")

FAVICON = ("data:image/svg+xml;utf8,"
           "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
           "<polygon points='32,3 58,17 58,47 32,61 6,47 6,17' fill='none' "
           "stroke='%23a06bff' stroke-width='4'/>"
           "<path d='M32 32 L18 23 L18 41 Z' fill='%233fd0ff'/>"
           "<path d='M32 32 L46 23 L46 41 Z' fill='%23a06bff'/>"
           "<circle cx='32' cy='32' r='4' fill='%23f2eaff'/></svg>")

_PALETTE = """
 :root {
   --vio:#a06bff; --vio-soft:#c9a4ff; --vio-dim:#6a4aa8;
   --blu:#3fd0ff; --blu-dim:#2b7f9e;
   --gold:#ffc65c; --gold-dim:#8a6a2a;
   --red:#ff5a6e;
   --ink:#05060f; --panel:rgba(10,8,22,.86);
   --vio-glow:rgba(160,107,255,.45); --blu-glow:rgba(63,208,255,.40);
   --line:rgba(160,107,255,.22);
 }
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALFRED</title>
<link rel="icon" href="__FAVICON__">
<style>
__PALETTE__
 * { box-sizing:border-box; margin:0; }
 body { background:
        radial-gradient(1100px 620px at 18% -12%, #2a1350 0%, transparent 62%),
        radial-gradient(900px 560px at 88% 6%, #06304a 0%, transparent 58%),
        var(--ink);
        color:var(--blu); font:14px Consolas, 'Cascadia Mono', monospace;
        min-height:100vh; display:flex; align-items:center; justify-content:center;
        padding:1.6rem 1.2rem; }
 body::after { content:""; position:fixed; inset:0; pointer-events:none;
        background:
        linear-gradient(rgba(160,107,255,.045) 1px, transparent 1px) 0 0/100% 46px,
        linear-gradient(90deg, rgba(63,208,255,.035) 1px, transparent 1px) 0 0/46px 100%; }

 /* --- three columns: cards, the voice, cards --------------------------- */
 #room { display:flex; gap:1.5rem; align-items:stretch;
        width:min(1400px,100%); }
 .side { width:212px; flex:none; display:flex; flex-direction:column; gap:.75rem; }

 /* each reading is its own card, standing apart from the stage */
 .card { position:relative; padding:.7rem .8rem;
        border:1px solid var(--line); background:var(--panel);
        box-shadow:0 0 26px rgba(160,107,255,.07); }
 .card::before { content:""; position:absolute; left:0; top:0; width:2px; height:100%;
        background:linear-gradient(180deg, var(--vio), transparent); }
 .card .name { font-size:.55rem; letter-spacing:.24em; text-transform:uppercase;
        color:var(--vio-dim); }
 .card .value { font-size:1.28rem; letter-spacing:.02em; color:var(--blu);
        font-variant-numeric:tabular-nums; margin:.2rem 0 .3rem;
        text-shadow:0 0 12px var(--blu-glow); transition:color .3s; }
 .card .note { font-size:.56rem; letter-spacing:.1em; color:var(--vio-dim); }
 .track { height:5px; background:rgba(160,107,255,.10);
        border:1px solid rgba(160,107,255,.16); overflow:hidden; position:relative; }
 .fill { height:100%; width:100%; transform:scaleX(0); transform-origin:left;
        background:linear-gradient(90deg, var(--vio), var(--blu));
        box-shadow:0 0 12px var(--blu-glow);
        transition:transform .8s cubic-bezier(.22,1,.36,1), background .4s; }
 .card.warm .fill { background:linear-gradient(90deg, var(--gold), #ff9a5c); }
 .card.warm .value { color:var(--gold); text-shadow:0 0 12px rgba(255,198,92,.5); }
 .card.hot .fill { background:linear-gradient(90deg, #ff7a5c, var(--red)); }
 .card.hot .value { color:var(--red); text-shadow:0 0 12px rgba(255,90,110,.5); }
 .card.hot::before { background:linear-gradient(180deg, var(--red), transparent); }
 .rows { display:flex; flex-direction:column; gap:.28rem; margin-top:.15rem; }
 .rows div { display:flex; justify-content:space-between; gap:.5rem;
        font-size:.58rem; letter-spacing:.14em; text-transform:uppercase;
        color:var(--vio-dim); }
 .rows b { color:var(--blu); text-transform:none; letter-spacing:.02em;
        font-size:.66rem; text-align:right; }
 .rows b.off { color:var(--vio-dim); }
 .rows b.live { color:var(--gold); text-shadow:0 0 8px rgba(255,198,92,.5); }

 /* --- the stage: the voice, and nothing that isn't the voice ----------- */
 #stage { flex:1; min-width:0; position:relative; padding:1.4rem 1.6rem 1.2rem;
        border:1px solid var(--line); background:var(--panel);
        display:flex; flex-direction:column;
        box-shadow:0 0 60px rgba(160,107,255,.10),
                   inset 0 0 70px rgba(63,208,255,.035); }
 .corner { position:absolute; width:20px; height:20px; border:2px solid var(--vio);
        filter:drop-shadow(0 0 5px var(--vio-glow)); }
 .tl { top:-2px; left:-2px; border-right:0; border-bottom:0; }
 .tr { top:-2px; right:-2px; border-left:0; border-bottom:0; }
 .bl { bottom:-2px; left:-2px; border-right:0; border-top:0; }
 .br { bottom:-2px; right:-2px; border-left:0; border-top:0; }

 header { display:flex; align-items:center; gap:.9rem; }
 #reactor { width:44px; height:44px; border-radius:50%; position:relative; flex:none;
        background:radial-gradient(circle, #fff 0%, #dcc6ff 14%, var(--vio) 42%,
                   rgba(40,16,80,.92) 72%);
        box-shadow:0 0 16px var(--vio-glow), 0 0 46px rgba(160,107,255,.28),
                   inset 0 0 12px rgba(255,255,255,.65);
        animation:pulse 2.6s ease-in-out infinite; }
 #reactor::before { content:""; position:absolute; inset:-6px; border-radius:50%;
        border:1px dashed rgba(63,208,255,.55); animation:spin 13s linear infinite; }
 #reactor.working { animation:pulse .7s ease-in-out infinite; }
 #reactor.listening { background:radial-gradient(circle, #fff8ea 0%, #ffe2ac 16%,
        var(--gold) 44%, rgba(70,48,10,.92) 72%);
        box-shadow:0 0 16px rgba(255,198,92,.55), 0 0 46px rgba(255,198,92,.30); }
 #reactor.speaking { background:radial-gradient(circle, #eafaff 0%, #a9e9ff 16%,
        var(--blu) 44%, rgba(8,52,70,.92) 72%);
        box-shadow:0 0 16px var(--blu-glow), 0 0 46px rgba(63,208,255,.30); }
 @keyframes pulse { 0%,100% { transform:scale(1) } 50% { transform:scale(1.07) } }
 @keyframes spin { to { transform:rotate(360deg) } }
 .crest { width:24px; height:24px; flex:none;
        filter:drop-shadow(0 0 6px var(--vio-glow)); }
 .wordmark { display:flex; align-items:center; gap:.5rem; }
 h1 { font-size:1rem; letter-spacing:.55em; font-weight:600;
      background:linear-gradient(90deg, var(--vio-soft), var(--blu));
      -webkit-background-clip:text; background-clip:text; color:transparent; }
 #status { font-size:.62rem; color:var(--vio-dim); letter-spacing:.22em;
      margin-top:.25rem; text-transform:uppercase; }
 #status b { color:var(--blu); }
 #tabs { display:flex; gap:.35rem; margin-left:auto; }
 .tab { padding:.4rem .9rem; cursor:pointer; border:1px solid var(--line);
      background:rgba(160,107,255,.05); font-size:.6rem; letter-spacing:.24em;
      text-transform:uppercase; color:var(--vio-dim);
      transition:color .25s, border-color .25s, background .25s, box-shadow .25s; }
 .tab:hover { color:var(--vio-soft); }
 .tab.on { color:var(--blu); border-color:rgba(63,208,255,.6);
      background:linear-gradient(180deg, rgba(63,208,255,.14), transparent);
      box-shadow:0 0 16px rgba(63,208,255,.20); }

 /* whose voice it is */
 #who { display:flex; justify-content:center; gap:2.4rem; margin-top:1rem;
      font-size:.6rem; letter-spacing:.3em; text-transform:uppercase; }
 #who span { color:rgba(160,107,255,.28); transition:color .3s, text-shadow .3s; }
 #who.listening .me { color:var(--gold); text-shadow:0 0 12px rgba(255,198,92,.6); }
 #who.speaking .him { color:var(--blu); text-shadow:0 0 12px var(--blu-glow); }

 /* the visualiser is a canvas: one element, drawn only when there is
    something to say, rather than dozens of animated boxes */
 #wave { display:block; width:100%; height:230px; }
 #sub { min-height:3rem; text-align:center; font-size:1.4rem; line-height:1.45;
      color:#f0f8ff; text-shadow:0 0 18px var(--blu-glow); padding:0 1rem; }
 #hint2 { text-align:center; font-size:.6rem; letter-spacing:.24em;
      text-transform:uppercase; color:var(--vio-dim); margin-top:.5rem; }

 /* the plan preview and gates — the consent surface must never be hidden */
 #feed { margin-top:.9rem; max-height:104px; overflow-y:auto; font-size:11.5px;
      line-height:1.65; color:var(--vio-soft); white-space:pre-wrap;
      scrollbar-color:var(--vio-dim) transparent; padding-right:.3rem; }
 #feed .me { color:#dff3ff; }
 #feed .act { color:var(--gold); }
 .gate { border:1px solid var(--gold); background:rgba(38,26,6,.55);
      padding:.55rem .75rem; margin:.5rem 0; display:flex; gap:.8rem;
      align-items:center; justify-content:space-between; color:var(--gold);
      font-size:11.5px; box-shadow:0 0 22px rgba(255,198,92,.12); }
 .gate::before { content:"⚠"; font-size:.9rem; flex:none; }
 .gate button { border-color:var(--gold); color:var(--gold); }

 /* the video page, for later */
 #screen { display:none; align-items:center; justify-content:center; height:230px; }
 #cam { max-width:100%; max-height:230px; border-radius:18px;
      box-shadow:0 0 40px rgba(160,107,255,.28); }
 #signs { display:flex; gap:.45rem; justify-content:center; margin-top:.8rem;
      flex-wrap:wrap; }
 .sign { padding:.36rem .7rem; border-radius:10px; font-size:.58rem;
      letter-spacing:.16em; text-transform:uppercase; color:var(--vio-dim);
      border:1px solid rgba(160,107,255,.22); background:rgba(160,107,255,.05);
      transition:color .25s, border-color .25s, box-shadow .25s, transform .25s; }
 .sign.seen { color:var(--gold); border-color:var(--gold); transform:translateY(-2px);
      box-shadow:0 0 18px rgba(255,198,92,.45); }

 #bar { display:flex; gap:.5rem; align-items:center; margin-top:auto;
      padding-top:.9rem; flex-wrap:wrap; }
 button { background:transparent; color:var(--blu); font:inherit; cursor:pointer;
      border:1px solid rgba(160,107,255,.45); padding:.55rem .85rem;
      letter-spacing:.12em; text-transform:uppercase; font-size:.68rem;
      clip-path:polygon(8px 0, 100% 0, 100% calc(100% - 8px),
                        calc(100% - 8px) 100%, 0 100%, 0 8px);
      transition:box-shadow .15s, background .15s, color .15s; }
 button:hover { background:rgba(160,107,255,.10); color:var(--vio-soft);
      box-shadow:0 0 16px var(--vio-glow); }
 #mic { border-color:rgba(63,208,255,.55); }
 #bell { color:var(--red); border-color:rgba(255,90,110,.6); }
 #bell:hover { background:rgba(255,90,110,.08); color:var(--red); }
 label { color:var(--vio-dim); font-size:.62rem; letter-spacing:.12em;
      text-transform:uppercase; display:flex; gap:.4rem; align-items:center;
      cursor:pointer; }
 input[type=checkbox] { accent-color:var(--vio); }

 #attune { display:flex; align-items:center; gap:1rem; margin-top:.8rem;
      padding:.6rem .8rem; border:1px solid var(--gold);
      background:linear-gradient(90deg, rgba(255,198,92,.10), transparent 70%); }
 #attune b { color:#ffe2ac; font-size:.8rem; }
 #attune span { display:block; color:var(--vio-dim); font-size:.66rem;
      margin-top:.15rem; }
 #attune button { border-color:var(--gold); color:var(--gold); margin-left:auto; }
 #attune.known { display:none; }

 @media (max-width:1120px) { #room { flex-wrap:wrap; }
      .side { width:calc(50% - .75rem); order:2; }
      #stage { order:1; flex:1 0 100%; } }
</style></head><body>
<div id="room">

 <div class="side">
  <div class="card" id="cCpu"><div class="name">processor</div>
   <div class="value">—</div><div class="track"><div class="fill"></div></div>
   <div class="note" id="nCpu">&nbsp;</div></div>
  <div class="card" id="cGpu"><div class="name">graphics</div>
   <div class="value">—</div><div class="track"><div class="fill"></div></div>
   <div class="note">all engines</div></div>
  <div class="card" id="cRam"><div class="name">memory</div>
   <div class="value">—</div><div class="track"><div class="fill"></div></div>
   <div class="note" id="nRam">&nbsp;</div></div>
  <div class="card" id="cDisk"><div class="name">storage</div>
   <div class="value">—</div><div class="track"><div class="fill"></div></div>
   <div class="note" id="nDisk">&nbsp;</div></div>
 </div>

 <main id="stage">
  <span class="corner tl"></span><span class="corner tr"></span>
  <span class="corner bl"></span><span class="corner br"></span>
  <header>
   <div id="reactor"></div>
   <div>
    <div class="wordmark">__LOGO__<h1>ALFRED</h1></div>
    <div id="status">systems <b id="state">nominal</b> · the gate is watching</div>
   </div>
   <div id="tabs">
    <div class="tab on" data-page="voice">◉ voice</div>
    <div class="tab" data-page="video">▣ video</div>
   </div>
  </header>

  <div id="who"><span class="me">you</span><span class="him">alfred</span></div>
  <canvas id="wave"></canvas>
  <div id="screen"><img id="cam" alt="the camera, as Alfred sees it"></div>
  <div id="signs" style="display:none">
   <span class="sign" data-sign="open_palm">open palm</span>
   <span class="sign" data-sign="fist">fist</span>
   <span class="sign" data-sign="peace">peace</span>
   <span class="sign" data-sign="point">point</span>
   <span class="sign" data-sign="thumbs_up">thumbs up</span>
  </div>
  <div id="sub">__GREETING__</div>
  <div id="hint2">press <b>__HOLD_LABEL__</b> to listen · press again to send</div>

  <div id="feed"></div><div id="gates"></div>

  <div id="attune" class="__ATTUNE_STATE__">
   <div><b>Make Alfred yours.</b>
    <span>He'll learn your software and where you actually go — all of it stays here.</span></div>
   <button id="attuneBtn">⟡ attune</button>
  </div>

  <div id="bar">
   <button id="mic" title="push-to-talk, 5 seconds">◉ mic</button>
   <button id="bell" title="the bell — abort everything">◼ stop</button>
   <button data-cmd="undo">undo</button>
   <button data-cmd="privacy" title="everything I know about you">privacy</button>
   <label title="webcam reads hand gestures on demand; every gesture is confirmed">
    <input type="checkbox" id="gestures"> &#128400; camera</label>
   <button id="cog" style="margin-left:auto" title="settings">&#9881;</button>
  </div>
 </main>

 <div class="side">
  <div class="card"><div class="name">the butler</div>
   <div class="rows">
    <div><span>brain</span><b id="rModel">—</b></div>
    <div><span>hearing</span><b id="rHearing">—</b></div>
    <div><span>voice</span><b id="rVoice">—</b></div>
    <div><span>pace</span><b id="rPace">—</b></div>
   </div></div>
  <div class="card"><div class="name">what he knows</div>
   <div class="rows">
    <div><span>places</span><b id="rSites">—</b></div>
    <div><span>programs</span><b id="rApps">—</b></div>
    <div><span>your names</span><b id="rShort">—</b></div>
   </div></div>
  <div class="card"><div class="name">the browser</div>
   <div class="rows">
    <div><span>bridge</span><b id="rBridge">—</b></div>
    <div><span>tabs seen</span><b id="rTabs">—</b></div>
    <div><span>camera</span><b id="rCam">—</b></div>
   </div></div>
  <div class="card"><div class="name">on duty</div>
   <div class="rows">
    <div><span>uptime</span><b id="rUp">—</b></div>
    <div><span>undo depth</span><b id="rUndo">—</b></div>
    <div><span>time</span><b id="clock">—</b></div>
   </div></div>
 </div>

</div>
<script>
const TOKEN = "__TOKEN__";
const feed = document.getElementById("feed");
const reactor = document.getElementById("reactor");
const stateEl = document.getElementById("state");
const who = document.getElementById("who");
const sub = document.getElementById("sub");
function say(t, me, flash){ const line = document.createElement("div");
  if (me) line.className = "me";
  if (flash) line.className = "act";
  line.textContent = (me ? "› " : "") + t;
  feed.append(line); feed.scrollTop = feed.scrollHeight;
  while (feed.childNodes.length > 60) feed.removeChild(feed.firstChild); }
function post(path, body){ return fetch(path, {method:"POST",
  headers:{"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}); }

// --- the visualiser --------------------------------------------------------
// One canvas rather than dozens of animated elements, and it only draws while
// there is something worth drawing: idle costs a slow drift, not sixty frames.
const wave = document.getElementById("wave");
const ctx = wave.getContext("2d");
let mode = "idle", energy = 0.10, target = 0.10, phase = 0, raf = null;
function fit(){ const r = wave.getBoundingClientRect(), d = devicePixelRatio || 1;
  wave.width = Math.max(1, r.width * d); wave.height = Math.max(1, r.height * d);
  ctx.setTransform(d, 0, 0, d, 0, 0); }
addEventListener("resize", fit);
const PALETTE = { idle:["#6a4aa8","#2b7f9e"], listening:["#ffc65c","#ff9a5c"],
                  speaking:["#3fd0ff","#a06bff"] };
function draw(){
  const w = wave.clientWidth, h = wave.clientHeight, mid = h / 2;
  ctx.clearRect(0, 0, w, h);
  energy += (target - energy) * 0.08;
  phase += mode === "idle" ? 0.006 : 0.028;
  const [a, b] = PALETTE[mode] || PALETTE.idle;
  const paint = ctx.createLinearGradient(0, 0, w, 0);
  paint.addColorStop(0, a); paint.addColorStop(1, b);
  for (let layer = 0; layer < 3; layer++){
    const depth = 1 - layer * 0.28;
    ctx.beginPath();
    for (let x = 0; x <= w; x += 3){
      const p = x / w;
      // a bell so the shape tapers to nothing at both ends, and three sines
      // of different speeds so it never repeats visibly
      const bell = Math.pow(Math.sin(Math.PI * p), 1.7);
      const y = Math.sin(p * 11 + phase * 2.1 + layer)
              + Math.sin(p * 19 - phase * 1.4 + layer * 2) * 0.55
              + Math.sin(p * 5 + phase * 0.8) * 0.75;
      const amp = bell * energy * (h * 0.34) * depth;
      const py = mid + y * amp * 0.42;
      x ? ctx.lineTo(x, py) : ctx.moveTo(x, py);
    }
    ctx.strokeStyle = paint;
    ctx.globalAlpha = layer === 0 ? 0.95 : 0.30 - layer * 0.07;
    ctx.lineWidth = layer === 0 ? 2.4 : 1.4;
    ctx.shadowBlur = layer === 0 ? 18 : 0; ctx.shadowColor = a;
    ctx.stroke();
  }
  ctx.globalAlpha = 1; ctx.shadowBlur = 0;
  raf = requestAnimationFrame(draw);
}
function startDrawing(){ if (!raf){ fit(); raf = requestAnimationFrame(draw); } }
function stopDrawing(){ if (raf){ cancelAnimationFrame(raf); raf = null; } }
document.addEventListener("visibilitychange",
  ()=> document.hidden ? stopDrawing() : startDrawing());
startDrawing();

function setState(s){
  reactor.className = s === "idle" ? "" : s;
  stateEl.textContent = s === "idle" ? "nominal" : s;
  who.className = (s === "listening" || s === "speaking") ? s : "";
  mode = (s === "listening" || s === "speaking") ? s : "idle";
  target = mode === "idle" ? 0.10 : 1.0;
  if (s === "listening") sub.textContent = "Listening…";
}
// --- the cards -------------------------------------------------------------
function card(id, percent, noteId, noteText){
  const box = document.getElementById(id); if (!box) return;
  const shown = Math.max(0, Math.min(100, percent || 0));
  box.querySelector(".fill").style.transform = "scaleX(" + (shown / 100) + ")";
  box.querySelector(".value").textContent = shown.toFixed(0) + "%";
  box.classList.toggle("warm", shown >= 65 && shown < 85);
  box.classList.toggle("hot", shown >= 85);
  if (noteId) document.getElementById(noteId).textContent = noteText;
}
function put(id, value, tone){ const el = document.getElementById(id);
  if (el){ el.textContent = value; el.className = tone || ""; } }
function instruments(t){
  card("cCpu", t.cpu, "nCpu", "busy " + (t.cpu||0).toFixed(0) + "%");
  card("cGpu", t.gpu);
  card("cRam", t.ram.percent, "nRam", t.ram.used + " / " + t.ram.total + " GiB");
  card("cDisk", t.disk.percent, "nDisk", t.disk.used + " / " + t.disk.total + " GB");
  const a = t.alfred; if (!a) return;
  put("rModel", a.model); put("rHearing", a.hearing);
  put("rVoice", a.muted ? "muted" : a.voice, a.muted ? "off" : "");
  put("rPace", a.pace + "×");
  put("rSites", a.sites); put("rApps", a.apps); put("rShort", a.shortcuts);
  put("rBridge", a.bridge, a.bridge === "connected" ? "live" : "off");
  put("rTabs", a.tabs || "—", a.tabs ? "" : "off");
  put("rCam", a.camera ? "open" : "closed", a.camera ? "live" : "off");
  put("rUndo", a.undo || "—", a.undo ? "" : "off");
  const m = Math.floor(a.uptime / 60), hh = Math.floor(m / 60);
  put("rUp", hh ? hh + "h " + (m % 60) + "m" : m + "m " + (a.uptime % 60) + "s");
}
setInterval(()=>{ const d = new Date();
  put("clock", String(d.getHours()).padStart(2,"0") + ":" +
               String(d.getMinutes()).padStart(2,"0")); }, 1000);
// --- consent ---------------------------------------------------------------
const gates = document.getElementById("gates");
function gateCard(e){
  const box = document.createElement("div"); box.className = "gate"; box.id = "g"+e.id;
  const label = document.createElement("span");
  const buttons = document.createElement("span");
  buttons.style.display = "flex"; buttons.style.gap = ".4rem";
  if (e.kind === "seal"){
    label.textContent = e.summary + " — type your approval, exactly:";
    const field = document.createElement("input");
    field.placeholder = "yes i approve please proceed";
    field.style.cssText = "flex:1;min-width:13rem;background:#0a0714;border:1px solid var(--gold);color:var(--gold);padding:.35rem .5rem;font:inherit";
    const b = document.createElement("button"); b.textContent = "approve";
    const send = ()=>{ post("/api/gate",{id:e.id,phrase:field.value}); box.remove(); };
    b.onclick = send;
    field.addEventListener("keydown",(k)=>{ if(k.key==="Enter") send(); });
    buttons.append(field, b); setTimeout(()=>field.focus(), 0);
  } else {
    label.textContent = e.summary;
    for (const [text, go] of [["engage", true], ["negative", false]]){
      const b = document.createElement("button"); b.textContent = text;
      b.onclick = ()=>{ post("/api/gate",{id:e.id,go}); box.remove(); };
      buttons.append(b);
    }
  }
  box.append(label, buttons); gates.append(box);
}
// --- voice / video ---------------------------------------------------------
const cam = document.getElementById("cam"), screen = document.getElementById("screen");
const signs = document.getElementById("signs");
let page = "voice";
function show(name){
  page = name;
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("on", t.dataset.page === name));
  const voice = name === "voice";
  wave.style.display = voice ? "block" : "none";
  who.style.display = voice ? "flex" : "none";
  screen.style.display = voice ? "none" : "flex";
  signs.style.display = voice ? "none" : "flex";
  if (voice){ camStream(false); startDrawing(); } else { stopDrawing(); }
}
document.querySelectorAll(".tab").forEach(t => t.onclick = ()=>show(t.dataset.page));
function camStream(on){
  if (on){ cam.src = "/api/camera.mjpg?t=" + TOKEN; cam.style.display = "block"; }
  else { cam.removeAttribute("src"); cam.style.display = "none"; }
}
// --- the wire --------------------------------------------------------------
const events = new EventSource("/api/events?t="+TOKEN);
events.onmessage = (m)=>{ const e = JSON.parse(m.data);
  if (e.type === "say") say(e.text, false, e.flash);
  else if (e.type === "subtitle") sub.textContent = e.text ? ("“" + e.text + "”") : "";
  else if (e.type === "telemetry") instruments(e);
  else if (e.type === "state") setState(e.state);
  else if (e.type === "gate") gateCard(e);
  else if (e.type === "gesture"){
    const chip = document.querySelector('.sign[data-sign="' + e.name + '"]');
    if (chip){ chip.classList.add("seen");
               setTimeout(()=>chip.classList.remove("seen"), 1600); } }
  else if (e.type === "gate_done"){ const c = document.getElementById("g"+e.id); if(c) c.remove(); } };
document.getElementById("mic").onclick = ()=>post("/api/voice");
document.getElementById("bell").onclick = ()=>post("/api/bell");
const HOLD = __HOLD_KEYS__;
const GLOBAL_KEYS = __GLOBAL_KEYS__;
function typingNow(){ const el = document.activeElement;
  return el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"); }
if (!GLOBAL_KEYS) {
  const held = new Set(); let latched = false;
  const allHeld = ()=> HOLD.every(k => held.has(k));
  addEventListener("keydown",(e)=>{ if(e.repeat || typingNow()) return;
    const k = e.key.toLowerCase(); if(!HOLD.includes(k)) return;
    held.add(k);
    if(allHeld()){ latched = !latched; post("/api/listen",{on:latched}); }
  });
  addEventListener("keyup",(e)=>{ const k = e.key.toLowerCase();
    if(HOLD.includes(k)) held.delete(k); });
}
document.querySelectorAll("[data-cmd]").forEach(b=>b.onclick=()=>post("/api/command",{name:b.dataset.cmd}));
document.getElementById("gestures").onchange = (e)=>{
  post("/api/gestures",{enable:e.target.checked});
  if (e.target.checked){ show("video");
    setTimeout(()=>{ if (page === "video") camStream(true); }, 1200); }
  else camStream(false);
};
document.getElementById("cog").onclick = ()=>{ location.href = "/settings?t="+TOKEN; };
document.getElementById("attuneBtn").onclick = (e)=>{
  e.target.disabled = true; e.target.textContent = "attuning…";
  post("/api/attune").finally(()=>setTimeout(()=>{
    document.getElementById("attune").classList.add("known"); }, 1500));
};
show("voice");
</script></body></html>"""


SETTINGS_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALFRED — settings</title>
<link rel="icon" href="__FAVICON__">
<style>
__PALETTE__
 * { box-sizing:border-box; margin:0; }
 body { background:
        radial-gradient(1100px 620px at 18% -12%, #2a1350 0%, transparent 62%),
        radial-gradient(900px 560px at 88% 6%, #06304a 0%, transparent 58%),
        var(--ink); color:var(--blu);
        font:14px Consolas, 'Cascadia Mono', monospace;
        min-height:100vh; display:flex; justify-content:center; padding:2rem 1rem; }
 body::before { content:""; position:fixed; inset:0; pointer-events:none; z-index:2;
        background:repeating-linear-gradient(0deg, rgba(255,255,255,.022) 0 1px,
        transparent 1px 3px); opacity:.55; }
 body::after { content:""; position:fixed; inset:0; pointer-events:none;
        background:
        linear-gradient(rgba(160,107,255,.045) 1px, transparent 1px) 0 0/100% 46px,
        linear-gradient(90deg, rgba(63,208,255,.035) 1px, transparent 1px) 0 0/46px 100%; }
 #frame { width:min(760px,100%); position:relative; align-self:flex-start;
        border:1px solid var(--line); background:var(--panel);
        padding:1.6rem;
        box-shadow:0 0 60px rgba(160,107,255,.10),
                   inset 0 0 70px rgba(63,208,255,.035); }
 .corner { position:absolute; width:20px; height:20px; border:2px solid var(--vio);
        filter:drop-shadow(0 0 5px var(--vio-glow)); }
 .tl { top:-2px; left:-2px; border-right:0; border-bottom:0; }
 .tr { top:-2px; right:-2px; border-left:0; border-bottom:0; }
 .bl { bottom:-2px; left:-2px; border-right:0; border-top:0; }
 .br { bottom:-2px; right:-2px; border-left:0; border-top:0; }
 .crest { width:30px; height:30px; flex:none;
        filter:drop-shadow(0 0 6px var(--vio-glow)); }
 header { display:flex; align-items:center; gap:.7rem; margin-bottom:1.2rem;
        padding-bottom:.9rem; border-bottom:1px solid var(--line); }
 h1 { font-size:1rem; letter-spacing:.45em; font-weight:600;
      background:linear-gradient(90deg, var(--vio-soft), var(--blu));
      -webkit-background-clip:text; background-clip:text; color:transparent; }
 h2 { font-size:.7rem; letter-spacing:.3em; color:var(--vio-dim);
        margin:1.5rem 0 .6rem; text-transform:uppercase;
        display:flex; align-items:center; gap:.6rem; }
 h2::after { content:""; flex:1; height:1px;
        background:linear-gradient(90deg, var(--line), transparent); }
 .row { display:flex; gap:.6rem; align-items:center; margin:.45rem 0; }
 .row label { width:190px; color:var(--vio-dim); font-size:.7rem;
        letter-spacing:.1em; text-transform:uppercase; }
 input, select, textarea { background:rgba(8,6,18,.9); color:#eaf7ff;
        border:1px solid rgba(160,107,255,.35); padding:.5rem .65rem;
        font:inherit; outline:none; flex:1;
        transition:border-color .15s, box-shadow .15s; }
 input:focus, select:focus, textarea:focus { border-color:var(--vio);
        box-shadow:0 0 14px rgba(160,107,255,.28); }
 textarea { width:100%; height:260px; white-space:pre; font-size:12px; }
 button { background:transparent; color:var(--blu); font:inherit; cursor:pointer;
        border:1px solid rgba(160,107,255,.45); padding:.55rem .9rem;
        letter-spacing:.12em; text-transform:uppercase; font-size:.7rem;
        transition:background .15s, box-shadow .15s, color .15s;
        clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),
                          calc(100% - 8px) 100%,0 100%,0 8px); }
 button:hover { background:rgba(160,107,255,.10); color:var(--vio-soft);
        box-shadow:0 0 16px var(--vio-glow); }
 #save { border-color:var(--gold); color:var(--gold); }
 #save:hover { background:rgba(255,198,92,.10); color:var(--gold);
        box-shadow:0 0 16px rgba(255,198,92,.45); }
 #status { margin-top:.9rem; color:var(--gold); font-size:.75rem; min-height:1.2em;
        text-shadow:0 0 6px rgba(255,198,92,.4); }
 .hintline { color:var(--vio-dim); font-size:.65rem; margin:.3rem 0 .5rem;
        letter-spacing:.08em; }
</style></head><body><div id="frame">
 <span class="corner tl"></span><span class="corner tr"></span>
 <span class="corner bl"></span><span class="corner br"></span>
 <header>__LOGO__<h1>ALFRED</h1>
  <span style="margin-left:auto;color:var(--vio-dim);font-size:.65rem;
        letter-spacing:.2em;text-transform:uppercase">settings</span></header>
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
 <h2>Hotkeys</h2>
 <p class="hintline">e.g. summon "ctrl+alt+c", hold-to-talk "j+k". Effective on the next summons.</p>
 <div class="row"><label>summon hotkey</label><input id="summon_hotkey"></div>
 <div class="row"><label>hold-to-talk keys</label><input id="hold_keys"></div>
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
const FIELDS = ["voice_pace","voice_volume","whisper","piper_voice","model","search",
               "summon_hotkey","hold_keys"];
function post(path, body){ return fetch(path, {method:"POST",
  headers:{"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"},
  body:JSON.stringify(body||{})}); }
fetch("/api/settings?t="+TOKEN).then(r=>r.json()).then(d=>{
  for (const f of FIELDS) document.getElementById(f).value = d.settings[f];
  document.getElementById("customs").value = d.customs; });
document.getElementById("save").onclick = async ()=>{
  const body = {}; for (const f of FIELDS) body[f] = document.getElementById(f).value;
  const r = await post("/api/settings", body);
  status(r.ok ? "Preferences saved — applied immediately." : "Rejected: " + await r.text()); };
document.getElementById("saveCustoms").onclick = async ()=>{
  const r = await post("/api/customs", {text: document.getElementById("customs").value});
  status(r.ok ? "Customs saved — live on the next ask." : "Rejected: " + await r.text()); };
document.getElementById("apps").onclick = async ()=>{
  await post("/api/rescan", {what:"apps"}); status("Start Menu rescanned."); };
document.getElementById("vocab").onclick = async ()=>{
  await post("/api/rescan", {what:"vocab"}); status("Bookmarks relearned."); };
document.getElementById("back").onclick = ()=>{ location.href = "/?t="+TOKEN; };
</script></body></html>"""


# the crest, palette and visualiser are static — bake them in once, at import
for _name in ("PAGE", "SETTINGS_PAGE"):
    _doc = globals()[_name].replace("__LOGO__", LOGO).replace("__FAVICON__", FAVICON)
    _doc = _doc.replace("__PALETTE__", _PALETTE)
    globals()[_name] = _doc
