# TROP: app and flow design

> Design for the TROP dashboard (working name until 21.11: RED PILL): information architecture, every screen, the explainability components and the key flows, built on Claude's design canvas.
> **Current direction:** the canvas page "TROP · Sprawdź" (see the canvas map). Only the first screen borrows zgrai's look (one field, sleeping bots). Everything after it grows out of the analysis view. There is no chat UI and no login. The older pages are earlier explorations.
> Owner of this folder: the design session. Inputs: `docs/PLAN.md` v2 (§0 pillars and demo, §4 schema, §6 method, §7 screens).
> **All data in the designs is fictional** (domains, IDs, people, numbers). Nothing comes from `data/`, so the canvas can be shared.

**Canvas:** https://claude.ai/artifact/9ZdsnJ3Mo4Z3KFGJy4QG6W (private until shared from the page's Share menu)

- Link to one artboard with `<canvas-url>#artboard-<name>`, e.g. `#artboard-S05-Campaign`. Play a flow from an artboard with `#play-<name>`.
- Every app artboard has a **`showApi` tweak** (Tweaks panel). Turn it on to see, at each panel, the endpoint that feeds it.
- App screens are clickable. The sidebar, the buttons and the table rows link between artboards, so Play mode works as a prototype.
- Source of the artboards: `docs/design/canvas/project/*.dc.html`. Shared tokens and component CSS: `docs/design/canvas/assets/rp.css`. On the canvas the artboards load the CSS from the canvas asset store (`/_blob/…`).
- The fictional data universe (campaigns KMP-017/022/031/034/040, INC-24817, the demo pipeline, the Agent Smith run) and the authoring conventions are in `docs/design/canvas/BRIEF.md`. Use the same values for the mocked API / seeded demo, so the UI and the design match.
- Interactive artboards: `S02` (`verdict` tweak: joins / new / unsure), `X5` (α slider), `F6` (demo stepper), `E2` (`result` tweak: scam / unknown). Every app screen is clickable through the sidebar.

---

## 1. Canvas map

| Page | Artboards |
|---|---|
| Start · IA · system | `Main` (IA, routes, object model, global patterns, legend) · `DesignSystem` (identity, tokens, base components, motion, copy rules) · `Nav` (sidebar component, imported by every screen) |
| Ekrany | `S01-Command` · `S02-Analyze` · `S03-Triage` · `S04-Incident` · `S05-Campaign` · `S06-Graph` · `S07-Investigation` · `S08-Oracle` · `S09-Radar` · `S10-Act` · `S11-Lab` · `S12-Hunter` |
| Wyjaśnialność | `X1-EvidenceChip` · `X2-WhyLinked` · `X3-TemplateDiff` · `X4-Coverage` · `X5-Conformal` |
| Przepływy | `F1-NewMaterial` · `F2-CampaignAct` · `F3-AgentInvestigation` · `F4-AlertTriage` · `F5-Citizen` · `F6-JudgeDemo` (interactive stepper) |
| Obywatel | `E1-Extension` (overlay on a sponsored post + popup) · `E2-SprawdzReklame` (public page; `result` tweak: scam / unknown) · style variants `E2b-Sprawdz-Zgrai` · `E2c-Sprawdz-Znak` · `E2d-Sprawdz-Rozmowa` |
| Styl zgrai (approved shell) | `ZB-Werdykt` (reference layout: verdict board with connections, bubbles and the action dock) · `ZB-Sledztwo` · `Z-S01-Command` · `Z-S02-Analyze` · `Z-S05-Campaign` · `Z-Chmura` (relation cloud) · `Z-S07-Investigation` · `Z-S10-Act` · `Z-E1-Extension` · `NavZ` (64 px icon rail) |
| TROP · Sprawdź (current direction) | `Sprawdz` (1 · pole) is the interactive prototype: it plays the whole flow after "Sprawdź". `Sprawdz-2-Analiza` is the same board opened at the analysis step. `Sprawdz-3-Raport` and `Sprawdz-4-Graf` are plain boards built from literal elements so they can be edited on the canvas; their Raport / Graf switch links the two boards. The UI shows no "why not KMP-034" line and no conformal-set jargon (α, „zbiór”); the verdict is "KMP-017 · pewność 0.94". Tabs across the top (Sprawdź · Kampanie · Śledztwa), no sidebar, no login.<br>**1 · Pole** (the only zgrai-style screen): one field labelled "Link, plik albo ślad". It takes a link, a file (chips: Zrzut ekranu · Wideo · HAR lub ZIP) or a typed trace (chip: Domena lub osoba). Sleeping bots sit around it; button **Sprawdź**. A link or file goes to the analysis; a typed trace opens board 14. The bots wake up, then the screen turns into the analysis.<br>**2 · Analiza:** the material bar on top (URL, INC id, timer, Anuluj); a strip of six bots that wake one by one, one pipeline step each (Zwiadowca: capture, Tropiciel: tracking and kit, Czytelnik: content and persons, Notariusz: domain and certificates, Archiwista: comparison with the base, Sędzia: verdict); below, three columns: the captured page with each finding outlined where it was found, the evidence list filling in live (who found it, value, rarity, strength, plus the bot still working), and the live campaign ranking with a small graph forming.<br>**3 · Raport:** verdict, the same findings with weights, feedback, a step summary with details.<br>**4 · Graf:** the same cards move into a graph with KMP-017, its materials and KMP-034 (same operator). Nodes are clickable ("Kliknij węzeł, żeby go rozwinąć"). A click keeps the page and turns the graph around the clicked node: a trail on top ("Graf › morvanta.click"), on the left where you came from, in the middle the node with a heavy outline, on the right its neighbours (each clickable again), and a side panel with facts, one bot sentence, one primary action and a text link. The × or the trail goes back to the graph.<br>**4a · `Graf-Domena`** (click the domain or the certificate card): morvanta.click with its certificate, the domains from the same night batch, the ads that used it and Cloudflare (skipped). Panel: registration, certificate, first ad, registrar unknown, report status. Action "Szukaj sąsiednich domen" (agent), link to the trace page.<br>**4b · `Graf-Slad`** (click "kit relay v1"): the kit leads to two campaigns (KMP-017 46, KMP-034 12) and their single operator OP-03. Action "Pokaż 58 materiałów".<br>**4c · `Graf-Osoba`** (click "Jan Kowalski"): campaigns using the face (31 / 18 / 7, 5 without a campaign) and what usually comes with it (Anna Nowak, «Kurier Dnia»). Action "Pokaż wszystko o tej osobie" (board 14).<br>**4d · `Graf-Material`** (click a dot in the campaign cloud, INC-24702): a bridge view. Your material on the left, the other one on the right, the traces between them; shared traces connect both sides, the two different domains connect only one side each ("4 z 5 śladów"). Action "Otwórz jej raport".<br>In the app each bot step maps to one step event of `GET /jobs/{id}/stream`, and each evidence card to an `evidence` event. The bots use the zgrai jelly scripts from the canvas asset store.<br>**Detective costume** (opt-in): `/_blob/8330ca0d163fc8da1b2601518af3de91` = `canvas/assets/jelly-overlay-detective.js`, a drop-in replacement for the second jelly script (`/_blob/0fec4c5e…`); the first script (three.js) stays. Turn it on per overlay with `mountOverlay(canvas, root, { costume: 'detective' })` or per avatar with `data-costume="detective"`. Each bot gets its own variant by colour: Zwiadowca a police patrol cap, Tropiciel and Archiwista a fedora with a magnifying glass (lies at their feet when asleep, raised while speaking), Czytelnik a fedora with a monocle, Notariusz a bowler with a monocle, Sędzia a peaked cap with a checked band; any other colour gets fedora + magnifier. Override with `data-costume="detective:police|lupa|monocle|bowler|chief"` or `bots: [{ color, costume: 'detective:monocle' }]` in field mode. Without the option the bots look exactly as before. All TROP boards with bots use it (boards 1–14 and 4a–4d; Kampanie has no bots). The parked `T-*` boards keep the plain bots. |
| TROP · Kampanie (same page, second row) | Built from plain elements like boards 3–4, so everything is editable. **Reports live inside the campaign:** a report is always about one campaign, so there is no Zgłoszenia tab.<br>**5 · `Kampanie`:** campaign list grouped by **operator** (OP-03 «Kestrel» → KMP-017, KMP-034, KMP-043 …), with an **Oracle** strip on top (domains that got a certificate before any ad, matched to a campaign), filters (all / growing / new / not reported / **do uzupełnienia**, i.e. campaigns that grew after reporting) and a **people** filter ("Kogo udają"). A merge strip says when two campaigns look like one ("KMP-017 i KMP-043 wyglądają na jedną kampanię", link "Porównaj i scal"); the suspect row carries a small "może to KMP-017? scal" pill. Per row: description, 14-day sparkline, materials and growth, domains (new / predicted), report status.<br>**6 · `Kampania-KMP017`:** description headline, stats, timeline with Oracle markers, "Co łączy te materiały" (bot evidence cards with coverage like "46 z 46"), domains with status, then a **Zgłoszenia** card: each sent package with per-recipient progress (Meta 0 of 46, CERT PL 24 of 24, Google queued) and a "Nowe zgłoszenie" link. On the side: a merge suggestion ("Możliwe, że to ta sama kampania · KMP-043"), the Oracle predictions, the operator (stats, "Rozpoznajemy go po", other campaign) and the people it impersonates. Main action "Zgłoś całą kampanię", text link to the agent.<br>**7 · `Zgloszenie-KMP017`:** opened from the campaign (Kampanie tab stays active). One package for the whole campaign: recipients (Meta DSA, CERT PL, Google, registrar off by default), what goes in (each part prepared by a bot), the notice text written by Sędzia and editable, PDF / STIX download. "Wyślij 3 zgłoszenia" returns to the campaign, where the package shows in the Zgłoszenia card.<br>**8 · `Scal-Kampanie`:** merge two campaigns. Two cards side by side (KMP-017: text and photos, 46 materials; KMP-043: deepfake video, 5 materials) with a radio for which one keeps the name; "Co je łączy" as bot evidence (same kit 5 of 5, shared domains 4 of 6, different format); "Po scaleniu" before → after (materials 46 + 5 → 51, domains 19 + 6 → 21); a note that the 5 videos go into the report supplement; "Scalenie można cofnąć". Primary "Scal kampanie", text link "albo zostaw osobno". In the app: `POST /campaigns/{a}/merge` with an undo window.<br>Decisions: Oracle, operators, people and reports live inside Kampanie (no tabs of their own). Search is the Sprawdź field: it takes a link, a file or a single trace (domain, pixel, name); a trace opens where it appears. |
| TROP · Śledztwa, inne wyniki, ślad (same page, rows 3–4) | **Top bar is now Sprawdź · Kampanie · Śledztwa.** Zgłoszenia moved into the campaign page. Kolejka is dropped: sure materials from Hunter / Oracle / extension join campaigns on their own (visible as growth in Kampanie).<br>**9 · `Sledztwo`:** investigation in progress, no chat. The bot strip shows who is working. A tree grows from the start domain, one branch per source (crt.sh, urlscan, Ad Library, CERT PL, our database, content), with node pills for new / already in the campaign / to decide / in progress. On the side: Sędzia's decision card (kalvesto.live: join or skip), the running totals and a progress bar.<br>**10 · `Sledztwo-Koniec`:** finished: what gets added (checkable rows, each with the bot that found it), the campaign before → after (19 → 29 domains, 46 → 55 materials), and what was skipped. Main action "Dodaj do kampanii", text link "albo zgłoś od razu".<br>**11 · `Sprawdz-Nowa`:** no campaign matches. A blue strip with an editable name for the new campaign (KMP-040 «Bon energetyczny»), the new traces marked "nowy", and the closest campaigns, all far below the 0.80 needed to join.<br>**12 · `Sprawdz-Niepewne`:** two campaigns of the same operator fit (0.52 / 0.47). Side-by-side cards say what matches and what is unknown, with one "To KMP-…" choice each; a hint to add a screenshot so the bots can decide.<br>**13 · `Sprawdz-Blad`:** the page does not respond. It shows what the bots could still establish (domain DNA, history) vs what failed, a preliminary guess, and other ways to check (archive copy, screenshot, HAR).<br>**14 · `Slad`:** what Sprawdź shows for a single trace (example: the name "Jan Kowalski"). The same field as board 1 stays on top, in a 380 px full-width strip where the six bots, dressed as detectives, roam freely around the field (jelly field mode, `state: 'awake'`, the field marked `data-jelly-clear`). They walk on their own, turn toward the cursor and react to a click. Below: campaigns it appears in, weekly chart, latest materials, how it is used, traces it usually comes with. |
| Odłożone (rejected) | `T-Kolejka` · `T-Sledztwo` · `T-Mapa`, plus the superseded `T-Kampania` and `T-Zgloszenia`: drawn in zgrai style (chat with bots, grey summary panels). Rejected as too close to zgrai. Also `Zgloszenia` (the sent-reports list as its own tab), parked when reports moved into each campaign page. |
| Sprawdź materiał · opcje | Four takes on the core flow "check a material → verdict", each with an `etap` tweak (start → analiza → werdykt): `C1-Pole` (one input, the result reads top to bottom, a "Werdykt trafny?" feedback row) · `C2-Tablica` (the board fills in live: evidence first, then the campaign, verdict in the dock) · `C3-Porownanie` (layer-by-layer table: this material vs KMP-017 vs KMP-034 vs a new campaign, the decision is a column button) · `C4-Skrzynka` (queue of Hunter / Oracle / extension / manual items, the decision in a right-hand panel, J/K/Enter) |
| Nowe kierunki (explorations) | `K1-Akta` · `K2-Tablica` · `K3-Plakat` · `K4-Terminal` |
| Motyw Matrix (theme study) | The `ZB-Werdykt` board re-themed four ways, same layout and content: `M1-Fosfor` (classic phosphor terminal) · `M2-Ciemny` (dark zgrai, one green accent, rain only behind the campaign) · `M3-Deszcz` (dense code rain, glass cards, terminal-window bubbles) · `M4-Pigulki` (red pill = linked, blue pill = not linked) |

