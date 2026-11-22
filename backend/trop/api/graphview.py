"""Focus views of the graph (boards 4a-4d): neighbourhood + panel + node meta (docs/contracts/REQUESTS.md, WS3 items 1-3)
and the trace-type aliases (item 7). Shared by MockStore and RealStore."""
from __future__ import annotations

from trop.schema import GraphEdge, GraphNode, GraphPayload

# Polish / short aliases used by the web routes -> (canonical type, evidence layer)
TYPE_ALIASES = {
    "domena": "domain", "domain": "domain", "osoba": "person", "person": "person", "piksel": "pixel", "pixel": "pixel",
    "kit": "kit", "tracking": "tracking", "infra": "infra", "content": "content", "persons": "persons", "visual": "visual",
    "ad": "ad", "media": "media", "tresc": "content", "treść": "content", "reklama": "ad", "obraz": "visual",
}
LAYER_OF = {"domain": "infra", "person": "persons", "pixel": "tracking", "kit": "kit", "tracking": "tracking", "infra": "infra",
            "content": "content", "persons": "persons", "visual": "visual", "ad": "ad", "media": "media"}


def norm_type(t: str) -> tuple[str, str]:
    """-> (canonical type, evidence layer); unknown types raise KeyError (routes turn it into 404)."""
    c = TYPE_ALIASES[t.lower()]
    return c, LAYER_OF[c]


KIND_LABEL = {"campaign": "KAMPANIA", "operator": "OPERATOR", "operation": "OPERACJA", "incident": "INCYDENT", "domain": "DOMENA",
              "trace": "ŚLAD", "cert": "CERTYFIKAT", "person": "OSOBA", "advertiser": "REKLAMODAWCA"}
KIND_TOPIC = {"campaign": "campaign", "incident": "incident", "domain": "trace", "trace": "trace", "person": "trace", "operator": "campaign"}


def _sub(n: GraphNode, deg: int) -> str:
    return {"campaign": f"{int(n.size * 5) if n.size else deg} powiązań w widoku", "operator": "operator (rodzina kampanii)",
            "domain": "domena" + (" · na liście CERT PL" if n.meta.get("certpl") else ""), "incident": "incydent",
            "trace": f"wspólny ślad · {deg} połączeń", "person": "wizerunek osoby", "cert": "partia certyfikatów"}.get(n.kind, n.kind)


def focus_view(g: GraphPayload, focus: str, origin: str | None = None, max_neighbours: int = 6) -> GraphPayload:
    """Focus node + origin + <= 6 strongest direct neighbours. Raises KeyError when the focus is unknown."""
    nodes = {n.id: n for n in g.nodes}
    g = GraphPayload(nodes=list(g.nodes), edges=list(g.edges), hulls=g.hulls)      # never mutate the caller's graph
    if focus not in nodes:
        by_label = [n for n in g.nodes if n.label.lower() == focus.lower() or n.id.lower() == f"person:{focus}".lower()]
        if by_label:
            focus = by_label[0].id
        elif origin and origin in nodes:      # an id the web derived from a chip (trace:kit, cert:..., domain): show it next to its origin
            kind = "trace" if focus.startswith("trace:") else "cert" if focus.startswith("cert:") else "person" if focus.startswith("person:") else "domain"
            n = GraphNode(id=focus, kind=kind, label=focus.split(":", 2)[-1][:40], size=2, meta={"synthetic": True})
            nodes[focus] = n
            g.nodes.append(n)
            g.edges.append(GraphEdge(a=focus, b=origin, type="tracking" if kind == "trace" else "infra", weight=1.0, level="L2"))
        else:
            raise KeyError(focus)
    adj: dict[str, list[GraphEdge]] = {}
    for e in g.edges:
        adj.setdefault(e.a, []).append(e)
        adj.setdefault(e.b, []).append(e)
    mine = sorted(adj.get(focus, []), key=lambda e: -e.weight)
    keep, seen = [focus], {focus}
    if origin and origin in nodes and origin != focus:
        keep.append(origin)
        seen.add(origin)
    for e in mine:
        o = e.b if e.a == focus else e.a
        if o not in seen and len(seen) < max_neighbours + 1 + (1 if origin in seen else 0):
            keep.append(o)
            seen.add(o)
    edges = [e for e in g.edges if e.a in seen and e.b in seen and (focus in (e.a, e.b) or origin in (e.a, e.b) or e.type != "member")]
    deg = {k: len(adj.get(k, [])) for k in keep}
    out_nodes: list[GraphNode] = []
    origin_n = {e.b if e.a == origin else e.a for e in adj.get(origin or "", [])}
    focus_n = {e.b if e.a == focus else e.a for e in adj.get(focus, [])}
    def _neigh(k: str) -> set[str]:
        return {e.b if e.a == k else e.a for e in adj.get(k, [])} - {k}

    def _materials(k: str) -> int:        # how many materials (incidents) share this trace
        inc = [o for o in _neigh(k) if o in nodes and nodes[o].kind == "incident"]
        return int(nodes[k].meta.get("materials") or len(inc) or deg.get(k) or len(_neigh(k)))
    for k in keep:
        n = nodes[k].model_copy(deep=True)
        meta = dict(n.meta)
        meta.setdefault("sub", _sub(n, deg[k]))
        meta["count"] = _materials(k) if n.kind in ("trace", "person", "domain", "cert") else meta.get("count", deg[k])
        meta["expandable"] = min(len(_neigh(k) - ({origin} if origin else set())), max_neighbours)
        if n.kind == "trace" and ("cloudflare" in n.label.lower() or n.meta.get("weak")):
            meta["weak"] = True
        if k == focus and n.kind == "incident":
            meta["side"] = "right"
        if origin and n.kind == "trace":
            if k in origin_n and k not in focus_n:
                meta["only"] = "origin"
            elif k in focus_n and k not in origin_n:
                meta["only"] = "focus"
        if n.kind == "campaign" or n.kind == "incident":
            meta.setdefault("thumb", f"/api/v1/mock/asset/{k}.svg")
        n.meta = meta
        out_nodes.append(n)
    out_edges = []
    for e in edges:
        e = e.model_copy(deep=True)
        if e.type in ("operator", "operation"):
            e.label = e.label or "ten sam operator"
        out_edges.append(e)
    fn = nodes[focus]
    nb = [nodes[k] for k in keep if k not in (focus, origin)]
    g2 = GraphPayload(nodes=out_nodes, edges=out_edges, hulls=[h for h in g.hulls if set(h["members"]) & seen], focus=focus)
    g2.panel = make_panel(fn, deg[focus], nb, origin_node=nodes.get(origin) if origin else None)
    return g2


