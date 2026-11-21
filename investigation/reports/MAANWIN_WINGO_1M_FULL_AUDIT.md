# PHASE 0 — MAANWIN WINGO 1M: AUTONOMOUS WEBSITE REVERSE ENGINEERING & DATA AUDIT

**Target:** `https://maanwin29.com/WinGo/WinGo_1M` · **Game:** WinGo 1 Minute
**Audit window:** 2026-11-21 04:29–05:36 UTC (site tenant timezone UTC+05:30, IST)
**Mode:** read-only, unauthenticated. No login, CAPTCHA, bet, deposit, withdrawal or account change was performed.

Evidence classification used throughout:
- **[CONFIRMED]** — directly observed in browser/network/data.
- **[STRONG]** — derived from official frontend code or consistent multi-sample data.
- **[UNVERIFIED]** — plausible but not proven in this audit.
- **[UNAVAILABLE]** — could not be observed with authorized public access.

---

## 1. Executive summary

| Item | Result |
|---|---|
| Website inspected | Yes — initial HTML, SPA bundles, homepage, login-gated game route |
| Full game UI observed | **No** — unauthenticated visitors are redirected to the login view (`isEnableGuestLogin: "0"`) |
| Historical records extracted | **46** unique WinGo 1M results (periods `…10270`–`…10337`), with a documented 22-period collection gap |
| Public snapshot size | **10** results per fetch (metadata advertises 500 total, externally unavailable) |
| Public API | No documented official API. Two undocumented, unauthenticated, CORS-open JSON objects on Alibaba OSS/CDN work reliably |
| Authenticated API | `api.ar-lottery01.com/api/Lottery/*` returns HTTP 401 without a Bearer token |
| Credentials | One GA4 **measurement secret** embedded in public config — redacted, not reused. Firebase `apiKey` and Turnstile site key are public-by-design client identifiers |
| Period schedule | 60 s continuous periods; period IDs follow `YYYYMMDD + "1000" + "1" + SSSS` (SSSS = UTC minute index + 1) |
| Game rules | Colour: odd → green, even → red, 0 → red+violet, 5 → green+violet; Size: 0–4 Small, 5–9 Big |
| Data quality | 0 duplicates, 0 out-of-range numbers, 0 colour-rule mismatches, 22 missing periods in observed range; n=46 too small for inferential claims |
| Integration | Use public result-feed polling (Option C) + manual CSV fallback (Option D) |
| **Phase 1 recommendation** | **GO for a read-only predictor/data collector; NO-GO for any authenticated, betting or gameplay integration** |

No predictive edge was demonstrated. The application should be framed as a statistical *visualisation / analysis* tool, not a guaranteed outcome predictor.

---

## 2. Website architecture

**[CONFIRMED]** Vue 3 single-page application, history-mode routing, Vite/Rolldown hashed bundles, Vant UI, theme `ar_saas11`, tenant ID `6015`.

Evidence: `investigation/raw/home.html` (`#app`, `/js/index-D88Fvtz0.js`, `window.__VERSION__`, `window._CONFIG_`), `investigation/raw/js/` (runtime-core, vue-router, vant CSS, rolldown-runtime), `investigation/network/capture_initial.json`, `investigation/network/capture_home.json`.

- Route: `{path:"/WinGo/:gameCode", name:"WinGo", meta:{hideTabber:true, gameHeader:true}}`.
- Lazy chain: `WinGo-BA0Lwu85.js` → `wingo1-a0zJt5--.js` / `wingo3-mT1SlsO6.js` depending on `lottery_skin`.
- Native game, vendor `ARLottery`; homepage game list contains `{"gameCode":"WinGo_1M","name":"WinGo 1 Min","type":1}`.
- Frontend calls: `/webapi/kv/issue/<gameCode>` for the current period, `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` for the last 10 results, `api.ar-lottery01.com/api/Lottery/*` for authenticated state, and `{gameInfo.webSocketUrl}/connect?token=…` for live push.
- Third parties: Cloudflare (CDN, Insights, bot cookie), Aliyun ARMS RUM, Alibaba OSS result storage, Firebase web config, Turnstile site key, Howler/lottie/SVGA media, SparkMD5 request signing.
- Full detail: `investigation/frontend/architecture.md`.

