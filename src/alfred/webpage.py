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
        padding:2rem 1rem; }
 body::before { content:""; position:fixed; inset:0; pointer-events:none; z-index:2;
        background:repeating-linear-gradient(0deg, rgba(255,255,255,.022) 0 1px,
        transparent 1px 3px); mix-blend-mode:overlay; }
 body::after { content:""; position:fixed; inset:0; pointer-events:none;
        background:
        linear-gradient(rgba(160,107,255,.045) 1px, transparent 1px) 0 0/100% 46px,
        linear-gradient(90deg, rgba(63,208,255,.035) 1px, transparent 1px) 0 0/46px 100%; }

 /* --- the instrument rail ------------------------------------------------ */
 #shell { display:flex; gap:1rem; align-items:flex-start;
        width:min(1080px,100%); }
 #rail { width:216px; flex:none; position:relative; padding:1.1rem .9rem;
        border:1px solid var(--line); background:var(--panel);
        backdrop-filter:blur(3px);
        box-shadow:0 0 40px rgba(160,107,255,.08),
                   inset 0 0 50px rgba(63,208,255,.03); }
 #rail h2 { font-size:.6rem; letter-spacing:.3em; color:var(--vio-dim);
        text-transform:uppercase; margin-bottom:.9rem;
        display:flex; align-items:center; gap:.5rem; }
 #rail h2::after { content:""; flex:1; height:1px;
        background:linear-gradient(90deg, var(--line), transparent); }
 .gauge { margin-bottom:1rem; }
 .gauge .top { display:flex; justify-content:space-between; align-items:baseline;
        font-size:.6rem; letter-spacing:.18em; text-transform:uppercase;
        color:var(--vio-dim); margin-bottom:.35rem; }
 .gauge .top b { font-size:.78rem; letter-spacing:.04em; color:var(--blu);
        font-variant-numeric:tabular-nums;
        transition:color .3s; text-shadow:0 0 8px var(--blu-glow); }
 .gauge .sub { font-size:.56rem; letter-spacing:.1em; color:var(--vio-dim);
        margin-top:.3rem; text-transform:none; }
 .track { height:7px; background:rgba(160,107,255,.10);
        border:1px solid rgba(160,107,255,.16); overflow:hidden; position:relative; }
 .fill { height:100%; width:0%;
        background:linear-gradient(90deg, var(--vio), var(--blu));
        box-shadow:0 0 12px var(--blu-glow);
        transition:width .8s cubic-bezier(.22,1,.36,1), background .4s; }
 .fill::after { content:""; position:absolute; inset:0;
        background:linear-gradient(90deg, transparent, rgba(255,255,255,.28), transparent);
        animation:shine 2.6s linear infinite; }
 @keyframes shine { 0% { transform:translateX(-100%) } 100% { transform:translateX(100%) } }
 .gauge.warm .fill { background:linear-gradient(90deg, var(--gold), #ff9a5c); }
 .gauge.warm .top b { color:var(--gold); text-shadow:0 0 8px rgba(255,198,92,.5); }
 .gauge.hot .fill { background:linear-gradient(90deg, #ff7a5c, var(--red)); }
 .gauge.hot .top b { color:var(--red); text-shadow:0 0 8px rgba(255,90,110,.5); }
 #spark { display:flex; align-items:flex-end; gap:2px; height:34px; margin-top:.2rem;
        border-bottom:1px solid var(--line); }
 #spark i { flex:1; background:linear-gradient(180deg, var(--blu), var(--vio));
        min-height:1px; opacity:.75; transition:height .5s ease; }
 @media (max-width:900px) { #shell { flex-direction:column-reverse; }
        #rail { width:100%; } }

 #frame { flex:1; min-width:0; position:relative; padding:1.5rem 1.6rem 1.3rem;
        border:1px solid var(--line); background:var(--panel);
        backdrop-filter:blur(3px);
        box-shadow:0 0 60px rgba(160,107,255,.10),
                   inset 0 0 70px rgba(63,208,255,.035); }
 #frame::before { content:""; position:absolute; inset:0; pointer-events:none;
        background:linear-gradient(160deg, rgba(160,107,255,.07), transparent 45%); }
 .corner { position:absolute; width:20px; height:20px; border:2px solid var(--vio);
        filter:drop-shadow(0 0 5px var(--vio-glow)); }
 .tl { top:-2px; left:-2px; border-right:0; border-bottom:0; }
 .tr { top:-2px; right:-2px; border-left:0; border-bottom:0; }
 .bl { bottom:-2px; left:-2px; border-right:0; border-top:0; }
 .br { bottom:-2px; right:-2px; border-left:0; border-top:0; }

 /* --- the reactor: a violet core inside blue rings ---------------------- */
 header { display:flex; align-items:center; gap:1rem; }
 #reactor { width:52px; height:52px; border-radius:50%; position:relative; flex:none;
        background:radial-gradient(circle, #fff 0%, #dcc6ff 14%, var(--vio) 42%,
                   rgba(40,16,80,.92) 72%);
        box-shadow:0 0 16px var(--vio-glow), 0 0 46px rgba(160,107,255,.28),
                   inset 0 0 12px rgba(255,255,255,.65);
        animation:pulse 2.6s ease-in-out infinite; }
 #reactor::before, #reactor::after { content:""; position:absolute; border-radius:50%; }
 #reactor::before { inset:-7px; border:1px dashed rgba(63,208,255,.55);
        animation:spin 13s linear infinite; }
 #reactor::after { inset:-13px; border:1px solid rgba(160,107,255,.22);
        border-top-color:rgba(63,208,255,.75); animation:spin 5s linear infinite reverse; }
 #reactor.working { animation:pulse .7s ease-in-out infinite; }
 #reactor.blip { animation:pulse .25s ease-in-out 3; }
 #reactor.listening { background:radial-gradient(circle, #fff8ea 0%, #ffe2ac 16%,
        var(--gold) 44%, rgba(70,48,10,.92) 72%);
        box-shadow:0 0 16px rgba(255,198,92,.55), 0 0 46px rgba(255,198,92,.30); }
 #reactor.speaking { background:radial-gradient(circle, #eafaff 0%, #a9e9ff 16%,
        var(--blu) 44%, rgba(8,52,70,.92) 72%);
        box-shadow:0 0 16px var(--blu-glow), 0 0 46px rgba(63,208,255,.30); }
 @keyframes pulse { 0%,100% { transform:scale(1) } 50% { transform:scale(1.07) } }
 @keyframes spin { to { transform:rotate(360deg) } }

 .crest { width:26px; height:26px; flex:none;
        filter:drop-shadow(0 0 6px var(--vio-glow)); }
 .wordmark { display:flex; align-items:center; gap:.55rem; }
 h1 { font-size:1.05rem; letter-spacing:.55em; font-weight:600;
      background:linear-gradient(90deg, var(--vio-soft), var(--blu));
      -webkit-background-clip:text; background-clip:text; color:transparent;
      filter:drop-shadow(0 0 10px rgba(160,107,255,.35)); }
 #status { font-size:.68rem; color:var(--vio-dim); letter-spacing:.22em;
      margin-top:.3rem; text-transform:uppercase; }
 #status b { color:var(--blu); }

 /* --- telemetry: the small readouts a cockpit ought to have -------------- */
 #readout { display:flex; gap:.4rem; flex-wrap:wrap; margin:.9rem 0 .2rem;
      padding-bottom:.7rem; border-bottom:1px solid var(--line); }
 .chip { display:flex; align-items:baseline; gap:.4rem; padding:.28rem .55rem;
      border:1px solid rgba(63,208,255,.18); background:rgba(63,208,255,.04);
      font-size:.62rem; letter-spacing:.16em; text-transform:uppercase; }
 .chip i { color:var(--vio-dim); font-style:normal; }
 .chip b { color:var(--blu); font-weight:600; letter-spacing:.1em; }
 .chip.hot b { color:var(--gold); }
 #sweep { height:1px; margin:0 0 .8rem; overflow:hidden; }
 #sweep::after { content:""; display:block; height:1px; width:38%;
      background:linear-gradient(90deg, transparent, var(--vio), var(--blu), transparent);
      animation:sweep 4.2s ease-in-out infinite; }
 @keyframes sweep { 0% { transform:translateX(-100%) } 100% { transform:translateX(320%) } }

 /* --- the first-run invitation ------------------------------------------ */
 #attune { display:flex; align-items:center; gap:1rem; margin:0 0 .8rem;
        padding:.75rem .9rem; border:1px solid var(--gold);
        background:linear-gradient(90deg, rgba(255,198,92,.10), transparent 70%);
        animation:beckon 2.8s ease-in-out infinite; }
 #attune b { color:#ffe2ac; letter-spacing:.06em; }
 #attune span { display:block; color:var(--vio-dim); font-size:.7rem;
        line-height:1.5; margin-top:.2rem; }
 #attune button { border-color:var(--gold); color:var(--gold);
        white-space:nowrap; margin-left:auto; }
 #attune button:hover { background:rgba(255,198,92,.10);
        box-shadow:0 0 14px rgba(255,198,92,.45); }
 @keyframes beckon { 0%,100% { border-color:rgba(255,198,92,.30) }
                     50% { border-color:rgba(255,198,92,.95) } }
 #attune.known { animation:none; border-color:var(--line); background:none;
        padding:.3rem 0; }
 #attune.known b, #attune.known span { display:none; }
 #attune.known button { border-color:rgba(160,107,255,.45); color:var(--vio-soft);
        margin-left:0; font-size:.64rem; padding:.32rem .6rem; }

 /* --- the subtitle: what he heard, big enough to check at a glance ------- */
 #subtitle { min-height:1.5rem; margin:.1rem 0 .7rem; text-align:center;
        font-size:1.05rem; letter-spacing:.03em; color:#e6f6ff;
        text-shadow:0 0 10px var(--blu-glow); }
 #subtitle:empty { display:none; }

 /* --- the log ------------------------------------------------------------ */
 #log { border:1px solid var(--line); background:rgba(6,4,14,.75);
      height:310px; overflow-y:auto; padding:.85rem .95rem; white-space:pre-wrap;
      font-size:12px; line-height:1.6; color:var(--vio-soft);
      scrollbar-color:var(--vio-dim) transparent; }
 #log div { padding:1px 0; }
 #log .me { color:#dff3ff; text-shadow:0 0 8px var(--blu-glow); }
 #log .act { color:var(--gold); animation:landed 1s ease-out; }
 @keyframes landed { 0% { background:rgba(255,198,92,.22); text-shadow:0 0 14px var(--gold) }
                     100% { background:transparent } }

 /* --- consent ------------------------------------------------------------ */
 .gate { border:1px solid var(--gold); background:rgba(38,26,6,.55);
      padding:.6rem .8rem; margin:.6rem 0; display:flex; gap:.8rem;
      align-items:center; justify-content:space-between; color:var(--gold);
      text-shadow:0 0 6px rgba(255,198,92,.4); font-size:12px;
      box-shadow:0 0 22px rgba(255,198,92,.12); }
 .gate::before { content:"⚠ AUTHORIZATION"; letter-spacing:.2em; font-size:.62rem;
      border-right:1px solid rgba(255,198,92,.4); padding-right:.8rem; flex:none; }
 .gate button { border-color:var(--gold); color:var(--gold); }
 .gate button:hover { background:rgba(255,198,92,.10);
      box-shadow:0 0 12px rgba(255,198,92,.5); }

 /* --- controls ----------------------------------------------------------- */
 #bar, #cmds { display:flex; gap:.5rem; margin-top:.8rem; align-items:center;
      flex-wrap:wrap; }
 input[type=text] { flex:1; min-width:200px; background:rgba(8,6,18,.9);
      color:#eaf7ff; border:1px solid rgba(160,107,255,.35); padding:.65rem .8rem;
      font:inherit; outline:none; caret-color:var(--blu);
      clip-path:polygon(10px 0, 100% 0, 100% calc(100% - 10px),
                        calc(100% - 10px) 100%, 0 100%, 0 10px); }
 input[type=text]:focus { border-color:var(--vio);
      box-shadow:0 0 16px rgba(160,107,255,.30); }
 button { background:transparent; color:var(--blu); font:inherit; cursor:pointer;
      border:1px solid rgba(160,107,255,.45); padding:.58rem .85rem;
      letter-spacing:.12em; text-transform:uppercase; font-size:.7rem;
      clip-path:polygon(8px 0, 100% 0, 100% calc(100% - 8px),
                        calc(100% - 8px) 100%, 0 100%, 0 8px);
      transition:box-shadow .15s, background .15s, color .15s; }
 button:hover { background:rgba(160,107,255,.10); color:var(--vio-soft);
      box-shadow:0 0 16px var(--vio-glow); }
 #mic { border-color:rgba(63,208,255,.55); }
 #bell { color:var(--red); border-color:rgba(255,90,110,.6); }
 #bell:hover { background:rgba(255,90,110,.08); color:var(--red);
      box-shadow:0 0 14px rgba(255,90,110,.5); }
 label { color:var(--vio-dim); font-size:.68rem; letter-spacing:.12em;
      text-transform:uppercase; display:flex; gap:.4rem; align-items:center;
      cursor:pointer; }
 input[type=checkbox] { accent-color:var(--vio); }
 #hint { margin-top:.9rem; font-size:.62rem; color:var(--vio-dim);
      letter-spacing:.16em; text-transform:uppercase; line-height:1.9; }
 #hint b { color:var(--blu); }
