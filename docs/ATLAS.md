# TROP — Atlas of scam-ad campaign patterns

> Contains identifiers derived from organizer data — do not publish outside the private repository.

Source: hand labels `experiments/labels.yaml` (sample_v1, p1–p15) and `experiments/labels_dane.yaml` (DANE, d1–d61),
verified against HARs, saved HTML and screenshots; numbers from `experiments/RESULTS.md`; registration and NS facts
from the cached enrichment (`infra_enrich.json`, RDAP/DNS). 25 incidents, 14 campaigns plus one unlabelled. Patterns
below are observations on this sample, not statistics: a "rule idea" is a hypothesis to test on NASK's larger pool.

Vocabulary: **campaign** = same operator and same narrative/offer (persona swaps are *variants*); **operator** = same
account (kit tenant, pixel, CAPI gateway, Cloudflare account); **operation** = campaigns sharing one funnel;
**platform** = shared commercial tooling, not evidence of the same operator.

## 1. Kit A — a multi-tenant landing/cloaking SaaS

- **What.** One commercial landing-page service hosts many unrelated scammers. Fingerprints: `/aio-static/sdk/main.js`
  (869,599 B) and `main.css`, `POST /api/v1/trigger/field/{visit_uuidv7}/`, `POST /api/v1/agent/persist-session-record/`
  (an **rrweb session recorder**, Kafka backend "kafka_catch"), assets under `/_cdn/production/landing-cdn/{TENANT}/{LANDER}/`,
  and entry URLs with `utm_id` (rand20), `utm_medium`/`utm_campaign`/`utm_content` (rand10) and `utm_visit` (UUIDv7).