**[UNAVAILABLE]** Authenticated UI: bet panel, rule modal, paginated history tabs, WebSocket payloads.

---

## 3. Historical data availability

| Question | Finding | Class |
|---|---|---|
| Public records per fetch | Exactly 10 (`list` length in every observation) | [CONFIRMED] |
| Advertised history | `totalCount:500`, `totalPage:50`, `pageNo:1` — metadata for authenticated API | [CONFIRMED] |
| Can pagination be forced publicly? | No. `page`, `pageNo`, `pageSize`, `limit`, `count` all ignored; filename variants 404 | [CONFIRMED] |
| Maximum one-shot public history | 10 records | [CONFIRMED] |
| Longer history | Accumulate by polling; 1 new result/minute | [CONFIRMED] |
| Automatic or on demand? | Frontend loads history automatically on game mount/visibility change; we fetched the same public object directly | [CONFIRMED] |
| Official documented API | None found; `robots.txt` empty, `sitemap.xml` 404 | [CONFIRMED] |

We did **not** log in or use another person's session to reach the 500-record authenticated history.

---

## 4. Historical extraction results

- Files:
  - `investigation/data/wingo_1m_history.csv` (8 required columns)
  - `investigation/data/wingo_1m_history.json` (metadata + records)
  - Raw observations: `investigation/data/observation_log.jsonl`, `investigation/data/transition_samples.jsonl`, `investigation/data/publication_timing.json`
- **46 records**, `20261121100010270` → `20261121100010337`.
- Fields: `period_id`, `result_number`, `result_colour`, `result_size`, `result_timestamp`, `source_url`, `retrieved_at`, `verification_status`.
- `result_timestamp` = exact period-end boundary derived from the verified ID schedule; status explicitly says `timestamp_derived_from_period_id`.
- Retrieval: ETag-aware 30 s polling (`collect_results.py`), one-shot snapshot backfill (`normalize_and_backfill.py`). Stored data contains **no cookies, tokens, account fields or personal data**.
- **Collection gap:** periods with sequence 303–323 (22 periods) were missed while the collector was stopped; they are *not invented*. See data-quality report.

---

## 5. Period ID format

**[CONFIRMED]** Structure of a 17-digit WinGo 1M ID, e.g. `20261121100010279`:

```
YYYYMMDD | 1000 | 1 | SSSS
20261121 | 1000 | 1 | 0279
```

* `YYYYMMDD` = calendar date (UTC indicated by sequence alignment).
* `1000` = WinGo lottery-family code (compare `1010` K3, `1030` TrxWinGo).
* `1` = interval-type digit for 1 minute (2 = 3 min, 3 = 5 min, 5 = 30 s).
* `SSSS` = 0-based minute index of the UTC day; `sequence = minutes_since_00:00_UTC`, and the period's `endTime` is exactly `00:00 UTC + sequence minutes`.
* Verified against 37 live `current` snapshots: **37 exact matches, 0 mismatches** between derived `endTime` and the API's `endTime` (epoch ms).
* Consecutive IDs increment by exactly 1 per minute; 4 boundary transitions were observed live (`…277→278`, `…278→279`, `…279→280`, `…303→…` etc.).
* **[UNVERIFIED]** Behaviour across UTC midnight (date rollover) and the 5-digit wrap were not observed. Do not hard-code future IDs without server confirmation.

The application should treat `issueNumber` as an opaque server-provided key and use the formula only to derive timestamps/validate ordering.

---