</style></head><body>
<div id="shell">
<aside id="rail">
 <span class="corner tl"></span><span class="corner br"></span>
 <h2>the machine</h2>
 <div class="gauge" id="gCpu"><div class="top"><span>cpu</span><b>—</b></div>
  <div class="track"><div class="fill"></div></div>
  <div class="sub" id="sCpu">&nbsp;</div></div>
 <div class="gauge" id="gGpu"><div class="top"><span>gpu</span><b>—</b></div>
  <div class="track"><div class="fill"></div></div>
  <div class="sub" id="sGpu">all engines</div></div>
 <div class="gauge" id="gRam"><div class="top"><span>memory</span><b>—</b></div>
  <div class="track"><div class="fill"></div></div>
  <div class="sub" id="sRam">&nbsp;</div></div>
 <div class="gauge" id="gDisk"><div class="top"><span>storage</span><b>—</b></div>
  <div class="track"><div class="fill"></div></div>
  <div class="sub" id="sDisk">&nbsp;</div></div>
 <h2>cpu, last minute</h2>
 <div id="spark"></div>
</aside>
<div id="frame">
 <span class="corner tl"></span><span class="corner tr"></span>
 <span class="corner bl"></span><span class="corner br"></span>
 <header>
  <div id="reactor"></div>
  <div>
   <div class="wordmark">__LOGO__<h1>ALFRED</h1></div>
   <div id="status">systems <b id="state">nominal</b> · the gate is watching</div>
  </div>
  <div id="viz" style="margin-left:auto"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
 </header>
 <div id="readout">
  <span class="chip"><i>time</i><b id="clock">--:--</b></span>
  <span class="chip"><i>state</i><b id="chipState">nominal</b></span>
  <span class="chip"><i>chord</i><b>__HOLD_LABEL__</b></span>
  <span class="chip"><i>reach</i><b id="chipReach">local</b></span>
  <span class="chip"><i>gate</i><b>watching</b></span>
 </div>
 <div id="sweep"></div>
 <div id="attune" class="__ATTUNE_STATE__">
  <div>
   <b>Make Alfred yours.</b>
   <span>He'll learn your software and the places you actually go — all of it
   stays on this machine.</span>
  </div>
  <button id="attuneBtn">⟡ attune to me</button>
 </div>
 <div id="subtitle"></div>
 <div id="log"></div><div id="gates"></div>
 <div id="bar">
  <input id="text" type="text" placeholder="your word is my command, sir…" autofocus>
  <button id="mic" title="push-to-talk, 5 seconds">◉ mic</button>
  <button id="bell" title="the bell — abort everything">◼ stop</button>
 </div>
 <div id="cmds">
  <button data-cmd="menu">menu</button><button data-cmd="undo">undo</button>
  <button data-cmd="ledger">ledger</button><button data-cmd="burn">burn</button>
  <button data-cmd="fieldlog" title="what you tested: mishears, refusals, errors">field log</button>
  <button data-cmd="tabs" title="audit exactly which tabs I can see">tabs</button>
  <button data-cmd="privacy" title="everything I know about you, and where it sits">privacy</button>
  <button data-cmd="forgettabs" title="wipe my view of your browser at once">forget tabs</button>
  <label title="webcam rings the stop bell on a big wave — never commands">
   <input type="checkbox" id="motion"> &#128247; motion bell</label>
  <label title="webcam reads hand gestures on demand; every gesture is confirmed before it acts">
   <input type="checkbox" id="gestures"> &#128400; gestures</label>
  <button id="cog" style="margin-left:auto" title="settings">&#9881; settings</button>
 </div>
 <div id="hint">press <b>__HOLD_LABEL__</b> to listen, press again to send · &#9673; mic (5s) ·
  say &#8220;mute&#8221; / &#8220;unmute&#8221; / &#8220;undo&#8221; · &#9000; CTRL+ALT+C summons me anywhere</div>
