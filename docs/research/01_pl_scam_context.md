# Research 1: Polish scam-ad context, NASK teaser page, impersonated people

> Research subagent report, 2026-11-21 morning (before the dataset arrived). Kept verbatim-ish for METHODOLOGY (related work), ATLAS (patterns), DATA_SOURCES and the face-gallery choices.
> Mark anything uncertain as uncertain. Organizer data is not quoted here.

Short version: the teaser page has no dataset. It's a parody scam landing page built as a CTF: a 1 KB encrypted file unlocks with a key hidden in one of its videos. The most useful real source for the design is a CSIRT KNF report that already clusters campaigns by hand.

## 1. science.nask.pl/hacknation (teaser)

**What the page says.** It describes the expected tool, with no dataset and no scoring rules:
- **Faces:** InsightFace (ArcFace), MagFace for face quality (so weak matches weigh less), facetorch for deepfake detection and "same editing template" signals.
- **Images:** perceptual hashing (`imagehash`) and CLIP/SigLIP.
- **Text:** OCR, `sentence-transformers`, MinHash/LSH for near-duplicates.
- **Infrastructure:** redirect chains, WHOIS/RDAP, DNS, crt.sh certificates, favicon hashes, shared scripts and trackers.
- **Clustering:** weighted similarity, HDBSCAN, a link graph (e.g. Neo4j), and a written reason on every link.
- "A small reference database of the most often impersonated people" is enough.
- One fake review hints at a linking signal: "five domains, same favicon, certificates issued the same day".

**Hidden material** (later solved by the CTF dump; see `data/raw/sample_v1/_HANDOFF_ctf.md`):
- `files/scam_links.enc` (AES-256-CBC, PBKDF2-SHA256, 10k iterations; key from the hero video: `93jng`) → 3 Google-Ads scam URLs.
- Decoy passwords in the source: `FollowTheFake2026!`, `Sup3rTajneHaslo!2026`, `Ghost-Font-0xDEADBEEF`, base64 `nice_try_robot_watch_the_video`, plus a comment addressed to AI agents (bait).
- The `czekoladka` cipher → `WSTAWAJ SAMURAJU` → the password of `files/___BACKUP.zip` (73 MB) = **sample_v1 (15 incidents)**.
- Caesar-like "VIHXFAEKDBQ" (alternating Caesar −3/+7) → **SPEECHBRAIN**.
- **Organizer hints:** facetorch (face deepfake), SpeechBrain (voice), favicon + SSL clustering.

## 2. What Polish CERTs published (2024–2026)

**CSIRT KNF, "Masowa kampania wyłudzeń finansowych"** — https://cebrf.knf.gov.pl/images/Raport_CSIRT_KNF_Masowa_Kampania_Wyludzen.pdf (the closest published example of what we build):
- **Flow:** Facebook/Google ad → redirect domain → landing.
- **Domain pattern:** `finance<20-99>-<Lorem Ipsum word><20-99>.sbs` (e.g. `finance23-voluptas94.sbs`). The annex has 554 of them; an earlier wave used `.pro`.
- **Redirect domains** like `balticpipetrade.com` and `orlenplatform.com` pass campaign-ID URL parameters. The page shows content only when those parameters are present.
- **Cloaking:** no response to some requests, content only for selected users, URL-parameter filtering, dynamic redirects, sites switched on and off.
- **Certificates:** free Let's Encrypt, ZeroSSL and Google Trust Services.
- **Rotating brand names:** 36 absurd ones ("Bystry Dochodal", "Cyrkiel Zyskanta", "Biegła Fundeza", "Brzask Wartonis"). Each gets domain variants (`.site`→`.net`, `-pl`, `ai`, hyphens) and even YouTube videos, partly to steer Google AI Overviews.
- **Localisation:** the page language follows the visitor's country. **Cyrillic code comments** in the page source.
- **Their linking method:** compare stylesheets, unique DOM elements and image metadata.