## 6. Game rule verification

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Number range 0–9 | [CONFIRMED] | All 46 extracted values in 0–9; `number` strings in feed |
| Green = 1,3,5,7,9 | [CONFIRMED] | 46/46 server `color` fields match odd→green rule |
| Red = 0,2,4,6,8 | [CONFIRMED] | 46/46 match even→red rule |
| 0 → red **and** violet | [CONFIRMED] | Observed `"color":"red,violet"` for number 0 (e.g. `…10271`) |
| 5 → green **and** violet | [CONFIRMED] | Observed `"color":"green,violet"` for number 5 (e.g. `…10278`, `…10306`) |
| Small = 0–4, Big = 5–9 | [CONFIRMED] | Frontend code `number > 4 ? big : small` (`wingo3-mT1SlsO6.js`); 46/46 derived sizes consistent with observed numbers |
| `premium` field meaning | [UNVERIFIED] | Equals `number` in all samples; likely internal odds/premium field, unused by HMX |
| `sum` field meaning | [UNVERIFIED] | Always 0 for WinGo; probably shared schema with dice games |

The site's published rule modal was not reachable without login; classification relies on the site's own result field plus frontend logic. No discrepancy found.

---

## 7. Network endpoint inventory

Full table, request/response shapes, parameters and authorization status: `investigation/network/endpoint_inventory.md`.

Key public reads:

| Endpoint | Method | Auth | Notes |
|---|---|---|---|
| `/webapi/kv/config.js`, `/webapi/kv/config` | GET | none | Public tenant config |
| `/webapi/kv/issue/WinGo_1M` | GET | none | Current ID, start/end, countdown, serverTime |
| `https://draw.ar-lottery01.com/WinGo/WinGo_1M.json` | GET | none | previous/current/next schedule, `intervalMinute:1.0` |
| `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` | GET | none | Last 10 results; ETag/304 supported; CORS `*` |
| `/api/Home/*` | POST | none, MD5-signed body | Public site data, not required by HMX |

Authenticated / not used: `/api/Lottery/GetHistoryIssuePage`, `GetGameInfo`, `GetTrendStatistics`, `GetGameList` (all HTTP 401 without Bearer), all `*/Bet` POSTs, WebSocket, all login/withdraw/recharge flows.

---

## 8. API authentication requirements

* Public result objects: **no** authentication, cookies or headers required. Cloudflare sets `__cf_bm`, but reads succeeded without sending it.
* Lottery API host `api.ar-lottery01.com`: Bearer token required (401 observed). Token stored as `localStorage['ar_g_token']` after login; **not extracted or used**.
* Tenant API `/api/Home/*`: body carries `random`, `timestamp`, `signature`. **[CONFIRMED]** signature = uppercase MD5 of canonically sorted JSON with no secret salt (SparkMD5 bundled in public JS). Reproduced successfully; this is integrity, not authentication.
* No API key is required for the recommended integration.

---

## 9. Public configuration findings

* `/webapi/kv/config.js` sets `window._DATA_` and `/webapi/kv/config.js` page also sets `window._CONFIG_` (tenantId 6015, host, country IN, domainType 1).
* `tenantTimeZone: UTC+05:30`, currency INR, languages `en,hi`, default theme/colours, `selfLotteryMode:0`.
* Public service URLs: `webImgUrl` (`pro-img.arsaaspub.com`), `walletDomain` (`apiweb.payapiar.com`), APK endpoints, `pwaList` with 30 alternate domains.
* Lottery backend defaults embedded in JS: `https://api.ar-lottery01.com`, `https://draw.ar-lottery01.com`, and fallback host `h5pages.ar-lottery02`.
* Firebase web identifiers and Turnstile site key are public-by-design; see security audit.

---

## 10. Security findings

Full audit: `investigation/security/security_audit.md`.

1. **[CONFIRMED — possible exposure]** GA4 `measurementApiSecret` present in public config `firebaseConfig`. Value **redacted** in `investigation/raw/config.js` (stored as `[REDACTED-BY-AUDITOR]`), never printed in reports or reused. Impact limited to forged analytics events; not an account/funds credential. Not claimed as a broader breach.
2. **[CONFIRMED]** Firebase `apiKey` is a public client key — not a secret, not a leak.
3. **[CONFIRMED]** No password, session cookie, Bearer token, private key, AWS key, Stripe key or JWT was found in delivered frontend config/bundles on the tested path or stored anywhere.
4. **[CONFIRMED]** No CSP or HSTS header on checked responses; `x-content-type-options: nosniff` and `referrer-policy` present.
5. **[CONFIRMED]** RUM `beforeReport` copies `document.cookie` substrings into telemetry properties (guest session had no cookies). Privacy review recommended for the site owner.
6. **[CONFIRMED]** Result objects are CORS-open (`access-control-allow-origin: *`) and Cloudflare sets bot cookie `__cf_bm`; bot protection was neither bypassed nor challenged.

