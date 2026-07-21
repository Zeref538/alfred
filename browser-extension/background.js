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

async function config() {
  const { base, token, paused } = await chrome.storage.local.get(
    ["base", "token", "paused"]);
  return { base, token, paused: !!paused };
}

async function pushTabs() {
  const { base, token, paused } = await config();
  if (!base || !token || paused) return;
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
  if (!base || !token || paused) return;
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
        if (event.type === "tab_focus" && typeof event.id === "number") {
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
