# TROP: pitch deck (HackNation 2026 final)

**Canvas:** https://claude.ai/artifact/7FYSNxQxdK9Hexhs9MnfJ6 (private until shared from the page's Share menu)

All four variants sit on one canvas page, one row per style, so slide N of every variant is in the same column and they can be compared side by side:

| Row | Variant | Reference it follows | First slide |
|---|---|---|---|
| 0 | Overview (`Main`) | – | `#artboard-Main` |
| 1 | **Akta sprawy** (our own, recommended) | – | `#artboard-AK-01-Tytul` |
| 2 | zgrai | `Solvro/web-zgrai`, deck `pitch/zgrai-pitch.html` | `#artboard-ZG-01-Tytul` |
| 3 | rogatka | `Solvro/web-rogatka-hackyeah`, `docs/ux/STYLEGUIDE.md` | `#artboard-RG-01-Tytul` |
| 4 | jak doczłapie | `Solvro/mobile-jak-doczlapie` (tokens + the deck slide in its README) | `#artboard-JD-01-Tytul` |
| 5 | Product screens, shared by all variants | the "TROP · Sprawdź" boards of the design canvas | `#artboard-Ekran-01-Sprawdz` |

Each variant has the same 13 slides:

1. Title
2. Problem (scam ads, NASK task „Kolekcjoner fejków”)
3. Insight: they rotate domains and personas, but reuse kits, pixels, Cloudflare accounts, templates and fake commenters
4. TROP in one sentence, plus the modules (Déjà Vu, White Rabbit, Oracle, Hunter, Act) and the six bots
5. Demo 1: Sprawdź field → the six bots wake → live evidence
6. Demo 2: Raport („Dołącza do kampanii KMP-017 · pewność 0.94”) → clickable Graf
7. Demo 3: the new-campaign case (KMP-040 «Bon energetyczny»)
8. Demo 4: White Rabbit tree + the Oracle strip
9. Demo 5: Act takedown package + Hunter and the extension badge
10. How it works: typed rarity-weighted evidence, the campaign vs operator score, five decisions
11. Results with the Lab screen: 0 wrong links, sample B³ 1.00, held-out DANE 9/9, 502 page recovered 0.87, face gallery precision 1.00
12. What we rejected and why: embeddings, GBM, one score, VLM for identity, mean-of-top-3
13. Impact for NASK / CERT PL, the ask, the team

## Decision (22.11): zgrai

The team picked the **zgrai** row. Its 13 slides are now:

1. Title (team Solvro Dawid, Dawid Linek)
2. Problem
3. Insight
4. TROP and modules
5. Demo: Sprawdź and the bots
6. Demo: Raport and Graf
7. Demo: new campaign
8. Demo: White Rabbit and Oracle
9. Demo: Act
10. Demo: browser extension and Hunter
11. How it works
12. Functionality: what the NASK task asks for, and what we added on top
13. Closing slide with a QR code to https://trop.b.solvro.pl

The zgrai slides and the product screens use no middle dots. The other three rows stay on the canvas for reference.

## How the styles differ

- **Akta sprawy:** a dark desk with manila sheets, typewriter type (Special Elite, Courier Prime), red thread between pinned evidence, yellow evidence tags, rubber stamps for verdicts and marker notes. Screens appear as clipped photos.
- **zgrai:** white, ink and red with Instrument Sans and IBM Plex Mono. It uses the giant filled and outlined wordmark, bot chat bubbles with one sharp corner, a full-red problem slide and a red closing slide. Screens appear in browser frames.
- **rogatka:** an editorial white grid with a 6 px red top rule and a 2 px red footer rule. It uses stat blocks with red top rules, a red-rail timeline, mono decision chips (DOŁĄCZA / NOWA / NIEPEWNE) and audit-log tables. Screens sit on dark devices tilted −8°. There is one red slide and a dark closing slide.
- **jak doczłapie:** full-bleed electric blue `#3057F4` (with a navy gradient and one yellow slide) and Onest 800. „trop trop trop” is repeated in three bleeding rows. Footprints fit the name: *trop* means a track. The demo is drawn as a transit line with five stops, with line badges, departure-time chips and glass cards. Screens appear on laptops.

All slides use the fictional universe of `docs/design/canvas/BRIEF.md` (KMP-017 «Zamach», INC-24817, OP-03 «Kestrel», morvanta.click …) and aggregate metrics from `docs/METHODOLOGY.md`. They contain no organizer data and no photos of people; persons are silhouettes.

## Recommendation: Akta sprawy

TROP's whole job is turning scattered ads into a case file whose links you can defend. The dossier, with red thread between evidence and a verdict stamp, says that before anyone reads a word. The detective bots (fedoras, monocle, police cap) already live in the product, so the deck and the product feel like one world. The judges at NASK and CERT PL are investigators, and this is their visual language. It also looks nothing like the other three Solvro decks, so it is memorable on a day full of white-and-red slides.

Fallback: **zgrai**. It is the safest choice because the product screens are already zgrai-like, so the demo slides need no translation.

## Illustration vs production

