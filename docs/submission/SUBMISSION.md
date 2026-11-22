# TROP: tekst zgłoszenia (HackNation 2026)

> Gotowe do wklejenia w formularz. Pola oznaczone ⚠ wymagają decyzji Dawida.

---

**Project Name**
TROP — follow the fake

**Team lead**
Dawid Linek

**Challenge** ⚠
Musi być: **[NASK] Kolekcjoner fejków**. Wklejony formularz jest przypisany do projektu „ex ante” z wyzwaniem „Risk Miner” (MFiPR), a zmiana wyzwania jest zablokowana. Jeśli to zgłoszenie ma być dla TROP, trzeba napisać do organizatorów albo wypełnić osobne zgłoszenie dla NASK.

**Idea stage**
New Idea

**Team status / size**
Full team · 1

---

## Problem
Fałszywe reklamy w social mediach to dziś główna droga oszustw „inwestycyjnych” w Polsce. Reklama ze znaną osobą, często w postaci deepfake'u, prowadzi do podrobionego artykułu (Gazeta.pl, TVN24, Onet), a stamtąd do „platformy inwestycyjnej”, która wyłudza dane i pieniądze.

- **Skala incydentów:** w 2024 r. CERT Polska (NASK) obsłużył ponad 100 tys. incydentów, o 29% więcej niż rok wcześniej. Zgłoszeń było ponad 600 tys., o 62% więcej. Zdecydowaną większość incydentów stanowią oszustwa komputerowe.
- **Fałszywe inwestycje:** CSIRT KNF zgłosił w 2024 r. 51 241 złośliwych domen (wobec 30 140 w 2023 r.). 89,4% z nich to fałszywe inwestycje.
- **Lista ostrzeżeń CERT Polska:** w 2024 r. trafiło na nią ok. 92 tys. domen.

Problem nie polega na braku zgłoszeń, tylko na ich rozproszeniu. Każda reklama i każda domena to osobny przypadek, a oszuści co kilka godzin zmieniają domenę, reklamodawcę i twarz. Analityk widzi tysiące pojedynczych „fejków”. Nie widzi, że setki z nich to jedna kampania jednego operatora na tym samym kicie, z tym samym pikselem i z domenami zarejestrowanymi tej samej nocy. Przez to zgłoszenia do platform i rejestrów są cząstkowe i spóźnione, a kampania działa dalej na nowych domenach.

## Solution
TROP („follow the fake”) łączy pojedyncze reklamy w kampanie, operatorów i operacje oraz pokazuje, dlaczego są połączone.

**Jak to działa.** Analityk lub obywatel wkleja link, zrzut ekranu, wideo, plik HAR albo cały folder z materiałem. Sześć botów-detektywów kolejno:
1. przechwytuje stronę w piaskownicy (bez wypełniania formularzy);
2. czyta ślady techniczne: piksel FB, bramkę CAPI, konto w kicie stron, identyfikator landera, wspólne pliki;
3. czyta treść, szablon nagłówka, osoby (twarze tylko z galerii 6,3 tys. osób publicznych, nigdy z modelu językowego) i marki;
4. sprawdza domenę, certyfikaty i daty rejestracji;
5. porównuje materiał z bazą;
6. wydaje werdykt: „Dołącza do kampanii KMP-001 · pewność 0.99” albo „Nowa kampania (kandydat)”, zawsze z listą dowodów, ich wagą i rzadkością.

**Metoda.** Silnik dowodów ważonych rzadkością liczy dla każdej pary dwa wyniki: kampania i operator. Ma pięć stanów decyzji i zasadę „ten sam operator ORAZ ta sama narracja = ta sama kampania”. Model językowy (Sędzia) może tylko zawetować słabe powiązanie, nigdy go stworzyć.
- Na danych z zadania: 0 błędnych powiązań, B³-F1 = 1.00.
- Na odłożonym zbiorze DANE 9/9 trafnych decyzji.
- Embeddingi i uczony GBM, które przetestowaliśmy, łączyły błędnie 3–7 par, więc zostały tylko wsparciem.

**Co zyskuje NASK / CERT Polska.**
- **Kampanie zamiast tysięcy zgłoszeń.** Widok kampanii, operatora i operacji, np. wspólny lejek kilku kampanii.
- **Act.** Jeden pakiet zgłoszeniowy dla całej kampanii: zgłoszenie DSA art. 16 (PDF/JSON), szkic dla listy CERT PL z domenami, których jeszcze na niej nie ma, STIX 2.1 / MISP i reguły wykrywania. Nic nie jest wysyłane automatycznie.
- **White Rabbit.** Agent-śledczy z jednej domeny znajduje resztę kampanii przez crt.sh, urlscan, Meta Ad Library, listę CERT PL i naszą bazę. W teście z jednej domeny znalazł 50 domen siostrzanych, w tym 23 nowe.
- **Hunter i Oracle.** Hunter pobiera nowe reklamy z Meta Ad Library (PL). Oracle wskazuje nowe domeny pasujące do „DNA” kampanii.
- **Wtyczka przeglądarki.** Oznacza sponsorowane posty pasujące do znanej kampanii i pozwala je zgłosić jednym kliknięciem.
- **Tryb wsadowy dla zbioru testowego.** `trop batch` albo „Importuj zbiór” w aplikacji: ZIP z folderami → `results.csv` z decyzją dla kampanii i operacji.

## What's done so far and goal of your project
**Przed wydarzeniem.** Analiza danych z zadania (sample_v1, DANE) i eksperymenty porównujące podejścia: silnik dowodów, embeddingi, GBM, sędzia LLM, VLM do zrzutów reklam, galeria twarzy. Wyniki i decyzje są w `experiments/RESULTS.md`.

