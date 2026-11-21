# TROP canvas (working name until 21.11: RED PILL): conventions and fictional data universe (used to build every artboard)

Canvas: https://claude.ai/artifact/9ZdsnJ3Mo4Z3KFGJy4QG6W  (Design type)
Artboards: `project/<Name>.dc.html` (flat folder). Index `project/canvas.json` is owned by the main session: NEVER write or publish it.
Shared stylesheet (uploaded): `/_blob/477be82a65055b423718bfd9aac4ea4d` = `assets/rp.css` (read it; use its classes; do not change it).
Reference artboard to copy structure from: `project/S05-Campaign.dc.html`.

## File skeleton (copy from S05)
- `<html lang="pl">`, own `<title>`, head: `<script src="./support.js"></script>` then `<link rel="stylesheet" href="/_blob/477be82a65055b423718bfd9aac4ea4d">`.
- `<helmet>`: the Google Fonts link exactly as in S05, `<style>body{margin:0;background:#050806}` + only small page-local classes.
- Root: `<div class="rp {{annot}}" style="min-height: 100vh; background: #050806; color: #DDEBE2">`.
- App screens: `.app` > `.side` with `<dc-import name="Nav" active="<id>" hint-size="100%,960px"></dc-import>` + `.main` > topbar `header.top` (copy S05, change the trail) + `main.page` + `p.footnote`.
  Nav ids: command, triage, hunter, analyze, incident, campaign, graph, invest, oracle, radar, act, lab, public.
- Script: `data-props='{"showApi":{"editor":"boolean","default":false,"section":"Spec"},"$preview":{"width":W,"height":H}}'` and `renderVals(){ return { annot: (this.props.showApi ?? false) ? 'show-api' : '' , ...} }`. Add more state only if the artboard is interactive.
- Fluid PAGE: no px root width; use `.split` (`.a` wide / `.b` side), `.cards`, `.kpis`, flex-wrap rows; wide tables in `.scroll-x`. Must not break at phone width.
- `<span class="api">GET /…</span>` in each panel header naming the endpoint that feeds it (shown by the showApi tweak). Use the endpoint names below exactly.
- Prototype links: `<a href="S04-Incident.dc.html">` etc. between artboards (all in the same folder). Style the `<a>` itself as a button (`class="btn"`), never a button inside an a.

## Hard rules
- UI copy in Polish; English technical terms where natural (pixel, HAR, CAPI, kit, TLS, DOM, pHash, embedding, triage, Act center, Oracle, Hunter, Agent Smith).
- Only FICTIONAL data from the universe below. Never use anything from the repo's `data/` folder. IPs only from 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24; ASN only AS64500–AS64511. People: generic silhouettes (`.sil` + inline SVG), never photos.
- No emoji. Icons = inline stroke SVG (24 viewBox, stroke 1.7–1.8, currentColor, aria-hidden). Charts may be one `<svg role="img" aria-label="…">`.
- Real elements: `<button type="button">`, `<a href>`, `<input>` with `<label>` or aria-label; aria-label on icon-only buttons. Text contrast ≥ 4.5:1 (use the CSS tokens; `--tx3` is the faintest allowed text colour).
- No filler. Every number is plausible for the scenario below and consistent across screens. Footnote: "Wszystkie dane na makiecie są fikcyjne · RED PILL · HackNation 2026".
- Evidence chip markup (see rp.css `.ev`): `<span class="ev t-tracking"><span class="t">Tracking</span><span class="v">CAPI cg-7f3a…</span><span class="sb h"><i></i><i></i><i></i></span><span class="w">+3.1</span><span class="r">47/1 284</span></span>`; type labels: Tracking, Kit, Infra, Treść, Osoby, Obraz, Reklama, Media; type classes t-tracking t-kit t-infra t-content t-persons t-visual t-ad t-media; modifiers `.conf` (conflict, weight negative), `.miss` (missing value: "brak"), `.zero` (common value, weight 0.0 e.g. Cloudflare).
- Levels: `.lvl.l0` duplikat, `.l1` wariant, `.l2` kampania, `.l3` operator.
- Verdict states: `.verdict` (dołącza do kampanii, green), `.verdict.new` (nowa kampania, amber), `.verdict.unsure` (niepewne → triage, cyan).
- Never class names containing "ad", "ads", "sponsor", "banner", "promo" as whole words (ad blockers hide them). `t-ad` is fine.
- Publishing: `Artifact` publish with `url` = the canvas, `root` = the folder above, `file_path` = your artboard's absolute path, no `files`, no `asset`. Never send canvas.json or another writer's file. If a publish is refused, stop publishing (keep writing files) and say so in your report.

