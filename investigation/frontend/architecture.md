# Frontend Architecture — Maanwin `/WinGo/WinGo_1M`

Evidence: saved HTML `investigation/raw/home.html`, DOM snapshots
`investigation/raw/wingo1m_*`, downloaded bundles in `investigation/raw/js/`,
network captures `investigation/network/capture_initial.json` and
`capture_home.json`. Only public source delivered to the browser was read;
no source was de-obfuscated beyond minified variable renaming.

## 1. Stack (confirmed)

| Component | Evidence |
|-----------|----------|
| Vue 3 SPA | chunks `runtime-core.esm-bundler-*.js`, `vue-router-*.js`, Vite-style hashed assets and `import()` code splitting |
| Build tool | `rolldown-runtime-*.js`, `window.__BUILD_INFO__` build `1795168414110`, built 2026-11-20T09:53:34Z |
| UI library | Vant (`css/vant-B6LH5B_G.css`, `van-*` CSS classes) |
| App shell | `#app`, `<script type="module" src="/js/index-D88Fvtz0.js">`, CSR (`window.__USE_CSR__=true`) |
| Routing | `vue-router` history mode; route `{path:'/WinGo/:gameCode', name:'WinGo', meta:{hideTabber:true,gameHeader:true}}` in `index-D88Fvtz0.js` |
| Theming | `/themes-499af1c7.json`, single theme `ar_saas11`, 153 CSS variables injected at runtime |
| HTTP layer | axios-like client (`m`) with Bearer transform and request interceptor; tenant API base `/api`; KV base `/webapi`; lottery host overrides `https://api.ar-lottery01.com` / `https://draw.ar-lottery01.com` |
| Request signing | SparkMD5 bundled in `src-ClNBAbcV.js`; MD5 of canonicalised JSON → `signature` |
| Media | Howler (`Howl`), lottie-light, SVGA animation assets |
| Monitoring | Cloudflare Insights beacon; Aliyun ARMS RUM (`sdk.rum.aliyuncs.com`, pid `1kryfn64w78…`) |
| Config | `/webapi/kv/config.js` → `window._DATA_`, `window._CONFIG_` (tenantId 6015, INR, UTC+05:30) |
| PWA | manifest-like `pwaList` of 30 alternate domains in public config; APK via `apk.arsaas-manage.workers.dev` |

## 2. Route and lazy chunks

`index-D88Fvtz0.js` defines:

```
/WinGo/:gameCode      -> WinGo-BA0Lwu85.js         (lazy)
/TrxWinGo/:gameCode   -> TrxWinGo-CZJnF4E4.js
/VideoWinGo/:gameCode -> VideoWinGo-BlU333mN.js
```

`WinGo-BA0Lwu85.js` selects `wingo1-a0zJt5--.js` or `wingo3-mT1SlsO6.js`
depending on `lottery_skin` (`skin_wade` → wingo1, otherwise wingo3). The
`WinGo_1M` page is therefore a *native* lottery game view, not an iframe.

Homepage data (`GetHomeAllGameList`) confirms:
`{"vendorCode":"ARLottery","gameCode":"WinGo_1M","name":"WinGo 1 Min","type":1}`.

## 3. Authentication gate (confirmed limitation)

Navigating unauthenticated to `/WinGo/WinGo_1M` ends on the SPA login view:
visible DOM text is only `EN +91 Remember password Forgot Password Login
Register Now`; bottom tabbar `Home/Promo/Earn/Profile`. The only application
API call observed on that route was `POST /api/Home/GetGiftInfo`.
Public config has `"isEnableGuestLogin":"0"`.

Evidence: `investigation/raw/wingo1m_dom_text_initial.txt`,
`investigation/raw/wingo1m_initial.png`, `investigation/network/capture_initial.json`.

Consequence: the full logged-in game UI (bet panel, rule modal, paginated
history tab, live WebSocket) could **not** be observed. Its behaviour below is
derived from frontend code, not from a live authenticated session.

## 4. Data flow for results (from `Skeleton-DDoXnHZv.js`)

