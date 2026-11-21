const $ = (id) => document.getElementById(id);
function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }

let current = "";
function render(r) {
  const out = $("out");
  out.replaceChildren();
  const box = node("div", "res " + (r.verdict === "scam" ? "scam" : "unk"));
  if (r.verdict === "scam") {
    box.append(node("h2", "", "To wygląda na znane oszustwo"));
    const c = r.public_campaign;
    if (c) {
      box.append(node("div", "", c.name));
      box.append(node("div", "dim", `Widzieliśmy ${c.seen_count} podobnych reklam od ${c.since}.`));
      if (c.reasons && c.reasons.length) { const ul = node("ul"); c.reasons.forEach((x) => ul.append(node("li", "", x))); box.append(ul); }
    }
  } else {
    box.append(node("h2", "", "Nie znamy tego materiału"));
    box.append(node("div", "", "To nie znaczy, że jest bezpieczny."));
  }
  if (r.advice && r.advice.length) { const ul = node("ul"); r.advice.forEach((x) => ul.append(node("li", "", x))); box.append(ul); }
  const st = node("div", "dim");
  st.setAttribute("role", "status");
  const b = node("button", "btn p", r.verdict === "scam" ? "Zgłoś tę reklamę" : "Wyślij do sprawdzenia");
  b.type = "button";
  b.addEventListener("click", () => {
    b.disabled = true;
    const isUrl = /^https?:\/\//i.test(current);
    chrome.runtime.sendMessage({ type: "report", post: isUrl ? { cta_url: current } : { caption: current } }, (x) => {
      if (x && x.ok) { b.textContent = "Zgłoszono"; st.textContent = `Dziękujemy, zgłoszenie przyjęte (${x.data.report_id}).`; }
      else { b.disabled = false; st.textContent = "Nie udało się wysłać zgłoszenia. Spróbuj ponownie."; }
    });
  });
  box.append(b, st);
  out.append(box);
}

$("f").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("q").value.trim();
  if (!v) return;
  current = v;
  $("go").disabled = true;
  $("out").textContent = "Sprawdzanie…";
  const isUrl = /^https?:\/\//i.test(v) || /^[\w-]+(\.[\w-]+)+(\/|$)/.test(v);
  chrome.runtime.sendMessage({ type: "check", ...(isUrl ? { url: v } : { text: v }) }, (r) => {
    $("go").disabled = false;
    if (r && r.ok) render(r.data); else $("out").textContent = "Nie udało się połączyć z serwerem. Sprawdź adres API w ustawieniach.";
  });
});