- **Tenants = operator accounts.** The first UUID in `landing-cdn/` is the tenant; the second is the lander. POST bodies
  leak the **lander UUID and the landing-type UUID** even when no HTML was saved.

  | Tenant | Campaigns | Incidents |
  |---|---|---|
  | `f141c307-…` | A (fake Gazeta investment) | p1, p2, p3, p4, p7, p15, d1, d2 |
  | `0660ffe3-…` | D (diabetes), E (RelieFlex) | p6, p12 |
  | `007e0023-…` | B2 (FinNews "Trudna odpowiedź") | p11 |
  | no tenant UUID extracted; landing type `25024431` (A's is `cbb230f4-…`) | K | d48 |

- **Detected by.** `kit` layer: tenant, lander id, landing-type id, endpoints; `tracking`: utm grammar; HAR bodies.
- **Use.** Endpoints are **platform** evidence (weight 1): p11 must not join A even though both run kit A. The tenant UUID
  is operator-level (strength 6) and a tenant **conflict scores −5**. Rule ideas: (a) group every incident by tenant to list
  all of one account's campaigns; (b) report the tenant to the SaaS vendor as an abuse pivot — one tenant id = every
  landing of one scammer; (c) hunt the SDK path with urlscan `hash:` / path pivots to discover tenants not yet seen.

## 2. Campaign A — persona-swap pre-landers ("Zyskarnia" / "Świtowin")

- **What.** Fake Gazeta.pl articles using a shocking-news story to push investment platforms "Zyskarnia" and "Świtowin".
  The same lander is reskinned per victim persona:
  - **A1** `«Wiem, kto strzelał»: zamach na Rafała Brzoskę, założyciela InPostu` — p1, p2 (byte-identical copy of p1),
    p7, p15, d1, d2. Fake byline/commenters "Michał Szczepanik", "Marek Tejchman". One lander UUID `a7b9f833-…`.
  - **A2** `PILNE: Brutalna napaść na {PER} tuż po publikacji tajnego śledztwa w sprawie polskich banków!` — p3
    (Krzysztof Stanowski), p4 (Tomasz Sekielski), each with its own lander UUID; p4 also names "Steryga".
- **Detected by.** Headline template with names masked (`{PER}`, strength 4); text MinHash; shared platform names; same
  `style.css` (57,500 B) and `favicon.ico` (15,406 B); and — the only link between A1 and A2 — the **FB pixel
  `4567646436826205` plus the CAPI gateway** `xd-f1cf3d4f…on.aws`. p15/d1/d2 carry a second pixel `2012165449475163` on
  the same lander and advertiser "Formal Favorable" (p15, d1): a second ad account feeding one campaign.
- **Ads.** A1 = one video thumbnail (motorcyclist shooting a Range Rover, Morawiecki/Brzoska inset, "NA ŻYWO | WTOREK,
  20:10 – WARSZAWA", caption "Wydarzenie, które wstrząsnęło całą Polską") posted by rotating throwaway advertisers
  (UniverseFlux Studio, Letty Zaswer, Formal Favorable).
- **Use.** Rule ideas: (a) cluster by the masked headline template, not by the person; (b) alert when a known template
  appears with a *new* person name — a persona swap, same operator; (c) an advertiser-name change with the same caption
  and thumbnail pHash is throwaway-page rotation (the Hunter run found one clickbait template on 208 ads from 160 pages).

## 3. Registration batches and the Cloudflare NS pair

- **What.** Operators buy domains in bursts and put them behind one Cloudflare account, which shows as a **fixed NS pair**.
  Campaign A domains (all Dynadot, random-word `.click`/`.live`):

  | Domain (incident) | Created (UTC) | NS |
  |---|---|---|
  | falmurek.live (p3) | 2026-10-05 18:20:32 | cartman / fish |
  | grentavo.click (p4) | 2026-10-05 18:20:38 (6 s later) | cartman / fish |
  | wernulio.live (p7) | 2026-10-07 18:22:29 | cartman / fish |
  | dorquesio.click (p1, p2) | 2026-10-07 18:22:47 (18 s later) | cartman / fish |
  | lundevra.live (p15) | 2026-10-07 18:27:41 | dyna-ns.net (not behind Cloudflare at capture) |
  | civicdaybook.live (d1) | 2026-10-08 18:18:20 | dyna-ns.net |
  | acrosscommunities.live (d2) | 2026-10-08 18:20:08 (108 s later) | cartman / fish |

  All seven registered between 18:18 and 18:28 UTC on three evenings. The same pattern repeats for the C network
  (smartcoved.pro, healthlinkq.pro: registrar NICENIC, NS braelyn/kurt) and for D+E (resader.com, konbjk.com: NS
  leland/princess, NameCheap).
- **Detected by.** `infra` enrichment: RDAP created + registrar, DNS NS, crt.sh issuance time (first cert about 30 min
  after registration for p1/p7). Strengths: NS pair 4, registrar batch 3.
- **Use.** Never decisive alone (Cloudflare anycast IPs `188.114.96/97.x` are noise: p4↔p10, p5↔p15 share only those),
  but it **confirms an operator link across full infrastructure rotation** and, through the conjunction rule, recovers
  variants whose landing stack was rebuilt (d3 ↔ p5). Rule ideas: (a) flag domains registered by one registrar within
  minutes with the same grammar (random word + `.click`/`.live`, or CSIRT KNF-style names); (b) when a new domain lands
  on a known NS pair, pre-assign it to that operator before any capture; (c) feed the NS pair and registration window to
  the Oracle's domain-DNA scorer.

## 4. Operation level — funnel A → C → K

- **What.** DANE showed three "campaigns" are one investment funnel (operation `OPN_INV`):
  - **A** (Brzoska pre-landers, tenant `f141c307`);
  - d2 is a **click chain**: A's pre-lander `acrosscommunities.live` → `healthlinkq.pro`, a lander with exactly p5's URL
    grammar `/L{8d}fl-{d}{a}{d}-fkf{d}{A}/?clickid&key&pixel_fb` and tracker `crimsonbase.pro`;
  - **C** (Olejnik vs NBP) is served from that same lander network: p5 on `smartcoved.pro`, d3 on `healthlinkq.pro`;
  - **K** ("37 minut po emisji wyprowadzono go w kajdankach…") uses the kit-A SDK and signs with the same fake author as C
    ("Natalia Pacholczyk"), and mentions Morawiecki and Brzoska like A.
- **Also.** d3's ad creative copies A1's template (traffic scene, face insets, "NA ŻYWO", lower third) with Olejnik and
  Glapiński insets, advertiser "EasyJoy".
- **Detected by.** Chain domains and tracker domains (operator-level, strength 4), URL path shape (3), fake byline (2),
  creative template similarity. Rule: **a chain domain reached by click-through is operator evidence, not campaign
  evidence** — treating it as campaign evidence made the only wrong link on DANE (C variant → A).
- **Use.** The product reports campaign → operator → operation, and `trop batch` outputs both granularities because the
  organizers' label definition is unknown. Rule ideas: crawl every HAR in a chain; take-down priority = the lander/tracker
  domains (`healthlinkq.pro`, `crimsonbase.pro`) that serve several pre-landers; K ↔ A/C is weak (byline + platform
  only), so show it as "same operation, low confidence".

## 5. K — one story on two ad platforms (Facebook vs Google Ads)

- d48 (`novumfy.com`, FB ad by "Sharon Coleman" with a deepfake TVN24 studio brawl, pixel `2351106582387557`) and d61
  (a **Google display ad** "Dziedzictwo gwiazd dla zwykłych ludzi", advertiser Glowpixel, AW-18463917747, leading through
  a 3-page chain pre-lander → "Trwały Działunek" → `glowpixel.org`) share the identical `<title>`, 8 asset hashes and the
  fake author. Rule idea: link ad-platform ids (FB pixel vs Google AW id) through the shared pre-lander, so a
  takedown on Meta triggers a check on Google Ads Transparency for the same landing.

## 6. Decoy (cloaked) creatives

- **What.** The ad shown to reviewers differs from what victims see. p3 and p4: advertiser "Exclusive Silver Group", a
  game-landscape image, display link **AMAZON.COM**, caption "Temat, o którym mówi cała Polska"; p8: an unrelated "PILNE!"
  creative; d61: a Google display ad that is itself a decoy for the funnel; d10's Ad Library modal shows bath mats (Olanly /
  AMAZON.COM) while the live ad is a gambling app. RESULTS counts **4 of the 14 sample creatives** as decoys;
  `ad_truth.yaml` marks p3, p4, p8 (the fourth is **to verify**).
- **Detected by.** VLM field `is_decoy` (12/14 correct), mismatch between ad display link/caption and the landing
  vertical, plus plain-vs-victim capture delta (cloak verdict).
- **Use.** Do not let a decoy creative decide anything: drop ad-layer weight when `is_decoy`, and link through the
  landing instead. A decoy advertiser name repeating across incidents is itself an operator signal.

## 7. Fake commenter rosters and fake bylines

- **What.** Pre-landers embed invented comment sections and authors; the names are reused across pages and sometimes across
  campaigns.
  - A: "Marek Tejchman", "Michał Szczepanik" (p1, p2, p7, p15, d1, d2).
  - **Shared fake author "Natalia Pacholczyk": C (p5) and K (d48, d61)** — the link between campaigns C and K.
  - B: "Andrzej Gibki", "Piotr Wiśniewski" (p8, p11 — joins the two stacks).
  - D: "Ojciec Bonifacy" and monks (p6). Health pages (p9, p10, p13, d14, d36, d47) use generic Polish names (Kowalska,
    Nowak, Wiśniewski), which are weak evidence on their own.
- **Detected by.** `comment_names` feature (strength 2; rarity-weighted, so common names count little).
- **Use.** Rule idea: keep a roster index of invented names; a rare name or a full roster match across domains is a
  content link that survives complete infrastructure rotation. Watch for over-merge: one author shared by two campaigns
  moves them to the same operation, not the same campaign.

## 8. Byte-copied lander builds on two stacks (p8 / p11)

- **Campaign B** "Trudna odpowiedź", the FinNews blog "Baltic Pipe" investment story (Nawrocki vs von der Leyen in p8;
  Sikorski vs Zełenski in p11). p8 is delivered by a Keitaro-like TDS (`/click?key&sid=pl&…`, DigitalOcean
  `142.93.95.250`, lander dir `/landers/u_bp_l_o/`); p11 on kit-A tenant `007e0023`, DigitalOcean `159.65.146.122`.
  Both share byte-identical assets with per-deploy random file names (kc-*.png 57,147 B, kasa-*.png 30,535 B, style.css
  27,689 B), the same 15 Facebook-avatar file names, the fake timestamp "Ekonomia 8:44, 07.10.2026 4 319 164 komentarzy"
  and an Italian privacy-policy boilerplate (template ripped from an Italian campaign). **No shared tracking** (p8 has a
  pixel, p11 none).
- **Detected by.** `asset_hash` rarity (strength 5) with name-randomisation ignored, comment names, page `<title>`.
- **Use.** A pure content link across different delivery infrastructure: hash the *content* of assets, not their names.
  Rule idea: alert on any new site whose asset hashes match a known build.

## 9. The 502 capture and video-only ads

- **502 case.** The p1 capture bundle recorded a real **Cloudflare 502**, so no landing content. Recovery then depends on
  the ad layer: with the VLM-extracted ad fields the 502 variant was linked correctly 0.87 of the time (landing alone
  0.47) with 0 wrong links. Error pages must produce no content negatives (an English 502 had created a spurious language
  conflict).
- **Video-only ad d5.** Ad Library id `1982065065827084`, page "TreeKollo", 3 creatives, 198 s 500×500 AI video, back-pain
  story, no landing page. Unattributable without Gemini video pass / ASR / keyframes; unlabelled and excluded from
  campaign metrics. Rule idea: attribute through page id + creative pHash + transcript phrases; repeated synthetic voice
  (`voice_id`) is the planned video link.

## 10. Phone screenshots and the fake App Store (gambling)

- **d10** `shop-77vault.xyz/{uuid}/`: a fake "App Store – Słodka Bonanza" page, FB pixels `1376242401352160`,
  `1549107073347817`, `2070071404384324`, `adop.team`; six iPhone screenshots + HAR. Overlay: "MŁODA PIELĘGNIARKA Z
  WARSZAWY – ZAMIENIŁA 100 ZŁ NA 4 000 000 ZŁ W APLIKACJI SWEET BONANZA OD CRISTIANO RONALDO" (the name comes from the
  ad text, not from a face match).