---

## 2. Visual identity, in short

- **Direction:** an SOC console with a phosphor accent. The ground is near-black with a green tint, there is one accent (phosphor green `#3BF07E`), semantic colours are used for states only, and a separate 8-colour palette marks the evidence types. Matrix shows up in details only: glyph rain in the hero and verdict moments, mono for data, a red/green capsule logo, and the tagline "follow the fake".
- **Fonts:** Space Grotesk (headings), Inter (UI), JetBrains Mono (data, IDs, evidence values). Google Fonts.
- **Tokens** (`rp.css` `:root`):
  - Grounds `--bg #050806`, `--bg1 #0A100C` (panel), `--bg2`, `--bg3`, `--bg4`; lines `--line #1D2B22`, `--line2`, `--line3`.
  - Text `--tx #DDEBE2`, `--tx2 #A9BDB0`, `--tx3 #83998B`. `--tx3` is the minimum label colour, at 6.3:1 on a panel.
  - Accent `--g #3BF07E`, with `--ink #03140A` for text on green.
  - States: `--amber #FFB547` (new campaign / warning), `--red #FF5D6C` (conflict, irreversible), `--cyan #5CC8FF` (uncertain / info / API), `--violet #B794FF` (operator family L3).
  - Evidence types `--e-tracking #5CC8FF`, `--e-kit #B794FF`, `--e-infra #FFB547`, `--e-content #FF8FB8`, `--e-persons #FF9A62`, `--e-visual #8FD3C4`, `--e-ad #C9E265`, `--e-media #E59CFF`. Each one always appears together with its label.
- **To Tailwind/shadcn:**
  - Copy the `:root` tokens into `tailwind.config` as `colors.bg.{0..4}`, `colors.line.{1..3}`, `colors.tx.{1..3}`, `colors.ev.{tracking…media}` and `colors.state.{g,amber,red,cyan,violet}`.
  - Font families map to `font-head`, `font-sans` and `font-mono`.
  - The class names in `rp.css` match the component inventory in §6, so each class can become one React component.
