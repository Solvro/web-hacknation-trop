const DEFAULT = "http://127.0.0.1:18000";
const $ = (id) => document.getElementById(id);
chrome.storage.local.get(["apiBase", "installId"]).then((s) => {
  $("base").value = s.apiBase || DEFAULT;
  $("iid").textContent = s.installId || "(zostanie utworzony przy pierwszym użyciu)";
});
$("f").addEventListener("submit", async (e) => {
  e.preventDefault();
  await chrome.storage.local.set({ apiBase: $("base").value.trim().replace(/\/+$/, "") || DEFAULT });
  $("msg").textContent = "Zapisano.";
});
$("reset").addEventListener("click", async () => {
  await chrome.storage.local.set({ apiBase: DEFAULT });
  $("base").value = DEFAULT;
  $("msg").textContent = "Przywrócono domyślny adres.";
});