- **Why it matters.** Capture formats differ (iPhone `IMG_*.PNG`, screen recordings, capture-tool bundles with
  `manifest.json`); the ingest adapters must treat them as ad/landing evidence. One unexplained d3 ↔ d10 face match
  existed; it caused no link because a face alone weighs 2.5 < τ = 5. Rule idea: fake store pages are detectable by
  store-UI template plus a non-store host.

## 11. Health nutra (Keitaro-style funnels) and the investment event lure

- **Health.** Same grammar across products, found on a Keitaro-like TDS with 8-character slugs and offer-named lander dirs.
  - **Metabo RX** (d14): `ineptsolidoval.top/?pxl=…&acc=hk77_tv6_tvtextdc3_feed15_text156tv_w_pl` (buyer-account naming),
    push-notification funnel, `clickline.org`, 339 MB screen recording.
  - **Uromexil Forte** (d47): `shryxla-mynx.icu/gKcXtVhV`, lander dir `prstt-pl-rmxlfrtm-svsh`, bunny CDN video.
  - **Hearing loss "OtinaxMax"/Cactus Recipe** (p9) and **Kardivix** (p10, fake Czech doctor "MUDr. Štěpán Kovář"):
    both show the FB URL-template bug `?%3Futm_placement=Others`, an 8-char random slug, `vstats.io/init.js`,
    `utm_source=ig&utm_medium=paid` → operator OP3 (medium confidence), but different products = different campaigns.
  - **Diabetes "Ojciec Bonifacy"** (p6) and **RelieFlex "600 kg horse"** (p12): kit A tenant `0660ffe3`, `afrdtech.com`
    kmnrKey, Snap loader → operator OP2, two campaigns. Also nail fungus "Dr. Merritz" (p13, Ad Library `4181234142166922`).