- **Copy:** UI is Polish, technical terms stay English (pixel, HAR, CAPI, kit, TLS, DOM, pHash, embedding, triage). Number formats:
  - scores and weights use a dot (`0.94`, `+2.7`), the same as the API;
  - counts use a space for thousands (`1 284`);
  - dates are `21.11.2026 02:31`;
  - rarity is written `47/1 284`, i.e. "widziane w 47 z 1 284".

  Verdict wording is fixed: **„Dołącza do kampanii” / „Nowa kampania (kandydat)” / „Niepewne → triage”**. The public page never says „bezpieczna”.
- **Accessibility:**
  - Focus ring: 2 px `--g` with a 2 px offset.
  - Colour never carries meaning alone.
  - Every control is a real button, link or input with a label.
  - Glyph rain, pulse and scan are switched off under `prefers-reduced-motion`.
  - Keyboard: `Ctrl K` omnibox; `A / R / M / S` and `J / K` in Triage; `?` shows the shortcut list.

---

## 3. Information architecture

Sidebar groups (`Nav` component, `active` prop). The order follows the loop **Poluj → Przechwyć → Zrozum → Przypisz → Przewiduj → Działaj**.

| Group | Screen | Route (Next.js app router) | Artboard |
|---|---|---|---|
| Monitoring | Centrum dowodzenia | `/` | S01-Command |
| | Triage | `/triage`, `/triage/[itemId]` | S03-Triage |
| | Hunter · źródła | `/settings/sources`, `/settings/sources/[sourceId]` | S12-Hunter |
| Analiza | Analizuj materiał | `/analyze`, `/analyze/[jobId]` | S02-Analyze |
| | Incydenty | `/incidents` (list), `/incidents/[id]` | S04-Incident |
| | Kampanie | `/campaigns` (list), `/campaigns/[id]` | S05-Campaign |
| | Graf powiązań | `/graph?scope=&layers=&level=` | S06-Graph |
| | Śledztwa · Agent Smith | `/investigations`, `/investigations/[id]` | S07-Investigation |
| Wywiad | Oracle | `/oracle`, `/oracle/[campaignId]` | S08-Oracle |
| | Radar podszyć | `/radar`, `/radar/[personId]` | S09-Radar |
| Działanie | Act center | `/act`, `/act/[packageId]` | S10-Act |
| System | Lab · metodologia | `/lab` | S11-Lab |
| | Strona publiczna | `/sprawdz` (separate public layout, no auth) | E2-SprawdzReklame |
| (outside app) | Browser extension | `extension/` (MV3) | E1-Extension |

There are no separate artboards for the list views (`/incidents`, `/campaigns`, `/investigations`, `/act`). They reuse the DataTable pattern from the S05 members table and the S03 queue, with filters as `fchip`/`seg` and row → detail.

**Global patterns** (all app screens):
- **Topbar:**
  - Omnibox (`Ctrl K`), which searches any indicator: domain, pixel, asset hash, `INC-`/`KMP-`/`OP-`/`INV-` ID, person or phrase. Typing `śledź <domena>` starts an investigation.
  - **Ślad** (trail breadcrumb): the follow path incident → campaign → operator.
  - A live pill (SSE state), a demo/offline pill and an alerts button.
- **No login:** the app has no accounts, sign-in screen or avatar. Decisions, feedback and notes are stored without an author (a note shows only its time). The API needs no auth headers.
- **Evidence drawer:** clicking any evidence chip anywhere opens a right-hand Sheet. It shows the value, its rarity, rarity over time, and the incidents and campaigns that share it.
- **Live:** one SSE stream feeds the live feed, the nav badges, the toasts and the "nowe" markers in tables.
- **Feedback everywhere:** "To błąd — popraw" on every verdict or link, which creates a triage item.
- **Demo/offline mode:** recorded runs for analyses and investigations, so the demo works without network or API keys.

---

## 4. Screens and the data each one needs

Endpoints are relative to `/api/v1`. "SSE" means typed events on `GET /events` (or the per-job and per-investigation streams). The resource names follow PLAN §4: `incident`, `evidence`, `campaign`, `operator`, …. The shapes are defined in §7.

### S01 · Centrum dowodzenia (`/`)
What the analyst sees on arrival: what happened overnight, which campaigns are heating up, what needs a decision.

| Panel | Data | Source |
|---|---|---|
| Hero (glyph rain, night summary, quick URL input → S02) | summary sentence, top campaign, counts since the last visit | `GET /stats/overview?window=night` |
| KPI row | new_materials_24h, active_campaigns (+new), triage_open, oracle_pre_ad (17), act_packages_7d, domains_not_on_certpl | `GET /stats/overview?window=24h` |
| Kampanie w natarciu | per campaign: id, name, narrative, heat series 48 h, trend %, new domains 24 h, persons (new flag), status | `GET /campaigns?sort=-heat&limit=5` |
| Pochodzenie infrastruktury (dot map) | per ASN: asn, city/geo, domain count, campaign ids, CDN-fronted share | `GET /graph?scope=active&layers=infra&group=asn` |
| Na żywo (feed) | event type, text, linked ids, time | SSE `incident.created`, `incident.attributed`, `oracle.match`, `hunter.capture`, `extension.report`, `agent.step`, `act.submitted` |
| Alerty | source (oracle / hunter / conformal), severity, text, refs, time; actions Do triage / Otwórz | `GET /alerts?status=open`, SSE `alert.created` |
| Agent card | running investigation: seed, step/budget, found counts | `GET /investigations?status=running` |

### S02 · Analizuj materiał (`/analyze/[jobId]`)
Drop a URL, screenshot, HAR, video or zip. A live pipeline follows, then the verdict card. The `verdict` tweak shows the three states.

| Panel | Data | Source |
|---|---|---|
| Drop zone + options | url or files; options `capture_live`, `local_llm`, `offline` | `POST /analyze` (multipart) → `{job_id}` |
| Pipeline | steps[]: key, label, status (pending/run/done/warn/skip/error), duration_ms, detail, warnings; total_ms | `GET /jobs/{id}`, SSE `GET /jobs/{id}/stream` (`job.step`) |
| Przechwycone artefakty | kind, thumbnail URL, caption; redirect chain; HAR stats (requests, hosts) | `GET /incidents/{id}/artifacts` |
| Verdict card | the full `Decision`: decision, campaign, p, conformal set, α, runner-up + margin, operator relation, coverage per layer, evidence[], why-not bullets, adjudicator note | `GET /incidents/{id}/decision` |
| Ostatnie analizy | job/incident id, input type, duration, verdict, time | `GET /jobs?limit=5` |

### S03 · Triage (`/triage/[itemId]`)
The queue of uncertain links, new-campaign candidates, Oracle/Hunter alerts, extension reports and merge proposals. Each decision is feedback for M1.

| Panel | Data | Source |
|---|---|---|
| Filters | counts per type; sort by priority or age | `GET /triage?status=open&sort=priority` (returns `facets`) |
| Kolejka | type, subject id, suggestion, score, age, priority | `GET /triage`, SSE `triage.created` |
| Detail: candidates | item, source, coverage; candidates[]: campaign_id, score, evidence for / against / missing | `GET /triage/{id}` |
| Adjudykator (LLM) | model, verdict text, confidence, rationale[] | `GET /links/{a}/{b}?adjudicate=1` (cached on the triage item) |
| Decision bar + note | `accept / reassign / reject / new_campaign / skip`, target campaign, note | `POST /triage/{id}/decision` |
| Daily stats | decisions, agreement with the model, threshold corrections, last retrain | `GET /feedback/stats?window=24h` |

### S04 · Incydent (`/incidents/[id]`)
Every extracted feature by layer, the captured artifacts, top matches with evidence, and the history.

