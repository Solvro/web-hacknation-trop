// Service worker: every network call goes through here (page CSP and mixed content cannot block it).
const DEFAULT_BASE = "https://trop.b.solvro.pl";

async function getSettings() {
  const s = await chrome.storage.local.get(["apiBase", "installId"]);
  let installId = s.installId;
  if (!installId) {
    installId = crypto.randomUUID(); // anonymous, random, not derived from the user
    await chrome.storage.local.set({ installId });
  }
  return { apiBase: (s.apiBase || DEFAULT_BASE).replace(/\/+$/, ""), installId };
}

async function api(path, init) {
  const { apiBase } = await getSettings();
  const res = await fetch(`${apiBase}/api/v1${path}`, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const postJson = (path, body) =>
  api(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

async function handle(msg) {
  const { installId } = await getSettings();
  switch (msg.type) {
    case "match":
      return postJson("/public/extension/match", { ...msg.post, install_id: installId });
    case "report":
      return postJson("/public/report", { post: { ...msg.post, install_id: installId }, note: "extension" });
    case "check": {
      const fd = new FormData();
      if (msg.url) fd.set("url", msg.url);
      if (msg.text) fd.set("text", msg.text);
      return api("/public/check", { method: "POST", body: fd });
    }
    case "settings":
      return getSettings();
    default:
      throw new Error("unknown message");
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  handle(msg).then(
    (data) => sendResponse({ ok: true, data }),
    (e) => sendResponse({ ok: false, error: String((e && e.message) || e) })
  );
  return true;
});

chrome.runtime.onInstalled.addListener(() => { getSettings(); });
