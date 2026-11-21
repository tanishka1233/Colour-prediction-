# Network Endpoint Inventory — Maanwin WinGo 1M

Investigation time: 2026-11-21 04:29–04:45 UTC (IST UTC+05:30).
All requests below were **read-only**. No login, wager, deposit or account-changing
request was issued. No session token was used: the public requests were made
without a Bearer token or cookie.

## 1. Summary

| # | Endpoint | Method | Auth | Purpose | Accessible publicly |
|---|----------|--------|------|---------|---------------------|
| 1 | `/webapi/kv/config.js` | GET | none | Server-rendered client config (`window._DATA_`, tenant 6015) | Yes |
| 2 | `/webapi/kv/config` | GET | none | Same config as JSON | Yes |
| 3 | `/webapi/kv/issue/WinGo_1M` | GET | none | Current period number, start/end (ms), countdown (s) | Yes |
| 4 | `https://draw.ar-lottery01.com/WinGo/WinGo_1M.json` | GET | none | Current / previous / next period schedule | Yes |
| 5 | `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` | GET | none | Public result snapshot: **latest 10** draws | Yes |
| 6 | `/api/Home/HomeBasic` | POST | none (signed body) | Homepage basic config | Yes |
| 7 | `/api/Home/GetHomeAllGameList` | POST | none (signed body) | Game list incl. `WinGo_1M`, vendor `ARLottery` | Yes |
| 8 | `/api/Home/GetCommonMessage` | POST | none (signed body) | Notices/popups | Yes |
| 9 | `/api/Home/GetGiftInfo` | POST | none (signed body) | Gift/promo counters | Yes |
| 10 | `/version.json` | GET | none | Frontend build info | Yes |
| 11 | `/themes-499af1c7.json` | GET | none | Theme variables (`ar_saas11`) | Yes |
| 12 | `https://api.ar-lottery01.com/api/Lottery/GetGameInfo` | GET | **401 Bearer required** | Game info incl. `webSocketUrl` | No |
| 13 | `https://api.ar-lottery01.com/api/Lottery/GetHistoryIssuePage` | GET | **401 Bearer required** | Paginated history (10/page, up to 500) | No |
| 14 | `https://api.ar-lottery01.com/api/Lottery/GetTrendStatistics` | GET | **401 Bearer required** | Trend statistics | No |
| 15 | `https://api.ar-lottery01.com/api/Lottery/GetGameList` | GET | **401 Bearer required** | Lottery game list | No |
| 16 | `{gameInfo.webSocketUrl}/connect?token={token}` | WebSocket | token in query | Live result/bet push | No (requires login) |
| 17 | `POST /cdn-cgi/rum?`, Aliyun `https://1kryfn64w78-default-sea.rum.aliyuncs.com/` | POST | none | Telemetry (Cloudflare + Aliyun ARMS) | Yes (not useful for results) |

## 2. Public result endpoints (details)

### 2.1 Current period — CDN schedule object

```
GET https://draw.ar-lottery01.com/WinGo/WinGo_1M.json
```

Observed response (2026-11-21T04:38:29Z; reformatted):

```json
{
  "gameCode": "WinGo_1M",
  "intervalMinute": 1.00,
  "state": 1,
  "previous": {"issueNumber":"20261121100010278","startTime":1795235820000,"endTime":1795235880000},
  "current":  {"issueNumber":"20261121100010279","startTime":1795235880000,"endTime":1795235940000},
  "next":     {"issueNumber":"20261121100010280","startTime":1795235940000,"endTime":1795236000000}
}
```

* Headers: `content-type: application/octet-stream`, `server: cloudflare`,
  `x-oss-*` (Alibaba OSS object store), ETag, Last-Modified, `vary: Origin`,
  `access-control-allow-origin: *`, `cf-cache-status: DYNAMIC`.
* Regenerated about once per minute (Last-Modified observed at `04:34:57Z`,
  `04:38:57Z` GMT).
* No authentication, no cookies submitted by our client. Cloudflare sets a
  `__cf_bm` bot-management cookie in responses, but it was not required for
  subsequent reads.
* **Stability:** undocumented but used directly by the official frontend;
  stable for the duration of this audit. Could change without notice.

### 2.2 Public result snapshot — last 10 draws

```
GET https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json
```

Observed response (2026-11-21T04:38Z; abbreviated):