| Panel | Data | Source |
|---|---|---|
| Header | id, source, captured_at, decision (campaign, p), coverage, domain, title | `GET /incidents/{id}` |
| Artefakty | ad snapshot (advertiser, page age, text, creative, display link, Ad Library ID, delivery); landing screenshot + pHash; redirect chain; HAR summary (hosts with df/N); download links (presigned) | `GET /incidents/{id}/artifacts` |
| Cechy według warstw | 8 layers × key/value, each with df/N, a "links" flag and missing/partial status; quality block (available / missing / errors) | `GET /incidents/{id}/features` |
| Najlepsze dopasowania | campaign, score, top evidence, why-not one-liner | `GET /incidents/{id}/matches?k=3` |
| Najbliższe incydenty | incident id, level L0–L2, score | `GET /incidents/{id}/matches?scope=incidents` |
| Historia | time, event text, actor | `GET /incidents/{id}/history` |

### S05 · Kampania (`/campaigns/[id]`)
DNA fingerprint, timeline, members, indicators, variants, kit phylogeny, operator family, and the Act buttons.

| Panel | Data | Source |
|---|---|---|
| Header + Act buttons | id, name, description, status, heat trend, level, operator_id; buttons → S10 with `campaign_id` and kind | `GET /campaigns/{id}` |
| KPI row | incidents (+24 h), domains (certs tonight), advertisers (removed), persons, certpl_listed/domains, first/last seen | `GET /campaigns/{id}` (`counts`) |
| DNA kampanii | signature[]: layer, field, value, members_with/members_total, strength (also drawn as the barcode glyph) | `GET /campaigns/{id}/dna` |
| Oś czasu | days[]: date, incidents; events[]: domain_registered, cert_batch, oracle_predicted, act_sent | `GET /campaigns/{id}/timeline?range=14d` |
| Członkowie | incident_id, captured_at, source, domain, person, level (L0 parent id), score, top_evidence[2], coverage layers | `GET /campaigns/{id}/members?level=&sort=-captured_at` |
| Podsumowanie (LLM) | text with citations (incident ids), model, generated_at | `GET /campaigns/{id}/summary` |
| Wskaźniki (tabs) | domains (cert_issued_at, oracle_predicted_at, on_certpl, online/502, ads_seen), tracking, kit, persons, advertisers | `GET /campaigns/{id}/indicators?type=` |
| Warianty (L1) | variant id, label/template, count | `GET /campaigns/{id}/variants` |
| Filogeneza kitu | nodes (kit version, campaign/variant, first_seen), edges (parent, child, shared DOM paths/assets) | `GET /campaigns/{id}/phylogeny` |
| Rodzina operatora | operator id, codename, campaigns[], shared evidence[] | `GET /operators/{id}` |
| Merge / split | (actions) | `POST /campaigns/{id}/merge`, `POST /campaigns/{id}/split` |

### S06 · Graf powiązań (`/graph`)
A WebGL graph (Sigma.js + graphology), coloured by campaign. Edges are coloured by evidence type and can be filtered by type. The **"tylko treść vs tylko infra" comparison** shows that content alone over-merges, while infra/kit splits correctly.

| Panel | Data | Source |
|---|---|---|
| Toolbar | scope (all / operator / campaign), level L0–L3, evidence-type filters with edge counts, min weight, time range, layout | query params of `GET /graph` |
| Graph | nodes[]: id, kind, campaign_id, label, size; edges[]: a, b, type, weight, level; hulls[]: campaign/operator groups | `GET /graph?scope=&layers=&level=&min_weight=&from=&to=` |
| Inspector: edge | endpoints, level, M1 p, Σ weight, evidence chips, per-layer contributions; "Oznacz jako błędne" | `GET /links/{a}/{b}`; `POST /feedback` |
| Inspector: node | incident summary, campaign, decision | `GET /incidents/{id}` |
| Porównanie warstw | two graphs (layers=content vs layers=infra,kit) + B-cubed precision of each | `GET /graph?layers=content`, `GET /graph?layers=infra,kit`, `GET /lab/metrics?view=layer_compare` |
| Communities in view | campaign id, nodes in view, cohesion, new flag; Louvain modularity | part of `GET /graph` |
| Timeline scrubber | node first_seen for the growth animation | `nodes[].first_seen`, or `GET /graph?until=<ts>` for replay |

### S07 · Śledztwo · Agent Smith (`/investigations/[id]`)
A React Flow canvas that grows live as the agent pivots, with the case file streamed next to it. The analyst can steer, pause or stop the agent.

| Panel | Data | Source |
|---|---|---|
| Header | id, seed, status, step/budget, elapsed, model, tool allowlist | `GET /investigations/{id}` |
| Steer / pause / stop | message; control | `POST /investigations/{id}/steer`, `POST /investigations/{id}/stop` (pause = stop with `resume:true`) |
| Canvas | nodes[]: id, kind (domain, cert, ip, query_result, ad, list_status, oracle_flag), label, meta, is_new; edges[]: a, b, label | SSE `GET /investigations/{id}/stream`: `graph.node_added`, `graph.edge_added` |
| Tool usage strip | per tool: calls, last latency, errors | SSE `agent.step` (aggregated client-side) |
| Akta sprawy | steps[]: n, tool, query, result_summary, why, produced node ids; streaming delta | SSE `agent.step`, `casefile.delta` |
| Wnioski + actions | conclusions[] with evidence refs (step numbers); promote 14 domains to KMP-017; send to Act; export case file | `POST /investigations/{id}/promote`, `POST /act/packages {kind:'certpl'}`, `GET /investigations/{id}?format=md\|pdf` |
| Start (from S05 / omnibox) | seed, budget, tools, offline flag | `POST /investigations` |

### S08 · Oracle (`/oracle/[campaignId]`)
Domain DNA per campaign, a live Certificate Transparency stream with matches, and predicted vs confirmed.

| Panel | Data | Source |
|---|---|---|
| KPI row | flagged_24h, confirmed (precision@20), median_lead_h, ct_rate_per_h, false_alarms_24h | `GET /oracle/metrics` |
| Campaign tabs | campaigns with a DNA model | `GET /oracle/dna` (list) |
| Strumień CT | time, domain, issuer, dna_score, campaign_id, status (predicted / confirmed / below_threshold / dismissed), incident_id, reviewer_note; actions to triage / investigate | SSE `GET /oracle/stream` (`oracle.match`), `GET /oracle/predictions?status=`; "Do triage" → `POST /triage {source: 'oracle', prediction_id}` |
| Przewidziane vs potwierdzone | per domain: predicted_at, first_ad_at, lead_time_h | `GET /oracle/predictions?status=confirmed` |
| DNA domen | grammar, examples, tld_dist, length_hist, registrars, issuance_hours[24], asns, ns, model (name, AUC), threshold + sweep rows {threshold, alerts_per_day, precision_at_20, lead_h} | `GET /oracle/dna?campaign={id}`; threshold change `PATCH /oracle/dna/{campaign_id} {threshold}` |

### S09 · Radar podszyć (`/radar/[personId]`)
Who is being impersonated this week, which campaigns are behind it, and the deepfake and voice evidence.

| Panel | Data | Source |
|---|---|---|
| Week selector + comms note | week list; note for NASK comms (markdown) | `GET /persons?window=7d&week=47`; note `GET /persons?window=7d&format=brief` |
| Person cards | person_id, name, role, ads_count, delta_pct, campaigns[], deepfake_score, synthetic_voice_score, is_new | `GET /persons?window=7d` |
| Heatmap | persons × 8 weeks counts | `GET /persons?window=8w&bucket=week` |
| Person detail | campaigns (id, count), face similarity, NER hits, deepfake, voice (or missing), narratives with counts, sample ads {text, incident_id, campaign, variant} | `GET /persons/{id}` |
| Marki podszywane | brand, kind, count, campaigns | `GET /brands?window=7d` |

### S10 · Act center (`/act/[packageId]`)
Campaign-level DSA Art. 16 notice, CERT PL submission, STIX 2.1/MISP export, and detection rules with "Testuj na zbiorze". **Sending always needs an explicit confirmation step.**