**Typical funnel** (gov.pl, Apr 2025 — https://www.gov.pl/web/cyfryzacja/reklama-ze-znana-osoba-uwazaj-to-moze-byc-oszustwo):
1. A news-style ad with a famous face.
2. An "investment platform" page.
3. A contact form.
4. A call from a "representative".
5. Pressure to transfer money.

CSIRT KNF also describes AnyDesk abuse and fake-article funnels into data forms, e.g. a PGNiG-branded one (https://cebrf.knf.gov.pl/images/Komunikaty/Raporty/Pdf/Faszywe_inwestycje_2022.pdf).

**Shift to platform lead forms:** in 2025–2026 scammers increasingly used Meta Lead Ads, so there may be no external page at all (https://www.analizy.pl/puls-rynku/40739/oszustwa-inwestycyjne-przenosza-sie-do-lead-ads-knf-ostrzega).

**Scale (CSIRT KNF):**
- Fake-investment domains reported for blocking: 45,985 in 2024 (89.4% of all) and 40,225 in 2025 (96.3%).
- 5,132 ad profiles flagged in Jan–Aug 2026.
- Politicians' faces appeared in 18–31% of campaigns per month; Orlen branding in 9%; XTB in 5%.

**NASK 2025 report on platform responses** (https://www.nask.pl/media/2026/03/reakcja-platform-spolecznosciowych-na-zgloszenia-w-2025-roku.pdf):
- **Doctor deepfake template:**
  1. a fake TV news clip (TVP, TVN or Polsat anchor);
  2. a deepfake "interview" with a doctor;
  3. a link to a fake TVP Info-style article;
  4. a form with a "state-subsidised" promotion and a countdown timer.
- Fake Ministry of Digital Affairs and PGNiG ads; YouTube deepfakes of President Nawrocki and journalist Rymanowski promoting a "narodowy program wsparcia dochodu".
- **Meta removes single ads, not whole advertiser accounts**, and its ad library updates with a delay. This is the motivation for TROP's campaign-level Act package.

**Parcels (InPost/OLX/Allegro):** mostly SMS and marketplace phishing, not ads (CERT Polska annual report, https://cert.pl/uploads/docs/Raport_CP_2025.pdf; figures not verified).

**CERT PL warning list:** https://hole.cert.pl/domains/v2/domains.txt (also JSON/CSV). Domains stay listed for 6 months and are re-added if still harmful.

**Keitaro / traffic-distribution research:**
- Infoblox and Confiant traced ~15,500 Keitaro-linked domains over four months from Oct 2025. Investment scams were the largest category, and cloaking sends scanners and ad reviewers to a harmless page.
  - https://www.infoblox.com/blog/threat-intelligence/patterns-pirates-and-provider-action-what-we-learned-working-with-keitaro/
  - https://blog.confiant.com/p/tracking-software-weaponized-by-criminals
  - https://www.malwarebytes.com/blog/news/2026/05/massive-ai-investment-scam-network-spans-15500-domains
- Infoblox "Reckless/Ruthless Rabbit": Facebook ads → fake celebrity news articles, RDGA-generated domains, wildcard DNS, geofencing (https://www.infoblox.com/blog/threat-intelligence/uncovering-actor-ttp-patterns-and-the-role-of-dns-in-investment-scams/).
- ESET "Nomani": deepfake ads that live only a few hours; Poland among the top countries (https://thehackernews.com/2025/12/nomani-investment-scam-surges-62-using.html).

**Disinformation analogues** (the clustering methods carry over):
- Doppelganger: ~1,000 throwaway front domains → ~50 intermediate → Keitaro → cloned news site (https://www.qurium.org/alerts/exposing-the-evil-empire-of-doppelganger-disinformation/, https://www.disinfo.eu/Doppelganger).
- CopyCop: domains registered in batches that stay dormant until used (https://www.recordedfuture.com/research/copycop-deepens-its-playbook-with-new-websites-and-targets).

**Meta:** has tested face matching against celebrity profile photos on scam ads since Oct 2024, rolled out in the EU in Mar 2025 (https://techcrunch.com/2024/10/21/meta-tests-facial-recognition-for-spotting-celeb-bait-ads-scams-and-easier-account-recovery).

## 3. Most impersonated public figures (for the face gallery)

NASK counted 121 people by mid-2024 and later about 380–450; the official NASK list PDF returned 404. Names below come from reports citing NASK.

| Group | Names | Source |
|---|---|---|
| Politicians | Andrzej Duda (9% of 2024 deepfakes), Donald Tusk, Karol Nawrocki | superbiz/NASK, NASK 2025 |
| Business | Rafał Brzoska (InPost CEO) | same |
| Athlete | Robert Lewandowski | spidersweb |
| Influencer | Kamil Labudda "Budda" | same |
| TV / journalists | Kuba Wojewódzki, Wojciech Cejrowski, Bogdan Rymanowski | xyz.pl, superbiz, NASK 2025 |
| Finance experts | Przemysław Kwiecień (XTB), Piotr Kuczyński, Maciej Samcik, Adam Glapiński (NBP) | xyz.pl, NASK 2025 |
| Doctors | Prof. Krzysztof Simon, Prof. Krzysztof Bielecki | NASK 2025 |
| Artists (miracle cures) | Maryla Rodowicz, Krzysztof Cugowski, Janusz Gajos, Marek Kondrat | superbiz |
| Clergy | Cardinals Nycz, Dziwisz, Abp Gądecki | superbiz |

Source URLs:
- https://superbiz.se.pl/wiadomosci/podszywaja-sie-po-ksiezy-i-politykow-oszusci-coraz-skuteczniej-wykorzystuja-deepfake-aa-9hB2-2Jyi-iNYp.html
- https://spidersweb.pl/2024/05/falszywi-celebryci-zachecaja-do-inwestycji-nask.html
- https://xyz.pl/falszywe-inwestycje-prawdziwe-twarze-tak-oszusci-kradna-zaufanie-polakow/

Uncertain: Anna Mucha and Małgorzata Rozenek-Majdan appear only in a bezprawnik.pl headline.

(The experiments session later built a much larger gallery: every Polish public figure on Wikidata with ≥ 5 Wikipedia editions plus 25 international figures, 6,305 people / 7,364 photos. See `experiments/RESULTS.md` §2c.)

## 4. Polish lure keywords and phrases

**Seen in sources:**
- "Polacy masowo wypłacają zyski"
- "Pierwsze zyski … już po 24 godzinach"
- "Nie potrzebujesz już wiedzy finansowej"
- "wysokie zyski bez ryzyka", "bezpieczny sposób pomnożenia majątku"
- "wyjątkowo opłacalna i bezpieczna inwestycja", "pewne inwestycje", "cudowne lekarstwo"
- "narodowy program wsparcia dochodu", "dofinansowanie z budżetu państwa", "uruchomić portfel inwestycyjny"
- Brand and theme names: Baltic Pipe, Orlen, PGNiG, ZUS, XTB, BitradeX, and the made-up "Dochodal / Zyskanta / Fundeza / Wartonis / Kapitex" names (a "zysk/dochód/fund + Latin-ish suffix" style).

**Seen in our sample** (ad layer): "🚨 PILNE! Ta wiadomość wywołała burzliwą dyskusję…", "Temat, o którym mówi cała Polska".

**Plausible but unconfirmed:** "zarabiaj", "pasywny dochód", "platforma AI", "rejestracja", "minimalna wpłata 250 €".
