# TROP — follow the fake

**HackNation 2026 · NASK · „Kolekcjoner fejków”.** TROP turns single scam ads into **campaigns, operators and operations** and shows *why* they are linked.

Paste a link, drop a screenshot, a video, a HAR or a whole folder into **Sprawdź**. Six detective bots then take turns:

1. **Zwiadowca** captures the page.
2. **Tropiciel** reads tracking and kit ids.
3. **Czytelnik** reads the content and the people in it.
4. **Notariusz** checks domains and certificates.
5. **Archiwista** compares the material with the base.
6. **Sędzia** gives the verdict, for example „Dołącza do kampanii KMP-… · pewność 0.94”.

Every verdict comes with the evidence behind it, how rare that evidence is, and a graph you can click through.

| Module | What it does |
|---|---|
| **Déjà Vu** | Matching engine: typed, rarity-weighted evidence with two scores per pair (campaign and operator) and five decision states. 0 wrong links on every test we have: sample LOCO, perturbations, held-out DANE 9/9. |
| **White Rabbit** | Investigator agent: starts from one domain, finds sibling domains, certificates, ads and list status, and shows its work live. |
| **Oracle** | Early warning: per-campaign domain DNA scores new certificates before the first ad appears. |
| **Hunter** | Live sources: Meta Ad Library, Google Ads Transparency, the CERT PL list and urlscan pivots. |
| **Act** | One takedown package per campaign: a DSA Art. 16 notice, a CERT PL draft and a STIX 2.1 bundle. It only prepares and exports; nothing is sent automatically. |

## Live demo

- **https://trop.b.solvro.pl**, the real product on the task data, no login. Click a sample on Sprawdź, or drop your own folder or ZIP (one case per folder). Lab → „Importuj zbiór” takes a ZIP of many folders and returns `results.csv`.
- Browser extension: `extension/dist/trop-extension.zip` (Load unpacked), demo feed: https://trop.b.solvro.pl/demo/feed-real.html
- Pitch deck: [docs/pitch/TROP-pitch-zgrai.pdf](docs/pitch/TROP-pitch-zgrai.pdf) · demo video project: [video/](video/) · submission texts: [docs/submission/SUBMISSION.md](docs/submission/SUBMISSION.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Quickstart (offline, no keys)

```bash
docker compose -f deploy/compose.yml up -d --build
# web http://127.0.0.1:13000 · API http://127.0.0.1:18000/api/v1/health
```

Batch mode (hidden-test format, one sub-folder per incident):

```bash
cd backend && uv sync && uv run trop batch /path/to/folders --out results.csv
```

Details are in [docs/INSTALL.md](docs/INSTALL.md).

## Docs
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md): features, evidence model, decisions, evaluation, what failed
- [docs/ATLAS.md](docs/ATLAS.md): the campaign patterns we found
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md): sources, models, libraries and licences; biometric note
- [docs/INSTALL.md](docs/INSTALL.md): install, keys, loading the organizer data
- [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) · [docs/CONTRACTS.md](docs/CONTRACTS.md): architecture and build contracts
- [experiments/RESULTS.md](experiments/RESULTS.md): the research behind the method (reproducible)

Organizer data is never part of this repository (`data/` is git-ignored).