| Panel | Data | Source |
|---|---|---|
| Packages list | id, kind, campaign_id, status, sent_at, outcome (e.g. removed 41/58) | `GET /act/packages` |
| Builder (DSA tab) | contents checklist with counts (ads + Ad Library IDs, advertisers, domains, evidence per element, pattern description, legal basis, reporter); preview document; recipient; formats | `POST /act/packages {campaign_id, kind}` → draft; `GET /act/packages/{id}` |
| CERT PL tab | unlisted domains + evidence each | same, `kind: certpl` |
| STIX / MISP tab | bundle preview | same, `kind: stix | misp`; `GET /act/packages/{id}/download?format=` |
| Confirm & send | checkbox + send | `POST /act/packages/{id}/submit` (requires `confirm: true`) |
| Reguły: test na zbiorze | rule kind (urlscan / url_regex / html_signature) + body; result: hits, tp, needs_review, benign_hits/benign_total, precision | `GET /act/rules?campaign=`, `POST /act/rules/test` |
| Skuteczność | removed / total ads per sent package | `GET /act/packages?status=sent` |
| Historia wysyłek | package, recipient, time, outcome, per campaign | `GET /act/packages?campaign_id=` |

### S11 · Lab · metodologia (`/lab`)
Metrics, ablation, a robustness stress test, leave-one-campaign-out, conformal calibration and the model registry. Values come from `eval/` at build or run time; the design shows sample values.

| Panel | Data | Source |
|---|---|---|
| Metric cards | bcubed_f1 (P/R), ari, pairwise_precision, openset_accuracy, new_campaign_precision, conformal {target, achieved} | `GET /lab/metrics` |
| Porównanie metod | F1 per method (M1, hand weights, infra-blind M2, HDBSCAN) | `GET /lab/metrics?view=baselines` |
| Ablacja | layer, delta_f1 | `GET /lab/ablation` |
| Stres-test | perturbations[] (drop HAR, drop screenshot, swap domain, 502, duplicates, other export format, mask infra) → run; results: perturbation, stability, f1, flipped_to_new, runtime | `POST /lab/stress` → `{run_id}`, `GET /lab/runs/{id}` |
| Leave-one-campaign-out | held-out campaign, came back as new or merged into which | `GET /lab/metrics?view=loco` |
| Kalibracja konformalna | points: alpha (target), achieved error | `GET /lab/metrics?view=conformal` |
| Rejestr modeli | M1–M6: id, type, version, trained_on, runs_on (CPU / WCSS → ONNX), METHODOLOGY links | `GET /lab/metrics?view=models` |

### S12 · Hunter · źródła (`/settings/sources`)
Sources, schedules, lure phrases, capture policy and data rules.

| Panel | Data | Source |
|---|---|---|
| Sources table | id, kind, schedule, status, last_run_at, new_24h, errors_24h, enabled; Uruchom teraz | `GET /hunter/sources`, `PATCH /hunter/sources/{id}`, `POST /hunter/sources/{id}/run` |
| Source detail | phrases[], persons watchlist, advertisers watchlist, country, schedule | `GET /hunter/sources/{id}`, `PATCH /hunter/sources/{id}` |
| KPIs | new items 24 h, auto-attributed, new-campaign candidates, errors | `GET /stats/overview?window=24h` |
| Capture policy | sandbox, no_form_submit, user_agent, egress country, max_redirects, timeout, artifacts to keep | `GET/PATCH /hunter/policy` |
| Data rules | raw material location (local / WCSS), cloud LLM features only | `GET /hunter/policy` (read-only) |
| API keys | per provider: set / missing (never the value) | `GET /hunter/sources?fields=credentials_status` |
| Recent runs | source, started, duration, new, errors, error detail (e.g. urlscan 429 backoff) | `GET /hunter/runs?limit=`, SSE `hunter.capture` |

### E1 · Wtyczka (browser extension)
An overlay strip pinned to a matching sponsored post, with "Dlaczego?", "Zgłoś" and "Ukryj", and a toolbar popup. Badge states: no match (nothing shown), possible match (amber, "sprawdzamy"), known campaign (strip).

| Part | Data | Source |
|---|---|---|
| Match a post | request: ad fingerprint only (advertiser name, text, link domain, creative pHash); response: state, public campaign name, seen_count, since, 3 plain reasons | `POST /public/extension/match` |
| Zgłoś | fingerprint + optional comment → creates an incident with `source.type = extension` | `POST /public/report` |
| Popup | matches on page (client-side), user's report count and confirmed count | `GET /public/reports/mine` (anonymous install id) |

### E2 · Sprawdź reklamę (`/sprawdz`, public)

| Part | Data | Source |
|---|---|---|
| Check | url or screenshot → verdict `scam | unknown`, public campaign name, seen_count, since, reasons[] (coarse, nothing that helps evasion), advice[] | `POST /public/check` |
| Report | url/screenshot + optional note | `POST /public/report` |
| Schematy tygodnia | 3 public cards: scheme name, promise, how to spot it | `GET /public/schemes?window=7d` |

---

## 5. Explainability components

| Component | Answers | Used on | Data contract |
|---|---|---|---|
| **X1 Chip dowodu** `[TYP][wartość][siła][waga][rzadkość]` | "What links them, and how rare is it?" | S02, S03, S04, S05, S06, S07, X2 | `EvidenceItem` (§7). Hover shows a tooltip (field, idf = log(N/df), strength meaning, M1/SHAP contribution). Click opens the evidence drawer, fed by `GET /evidence/values/{type}/{value}`. |
| **X2 Dlaczego połączone / dlaczego NIE** | "Why this campaign, and why not the runner-up?" | S02 verdict (inline), S04 matches, S06 inspector, S03 | `GET /links/{a}/{b}`, which returns `LinkExplanation`: p, τ, decision, independent layers, contributions per layer, evidence, missing (not counted), conflicts, zeroed (too common), counterfactuals |
| **X3 Diff szablonów** (Tekst · DOM · Zasoby · Zrzut) | "Is this the same template with the name swapped?" | S05 variants, S04, S03 | `GET /links/{a}/{b}?view=diff`, which returns `TemplateDiff`: text tokens with slots ({PER}, {DATA}), DOM tag-path tree match, asset hash list, pHash distance and regions |
| **X4 Pewność i pokrycie** | "How much of the picture do we actually have?" | every verdict, member rows, triage | `incident.quality {available, missing, errors}` + `coverage` + `layers[{layer, state, reason}]`. Rule shown in the UI: **a missing value is not evidence of difference**. |
| **X5 Decyzja konformalna** | "Is it a known campaign, or something new?" | S02 verdict, S03, S11 | `GET /incidents/{id}/decision`, which returns `Decision`: α, τ, scores with p-values and in_set, set, decision assign / new / ambiguous, margin, calibration {target, achieved, n_cal} |

---

## 6. Component inventory (frontend)

Every component appears in `rp.css` (class) and on the `DesignSystem` artboard. The base column is the suggested implementation.