```
Pe() composable  (game state provider)
 ├── getIssue()          -> GET /webapi/kv/issue/{gameCode}   (same origin)
 │                          normalises countdown from endTime - serverTime
 ├── getHistoryIssues()  -> GET https://draw.ar-lottery01.com/{lotteryCode}/{gameCode}/GetHistoryIssuePage.json
 ├── getOpenLottery()    -> same public JSON; compares newest issueNumber to current
 ├── getGameInfo()       -> GET /api/Lottery/GetGameInfo (401 without token)
 └── websocket URL       -> gameInfo.webSocketUrl + /connect?token={token}
```

* `le({gameCode, lotteryCode}, true)` forces the `/webapi/kv/issue/<gameCode>`
  path; host resolution is bypassed for URLs containing `/kv/`.
* `V({lotteryCode, gameCode})` produces the `.json` URL; the interceptor sends
  any `.json` request to the `draw` host (`https://draw.ar-lottery01.com`).
* Non-`.json` lottery requests go to `https://api.ar-lottery01.com` with
  `Authorization: Bearer <token from localStorage['ar_g_token']>`.
* `Se()` converts `intervalMinute` to seconds and computes
  `countdown = floor((endTime - synchronizer.getCurrentTime()) / 1000)`.

## 5. Countdown / rendering (confirmed in code)

* A 1-second composable (`useInterval`, backed by a Blob Web Worker ticker in
  `game-BCz8F29c.js`) decrements `countdown`; at `< 1` it advances to the
  pre-fetched `next` period or calls `getIssue()` again. Betting is locked when
  remaining seconds exceed `limitBetTime = 5`.
* Visibility change handler re-fetches issue + history after 100 ms.
* Winner overlay (`wingo3-mT1SlsO6.js`) renders:
  `color.split(',')` → colour labels; `number` → ball `ball_${number}`;
  `number > 4 ? big : small` (i.e. 0–4 Small, 5–9 Big).
* Paginated history component `record-DY-yY3vf.js` uses `pageSize = 10` and
  `pageNo` against the authenticated `GetHistoryIssuePage` — unavailable to us.
* `ResultItem-BsGly1qB.js` renders bet records (not public draw results) and
  maps numbers 1–10 to a colour palette; it is not the source of truth for
  WinGo draw colours.

## 6. Caching and refresh behaviour

* OSS result objects return ETag + Last-Modified and no explicit
  `Cache-Control`; Cloudflare marks responses `cf-cache-status: DYNAMIC`.
* Conditional GET (`If-None-Match`) returned HTTP 304 with empty body —
  confirmed. The official frontend does not send conditional headers, so it
  re-downloads the small (~1 KB) object on each visibility change / period.
* The result object is rewritten around each period boundary: observed
  `Last-Modified` values were `:57` seconds of consecutive minutes
  (`04:34:57Z`, `04:38:57Z`, and `endTime - 3 s` for later samples). Early in
  the session an edge-cached copy lagged by ~2 periods. Conclusion: publish
  timing is near the boundary but not sub-second reliable; poll at ≥30 s
  intervals with de-duplication.

## 7. Minimum data needed by HMX Predictor

1. `period_id` (`issueNumber`) — unique key.
2. `result_number` (0–9).
3. `result_colour` (server field; can be derived and cross-checked).
4. `result_size` (derived: `>4` Big else Small).
5. `result_timestamp` — period end / publication time.
6. `source_url`, `retrieved_at`, `verification_status`.

No token, cookie, account field, bet, balance or user identifier is required.

## 8. Third-party dependencies (identified)

Vue 3, Vue Router, Vant, SparkMD5, axios, Howler, lottie-web, SVGA,
Aliyun ARMS RUM, Cloudflare Insights, Cloudflare bot management, Alibaba OSS
(result CDN), Firebase web SDK (config only — no Firebase calls observed on
the path we tested), Cloudflare Turnstile site key (login/register only).

## 9. IP / implementation caution

This report records interface behaviour only. Proprietary frontend source must
not be copied into HMX Predictor. Reimplement the minimal read-only data model
and polling logic independently; do not bundle or reuse site JS/CSS/assets.
