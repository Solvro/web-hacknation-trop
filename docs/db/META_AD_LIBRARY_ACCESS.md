# Getting Meta Ad Library API access (do this yourself, today)

Meta ties API access to a **personal identity check**. This guide is for a team member to do; we cannot apply on anyone's behalf.
- The facebook.com/ID check can take **from minutes to several days**, so start it first.
- No App Review is needed for the Ad Library API.

**Who should do it:** a team member with an established personal Facebook account (not a fresh one) and a government ID. Pick someone who can stay the token owner for the whole hackathon.

## Step 1: Confirm your identity and location (the slow part)
1. Log in to Facebook and open **https://www.facebook.com/ID**.
2. Choose **Confirm identity** and the country where you live (Poland).
3. Upload a photo of an ID document (dowód osobisty or passport).
4. Wait for the confirmation (e-mail or notification). Until it arrives, step 4 fails with an "identity not confirmed" error.
5. If Meta asks for location confirmation as well (it used to for political ads), complete it too.

## Step 2: Turn on developer mode
1. Go to **https://developers.facebook.com/** and choose **Get started**.
2. Accept the Meta Platform Terms and verify your phone or e-mail if asked.

## Step 3: Create an app
> Learned the hard way: an app created **without a use case** has no Facebook Login, so Graph API Explorer cannot issue it a token ("Funkcja niedostępna"). Add the use case **"Authenticate and request data from users with Facebook Login"** to the app. The token must come from the identity-confirmed person; a friend's token fails with subcode 2332002, and app tokens fail with 2332004.

1. Open **My Apps** and choose **Create App**.
2. Use case: **Other**. App type: **Business** (or "None", if offered).
3. Name it, e.g. `redpill-adlib-<yourname>`. No business portfolio is needed.
4. Open **https://www.facebook.com/ads/library/api** while logged in and accept the **Ad Library API terms** if prompted. This page is the official entry point.

## Step 4: Get a token
1. Open **Graph API Explorer**: https://developers.facebook.com/tools/explorer/
2. Select your app and choose **Generate Access Token** (a user token; no special permissions are needed for `ads_archive`).
3. Test it in the explorer:
   ```
   ads_archive?search_terms=PILNE&ad_reached_countries=["PL"]&ad_active_status=ACTIVE&ad_type=ALL&fields=id,page_name,ad_creative_bodies,ad_snapshot_url,eu_total_reach&limit=5
   ```
   - "error 2332002 / identity not confirmed" means step 1 is not finished yet.
4. Exchange the short-lived token (about 1 h) for a long-lived one (about 60 days). Simplest: put `META_APP_ID`, `META_APP_SECRET` and the short token in `.env`, then run `python -m scrapers.hunter.meta_adlib --exchange-token`. Manual alternative:
   ```powershell
   curl.exe -G "https://graph.facebook.com/v27.0/oauth/access_token" --data-urlencode "grant_type=fb_exchange_token" --data-urlencode "client_id=<APP_ID>" --data-urlencode "client_secret=<APP_SECRET>" --data-urlencode "fb_exchange_token=<SHORT_TOKEN>"
   ```
   - App ID and secret are in **App settings → Basic**.
   - Never commit them. Put them in the git-ignored `.env`.

## Step 5: Plug the token into RED PILL
```powershell
$env:META_ACCESS_TOKEN = "<LONG_LIVED_TOKEN>"
```
```powershell
python -m scrapers.hunter.meta_adlib --terms "Brzoska" --dry-run
```
```powershell
python -m scrapers.hunter.meta_adlib --job "hunter:meta:lures_pl" --ingest
```
```powershell
docker exec redpill-db-postgres-1 psql -U redpill -d redpill -c "UPDATE jobs SET enabled = true WHERE key = 'hunter:meta:lures_pl'"
```
- The first command checks the request without spending quota.
- The second runs the preconfigured lure-phrase job: PL, active ads, terms in `jobs.params`.
- The third enables the job for the scheduler once the token works.

## What you get, and what you don't
| | |
|---|---|
| ✅ | Every ad that reached the EU, with text, link title and caption, page id and name, delivery dates, EU reach, targeting, and the snapshot URL |
| ❌ | The landing URL, image or video URLs, and the click-tracking link |

The landing URL must come from somewhere else:
- the ad snapshot (rendered by our capture worker under the same token, one ad at a time, which is what Meta allows: "for analysis of individual ads");
- extension and user reports;
- OCR of the creative.

## Limits and rules
- **Rate limit.** Meta publishes no number for `ads_archive`. Error **613** means back off. The hunter's budget is 200 calls per run, and the job runs every 2 h.
- **Search terms.** Max 100 characters and not translated, so query in Polish. Pair phrases with `search_type=KEYWORD_EXACT_PHRASE` for known clickbait templates.
- **Retention.** EU ads stay in the library for 1 year after their last impression. Our `ads` and `ad_observations` tables keep our own copy.
- **No scraping of the public web UI.** Meta's terms allow only the API. The web UI fallback in PLAN §10 is for **manual demo use only**: an analyst pastes a Library ID or URL into the Analyze screen.
- **Token hygiene.** The token is personal. Rotate it if it leaks, and never put it in screenshots, logs or the repo.