| Component | Class / artboard | Base | Props (main) | Screens |
|---|---|---|---|---|
| AppShell | `.app .side .main .page` | layout | `nav active`, children | all app screens |
| SideNav | `Nav.dc.html`, `.nav .nav-i .nav-b` | custom | `active`, badges (triage open, campaigns, oracle, act, live agent) | all |
| Topbar | `.top` | custom | trail, live state, demo flag, alerts count | all |
| Omnibox | `.omni` + results | shadcn Command | query → `GET /search` grouped results | all |
| Trail | `.trail` | custom | `[{label, href}]` | all |
| Panel | `.panel .ph .pb` (+ `.hot .warn .info`) | shadcn Card | title, actions, api annotation | all |
| KpiTile | `.kpi .num .delta` | custom | label, value, delta, tone | S01, S05, S08, S11 |
| Button | `.btn` (`-p -d -a -gh -sm -lg -i`) | shadcn Button | variant, size, icon | all |
| Pill / StatusBadge | `.pill` (`g am rd cy`) + `.dot` | shadcn Badge | tone, live | all |
| LevelBadge | `.lvl.l0…l3` | custom | level, label | S04, S05, S06 |
| IdTag | `.id` | custom | id → href | all |
| **EvidenceChip** | `.ev .t-*` (`.conf .miss .zero .big`) | custom + Tooltip | `EvidenceItem`, size | see X1 |
| StrengthBars | `.sb.l/.m/.h` | custom | strength | chips, legends |
| EvidenceDrawer | X1 drawer | shadcn Sheet | type, value → `GET /evidence/values/…` | global |
| FilterChip | `.fchip .t-*` (`.on .off`) | Toggle | type, count, on | S03, S06 |
| Segmented | `.seg` | ToggleGroup | options, value | many |
| Tabs | `.tabs .tab` | shadcn Tabs | items with counts | S04, S05, S10 |
| DataTable | `.tbl` (+ `.sel`, `.scroll-x`) | TanStack Table + shadcn Table | columns, rows, selection | S01, S03, S04, S05, S08, S10, S12 |
| CoverageBar | `.cov` (`.miss .part .err`) | custom | layers[{layer, state}] | X4, members, verdict |
| ScoreRing | `.ring` (`.am .cy`) | custom | p, tone | S02, X5 |
| ContributionBar | `.bar` with `.t-*` segments | custom | contributions[] | X2, S06 |
| PipelineSteps | `.steps .stp` (`done run warn skip`) | custom | steps[] (SSE-driven) | S02, F1 |
| VerdictCard | `.verdict` (`.new .unsure`) | custom | `Decision` | S02, E2 (public variant) |
| WhyPanel | X2 | custom | `LinkExplanation` | S02, S04, S06 |
| TemplateDiff | `.diff` (`.same .ins .del .slot`) | custom | `TemplateDiff` | X3, S05 |
| ConformalDisplay | X5 | custom (visx) | `Decision` | S02, S03 |
| LiveFeed | `.feed .fi .when` | custom | SSE events | S01, S12 |
| CampaignDNA | `.dna` barcode + rows | custom | `CampaignDNA` | S05 |
| TimelineChart | SVG in S05 | visx | `Timeline` | S05, S08 |
| GraphView | S06 | Sigma.js + graphology | `GraphPayload`, filters | S06 |
| InvestigationCanvas | S07 | React Flow | nodes/edges from SSE | S07 |
| CaseFile | S07 | custom (markdown stream) | steps, conclusions | S07 |
| InfraMap | S01 | deck.gl + MapLibre | ASN points | S01 |
| Heatmap | S09 | visx | persons × weeks | S09 |
| PersonSilhouette | `.sil` | SVG | name | S09, E2 |
| CodeBlock | `.code` (`.ck .cs .cc .cg`) | Shiki (optional) | text, lang | S10, X* |
| KeyValue | `.kv` | `<dl>` | pairs | S04, S10, S12 |
| Placeholder media | `.ph-img` | img with fallback | src from MinIO presigned URL | S02, S04, S09 |
| GlyphRain | `.rain` | CSS only | columns[] | S01, Main, verdict |
| ApiAnnotation (design only) | `.api .dnote` | — | — | canvas only |
| Form controls | `.inp .lbl .fld .tgl .kbd` | shadcn Input / Label / Switch / Kbd | — | S02, S10, S12, E2 |
| ConfirmDialog | S10 confirm step | shadcn Dialog | summary, checkbox | S10 (send), S12 (run) |

---

## 7. API contract (input for the OpenAPI file)

Base `/api/v1`, JSON, cursor pagination (`?cursor=&limit=`), ISO-8601 timestamps.

### 7.1 Endpoints

| Method | Path | Returns | Screens |
|---|---|---|---|
| GET | `/stats/overview?window=24h\|night` | `StatsOverview` | S01 |
| GET | `/events` (SSE) | `Event` stream | all |
| GET | `/alerts?status=open` | `Alert[]` | S01 |
| GET | `/search?q=` | grouped hits (incident, campaign, operator, domain, tracking id, person) | omnibox |
| POST | `/analyze` (multipart: url \| files, options) | `{job_id, incident_id?}` | S02 |
| GET | `/jobs?limit=` · `/jobs/{id}` | `Job[]` · `Job` | S02 |
| GET | `/jobs/{id}/stream` (SSE) | `job.step` events | S02 |
| GET | `/incidents?campaign_id=&source=&q=&from=&to=` | `IncidentSummary[]` | lists |
| GET | `/incidents/{id}` | `Incident` (PLAN §4) + `decision` summary + `coverage` | S04 |
| GET | `/incidents/{id}/artifacts` | `Artifact[]` (presigned URLs) | S02, S04 |
| GET | `/incidents/{id}/features` | features grouped by layer with df/N | S04 |
| GET | `/incidents/{id}/matches?k=&scope=campaigns\|incidents` | `Match[]` | S04 |
| GET | `/incidents/{id}/decision` | `Decision` | S02, X5 |
| GET | `/incidents/{id}/history` | `HistoryEvent[]` | S04 |
| GET | `/links/{a}/{b}?view=explain\|diff&adjudicate=0\|1&compact=0\|1` (`b` may be an incident or a campaign id) | `LinkExplanation` / `TemplateDiff` | X2, X3, S03, S06 |
| GET | `/evidence/values/{type}/{value}` | `EvidenceValue` (df, N, idf, series, incidents, campaigns) | evidence drawer |
| GET | `/campaigns?sort=-heat&status=` | `CampaignSummary[]` | S01, lists |
| GET | `/campaigns/{id}` | `Campaign` | S05 |
| GET | `/campaigns/{id}/dna` · `/timeline?range=` · `/members?level=&sort=` · `/indicators?type=` · `/variants` · `/phylogeny` · `/summary` | `CampaignDNA` · `Timeline` · `Member[]` · `Indicators` · `Variant[]` · `Phylogeny` · `Summary` | S05 |
| POST | `/campaigns {seed_incident, name, status:'candidate'}` | `Campaign` (new-campaign candidate, e.g. KMP-040) | S02, S03 (F1 branch B) |
| POST | `/campaigns/{id}/merge` · `/campaigns/{id}/split` | `Campaign` | S05, S03 |
| GET | `/operators/{id}` | `Operator` | S05, S06 |
| GET | `/graph?scope=&layers=&level=&min_weight=&from=&to=&group=` | `GraphPayload` | S06, S01 |
| GET · POST | `/investigations?status=` · `/investigations` | `Investigation[]` · `{id}` | S07, S01 |
| GET | `/investigations/{id}` | `Investigation` | S07 |
| GET | `/investigations/{id}/stream` (SSE) | `agent.step`, `graph.node_added`, `graph.edge_added`, `casefile.delta` | S07 |
| POST | `/investigations/{id}/steer` · `/stop` · `/promote` | ack · ack · `{campaign_id, added}` | S07 |
| GET | `/oracle/metrics` · `/oracle/dna?campaign=` · `/oracle/predictions?status=` | `OracleMetrics` · `DomainDNA` · `OraclePrediction[]` | S08 |
| PATCH | `/oracle/dna/{campaign_id}` | `DomainDNA` (threshold) | S08 |
| GET | `/oracle/stream` (SSE) | `oracle.match` | S08 |
| GET | `/persons?window=7d\|8w&bucket=week&format=brief` · `/persons/{id}` · `/brands?window=7d` | `PersonSummary[]` (or markdown brief) · `Person` · `Brand[]` | S09 |
| GET · POST | `/act/packages` · `/act/packages {campaign_id, kind}` | `ActPackage[]` · `ActPackage` (draft) | S10 |
| GET | `/act/packages/{id}` · `/act/packages/{id}/download?format=pdf\|json\|csv\|stix\|misp` | `ActPackage` · file | S10 |
| POST | `/act/packages/{id}/submit {confirm: true}` | `ActPackage` (sent) | S10 |
| GET · POST | `/act/rules?campaign=` · `/act/rules/test {kind, body}` | `Rule[]` · `RuleTest` | S10 |
| GET | `/triage?status=&type=&sort=priority\|age\|coverage` · `/triage/{id}` | `{items: TriageItem[], facets}` · `TriageItem` | S03, X4 |
| POST | `/triage {source, subject_id \| prediction_id}` | `TriageItem` (manual "Do triage" from S01/S08) | S01, S08 |
| POST | `/triage/{id}/decision` | `TriageItem` (closed) + `feedback_id` | S03 |
| POST · GET | `/feedback` · `/feedback/stats?window=` | ack · `FeedbackStats` | everywhere · S03 |
| GET | `/lab/metrics?view=summary\|baselines\|loco\|conformal\|models\|layer_compare` · `/lab/ablation` | `LabMetrics` (shape per view) · `{layer, delta_f1}[]` | S11, S06, X5 |
| POST · GET | `/lab/stress` · `/lab/runs/{id}` | `{run_id}` · `StressRun` | S11 |
| GET · PATCH | `/hunter/sources` · `/hunter/sources/{id}` | `HunterSource[]` · `HunterSource` | S12 |
| POST | `/hunter/sources/{id}/run` | `{run_id}` | S12 |
| GET | `/hunter/runs?limit=` · `/hunter/policy` · `/hunter/sources?fields=credentials_status` | `HunterRun[]` · `CapturePolicy` · `{source_id, status: 'set'\|'missing'}[]` | S12 |
| POST | `/public/check` · `/public/report` · `/public/extension/match` | `CheckResult` · ack · `ExtensionMatch` | E1, E2 |
| GET | `/public/schemes?window=7d` · `/public/reports/mine` | `PublicScheme[]` · counts | E2, E1 |

