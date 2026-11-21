// TROP content script: finds sponsored posts, sends an anonymous fingerprint, overlays a warning on a match.
// Never claims an ad is safe: no match means no overlay at all.
(function () {
  if (window.__tropLoaded) return;
  window.__tropLoaded = true;

  const SPONSORED = /^(sponsorowane|sponsored|reklama)$/i;
  const SEEN = new WeakSet();

  function send(msg) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(msg, (r) => resolve(r || { ok: false, error: chrome.runtime.lastError?.message }));
      } catch (e) {
        resolve({ ok: false, error: String(e) });
      }
    });
  }

  function isSponsored(article) {
    const nodes = article.querySelectorAll("span, a, div[aria-label]");
    for (const n of nodes) {
      if (n.children.length > 0 && n.tagName !== "A") continue;
      const t = (n.textContent || n.getAttribute("aria-label") || "").trim();
      if (t.length <= 16 && SPONSORED.test(t)) return true;
    }
    return false;
  }

  function unwrap(href) {
    try {
      const u = new URL(href, location.href);
      if (/(^|\.)facebook\.com$/.test(u.hostname) && u.pathname.startsWith("/l.php")) return u.searchParams.get("u") || href;
      return u.href;
    } catch (e) {
      return null;
    }
  }

  function extract(article) {
    const head = article.querySelector("h2, h3, h4, [data-ad-rendering-role='profile_name'], strong");
    const advertiser = (head?.textContent || "").trim().slice(0, 120) || null;
    const msgEl = article.querySelector("[data-ad-preview='message'], [data-ad-comet-preview='message'], .post-text");
    let caption = (msgEl?.textContent || "").trim();
    if (!caption) {
      const blocks = [...article.querySelectorAll("div[dir='auto'], p")].map((e) => (e.textContent || "").trim());
      caption = blocks.sort((a, b) => b.length - a.length)[0] || "";
    }
    caption = caption.slice(0, 1000) || null;
    let cta = null;
    for (const a of article.querySelectorAll("a[href]")) {
      const u = unwrap(a.getAttribute("href"));
      if (u && !/^https?:\/\/([^/]*\.)?facebook\.com\//.test(u) && /^https?:/.test(u)) { cta = u; break; }
    }
    let best = null, area = 0;
    for (const im of article.querySelectorAll("img")) {
      const a = (im.naturalWidth || im.width) * (im.naturalHeight || im.height);
      if (a > area) { best = im; area = a; }
    }
    return { advertiser, caption, cta_url: cta, img: best };
  }

  async function hashImage(img) {
    if (!img) return null;
    if (!img.complete) await new Promise((r) => { img.addEventListener("load", r, { once: true }); img.addEventListener("error", r, { once: true }); setTimeout(r, 2000); });
    if (!img.naturalWidth) return null;
    return globalThis.TROP_phash(img);
  }

  const CSS = `
    :host{all:initial;display:block}
    .strip{box-sizing:border-box;background:#2A1418;border:1px solid rgba(255,93,108,.6);border-radius:8px;color:#FFE3E6;padding:10px 14px;margin:8px;font:14px/1.45 Inter,system-ui,sans-serif;display:flex;flex-direction:column;gap:10px}
    .row{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap}
    .txt{flex:1 1 240px;min-width:0;display:flex;flex-direction:column;gap:6px}
    b.t{font-size:14px}
    .chips{display:flex;gap:6px;flex-wrap:wrap}
    .chip{display:inline-flex;align-items:center;min-height:22px;padding:0 8px;border-radius:999px;background:rgba(255,93,108,.14);border:1px solid rgba(255,93,108,.4);font-size:12px;color:#FFD4D9}
    .btns{display:flex;gap:6px;flex-wrap:wrap}
    button{font:500 13px Inter,system-ui,sans-serif;min-height:32px;padding:0 12px;border-radius:6px;border:1px solid rgba(255,93,108,.55);background:transparent;color:#FFE3E6;cursor:pointer}
    button:hover{background:rgba(255,93,108,.18)}
    button:focus-visible{outline:2px solid #5CC8FF;outline-offset:2px}
    button[aria-expanded=true]{background:rgba(255,93,108,.22)}
    button[disabled]{opacity:.7;cursor:default}
    .why{background:#1A0E11;border:1px solid rgba(255,93,108,.35);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:6px}
    .why[hidden]{display:none}
    .why ol{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:4px}
    .st{font-size:12.5px;color:#FFB3BB}
  `;

  function el(tag, props, ...kids) {
    const n = document.createElement(tag);
    Object.assign(n, props || {});
    for (const k of kids) n.append(k);
    return n;
  }

  function showOverlay(article, post, m) {
    const host = document.createElement("div");
    host.setAttribute("data-trop-overlay", "1");
    const root = host.attachShadow({ mode: "open" });
    const camp = m.public_campaign;
    const reasons = (m.reasons && m.reasons.length ? m.reasons : camp?.reasons) || [];

    const chips = el("div", { className: "chips" });
    if (camp) {
      chips.append(el("span", { className: "chip", textContent: camp.name }));
      chips.append(el("span", { className: "chip", textContent: `${camp.seen_count} podobnych reklam od ${camp.since}` }));
    }
    const why = el("div", { className: "why", id: "why", hidden: true });
    const ol = el("ol");
    reasons.forEach((r) => ol.append(el("li", { textContent: r })));
    why.append(
      el("b", { textContent: "Dlaczego to ostrzeżenie?" }),
      ol,
      el("b", { textContent: "Co zrobić" }),
      el("span", { textContent: "Nie klikaj w link i nie podawaj danych ani pieniędzy. Możesz zgłosić reklamę jednym kliknięciem: wyślemy tylko jej odcisk i tekst." })
    );
    const status = el("span", { className: "st", role: "status" });

    const bWhy = el("button", { type: "button", textContent: "Dlaczego?" });
    bWhy.setAttribute("aria-expanded", "false");
    bWhy.setAttribute("aria-controls", "why");
    bWhy.onclick = () => {
      const open = why.hidden;
      why.hidden = !open;
      bWhy.setAttribute("aria-expanded", String(open));
    };
    const bRep = el("button", { type: "button", textContent: "Zgłoś" });
    bRep.onclick = async () => {
      bRep.disabled = true;
      status.textContent = "Wysyłanie zgłoszenia…";
      const r = await send({ type: "report", post });
      if (r.ok) { status.textContent = `Zgłoszono, dziękujemy (${r.data.report_id}).`; bRep.textContent = "Zgłoszono"; host.dataset.reported = r.data.report_id; }
      else { status.textContent = "Nie udało się wysłać zgłoszenia. Spróbuj ponownie."; bRep.disabled = false; }
    };
    const bHide = el("button", { type: "button", textContent: "Ukryj" });
    bHide.onclick = () => { host.remove(); };

    const logo = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    logo.setAttribute("width", "22"); logo.setAttribute("height", "22"); logo.setAttribute("viewBox", "0 0 28 28"); logo.setAttribute("aria-hidden", "true");
    logo.innerHTML = '<g transform="rotate(-40 14 14)"><rect x="3" y="9" width="22" height="10" rx="5" fill="none" stroke="#3BF07E" stroke-width="1.5"></rect><path d="M8 9h6v10H8a5 5 0 0 1 0-10z" fill="#FF5D6C"></path></g>';

    const strip = el("div", { className: "strip", role: "region" });
    strip.setAttribute("aria-label", "Ostrzeżenie TROP");
    const txt = el("div", { className: "txt" }, el("b", { className: "t", textContent: `TROP: ${m.label || "Pasuje do znanej kampanii oszustwa"}` }), chips);
    const row = el("div", { className: "row" }, logo, txt, el("div", { className: "btns" }, bWhy, bRep, bHide));
    strip.append(row, why, status);
    root.append(el("style", { textContent: CSS }), strip);
    article.prepend(host);
    return host;
  }

  async function process(article) {
    if (SEEN.has(article)) return;
    if (!isSponsored(article)) return;
    SEEN.add(article);
    const ex = extract(article);
    const post = {
      advertiser: ex.advertiser,
      caption: ex.caption,
      cta_url: ex.cta_url,
      creative_phash: await hashImage(ex.img),
      page_url: location.origin + location.pathname,
    };
    const r = await send({ type: "match", post });
    if (r.ok && r.data && r.data.match) showOverlay(article, post, r.data);
  }

  function scan() {
    document.querySelectorAll("[role='article'], article").forEach((a) => { process(a); });
  }

  let timer = null;
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(scan, 400); })
    .observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