def _trace_href(n: GraphNode) -> str | None:
    """Ślad page for a node: node ids are `trace:<field>:<value>`, `person:<name>`, `d:<host>` — never put the raw id in the URL."""
    from urllib.parse import quote
    nid = n.id
    if nid.startswith("person:"):
        return "/slad/osoba/" + quote(nid.split(":", 1)[1])
    if nid.startswith("d:"):
        return "/slad/domena/" + quote(nid.split(":", 1)[1])
    if nid.startswith("trace:"):
        parts = nid.split(":", 2)
        if len(parts) < 3 or parts[1] in ("text_minhash", "dom_minhash", "cert_batch"):
            return None                          # similarity groups / cert batches have no trace page
        try:
            from trop.engine.items import ui_layer
            f = parts[1]
            sing = f[:-2] if f.endswith("hes") else f[:-1] if f.endswith("s") else f   # fb_pixels -> fb_pixel, asset_hashes -> asset_hash
            layer = ui_layer(sing)
            if layer in (None, "", "content") and ui_layer(f) not in (None, ""):
                layer = ui_layer(f) if ui_layer(sing) in (None, "") else layer
        except Exception:  # noqa: BLE001
            layer = "kit"
        value = (n.meta or {}).get("value") or parts[2]
        return f"/slad/{layer}/" + quote(str(value), safe="")
    return f"/slad/{n.kind}/" + quote(n.label or nid, safe="")


def make_panel(n: GraphNode, deg: int, neighbours: list[GraphNode], origin_node: GraphNode | None = None) -> dict:
    kinds = {x.kind for x in neighbours}
    tone = {"campaign": "g", "operator": "violet", "trace": "cyan", "incident": "g", "domain": "amber", "person": "cyan"}.get(n.kind, "g")
    topic = KIND_TOPIC.get(n.kind, "trace")
    facts = [{"k": "Połączenia", "v": str(deg)}, {"k": "Kampania", "v": n.campaign_id or "—"}]
    if n.first_seen:
        facts.append({"k": "Pierwszy raz", "v": n.first_seen})
    tags = sorted(k for k in kinds)[:4]
    action: dict = {"label": "Otwórz szczegóły", "href": _trace_href(n), "kind": topic}
    if action["href"] is None:
        action = {}
    if n.kind == "domain":
        action = {"label": "Śledź z agentem", "kind": "investigate", "seed": n.label}
    elif n.kind == "campaign":
        action = {"label": "Otwórz kampanię", "kind": "campaign", "href": f"/kampanie/{n.id}"}
    elif n.kind == "incident":
        action = {"label": "Otwórz incydent", "kind": "incident", "href": f"/incydenty/{n.id}"}
    panel = {"kind_label": KIND_LABEL.get(n.kind, n.kind.upper()), "badge": {"text": n.kind, "tone": tone}, "tags": tags, "title": n.label,
             "description": f"{n.label} łączy się z {deg} węzłami w tym widoku.", "facts": facts, "bot": "Tropiciel",
             "bot_text": f"{n.label}: {deg} połączeń" + (f"; most do {origin_node.label}." if origin_node else "."),
             "action": action}
    if n.campaign_id and n.kind != "campaign":
        panel["link"] = {"label": f"Kampania {n.campaign_id}", "href": f"/kampanie/{n.campaign_id}"}
    return panel
