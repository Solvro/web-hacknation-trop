"""Bounding-box extraction (runs inside the page; used by render_saved and by the live capture).

Boxes are in CSS pixels of the full page (document coordinates). Kinds: headline, form, input, iframe, image, marker.
`markers` lists every element/script whose src/href/action matches a tracking/kit marker, visible or not.
"""

MARKERS = ["facebook.com/tr", "connect.facebook.net", "fbevents", "landing-cdn", "aio-static", "googletagmanager",
           "gtm.js", "google-analytics.com", "analytics.tiktok.com", "ttq.load"]

BOXES_JS = """
(markers) => {
  const out = [], seen = new Set();
  const sx = window.scrollX || 0, sy = window.scrollY || 0;
  const sel = (el) => {
    if (el.id) return el.tagName.toLowerCase() + '#' + CSS.escape(el.id);
    const parts = [];
    let e = el;
    while (e && e.nodeType === 1 && parts.length < 4 && e !== document.body) {
      let s = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(s + '#' + CSS.escape(e.id)); break; }
      const sib = e.parentElement ? [...e.parentElement.children].filter(c => c.tagName === e.tagName) : [];
      if (sib.length > 1) s += ':nth-of-type(' + (sib.indexOf(e) + 1) + ')';
      parts.unshift(s); e = e.parentElement;
    }
    return parts.join(' > ');
  };
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return null;
    return {x: Math.round(r.left + sx), y: Math.round(r.top + sy), w: Math.round(r.width), h: Math.round(r.height)};
  };
  const add = (kind, el, extra) => {
    const b = vis(el); if (!b) return false;
    const key = kind + b.x + ',' + b.y + ',' + b.w + ',' + b.h;
    if (seen.has(key)) return false; seen.add(key);
    const text = (el.innerText || el.value || el.alt || el.placeholder || '').trim().replace(/\\s+/g, ' ').slice(0, 120);
    out.push(Object.assign({kind, selector: sel(el), ...b}, text ? {text} : {}, extra || {}));
    return true;
  };
  // headline: first visible h1, else the visible heading with the biggest font
  let h = [...document.querySelectorAll('h1')].find(e => vis(e) && (e.innerText || '').trim());
  if (!h) {
    let best = 0;
    for (const e of document.querySelectorAll('h2,h3,h4')) {
      const fs = parseFloat(getComputedStyle(e).fontSize) || 0;
      if (vis(e) && (e.innerText || '').trim() && fs > best) { best = fs; h = e; }
    }
  }
  if (h) add('headline', h);
  for (const f of document.forms) {
    if (add('form', f, {action: f.getAttribute('action') || null, method: (f.method || 'get').toLowerCase()}))
      for (const i of f.querySelectorAll('input:not([type=hidden]),select,textarea,button'))
        add('input', i, {type: i.type || i.tagName.toLowerCase(), name: i.name || i.id || null});
  }
  for (const i of document.querySelectorAll('input:not([type=hidden]),textarea')) if (!i.form) add('input', i, {type: i.type, name: i.name || i.id || null});
  for (const f of document.querySelectorAll('iframe')) add('iframe', f, {src: (f.getAttribute('src') || '').slice(0, 200)});
  // hero image: the largest <img> that starts in the first 1600 px (a face candidate; faces are matched elsewhere)
  let hero = null, ha = 0;
  for (const im of document.images) {
    const b = vis(im); if (!b || b.w < 80 || b.h < 80 || b.y > 1600) continue;
    if (b.w * b.h > ha) { ha = b.w * b.h; hero = im; }
  }
  if (hero) add('image', hero, {role: 'hero', src: (hero.currentSrc || hero.src || '').slice(0, 200)});
  const markersFound = [], attrs = ['src', 'href', 'action', 'data-src'];
  for (const el of document.querySelectorAll('[src],[href],[action],[data-src]')) {
    for (const a of attrs) {
      const v = el.getAttribute(a); if (!v) continue;
      const m = markers.find(m => v.toLowerCase().includes(m));
      if (m) {
        markersFound.push({marker: m, tag: el.tagName.toLowerCase(), attr: a, url: v.slice(0, 200)});
        add('marker', el, {marker: m});
        break;
      }
    }
  }
  const inline = markers.filter(m => (document.documentElement.innerHTML || '').toLowerCase().includes(m));
  return {boxes: out, markers: markersFound.slice(0, 40), inline_markers: inline,
          page: {w: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
                 h: Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)}};
}
"""