## Fictional universe (use consistently)
Now: 21.11.2026, ~08:50. Corpus N = 1 284 incidents, 41 active campaigns, 6 operator families.

Campaigns
- **KMP-017 «Zamach» — fałszywy portal → „inwestycja”** (L2, active, +38%/48h). Operator **OP-03 «Kestrel»**. 46 incidents, 19 domains, 11 advertisers (random names: „Ogród i Pasja 24”, „Puzzle Mania PL”, „Lena Kwiatkowska Sklep”), 3 persons: Jan Kowalski (przedsiębiorca), Anna Nowak (dziennikarka), Tomasz Lewandowski (dziennikarz). Impersonated outlet: «Kurier Dnia» (fictional). Headline templates: „PILNE: {PER} przerywa milczenie po napaści…” (V2, 22), „«Wiem, kto to zrobił»: atak na {PER}” (V1, 19), V3 nagranie wideo deepfake (5). Ad decoys: landscape/animal creatives, display link OKAZJE-DNIA.COM. Kit endpoint `/api/v2/relay/lead/{uuid}/`; URL grammar `utm×5 + utm_visit=uuidv7`; CAPI gateway `cg-7f3a91e0.ecs.eu-west-1.on.aws/events`; Let's Encrypt R11 night batches 00:00–03:00 UTC; origin AS64500 behind Cloudflare (Cloudflare IPs are weight 0). Domains: morvanta.click (cert today 02:31, Oracle predicted 19.11), orvinta.click (cert today 01:12, Oracle 20.11), plessuro.live (cert today 00:47, no ads yet), velmoria.click (CERT PL), trastino.live (CERT PL), quorvex.click, ambrelio.live, dunvarra.click, selqueno.live (offline 502), tranvello.click. 5/19 on CERT PL list.
- **KMP-034 «Cukrzyca — Glikonor»** (health, OP-03, 12 incidents, shares relay kit v1 and the CAPI gateway with KMP-017). Persona „dr Piotr Wiśniewski” (deepfake video). Product Glikonor. Domain glikonor-pl.shop, kelvaro.live.
- **KMP-022 «Stawy — fałszywy lekarz»** (health, OP-07 «Orchid», 31 incidents). Persona dr Piotr Wiśniewski (synthetic voice 0.87). Product Artovita Forte. FB pixel 870011223344556. Keitaro-like params `clickid / key / pixel_fb`. Domains artovita-forte.shop, zdrowestawy-pl.store.
- **KMP-031 «Platforma AI — inwestycje»** (investment, OP-05 «Heron», 58 incidents). Personas Marek Zieliński (sportowiec), Katarzyna Wójcik (prezenterka). Domain quantapl-invest.top. Google Ads AW-11122233344 (fictional).
- **KMP-040 — kandydat nowej kampanii «Bon energetyczny»** (3 incidents, gov-subsidy lure, no shared infra with known campaigns; conformal set empty).

Key incident for demos: **INC-24817** — captured 21.11 02:31 by Hunter (Ad Library), URL `https://morvanta.click/?utm_source=…&utm_visit=<uuidv7>`, verdict: joins KMP-017, p = 0.94, conformal set {KMP-017} at α = 0.05, runner-up KMP-034 0.41 (same operator family, margin 0.53), coverage 0.78 (6/8 layers; missing: media/ASR, RDAP timeout = partial infra). Evidence:
Tracking CAPI gateway H +3.1 47/1 284 · Kit relay/lead template H +2.7 58/1 284 · Treść template „PILNE: {PER}…” H +2.2 22/1 284 · Infra cert batch LE R11 21.11 00:47–02:31 M +1.4 6/1 284 · Obraz landing pHash Δ4 M +0.9 · Osoby Jan Kowalski (face 0.91 + NER) M +0.8 61/1 284 · Reklama decoy creative L +0.3 · Infra Cloudflare 203.0.113.0/24 zero 0.0 512/1 284.
Pipeline for the Analyze demo (total 19.6 s): przyjęcie 0.2 s · capture Playwright sandbox 6.8 s (4 redirecty, HAR 212 żądań, DOM, TLS) · ekstrakcja tracking/kit 0.6 s · OCR+VLM 3.9 s · twarze 1.7 s · tekst/NER/szablon 0.8 s · embeddingi 1.1 s · enrichment DNS/RDAP/crt.sh 2.4 s (RDAP timeout → częściowe) · blocking + dowody 0.4 s (312 kandydatów → 9 kampanii) · M1 + kalibracja 0.3 s · decyzja konformalna 0.1 s.

