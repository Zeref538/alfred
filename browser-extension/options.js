const status = (t) => { document.getElementById("status").textContent = t; };

chrome.storage.local.get(["base", "token", "paused"]).then(({ base, token, paused }) => {
  if (base && token) document.getElementById("url").value = base + "/?t=" + token;
  document.getElementById("pause").textContent = paused ? "resume" : "pause";
  if (base) status(paused ? "Paused — reporting nothing." : "Connected to " + base);
});

document.getElementById("save").onclick = async () => {
  const raw = document.getElementById("url").value.trim();
  let url;
  try { url = new URL(raw); } catch { return status("That is not a valid address."); }
  if (url.hostname !== "127.0.0.1") return status("Needs a 127.0.0.1 address.");
  const base = url.origin;
  // Go through the real pairing handshake rather than lifting the ?t= out of
  // the pasted URL — that's this session's key, which changes every time
  // Alfred restarts. /api/pair hands back the long-lived bridge key instead,
  // the same one the automatic background pairing uses, so this survives
  // restarts instead of silently breaking after the next one.
  try {
    status("Asking Alfred to approve this — check the HUD…");
    const r = await fetch(base + "/api/pair", { method: "POST" });
    if (!r.ok) return status("Alfred refused: " + r.status);
    const { token } = await r.json();
    if (!token) return status("No key came back.");
    await chrome.storage.local.set({ base, token, paused: false });
    document.getElementById("pause").textContent = "pause";
    status("Connected — Alfred can see your tabs.");
  } catch { status("Couldn't reach Alfred — is he running?"); }
};

document.getElementById("pause").onclick = async () => {
  const { paused } = await chrome.storage.local.get("paused");
  const now = !paused;
  await chrome.storage.local.set({ paused: now });
  document.getElementById("pause").textContent = now ? "resume" : "pause";
  status(now ? "Paused — reporting nothing." : "Reporting resumed.");
};