### 7.2 SSE event catalogue (`Event = {type, at, data}`)

| type | data | Consumers |
|---|---|---|
| `incident.created` | `{incident_id, source}` | S01 feed |
| `incident.attributed` | `{incident_id, decision, campaign_id?, p}` | S01, S05 members (live row), S04 |
| `campaign.updated` | `{campaign_id, counts, heat}` | S01, S05 |
| `alert.created` | `Alert` | S01, nav badge |
| `triage.created` | `{item_id, type}` | S03, nav badge |
| `job.step` | `{job_id, step}` | S02 |
| `agent.step` | `{investigation_id, step}` | S07, S01 card |
| `graph.node_added` / `graph.edge_added` | `{investigation_id, node}` / `{…, edge}` | S07 |
| `casefile.delta` | `{investigation_id, step_n, text_delta}` | S07 |
| `oracle.match` | `OraclePrediction` | S08, S01 |
| `hunter.capture` | `{source_id, incident_id}` | S01, S12 |
| `extension.report` | `{incident_id}` | S01, S03 |
| `act.submitted` | `{package_id, kind, campaign_id}` | S01, S10 |
| `triage.updated` | `{item_id, status}` (decided in another window; there are no user accounts) | S03 |
| `model.updated` | `{model: 'M1', version, metrics_delta}` after feedback retraining | S03 toast, S11 |

Conventions:
- **Demo replay:** `?replay=demo` on any SSE endpoint swaps the live source for a recorded event stream (F6 fallback).
- **Concurrency:** `POST /triage/{id}/decision` takes `If-Match: <item version>`. A stale decision returns 409 and the UI refreshes the item.
- **Public ids:** the public endpoints return `campaign_public_id` / `campaign_public_name` and never internal `KMP-…` ids or raw indicators.
- **Extra filters:** `GET /campaigns/{id}/members?coverage_lt=0.6` (weak members to review before Act) and `GET /campaigns?sort=-heat`.

### 7.3 Resource shapes (aligned with PLAN §4)

```ts
type Layer = 'tracking'|'kit'|'infra'|'content'|'persons'|'visual'|'ad'|'media';
type Level = 'L0'|'L1'|'L2'|'L3';

interface EvidenceItem {           // one chip
  type: Layer; field: string;        // e.g. 'tracking.capi_gateways'
  value: string; display: string;    // raw value, short label
  strength: 'H'|'M'|'L';
  weight: number;                    // strength × rarity (or M1 contribution)
  shap?: number;                     // learned contribution (M1)
  df: number; N: number; idf: number;
  state: 'match'|'conflict'|'missing'|'zero';
  sides?: { a?: string; b?: string };// values on each side (conflicts)
}

interface LayerCoverage { layer: Layer; state: 'available'|'partial'|'missing'|'error'; reason?: string }

interface Decision {               // GET /incidents/{id}/decision (also rides on SSE incident.attributed)
  incident_id: string;
  // assign: one campaign in the set and p ≥ tau_auto with margin ≥ delta
  // confirm: one campaign in the set but below tau_auto → analyst confirms in triage
  // ambiguous: 2+ campaigns in the set → triage;  new: empty set → new-campaign candidate
  // insufficient: coverage too low to decide → re-capture / run agent
  decision: 'assign'|'confirm'|'ambiguous'|'new'|'insufficient';
  campaign_id?: string; candidate_campaign_id?: string; p: number;
  alpha: number;                     // conformal level, e.g. 0.05
  tau: number;                       // conformal threshold τ(α), e.g. 0.55: "is it a known campaign?"
  tau_auto: number; delta: number;   // e.g. 0.80 / 0.15: "may we assign without a human?"
  set: string[];
  scores: { campaign_id: string; score: number; p_value: number; in_set: boolean }[];
  margin: number; runner_up?: { campaign_id: string; score: number; same_operator: boolean };
  coverage: number; layers: LayerCoverage[];
  evidence: EvidenceItem[];
  why_not?: { campaign_id: string; bullets: string[] }[];
  adjudicator?: { model: string; verdict: string; confidence: number; rationale: string[] };
  calibration?: { target: number; achieved: number; n_cal: number };
}

interface LinkExplanation {        // GET /links/{a}/{b}
  a: string; b: string; p: number; tau: number; delta: number;
  decision: 'linked'|'not_linked'|'triage';
  shared_level: Level|null;          // e.g. 'L3' = same operator family, different campaign
  operator_id?: string;
  layers_independent: number; layers_required: number;   // rule: ≥ 2 independent layers
  coverage: number; summary: string; // one-sentence verdict
  contributions: { layer: Layer; value: number }[];
  evidence: EvidenceItem[]; missing: EvidenceItem[]; conflicts: EvidenceItem[]; zeroed: EvidenceItem[];
  counterfactuals: { change: string; p_new: number; decision_new: string }[];
  conformal?: { alpha: number; in_set: boolean };
  adjudicator?: Decision['adjudicator'];
}

interface EvidenceValue {          // GET /evidence/values/{type}/{value} (evidence drawer)
  type: Layer; value: string; df: number; N: number; idf: number;
  first_seen: string; last_seen: string; weekly: number[];
  campaigns: { id: string; n: number }[]; operator_hint?: string;
  incidents: { items: { id: string; captured_at: string; campaign_id?: string }[]; next?: string };
}

interface TemplateDiff {           // GET /links/{a}/{b}?view=diff
  text: { a_tokens: Tok[]; b_tokens: Tok[] };   // Tok = {t, kind:'same'|'ins'|'del'|'slot', slot?: 'PER'|'DATA'|'MIASTO'}
  dom: { a: TagNode; b: TagNode; matched: string[]; differing: string[] };
  assets: { url: string; sha256: string; same: boolean; third_party: boolean }[];
  visual: { phash_distance: number; regions: {x:number;y:number;w:number;h:number}[] };
  metrics: { minhash: number; dom_shingles: number; phash_delta: number; shared_assets: [number, number] };
}

interface CampaignSummary { id: string; name: string; narrative: string; status: 'active'|'fading'|'candidate'|'closed';
  operator_id?: string; heat: { series_48h: number[]; trend_pct: number }; new_domains_24h: number; persons: string[] }
interface Campaign extends CampaignSummary { description: string; level: 'L2';
  counts: { incidents: number; incidents_24h: number; domains: number; certs_tonight: number; advertisers: number;
            advertisers_removed: number; persons: number; certpl_listed: number };
  first_seen: string; last_seen: string; brands: string[] }
interface CampaignDNA { campaign_id: string; signature: { layer: Layer; field: string; value: string;
  members_with: number; members_total: number; strength: 'H'|'M'|'L' }[] }
interface Timeline { days: { date: string; incidents: number }[];
  events: { at: string; kind: 'domain_registered'|'cert_batch'|'oracle_predicted'|'act_sent'; ref: string }[] }
interface Member { incident_id: string; captured_at: string; source: string; domain: string; person?: string;
  level: Level; parent_id?: string; score: number; top_evidence: EvidenceItem[]; layers: LayerCoverage[] }
interface Indicators { domains: { fqdn: string; cert_issued_at?: string; oracle_predicted_at?: string;
  on_certpl: boolean; online: boolean|'502'; ads_seen: number }[]; tracking: EvidenceItem[]; kit: EvidenceItem[];
  persons: { id: string; name: string; count: number }[]; advertisers: { name: string; page_id: string; removed: boolean }[] }
interface Operator { id: string; codename: string; campaigns: { id: string; name: string; incidents: number }[];
  shared: EvidenceItem[]; narratives: string[] }

interface GraphPayload { nodes: { id: string; kind: 'incident'|'domain'|'campaign'|'operator'; campaign_id?: string;
  label: string; size: number; first_seen: string }[];
  edges: { a: string; b: string; type: Layer; weight: number; level: Level }[];
  hulls: { id: string; kind: 'campaign'|'operator'; members: string[]; label: string }[] }

interface Job { id: string; status: 'queued'|'running'|'done'|'error'; input: { kind: string; name: string };
  incident_id?: string; total_ms?: number;
  steps: { key: string; label: string; status: 'pending'|'run'|'done'|'warn'|'skip'|'error';
           duration_ms?: number; detail?: string; warnings?: string[] }[] }

interface Investigation { id: string; seed: string; status: 'running'|'paused'|'done'|'stopped';
  budget: { steps: number; used: number }; model: string; tools: string[]; started_at: string;
  nodes: { id: string; kind: 'domain'|'cert'|'ip'|'query_result'|'ad'|'list_status'|'oracle_flag'; label: string; meta: Record<string,string>; is_new?: boolean }[];
  edges: { a: string; b: string; label?: string }[];
  steps: { n: number; tool: string; query: string; result_summary: string; why: string; produced: string[]; at: string }[];
  conclusions: { text: string; evidence_refs: string[] }[] }

interface OraclePrediction { domain: string; issued_at: string; issuer: string; dna_score: number; campaign_id?: string;
  status: 'predicted'|'confirmed'|'below_threshold'|'dismissed'; first_ad_at?: string; lead_time_h?: number }
interface DomainDNA { campaign_id: string; grammar: string; examples: string[]; tld_dist: Record<string, number>;
  length_hist: Record<string, number>; registrars: string[]; issuance_hours: number[]; asns: string[];
  model: { name: string; auc: number }; threshold: number }
interface OracleMetrics { flagged_24h: number; confirmed: number; precision_at_20: number; median_lead_h: number;
  ct_rate_per_h: number; false_alarms_24h: number }

interface Person { id: string; name: string; role: string; weekly: { week: string; count: number }[];
  campaigns: { id: string; count: number }[]; face_match?: number; deepfake_score?: number; voice_score?: number;
  narratives: string[]; sample_incidents: string[] }

interface ActPackage { id: string; kind: 'dsa'|'certpl'|'stix'|'misp'|'rules'; campaign_id: string;
  status: 'draft'|'ready'|'sent'|'exported'; contents: { ads: number; advertisers: number; domains: number; evidence_items: number };
  recipient?: string; formats: string[]; created_at: string; sent_at?: string; outcome?: { removed: number; total: number } }
interface RuleTest { hits: number; tp: number; needs_review: number; benign_hits: number; benign_total: number; precision: number }

interface TriageItem { id: string; type: 'uncertain'|'new_campaign'|'oracle'|'hunter'|'extension'|'merge';
  subject_id: string; suggestion: string; score: number; priority: number; created_at: string;
  candidates: { campaign_id: string; score: number; for: EvidenceItem[]; against: EvidenceItem[]; missing: EvidenceItem[] }[];
  adjudicator?: Decision['adjudicator'] }
interface TriageDecision { action: 'accept'|'reassign'|'reject'|'new_campaign'|'skip'; campaign_id?: string; note?: string }

interface HunterSource { id: string; kind: 'meta_adlibrary'|'google_ads_transparency'|'certpl'|'urlscan'|'ct'|'extension'|'manual';
  schedule: string; status: 'ok'|'degraded'|'error'|'disabled'; last_run_at?: string; new_24h: number; errors_24h: number;
  enabled: boolean; config: { phrases?: string[]; persons?: string[]; advertisers?: string[]; country?: string } }

interface CheckResult { verdict: 'scam'|'unknown';
  public_campaign?: { name: string; seen_count: number; since: string; reasons: string[] }; advice: string[] }
```