Agent Smith demo (seed velmoria.click): crt.sh cert batch → 6 SAN domains; DNS/RDAP → origin 198.51.100.23 AS64500; urlscan search for kit path → 14 domains; Ad Library → 9 active ads, 4 advertiser pages; CERT PL check → 11 of 14 not listed; 3 certificates issued tonight (00:47 plessuro.live, 01:12 orvinta.click, 02:31 morvanta.click); Oracle had flagged 2 of them (orvinta, morvanta). 20-step budget, ~2 min.

Oracle: CT stream matches (orvinta.click 0.93 KMP-017, plessuro.live 0.88 KMP-017, tranvello.click 0.71 KMP-017 pending, kelvaro.live 0.64 KMP-034, brustia.click 0.42 below threshold), precision@20 0.85, median lead time 31 h before first ad. Domain DNA KMP-017: CVCCVCV-like pseudo-words 7–9 letters, .click|.live, registrar „R-114 (anonimizowany)”, LE R10/R11 night batches, hosting AS64500.

Triage queue: 23 open items. Types: niepewne przypisanie (pasmo 0.35–0.65), kandydat nowej kampanii, Oracle: domena przewidziana, Hunter: nowa reklama, zgłoszenie z wtyczki, propozycja scalenia kampanii. Shortcuts A akceptuj, R odrzuć, M przenieś, S pomiń.

Lab (mark „przykładowe wartości, podmienić z eval/”): B-cubed F1 M1 0.91 vs ręczne wagi 0.78 vs HDBSCAN 0.61; ARI 0.87; pairwise precision 0.96; open-set accuracy 0.93; precision of „nowa kampania” 0.95; conformal achieved error 4.1% vs target 5%; infra-blind (M2) F1 0.74.

Impersonated people (radar): Jan Kowalski, Anna Nowak, Tomasz Lewandowski, dr Piotr Wiśniewski, Marek Zieliński, Katarzyna Wójcik. Brands: «Kurier Dnia», «TV Info24», bank «Bank Przykładowy».

## API naming (base /api/v1; annotations omit the prefix)
stats/overview · events (SSE stream) · alerts · search?q=
jobs (POST /analyze → job; GET /jobs/{id}; SSE /jobs/{id}/stream)
incidents · incidents/{id} · incidents/{id}/artifacts · incidents/{id}/features · incidents/{id}/matches · incidents/{id}/decision
links/{a}/{b} (pair explanation: evidence, missing, conflicts, contributions) · evidence/values/{type}/{value} (rarity, incidents sharing it)
campaigns · campaigns/{id} · /dna · /timeline · /members · /indicators · /variants · /phylogeny · /summary · POST /merge · POST /split
operators/{id} · graph?scope=&layers=&level=&min_weight=
investigations (POST seed) · investigations/{id} · SSE investigations/{id}/stream · POST /steer · POST /stop · POST /promote
oracle/dna?campaign= · SSE oracle/stream · oracle/predictions · oracle/metrics
persons?window= · persons/{id}
act/packages (POST {campaign_id, kind: dsa|certpl|stix|misp|rules}) · act/packages/{id} · /download · POST /submit · act/rules · POST act/rules/test
triage · triage/{id} · POST triage/{id}/decision · feedback
lab/metrics · lab/ablation · POST lab/stress · lab/runs/{id}
hunter/sources · PATCH hunter/sources/{id} · POST hunter/sources/{id}/run · hunter/runs
public: POST public/check · POST public/report · POST public/extension/match
SSE event names: incident.created, incident.attributed, campaign.updated, alert.created, job.step, agent.step, graph.node_added, graph.edge_added, casefile.delta, oracle.match, hunter.capture, triage.created

