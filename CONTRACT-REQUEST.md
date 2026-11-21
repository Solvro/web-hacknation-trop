# WS3 (web) contract requests

The web works against today's API with local adapters (web/lib/graph.ts, web/lib/mock/*). These would remove them.

1. **`GET /graph?focus=<id>` returns the neighbourhood, not the whole graph** (focus node + origin + ≤ 6 direct
   neighbours), and answers for `INC-…` and `person:<name>` ids (today: empty `nodes`). The web trims a whole-graph
   answer itself (`neighbourhood()`), but cannot invent missing neighbours.
2. **`GraphPayload.panel` shape** (open dict in the schema). The web reads (all optional):
   `{kind_label, badge:{text,tone:g|amber|red|cyan|violet}, tags[], title, description, facts:[{k,v}], bot, bot_text,
   action:{label, href?, kind?:'investigate'|'trace'|'incident'|'campaign', seed?}, link:{label, href}}`.
   Today's `{kind, facts:["K: V"], bot_sentence:"Bot: …", primary_action}` is also accepted. Board copy for the four
   demo focus views (4a–4d) is in `web/lib/mock/graph.ts`; when the API panel has no `description` and a fixture exists
   the web shows the fixture (remove once the API serves these).
3. **Node `meta` for focus cards**: `sub` (second line), `count`, `thumb` (material/campaign thumbnail), `weak`
   (dashed, e.g. Cloudflare), `relation:'operator'|'oracle'` (violet dashed edge), `bot`, and for the bridge view 4d
   `side:'right'` on the centre plus `only:'origin'|'focus'` on traces present on one side.
4. **`JobStep.detail` convention**: first line = short summary shown in the bot strip / Raport row; following lines
   (`\n`) = the bot's sentences shown when the step is expanded.
5. **`Campaign.description`**: if it contains `\n`, line 1 is the Raport headline (board 3 h1) and the rest the lead
   paragraph; otherwise the web uses `narrative` as the headline. `name` may be `Zamach` or `«Zamach»`; the web wraps it.
6. Mock scenarios for the other outcomes from `POST /analyze`: `kelvaro.live` / HAR → `ambiguous` (board 12),
   `selqueno.live` → `job.error` at capture + `insufficient` (board 13). The web simulates these offline already.
7. `GET /traces/{type}/{value}`: the web uses Polish path types `domena|osoba|piksel|kit` in its own routes and sends
   the same strings to the API; please accept `domena→domain`, `osoba→person`, `piksel→pixel` aliases.