`Incident` itself is the PLAN §4 object unchanged. The UI additionally reads `incident.quality` (X4) and a `decision` summary `{campaign_id, p, decision}` embedded in `GET /incidents/{id}`.

---

## 8. Flows (canvas page "Przepływy")

| Flow | Path | Endpoints / events, in order |
|---|---|---|
| **F1 Nowy materiał → werdykt** | S02 drop → pipeline → verdict. Branches: A joins KMP-017 → S04/S05, X2; B new-campaign candidate (conformal set ∅) → create KMP-040 or triage; C uncertain → S03 | `POST /analyze` → SSE `jobs/{id}/stream` → `GET /incidents/{id}/decision` → (`GET /links/{a}/{b}`) → (`POST /feedback`) |
| **F2 Kampania → Act → DSA** | S01 hot campaign → S05 (DNA, timeline, members, weak members) → optional merge/split → S10 DSA builder → **confirm** → status tracking → CERT PL + STIX. Side branch: rule → test on dataset → publish to Hunter | `GET /campaigns/{id}` (+ dna/timeline/members) → `POST /act/packages` → `GET /act/packages/{id}` → `POST /act/packages/{id}/submit` → SSE `act.submitted` |
| **F3 Śledztwo agenta** | S05 "Śledź z agentem" or omnibox `śledź velmoria.click` → config (budget 20, tools, offline) → live pivots → steer → review → promote 14 domains → Act CERT PL | `POST /investigations` → SSE `agent.step`, `graph.node_added`, `graph.edge_added`, `casefile.delta` → `POST /steer` → `POST /promote` → `POST /act/packages {kind:'certpl'}` |
| **F4 Alert → triage → feedback** | Hunter capture or Oracle CT match → alert in S01 → S03 → candidates + adjudicator → accept / reject / reassign / new → M1 retrain (~8 s) → S11 metrics, Oracle threshold | SSE `alert.created` / `triage.created` → `GET /triage/{id}` → `POST /triage/{id}/decision` → SSE `campaign.updated` → `GET /lab/metrics` |
| **F5 Obywatel** | Extension: fingerprint post → match → overlay (E1) → "Dlaczego?" → "Zgłoś" → incident `source=extension` → S03. Public page: paste URL/screenshot → verdict → report | `POST /public/extension/match` → `POST /public/report` → SSE `extension.report`; `POST /public/check` |
| **F6 Demo dla jury (3 min)** | 0:00 S01 hook → 0:15 S02 judge's URL → 0:35 verdict KMP-017 + chips → 0:55 X2 why / why not → 1:15 S06 content vs infra → 1:35 S07 agent from velmoria.click, 14 domains → 2:05 3 certs tonight, not on CERT PL, Oracle flagged 2 (S08) → 2:30 S10 DSA package for the whole campaign → 2:50 S11 metrics + E1 extension | as F1 + F3 + F2. Every step has a cached fallback: offline mode, seeded dataset, recorded video |

---

## 9. Assumptions and open points

- The 8 evidence layers in the UI are tracking, kit, infra, content, persons, visual, ad and media. They map onto the PLAN §5 feature catalogue (kit features split out of tracking; visual and ad split as in §5).
- **Two thresholds, shown the same way on every screen** (S02, S03, S04, X2, X4, X5):
  - The conformal **τ(α)** (example 0.55 at α = 5%) answers "is this a known campaign?". The conformal set is every campaign scoring at or above it.
  - **τ_auto / δ** (example 0.80 / 0.15) answers "may we assign without a human?".

  That gives five decision states: assign, confirm, ambiguous, new and insufficient (see `Decision`). Scores are calibrated M1 probabilities, and the real τ, τ_auto and δ come from `eval/`.
- The public API (`/public/*`) returns only coarse reasons, never indicators that would help scammers evade detection. Rate limits and an anonymous install id for the extension.
- The DSA package text and recipients are placeholders. The legal wording needs a check before any real sending. Sending is always a two-step, explicitly confirmed action.
- List screens (incidents, campaigns, investigations, packages) are not drawn separately (see §3).