The walkthrough slides use the **fictional** KMP-017 universe for illustration. Say so if asked. Production (https://trop.b.solvro.pl) runs on the real organizer data, so the deck deliberately contains **no production screenshots**: the deck may be shown publicly, and real captures would show organizer identifiers. Show production live in the demo instead.

Product changes since the screens were drawn, to mention in the live demo:
- Raport shows real screenshots of the captured page with evidence outlines.
- The Graf unfolds in place.
- Sędzia (the adjudicator) explains in Polish and can only veto a link.
- DANE: items 1 and 2 → KMP-001, item 3 → KMP-003, all others are new campaigns, with 0 wrong links.
- White Rabbit on production: 8 steps, 26 nodes, 3 new domains, including the domains of DANE 1 and 2, found independently.

## Fill in before the final

- `[Imię Nazwisko]` / `[skład zespołu]`: team members (slides 1 and 13 of every variant).
- The ask on slide 13 („tydzień pilotażu na żywym strumieniu zgłoszeń NASK”) is a proposal. Confirm it, or replace it with the team's ask.
- `trop.b.solvro.pl` is the planned public URL (IMPLEMENTATION §1a). Check that it is live.
- The product screens are rebuilt from the design boards, because no app screenshots existed when the deck was made. Swap in real screenshots from the web app if they look different.

## Speaker notes (3 minutes)

Timings assume a live demo. Slides 5–9 double as the fallback if the demo fails.

**0:00 · 1 Tytuł.** „Jesteśmy z Solvro, to jest TROP: follow the fake. Z jednej reklamy dochodzimy do całej kampanii oszustwa, a każde powiązanie ma dowody.”

**0:10 · 2 Problem.** „Platformy zdejmują reklamy pojedynczo. Kampania wraca następnej nocy pod nową domeną, z nowym reklamodawcą i nową twarzą. Zadanie NASK brzmi: pogrupować to w kampanie i wyjaśnić dlaczego.”

**0:25 · 3 Wgląd.** „Oszuści zmieniają domeny i twarze, ale zaplecze zostaje: ten sam kit, ta sama bramka CAPI, to samo konto Cloudflare, ten sam szablon i ci sami fałszywi komentujący. Rzadki wspólny ślad znaczy ten sam operator. Pospolity, jak sam Cloudflare, waży zero.”

**0:40 · 4 TROP.** „TROP zamienia pojedyncze reklamy w kampanie, operatorów i operacje, i pokazuje, dlaczego są połączone. Pięć modułów: Déjà Vu, White Rabbit, Oracle, Hunter i Act. Sześć botów prowadzi każdą sprawę.”

**0:50 · 5 Demo: Sprawdź.** „Wklejam link. Boty budzą się po kolei: Zwiadowca przechwytuje stronę, Tropiciel czyta piksele i kit, Czytelnik treść i twarze, Notariusz domeny i certyfikaty, Archiwista porównuje z bazą.”

**1:10 · 6 Raport → Graf.** „Po 20 sekundach Sędzia mówi: dołącza do kampanii KMP-017, pewność 0.94. Każdy dowód ma wagę i rzadkość. Klikam domenę: ta sama nocna partia certyfikatów.”

**1:30 · 7 Nowa kampania.** „Równie ważne: TROP umie powiedzieć »to coś nowego«. Ten materiał nie pasuje do żadnej z 41 kampanii, więc dostaje kandydata nowej kampanii zamiast złego linku.”

**1:45 · 8 White Rabbit + Oracle.** „Agent startuje od jednej domeny i znajduje resztę sieci. W demo jest 14 domen, z czego 11 nie ma na liście CERT PL. Oracle oznacza domeny już przy certyfikacie, zanim ruszy reklama.”

**2:05 · 9 Act + Hunter.** „Jeden klik i powstaje pakiet na całą kampanię: zgłoszenie DSA, szkic dla CERT PL i STIX. Wysyła człowiek. Hunter i wtyczka same dokładają nowe materiały.”

**2:20 · 10 Metoda.** „Pod spodem: waga to siła typu razy rzadkość wartości. Liczymy dwa wyniki, kampanii i operatora, i podejmujemy pięć decyzji. Brak danych nigdy nie jest dowodem różnicy.”

**2:35 · 11 Wyniki.** „Zero błędnych powiązań we wszystkich testach. B³ 1.00 na próbce i 9 na 9 na odłożonych danych. Uczciwie: silnik zamrożony przed DANE miał 8 na 9, też bez błędnego linku.”

**2:45 · 12 Odrzucone.** „Embeddingi i GBM robiły złe linki, bo podobne historie to nie ten sam oszust. U nas LLM może tylko wetować.”

**2:52 · 13 Wpływ i prośba.** „Dla NASK to jedno zgłoszenie na kampanię i domeny blokowane wcześniej. Prosimy o tydzień pilotażu. Dziękujemy.”

## Sources

- Product facts and demo script: `README.md`, `docs/IMPLEMENTATION.md` §3 and §8, `docs/PLAN.md` §0.
- Numbers: `docs/METHODOLOGY.md` §5–§6.
- Screens: `docs/design/canvas/project/Sprawdz*.dc.html`, `Kampanie`, `Sledztwo`, `Zgloszenie-KMP017`, `Graf-*`, rebuilt as `Ekran-01…10` on the pitch canvas.
- Style references: found on GitHub in the Solvro org (see the table above).
