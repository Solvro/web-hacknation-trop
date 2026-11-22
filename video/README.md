# TROP demo videos

Remotion project for the demo / walkthrough videos (1920×1080, 60 fps, no voice-over,
Polish captions). Every version is a list of scenes in `src/timeline.ts` (`CUTS`); the
scenes, captions and handovers are shared, so a new version is a new list, not new code.
Nothing here is part of the product build.

| Cut | Length | Story |
|---|---|---|
| `A-Przeglad` | 1:53 | Straight jury walkthrough: Sprawdź → bots → verdict → outlines → Graf → new-campaign case → live link → Kampanie → Zgłoszenie → Śledztwa → extension → Lab → results |
| `B-Pitch` | 1:01 | Fast pitch cut, black captions, the strongest beats only |
| `C-Problem` | 1:19 | Problem → solution: ads are reported one by one, scammers run campaigns; then TROP |
| `D-Zgrai` | 1:49 | The pitch deck's zgrai look (red problem slide with four points, outlined TROP wordmark, captions as bubbles with the jelly bots from `public/bots`, A's end card; no KMP-001 numbers slide, no results slide). Full-frame walkthrough with no zoom: dropped DANE 1 folder, bots at their own pace, Graf, domain and person traces, new campaign, Kampanie and Zgłoszenie, White Rabbit, extension. No Lab. |

## Workflow

```sh
cd video && pnpm install
pnpm exec playwright install chromium        # once
pnpm capture                                 # all shots -> public/captures/*.mp4 + src/captures.json
pnpm capture sprawdz lab                     # just these
pnpm capture --origin http://127.0.0.1:13100 # a local build instead of production
pnpm studio                                  # preview and edit
pnpm render                                  # every cut -> out/<cut>.mp4 (CPU, nice -n 10)
pnpm render A-Przeglad                       # just this one
python3 scripts/contact_sheet.py out/A-Przeglad.mp4 sheet.jpg --step 1   # QA
```

A missing capture renders as a striped placeholder naming the file to record.

## How the captures are made

`scripts/capture.ts` drives the live app (`https://trop.b.solvro.pl`) with Playwright,
headless, at 1600×900 CSS px × 1.2 = 1920×1080. The shot list is `src/shots.ts`: each shot
clicks by visible text the way a viewer would, with a drawn cursor and click ring
(headless screenshots have no cursor).

Motion is recorded in **virtual time**: from a shot's `mark()` the page clock
(`performance.now`, `Date.now`, `requestAnimationFrame`, timers) is frozen and stepped
1/60 s per screenshot, so the video is exactly 60 fps whatever the machine does. The
analysis screen paces its SSE events with timers, so the bots run at their designed pace.
Requests still finish in real time while the clock is frozen, so **data shows up without
the loading pauses a real visitor sees**: the footage shows the app a little faster than
it is. CSS animations run on the compositor clock; their playback rate is matched to the
measured capture speed.

While a take records, every wait advances frames (the page clock only moves when a
frame is taken), so timer-driven fetches such as the report's screenshot still arrive.

Shot notes:

- `graf` makes a fresh check of the same sample off camera, then records its report page
  (`/analiza/INC-…`): a finished job's stream expires on the server while a slow take is
  still recording, so the Graf switch cannot stay on `/analiza/JOB-…`. Checks made by
  visitors are wiped by redeploys, which is why the shot never reuses an old incident id.
- `sledztwo` plays the recorded White Rabbit run (`/sledztwa/INV-103?replay=live`, a real
  agent run on `mintforge-capital-apps.com`). Its SSE events are recorded in a warm-up pass
  and replayed on the page clock in the take, so the graph grows smoothly.
- `live` checks `https://example.com` only. No scam URL is ever opened directly.
- `extension` loads `../extension` unpacked and opens the app's own demo feed
  (`/demo/feed-real.html`). It clicks "Dlaczego?", never "Zgłoś".
- `kampanie` clicks "Pobierz PDF" (a local download); "Wyślij" is never clicked.
- Each run of `sprawdz`, `nowa` and `live` creates a check (job) on the server it records.

## Rendering

`pnpm render` renders on the CPU only (CSS handovers: fade, slide, wipe; no WebGL), under
`nice -n 10`, H.264 CRF 20. Rendered videos and captures are git-ignored.

Fonts: Geist (OFL, from the web app), Instrument Sans and IBM Plex Mono (OFL, Google Fonts) for the zgrai cut. No music is used.