---

## 11. Data quality analysis

Full report: `investigation/reports/DATA_QUALITY_ANALYSIS.md`; machine-readable `investigation/data/statistics.json`.

* n=46; all numbers 0–9 **[CONFIRMED]**; 0 duplicate periods **[CONFIRMED]**; chronological order **[CONFIRMED]**.
* 0 colour-rule mismatches against the site's own `color` field **[CONFIRMED]**.
* 22 missing periods in range (collection gap) **[CONFIRMED] — not filled with invented data**.
* Counts: `0:2, 1:1, 2:5, 3:2, 4:6, 5:4, 6:4, 7:9, 8:6, 9:7`; colours green 19, red 21, green+violet 4, red+violet 2; Big 30, Small 16.
* 4 consecutive repeats / 45 transitions (8.9%); longest number streak 2, colour 4, size 6.
* χ²≈12.26 (df=9) — **descriptive only**; n=46 has too little power for any randomness claim.
* **[CONFIRMED]** No evidence of predictive signal; random variation must not be presented as a pattern guaranteeing future outcomes. No backtest performed.

---

## 12. Result refresh mechanism

* Current-period state: `GET /webapi/kv/issue/WinGo_1M` provides `countdown` (seconds) and `serverTime`; frontend recomputes `countdown = endTime - serverTime` and decrements every second via a Web Worker ticker. **[CONFIRMED from code + live data]**
* Period rollover: when countdown reaches 0, the UI switches to the pre-fetched `next` period or re-fetches the issue. **[STRONG — frontend code]**
* Results: `GetHistoryIssuePage.json` rewritten near each period boundary. Observed object `Last-Modified` = `endTime − 3 s` in later samples; early in the session an edge-cached copy lagged ~2 periods. Detection delays in our 15 s poll: −3.8 s to +9.5 s relative to period end. **[CONFIRMED]**
* ETag conditional GET → HTTP 304 with empty body. **[CONFIRMED]**
* Data visibility: when a new period starts, the result for the just-ended period is typically already present (within seconds). A 30–60 s polling interval with dedup is adequate.
* WebSocket live push exists in code but requires a login token; **[UNAVAILABLE]** — not needed for read-only collection.

---

## 13. Period schedule

* Duration: **60 seconds**, continuous, `state:1`, `intervalMinute:1.00`. **[CONFIRMED]**
* `startTime`/`endTime` are epoch-ms and exactly 60 000 ms apart; 37/37 matched the ID-derived boundary. **[CONFIRMED]**
* IDs increment by 1 each minute; 4 live transitions observed. **[CONFIRMED]**
* Local tenant timezone is UTC+05:30, but the ID sequence and draw boundaries align to **UTC** minute boundaries. **[STRONG]**
* Publication delay near boundary (see §12). **[CONFIRMED]**
* Countdown exposed publicly via KV endpoint and schedule object. **[CONFIRMED]**
* No guessed future period IDs are used in stored data; future IDs must come from the server.

---

## 14. Integration feasibility

| Option | Assessment |
|---|---|
| A. Official public API | **Unavailable** — no docs/portal found |
| B. Documented third-party API | **Unavailable** — none identified in this audit |
| C. Public result feed | **Available & recommended** — two unauthenticated JSON objects, CORS-open, stable for this audit, but undocumented and fragile |
| D. Manual CSV import | **Available & recommended fallback** — use this investigation's CSV/JSON |

The public feed is *not* an officially supported integration: obtain authorization or a documented feed before any production/commercial reliance.

---