- **Investment event lure (d36).** "Poland Invest Summit 2026 – Gdzie Kapitał Spotyka Przyszłość" on
  `meroporepufulo.life`, pixel `1536860380829193`; its URL leaks `fbpx` and an FB `access_token` like p9 (platform-level
  similarity only).
- **Detected by.** URL-parameter grammar, slug length, offer-in-path, third-party hosts (vstats.io, afrdtech, Snap),
  `ad_name` strings leaking offer/geo/pixel (`FARM/PL/MUDr. Štěpán Kovář/…/Kardivix/…`).
- **Use.** Rule ideas: a leaked `access_token` in a URL is a reportable credential leak and a platform marker; the
  "same operator, different product" cases (p6↔p12, p9↔p10) belong at operator level, not campaign level.

## 12. Unrelated reference campaign

- **I** (p14): English "Divine Script" abundance offer, Brazilian affiliate stack (`utmify.com.br`, utm_campaign in
  Portuguese, Google AW-16725023086, AI-Jesus video). Operator OP_I; unrelated to everything else — a useful negative.

## 13. Summary table

| Campaign | Incidents | Key evidence | Vertical | Impersonated brands / persons |
|---|---|---|---|---|
| A (A1, A2) | p1, p2, p3, p4, p7, p15, d1, d2 | kit tenant `f141c307`, lander `a7b9f833`, pixel `4567646436826205` + CAPI gateway, headline template, Cloudflare NS cartman/fish, Dynadot batch | investment | Gazeta.pl; Brzoska, Morawiecki, Stanowski, Sekielski |
| B (B1, B2) | p8, p11 | byte-identical lander build on Keitaro-like TDS and kit tenant `007e0023`; shared avatars, timestamp | investment | Nawrocki, von der Leyen, Sikorski, Zełenski; "FinNews" |
| C (C1, C2) | p5, d3 | `/L…fl-…-fkf…/?clickid` grammar, tracker `crimsonbase.pro`, NS braelyn/kurt, fake author "Natalia Pacholczyk" | investment | Gazeta.pl, TVN24 "Kropka nad i"; Olejnik, Glapiński |
| D | p6 | kit tenant `0660ffe3`, pixel `1872419533729032`, afrdtech | health (diabetes) | fake priest "Ojciec Bonifacy" |
| E | p12 | kit tenant `0660ffe3`, pixel `1396608265958754`, matomo, bunny video | health (joint pain) | fake vet story |
| F | p9 | `?%3Futm_placement=Others`, pixel `1550629110431763`, vstats.io | health (hearing) | none named |
| G | p10 | same URL bug, pixel `2420768028414250`, CAPI gateway | health (hypertension) | fake doctor "MUDr. Štěpán Kovář" |
| H | p13 | Keitaro lander dir `fungus---dr.-merritz-…`, Ad Library `4181234142166922` | health (nail fungus) | "Dr. Merritz" |
| I | p14 | utmify, Google AW-16725023086, 3 FB pixels | other (manifestation) | AI Jesus |
| K | d48, d61 | identical title, 8 asset hashes, kit-A SDK, author "Natalia Pacholczyk", FB vs Google Ads | investment | TVN24 studio (deepfake), Morawiecki, Brzoska, Tusk |
| L | d36 | pixel `1536860380829193`, leaked `fbpx`/`access_token` | investment event | "Poland Invest Summit 2026" |
| M | d47 | `shryxla-mynx.icu` slug, lander dir `prstt-pl-rmxlfrtm-svsh` | health (prostate) | Domański appears in text (to verify) |
| N | d14 | `?pxl=…&acc=hk77_…`, `clickline.org`, push funnel | health (weight loss) | none named |
| O | d10 | fake App Store page, 3 FB pixels, `adop.team` | gambling app | TVN24-style news, Cristiano Ronaldo (caption) |
| (UNK) | d5 | Ad Library `1982065065827084`, video only | back pain (video) | — |

Operators: OP1 = A; OP2 = D + E; OP3 = F + G (medium); OP_B, OP_C, OP_H, OP_I, OP_K, OP_L–OP_O single-campaign.
Operation `OPN_INV` = A + C + K.

Caveat: 25 incidents; labels were made by hand and two engine rules were added after seeing DANE. Treat every
rule idea above as a hypothesis to validate on NASK's larger pool.