```json
{
  "data": {
    "list": [
      {"issueNumber":"20261121100010278","number":"5","color":"green,violet","premium":"5","sum":0},
      {"issueNumber":"20261121100010277","number":"8","color":"red","premium":"8","sum":0},
      {"issueNumber":"20261121100010271","number":"0","color":"red,violet","premium":"0","sum":0}
    ],
    "pageNo": 1,
    "totalPage": 50,
    "totalCount": 500
  }
}
```

* `list` is **always 10 items** in every observation. `totalPage/totalCount`
  are metadata (500 results / 50 pages) for the **authenticated** API; the
  public static object does not expose those pages.
* Query parameters `page`, `pageNo`, `pageSize`, `limit`, `count` were tested
  and **ignored** (identical 992-byte body, same first/last issue).
* Per-page filename variants (`...2.json`, `..._2.json`, `/2.json`,
  `20261121100010278.json`) all returned HTTP 404 from OSS.
* Conditional GET with `If-None-Match` returned **HTTP 304** — suitable for
  low-bandwidth polling.
* **Maximum publicly retrievable history in a single snapshot: 10 records.**
  Longer history must be accumulated by repeated polling (1 new result/minute).
* **Stability:** undocumented static object; fragile but is the site's own
  guest-visible result source.

### 2.3 Tenant current-period endpoint

```
GET https://maanwin29.com/webapi/kv/issue/WinGo_1M
```

```json
{"code":0,"data":{"startTime":1795235880000,"endTime":1795235940000,
 "issueNumber":"20261121100010279","intervalMinute":60,"gameCode":"WinGo_1M",
 "diif":0,"countdown":28},"msg":"Succeed","msgCode":0,"serverTime":1795235911274}
```

* Public, no auth. `intervalMinute:60` appears to actually mean **60 seconds**
  (the CDN object says `1.00` minute). `countdown` is seconds remaining in the
  current period; `serverTime` allows clock synchronisation.
* Used by the official game client's `getIssue()` every second/period boundary.
* Useful to an independent client for authoritative clock sync, not required
  for result collection.

## 3. Tenant API signature (public integrity scheme, not a secret)

Guest homepage requests carry `random`, `signature`, `timestamp` in the JSON
body, e.g. `{"language":"en","random":…,"signature":"…","timestamp":…}`.
Frontend implementation in `src-ClNBAbcV.js`:

* deep-sort all body keys, omit `signature`, `track`, `timestamp` and empty
  values;
* `MD5(JSON.stringify(sortedBody))`, uppercase, first 32 chars;
* add `timestamp = floor(Date.now()/1000)`.

SparkMD5 is bundled in the public JS. **No secret key or salt is used** — this
is request canonicalisation/integrity, *not* authentication. It was reproduced
in Python and `POST /api/Home/HomeBasic` returned HTTP 200. This behaviour is
documented but is not recommended as the HMX integration path (undocumented
internal API).

## 4. Endpoints deliberately NOT used

* All `/api/Lottery/*` result, bet-limit, trend and history endpoints on
  `api.ar-lottery01.com` return HTTP 401 without a Bearer token. We did not
  attempt to obtain or forge a token.
* All `/Lottery/*Bet` POST endpoints (wagering) — never called.
* `/Home/Login`, `/Home/AutoLogin`, `/Home/Register`, `/Home/MobileAutoLogin`,
  password/OTP/SMS flows — never called.
* `/Withdraw/*`, `/Recharge/*`, `/ThirdGame/Transfer` — never called.
* WebSocket connect — not opened (token required).

## 5. Access-control / authorization assessment

| Option | Finding |
|--------|---------|
| A. Official documented public API | **Not found.** No API docs, no developer portal, `robots.txt` empty, `sitemap.xml` 404. |
| B. Documented third-party API | **Not found** during this audit. |
| C. Publicly accessible result feed | **Available** — the two OSS objects in §2.1/§2.2. This is what the website uses for guest-visible period data. Undocumented, unauthenticated, CORS-open. |
| D. Manual CSV import | **Available** as fallback from this investigation's exported CSV. |

Recommendation for Phase 1: use **C** as the primary collector with ETag-based
polling and local de-duplication, with **D** as fallback. Treat the API host
(A/B) as unavailable until an authorized documented integration is obtained.