## 15. Recommended HMX Predictor architecture (Phase 1)

```
[Public draw objects] --(ETag-aware, 60s poll)--> [Collector]
        |                                           |
        +-- current schedule + KV countdown --------+
                                                    v
                                   [Validation + de-duplication]
                                   (range 0-9, ID order, colour rule,
                                    colour cross-check, no future data)
                                                    v
                                   [Append-only local store CSV/JSON]
                                                    v
                                   [Statistics / UI: frequencies,
                                    streaks, charts, CSV import/export]
```

Constraints:
1. **Read-only** — never login, place bets, transfer funds, automate gameplay, submit CAPTCHA or use another identity.
2. Poll at most once per minute (ETag conditional); honour 304; back off on errors; no aggressive retries.
3. Store only the eight normalized fields; keep provenance and `retrieved_at`; never store cookies/tokens.
4. Treat `issueNumber`, `number`, `color` from the feed as authoritative; derive size; cross-check colour and flag mismatches.
5. Label all statistics as descriptive; avoid language implying guarantee; implement time-ordered walk-forward validation if a backtest is ever added.
6. Keep undocumented endpoints behind a configuration module with a CSV-import fallback so the app survives feed changes.
7. Do not copy proprietary site source, CSS or assets into HMX Predictor.

---

## 16. Known limitations

1. Full authenticated game interface, rule modal, bet history pages and WebSocket payloads were **[UNAVAILABLE]**.
2. Public history is limited to 10 records per fetch; 500-record history requires authentication we do not have. **[CONFIRMED]**
3. Sample n=46 with a 22-period gap; distributions have wide uncertainty. **[CONFIRMED]**
4. Public endpoints are undocumented; host/path changes can break collection without notice. **[CONFIRMED]**
5. UTC midnight rollover and counter wrap **[UNVERIFIED]**.
6. No official permission statement for commercial reuse of the result data was found **[UNAVAILABLE]** — seek authorization before deployment.
7. The GA4 secret exposure is reported by location and type only; value remains redacted.

---

## 17. Recommended next implementation phase

1. Implement the read-only collector + storage + CSV import/export exactly as in §15.
2. Run it continuously to build a gap-free dataset (≈1440 rows/day), with monitoring for schema/host changes.
3. Build descriptive dashboards (frequency, colour, big/small, streaks) with explicit "not predictive" framing.
4. Add optional authorized data source only if the operator supplies a documented API or written permission.
5. Separately, if desired, report the GA4 secret exposure to the site owner through a responsible channel — without reproducing the value.

**GO / NO-GO:** **GO** for Phase 1 as a read-only statistical predictor/collector. **NO-GO** for any integration requiring authentication, wagering, account automation or reliance on undocumented endpoints without authorization.

---

## Completion report

- **Website successfully inspected?** Yes (public routes and bundles); full game UI not accessible without login.
- **Historical records actually extracted:** 46 unique results (22-period gap documented).
- **CSV / JSON:** `investigation/data/wingo_1m_history.csv`, `investigation/data/wingo_1m_history.json`.
- **Endpoints discovered:** 17 documented (7 public read endpoints used; 4 auth-required lottery endpoints; remaining telemetry/config/auth).
- **Public API availability:** No documented API; public unauthenticated JSON feed available.
- **Credential security findings:** 1 possible exposure (GA4 measurement secret, redacted); public client keys not secrets; no tokens stored.
- **Period schedule findings:** 60 s continuous UTC periods; ID format and 37/37 timestamp validation; publication near boundary.
- **Verified game rules:** odd green / even red; 0 red+violet; 5 green+violet; 0–4 Small, 5–9 Big.
- **Data quality findings:** no duplicates, no invalid numbers, no rule mismatches; 22 missing periods; small sample; no predictive signal.
- **Recommended integration method:** ETag-aware polling of public result feed + CSV fallback, strictly read-only.
- **Remaining blockers:** login-gated 500-record history, no documented/authorized API, small sample, possible feed fragility.
- **Phase 1 decision:** **GO (read-only only)**.