</div>
</div>
<script>
const TOKEN = "__TOKEN__";
const log = document.getElementById("log");
const reactor = document.getElementById("reactor");
const stateEl = document.getElementById("state");
const viz = document.getElementById("viz");
const subtitle = document.getElementById("subtitle");
const chipState = document.getElementById("chipState");
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
  stateEl.textContent = s === "idle" ? "nominal" : s;
  chipState.textContent = s === "idle" ? "nominal" : s;
  chipState.parentElement.classList.toggle("hot", s !== "idle");
  viz.className = (s === "listening" || s === "speaking") ? s : "";
  if (s === "listening") subtitle.textContent = "";  // a fresh turn begins
}
const clock = document.getElementById("clock");
setInterval(()=>{ const d = new Date();
  clock.textContent = String(d.getHours()).padStart(2,"0") + ":" +
                      String(d.getMinutes()).padStart(2,"0") + ":" +
                      String(d.getSeconds()).padStart(2,"0"); }, 1000);
// --- the instruments -------------------------------------------------------
// A gauge warms as it fills, so the rail can be read at a glance rather than
// studied: cool is fine, gold is working, red is straining.
function gauge(id, percent, caption){
  const box = document.getElementById(id);
  if (!box) return;
  const shown = Math.max(0, Math.min(100, percent || 0));
  box.querySelector(".fill").style.width = shown + "%";
  box.querySelector("b").textContent = shown.toFixed(0) + "%";
  box.classList.toggle("warm", shown >= 65 && shown < 85);
  box.classList.toggle("hot", shown >= 85);
  if (caption) document.getElementById(caption.id).textContent = caption.text;
}
const spark = document.getElementById("spark");
for (let i = 0; i < 30; i++) spark.append(document.createElement("i"));
function pushSpark(percent){
  const bars = spark.querySelectorAll("i");
  for (let i = 0; i < bars.length - 1; i++)
    bars[i].style.height = bars[i + 1].style.height || "1px";
  bars[bars.length - 1].style.height = Math.max(1, percent) + "%";
}
function instruments(t){
  gauge("gCpu", t.cpu, {id:"sCpu", text:"busy " + (t.cpu||0).toFixed(0) + "%"});
  gauge("gGpu", t.gpu, {id:"sGpu", text:"all engines"});
  gauge("gRam", t.ram.percent, {id:"sRam",
        text:t.ram.used + " / " + t.ram.total + " GiB"});
  gauge("gDisk", t.disk.percent, {id:"sDisk",
        text:t.disk.used + " / " + t.disk.total + " GB"});
  pushSpark(t.cpu || 0);
}
const gates = document.getElementById("gates");
function gateCard(e){
  const card = document.createElement("div"); card.className = "gate"; card.id = "g"+e.id;
  const label = document.createElement("span");
  const buttons = document.createElement("span");
  buttons.style.display = "flex"; buttons.style.gap = ".4rem";
  if (e.kind === "seal"){
    label.textContent = e.summary + " — this reaches your files. Type your approval, exactly:";
    const field = document.createElement("input");
    field.placeholder = "yes i approve please proceed";
    field.style.cssText = "flex:1;min-width:14rem;background:#0a0714;border:1px solid var(--gold);color:var(--gold);padding:.35rem .5rem;font:inherit";
    const b = document.createElement("button"); b.textContent = "approve";
    const send = ()=>{ post("/api/gate",{id:e.id,phrase:field.value}); card.remove(); };
    b.onclick = send;
    field.addEventListener("keydown",(k)=>{ if(k.key==="Enter") send(); });
    buttons.append(field, b);
    setTimeout(()=>field.focus(), 0);
  } else {  // confirm
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
  else if (e.type === "subtitle") subtitle.textContent = e.text ? ("“" + e.text + "”") : "";
  else if (e.type === "telemetry") instruments(e);
  else if (e.type === "state") setState(e.state);
  else if (e.type === "gate") gateCard(e);
  else if (e.type === "gate_done"){ const c = document.getElementById("g"+e.id); if(c) c.remove(); } };
const text = document.getElementById("text");
text.addEventListener("keydown",(k)=>{ if(k.key==="Enter" && text.value.trim()){
  say(text.value.trim(), true); post("/api/ask",{text:text.value.trim()}); text.value=""; }});
document.getElementById("mic").onclick = ()=>post("/api/voice");
document.getElementById("bell").onclick = ()=>post("/api/bell");
// press the chord to begin listening, press it again to send.
// When the global latch is armed it covers this page too, so we stand down
// rather than toggle twice on the same keystroke.
const HOLD = __HOLD_KEYS__;        // e.g. ["j","k"] — editable in settings
const GLOBAL_KEYS = __GLOBAL_KEYS__;
document.getElementById("chipReach").textContent = GLOBAL_KEYS ? "anywhere" : "this page";
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
say("__GREETING__", false);  // the boot line (audio is spoken server-side)
document.querySelectorAll("[data-cmd]").forEach(b=>b.onclick=()=>post("/api/command",{name:b.dataset.cmd}));
document.getElementById("motion").onchange = (e)=>post("/api/motion",{enable:e.target.checked});
document.getElementById("gestures").onchange = (e)=>post("/api/gestures",{enable:e.target.checked});
document.getElementById("cog").onclick = ()=>{ location.href = "/settings?t="+TOKEN; };
document.getElementById("attuneBtn").onclick = (e)=>{
  e.target.disabled = true; e.target.textContent = "attuning…";
  post("/api/attune").finally(()=>setTimeout(()=>{
    e.target.disabled = false; e.target.textContent = "⟡ re-attune";
    document.getElementById("attune").classList.add("known");
  }, 1500));
};
</script></body></html>"""

# the voice visualiser and its animation, shared shape with the reactor states
_VIZ_CSS = """
 #viz { display:flex; align-items:flex-end; gap:3px; height:26px; }
 #viz i { width:3px; height:5px; background:var(--vio-dim); border-radius:2px; }
 #viz.listening i { background:var(--gold); animation:bounce .8s ease-in-out infinite; }
 #viz.speaking i { background:var(--blu); animation:bounce .5s ease-in-out infinite; }
 #viz i:nth-child(2){ animation-delay:.10s } #viz i:nth-child(3){ animation-delay:.22s }
 #viz i:nth-child(4){ animation-delay:.32s } #viz i:nth-child(5){ animation-delay:.16s }
 #viz i:nth-child(6){ animation-delay:.26s } #viz i:nth-child(7){ animation-delay:.06s }
 @keyframes bounce { 0%,100%{ height:5px } 50%{ height:24px } }
"""

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
        transparent 1px 3px); mix-blend-mode:overlay; }
 body::after { content:""; position:fixed; inset:0; pointer-events:none;
        background:
        linear-gradient(rgba(160,107,255,.045) 1px, transparent 1px) 0 0/100% 46px,
        linear-gradient(90deg, rgba(63,208,255,.035) 1px, transparent 1px) 0 0/46px 100%; }
 #frame { width:min(760px,100%); position:relative; align-self:flex-start;
        border:1px solid var(--line); background:var(--panel);
        backdrop-filter:blur(3px); padding:1.6rem;
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
    _doc = _doc.replace("__PALETTE__", _PALETTE + (_VIZ_CSS if _name == "PAGE" else ""))
    globals()[_name] = _doc
