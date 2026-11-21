# Frontend Configuration & Credential Security Audit

Scope: only configuration and code that the web server **publicly delivers to
any anonymous visitor**, plus response headers observed during read-only
network capture. No account, cookie, session token or private key was used,
requested or stored. No attempt was made to authenticate.

## 1. Handling rules applied

* Values of anything resembling a credential were **redacted in storage**:
  `investigation/raw/config.js` was rewritten with
  `measurementApiSecret: "[REDACTED-BY-AUDITOR]"`. The live response was not
  modified.
* No password, session cookie, Bearer token, private API key, signing secret or
  personal account information appears in any report or exported dataset.
* Public client identifiers are reported by **name and type only** where their
  value is not needed.

## 2. Public configuration (not secrets)

Source: `GET /webapi/kv/config.js` and `/webapi/kv/config`, saved as
`investigation/raw/config.js` (redacted copy) and `/tmp` live capture.

| Key | Type | Assessment |
|-----|------|------------|
| `tenantId` 6015, `host` maanwin29.com, `domainType` 1 | public tenant config | Normal |
| `tenantTimeZone` `UTC+05:30`, currency INR | public locale config | Normal |
| `defaultLanguage` en, languages `en,hi` | public locale config | Normal |
| `turnstileSiteKey` | public CAPTCHA **site key** | By design public; only used on login/register. Not a secret. |
| `firebaseConfig.apiKey` (`AIza…`, 39 chars) | Firebase **Web API key** | Public by design; identifies a Firebase project. Not a secret and not a breach. |
| `firebaseConfig.projectId`, `appId`, `measurementId`, `authDomainUrl`, `storageBucket`, `msgSenderId` | public Firebase identifiers | Normal |
| `walletDomain: https://apiweb.payapiar.com`, `webImgUrl`, APK URLs, `pwaList` (30 domains) | public service/domain config | Normal but see §5 |
| `isEnableGuestLogin: "0"` | feature flag | Explains login gate |
| `window.__rum` / `VITE_RUM_PID`, `VITE_RUM_ENDPOINT`, Cloudflare beacon token | public telemetry identifiers | Normal |
| `VITE_SAAS_API_URL`, `VITE_SAAS_JSON_URL` (`api/draw.ar-lottery01.com`) | public backend base URLs | Normal |

## 3. Credential-type findings

### 3.1 Possible exposure — GA4 Measurement Protocol secret (REDACTED)

* **Location:** `/webapi/kv/config.js` and `/webapi/kv/config` →
  `window._DATA_.firebaseConfig.measurementApiSecret` (key present, value
  **redacted** in the saved copy).
* **Type:** Google Analytics 4 **Measurement Protocol API secret** (write-only
  "measurement ID secret", typically ~22 chars).
* **Classification:** *possible security exposure / sensitive credential in
  public client bundle*. A measurement secret is intended for server-side
  use; shipping it to anonymous browsers allows third parties to send forged
  analytics events for that measurement ID.
* **Impact:** analytics data pollution only. It does **not** grant access to
  accounts, game data, funds or the Firebase project.
* **Action taken:** value redacted, not reused, not used to authenticate,
  not published in any report. No testing of the secret was performed.
* **Confidence in classification:** high (key name and value format match a
  GA4 measurement secret); no claim of a broader breach.

### 3.2 Bearer token handling (not encountered)

* Frontend stores the lottery auth token in `localStorage['ar_g_token']` and
  sends `Authorization: Bearer …` to `api.ar-lottery01.com`; refreshed tokens
  can be returned in an `authorization` response header.
* Our guest browser context contained keys `_arms_session`, `_arms_uid`,
  `ar_device_id`, `language`, `IS_SHOW_REQUEST_PERMISSION`, `hasShownNationPopup`,
  but **no `ar_g_token`** (key names only were read; no values stored).
* No token was extracted, printed or used. The paginated authenticated
  endpoints returned HTTP 401 as expected.

### 3.3 Tenant API `signature` is not a secret

`src-ClNBAbcV.js` computes `MD5(canonicalised JSON body)` via bundled
SparkMD5, uppercases it and adds `random`/`timestamp`. No salt or key is
present. This is an integrity/nonce scheme, not a credential. It was
reproduced against a public homepage endpoint only (HTTP 200).

### 3.4 No other credential patterns found

A regex sweep of all downloaded public bundles found no AWS keys
(`AKIA…`), private keys (`BEGIN … PRIVATE KEY`), JWTs, Stripe keys or OAuth
client secrets on the delivered frontend path. Absence in these files is not
proof of absence elsewhere on the site.

## 4. Transport / response-header observations

| Host | Observation | Assessment |
|------|-------------|------------|
| `maanwin29.com` | `x-content-type-options: nosniff`, `referrer-policy: strict-origin-when-cross-origin`; **no** `Content-Security-Policy`, **no** HSTS, **no** `X-Frame-Options` on checked responses | Weak hardening; CSP absent |
| public assets / results | `access-control-allow-origin: *` on `/js/*`, `/webapi/kv/config.js`, draw OSS objects | Intentionally open; enables CORS-based read-only integration |
| `draw.ar-lottery01.com` | Cloudflare `set-cookie: __cf_bm=…` (bot-management), `cf-cache-status: DYNAMIC`, Aliyun OSS `x-oss-*` headers | Standard bot management; cookie not needed for our reads |
| result objects | ETag + Last-Modified, no explicit `Cache-Control` | Heuristic caching possible; use `If-None-Match` |

## 5. Other observations (not vulnerabilities claimed)

* The RUM `beforeReport` hook iterates `document.cookie` and places cookie
  substrings into telemetry properties (`window.__rum.beforeReport` in
  `home.html`). On guest routes the browser had no cookies, so no values were
  sent in our session. On authenticated pages this may transmit session
  fragments to a third-party analytics endpoint — worth a privacy review by
  the site owner.
* Public config lists 30 alternate PWA domains; branding/mirror surface should
  be verified by the owner. We did not access them.
* Login/register use Cloudflare Turnstile (site key public) and SMS/OTP flows;
  bot protection was not challenged or bypassed.

## 6. Compliance statement for HMX Predictor

The independent application must:

* store **only** the eight normalized result fields (no cookies/tokens);
* use only unauthenticated public result objects or manual CSV import;
* never automate login, CAPTCHA, betting, deposits or withdrawals;
* keep the redacted config copy out of any published repository; if a config
  sample is needed, remove `measurementApiSecret` entirely;
* treat third-party hosts as untrusted input: validate ranges and reject
  unexpected schemas before storing.
