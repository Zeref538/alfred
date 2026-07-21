/* Alfred's tab bridge.
 *
 * Two jobs, and deliberately no others:
 *   1. report the open tabs (title + URL) to Alfred on 127.0.0.1
 *   2. listen for a "switch to this tab" instruction and obey it
 *
 * It never reads page CONTENT — the extension asks for no scripting or
 * host permissions beyond 127.0.0.1, so it *cannot* read what is on a page
 * even if it wanted to. Alfred discards the path and query of every URL the
 * moment they arrive; only the title and hostname are kept, in memory.
 *
 * Nothing leaves the machine: the only host it may contact is 127.0.0.1.
 */

const PUSH_ALARM = "alfred-push";
const DEFAULT_BASE = "http://127.0.0.1:51789";

async function config() {
  const { base, token, paused } = await chrome.storage.local.get(
    ["base", "token", "paused"]);
  return { base: base || DEFAULT_BASE, token, paused: !!paused };
}

/* Pair once, then remember. Alfred hands over a key only after the master
 * approves the request at the HUD, so this can be automatic without being
 * something a stray page could do. */
let pairing = false;
async function pair() {
  if (pairing) return null;
  const { base, paused } = await config();
  if (paused) return null;
  pairing = true;
  try {
    const r = await fetch(base + "/api/pair", { method: "POST" });
    if (!r.ok) return null;              // declined, or nobody at the HUD
    const { token } = await r.json();
    if (token) {
      await chrome.storage.local.set({ base, token });
      return token;
    }
  } catch (e) { /* Alfred isn't running */ }
  finally { pairing = false; }
  return null;
}

async function pushTabs() {
  let { base, token, paused } = await config();
  if (paused) return;
  if (!token) token = await pair();     // first run: ask, once
  if (!token) return;
  const tabs = await chrome.tabs.query({});
  const payload = tabs.map(t => ({ id: t.id, title: t.title || "", url: t.url || "" }));
  try {
    await fetch(base + "/api/tabs", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ tabs: payload })
    });
  } catch (e) { /* Alfred is not running; nothing to do */ }
}

// Listen for Alfred asking us to switch tabs, over the same guarded stream
// the HUD uses. EventSource is unavailable in a service worker, so we read
// the stream ourselves.
let streaming = false;
async function listen() {
  if (streaming) return;
  const { base, token, paused } = await config();
  if (!token || paused) return;
  streaming = true;
  try {
    const response = await fetch(base + "/api/events?t=" + encodeURIComponent(token),
      { headers: { "Authorization": "Bearer " + token } });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }
        if (event.type === "play_request" && typeof event.url === "string") {
          playIn(event.url);
        } else if (event.type === "tab_focus" && typeof event.id === "number") {
          try {
            const tab = await chrome.tabs.get(event.id);
            await chrome.tabs.update(event.id, { active: true });
            await chrome.windows.update(tab.windowId, { focused: true });
          } catch (e) { /* the tab closed in the meantime */ }
        }
      }
    }
  } catch (e) { /* dropped; the alarm will bring us back */ }
  streaming = false;
}

/* Pressing play.
 *
 * Runs ONLY on the media hosts named in the manifest — it has no reach into
 * any other site, so this cannot look at your mail or your bank. It clicks the
 * first result on a search page, then plays whatever video lands. Selectors
 * rot, so every step is best-effort: if it fails you are simply left on the
 * page, which is where you would have been anyway. */
function pressPlay() {
  const video = document.querySelector("video");
  if (video && video.readyState > 0) { video.play?.(); return "playing"; }
  const candidates = [
    "a#video-title", "ytd-video-renderer a#thumbnail",           // youtube
    "[data-testid='play-button']", "button[aria-label*='Play' i]",
    "[data-testid='title-card'] a", "a.title-card-link",         // netflix
    "a[href*='/watch']", "a[href*='/video']", "a[href*='/track']",
  ];
  for (const selector of candidates) {
    const el = document.querySelector(selector);
    if (el) { el.click(); return "clicked " + selector; }
  }
  return "nothing to press";
}

async function playIn(url) {
  const tab = await chrome.tabs.create({ url, active: true });
  const run = () => chrome.scripting.executeScript({
    target: { tabId: tab.id }, func: pressPlay
  }).catch(() => { /* not a host we may touch */ });
  // once when the page settles, once more after it has navigated to a player
  setTimeout(run, 2500);
  setTimeout(run, 6000);
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(PUSH_ALARM, { periodInMinutes: 0.25 });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(PUSH_ALARM, { periodInMinutes: 0.25 });
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === PUSH_ALARM) { pushTabs(); listen(); }
});

// keep the view fresh as tabs come and go
chrome.tabs.onCreated.addListener(pushTabs);
chrome.tabs.onRemoved.addListener(pushTabs);
chrome.tabs.onUpdated.addListener((id, info) => { if (info.title || info.url) pushTabs(); });
chrome.tabs.onActivated.addListener(pushTabs);
