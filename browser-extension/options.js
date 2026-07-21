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
  const token = url.searchParams.get("t");
  if (url.hostname !== "127.0.0.1" || !token) {
    return status("Needs a 127.0.0.1 address including the ?t= key.");
  }
  const base = url.origin;
  await chrome.storage.local.set({ base, token, paused: false });
  document.getElementById("pause").textContent = "pause";
  try {
    const r = await fetch(base + "/api/tabs", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ tabs: [] })
    });
    status(r.ok ? "Connected — Alfred can see your tabs." : "Alfred refused: " + r.status);
  } catch { status("Couldn't reach Alfred — is he running?"); }
};

document.getElementById("pause").onclick = async () => {
  const { paused } = await chrome.storage.local.get("paused");
  const now = !paused;
  await chrome.storage.local.set({ paused: now });
  document.getElementById("pause").textContent = now ? "resume" : "pause";
  status(now ? "Paused — reporting nothing." : "Reporting resumed.");
};