**W trakcie wydarzenia zbudowaliśmy cały produkt:**
- **Silnik:** port silnika z testem regresyjnym (sample: B³ 1.00, 0 błędów; DANE 9/9) i obsługa wszystkich formatów danych z zadania (foldery „zapisz stronę”, wiele HAR-ów, lejki strona_N, zrzuty z telefonu, nagrania ekranu, wideo z Ad Library, ZIP).
- **API i worker:** FastAPI + worker na kolejce, strumień zdarzeń na żywo, przechwytywanie stron w sandboxowym Chromium.
- **Panel:** własny panel Next.js (Sprawdź · Kampanie · Śledztwa) z grafem powiązań rozwijanym w miejscu i prawdziwymi zrzutami stron z obrysami dowodów.
- **Media:** analiza wideo i mowy (Gemini), rozpoznawanie głosu, galeria twarzy.
- **Moduły:** White Rabbit, Act, Hunter (Meta Ad Library, CERT PL, urlscan, Google Ads Transparency), Oracle, wtyczka MV3.
- **Wdrożenie:** produkcja na https://trop.b.solvro.pl (Coolify, Docker Compose, limity pamięci łącznie ≤ 5 GB).
- **Dokumentacja:** METHODOLOGY, DATA_SOURCES (licencje, nota o danych biometrycznych), ATLAS (wzorce kampanii), INSTALL.

**Cel.** Narzędzie, które CERT Polska może uruchomić u siebie i karmić zgłoszeniami z listy ostrzeżeń oraz z Ad Library, tak żeby zgłaszać całe kampanie zamiast pojedynczych domen.

---

**Your video presentation (YouTube, Listed)** ⚠
Wgrać wybraną wersję z `data/video/` (A 1:53 · B 1:01 · C 1:19 · D z lektorem) jako „Niepubliczny / Listed” i wkleić link.

**Website**
https://trop.b.solvro.pl

**[Obowiązkowe] Link do repozytorium** ⚠
https://github.com/Solvro/web-hacknation-trop
Repozytorium jest prywatne. Jury potrzebuje dostępu: dodać konta organizatorów jako collaboratorów (Read) albo upublicznić. Przed upublicznieniem trzeba usunąć dane pochodne od organizatorów: `deploy/bundle/`, `experiments/RESULTS.md`, `experiments/DATA_NOTES.md`, `docs/ATLAS.md`, `experiments/labels*.yaml`, `backend/trop/api/campaigns_pl.json`.

**[Opcjonalne] Instrukcje jak otworzyć projekt**
1. Otwórz https://trop.b.solvro.pl (bez logowania).
2. **Sprawdź:** kliknij jedną z gotowych próbek (np. „DANE 1”) albo przeciągnij własny folder lub ZIP z jednym przypadkiem. Pliki powyżej 8 MB wysyłają się w częściach z paskiem postępu. Boty pokażą analizę, potem Raport z werdyktem i dowodami, potem Graf (kliknięcie węzła rozwija go w miejscu).
3. **Cały zbiór testowy:** zakładka Lab → „Importuj zbiór” → ZIP z folderami → tabela i `results.csv` (kolumny kampania i operacja). Lokalnie: `cd backend && uv sync && uv run trop batch <folder|zip> --out results.csv`.
4. **Kampanie:** wybierz kampanię → „Zgłoś całą kampanię” → pobierz PDF / STIX. Nic nie jest wysyłane.
5. **Śledztwa:** „Śledź dalej” w Raporcie uruchamia agenta White Rabbit.
6. **Wtyczka:** pobierz `extension/dist/trop-extension.zip` z repozytorium → chrome://extensions → tryb dewelopera → „Załaduj rozpakowane” → otwórz https://trop.b.solvro.pl/demo/feed-real.html.
7. **Lokalnie bez kluczy:** `docker compose -f deploy/compose.yml up -d --build` (szczegóły w `docs/INSTALL.md`).

**[Obowiązkowe] Nazwa zespołu**
Solvro Dawid

**[Obowiązkowe] Numer stolika**
11E

**[Opcjonalne] Prezentacja (PDF ≤ 10 MB)**
`TROP-pitch-zgrai.pdf` (13 slajdów, 4,2 MB): `.claude/worktrees/pitch-deck-2c1809/docs/pitch/TROP-pitch-zgrai.pdf`

**[Opcjonalne] Dodatkowe materiały**
Canvas z prezentacją (4 warianty) i film demo. Link do canvasa trzeba najpierw udostępnić z menu Share: https://claude.ai/artifact/7FYSNxQxdK9Hexhs9MnfJ6

**Cover image (800×600)**
`docs/submission/cover.png`: Raport dla DANE 1 z werdyktem, dowodami i prawdziwym zrzutem strony. Uwaga: na zrzucie widać twarze osób publicznych wykorzystanych przez oszustów. Jeśli to przeszkadza, można przyciąć obraz do lewej kolumny.

---
Źródła statystyk:
- CERT Polska, raport roczny 2024: https://cert.pl/uploads/docs/Raport_CP_2024.pdf
- omówienie raportu CERT Polska: https://www.gazetaprawna.pl/biznes/artykuly/10662517,raport-roczny-cert-polska-nask-za-2024-rok-wzrasta-ilosc-oszust-inter.html
- CSIRT KNF, raport roczny 2024: https://www.knf.gov.pl/knf/pl/komponenty/img/Raport_Roczny_CSIRT_KNF_2024_93226.pdf
- omówienie raportu CSIRT KNF (lista ostrzeżeń): https://www.telepolis.pl/tech/bezpieczenstwo/raport-csirt-knf-2024-falszywe-inwestycje
