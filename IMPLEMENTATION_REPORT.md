# HMX PREDICTOR — PHASE 1 IMPLEMENTATION REPORT

**Completed:** 2026-11-21 (UTC) · **Version:** 1.0.0 · **Stack:** Python 3 stdlib + SQLite + static mobile web UI (no build step, no third-party packages)

---

## 1. Repository inspection

The repository initially contained only `investigation/` (Phase 0 artifacts). No application code, package manifest or CI existed. All Phase 0 files were read before implementation; the main audit, data-quality report, endpoint inventory and Phase 0 CSV/JSON were used as the source of truth for schemas, rules and feed URLs.

**Phase 0 artifacts were not modified.** `scripts/migrate_phase0.py` records the SHA-256 of `investigation/data/wingo_1m_history.csv` before and after import and asserts equality (`962585962c1fea1be2e7ce481b8ed33f26418aac7d3608ca6a1666df76039c6d`).

---

## 2. Files added

| Area | Files |
|---|---|
| Core | `hmx/__init__.py`, `hmx/config.py`, `hmx/logging_util.py`, `hmx/rules.py`, `hmx/db.py`, `hmx/engine.py`, `hmx/evaluation.py`, `hmx/scheduler.py`, `hmx/collector.py`, `hmx/importer.py`, `hmx/app.py`, `hmx/cli.py` |
| Providers (isolated) | `hmx/providers/__init__.py`, `hmx/providers/http.py`, `hmx/providers/wingo_public.py` |
| Frontend | `web/index.html`, `web/styles.css`, `web/app.js` |
| Tests | `tests/__init__.py`, `tests/common.py`, `tests/test_rules.py`, `tests/test_provider.py`, `tests/test_store.py`, `tests/test_engine.py`, `tests/test_scheduler.py`, `tests/test_evaluation.py`, `tests/test_import_export.py`, `tests/test_collector.py`, `tests/test_app.py` |
| Scripts / CI | `scripts/migrate_phase0.py`, `.github/workflows/tests.yml`, `.gitignore`, `.env.example` |
| Docs | `README.md`, `DEPLOYMENT.md`, this report |

Generated at runtime (gitignored): `data/hmx.sqlite3`, `data/phase0_import_report.json`, `logs/*.jsonl`.

No secrets, cookies, tokens or discovered credentials appear in any file.

---

## 3. Architecture

```
Public read-only feeds (Phase 0, undocumented)
  /webapi/kv/issue/WinGo_1M          -> current period + countdown
  draw.../WinGo/WinGo_1M.json        -> previous/current/next schedule
  draw.../GetHistoryIssuePage.json   -> last 10 results
        |
        v  hmx/providers/  (only place these URLs exist; ETag + throttle + backoff)
        v
  hmx/collector.py  -- fetch ALL feeds first, then validate/persist/predict/reconcile
        |                \
        |                 -> hmx/scheduler.py (one prediction per server period)
        v                        \
  hmx/db.py (SQLite)  <----------- hmx/engine.py + hmx/evaluation.py
        |
        v
  hmx/app.py (stdlib HTTP API, rate limiting, health) -> web/ (mobile UI)
```

* **No framework/build step.** Suitable for the low-RAM Android environment.
* External data access is confined to `hmx/providers/`. Replacing it with an authorized feed does not affect storage, engine, evaluation or UI.
* Deterministic engine version `hmx-engine-1.0.0`; dataset version = SHA-256 prefix of ordered `(period_id, result_number)` pairs.

---

## 4. Database migrations

Schema version 1 (`hmx/db.py`), created idempotently on startup:

| Table | Purpose |
|---|---|
| `schema_meta` | schema version |
| `results` | append-only normalized results; `period_id` PRIMARY KEY; CHECK number 0–9, size Small/Big |
| `predictions` | one row per period; UNIQUE `period_id`; full model snapshot + config + status |
| `evaluations` | one row per prediction; hits, log loss, Brier, baseline, calibration |
| `feed_state` | ETag, Last-Modified, last request/success, failure count, last status |
| `collector_events` | structured event log |
| `app_config` | user settings (analysis window) |

**Immutability:** a SQLite trigger (`predictions_immutable`) aborts any update to model content after publication. The only legal post-publication change is the controlled `published → evaluated` transition adding actual-outcome metadata.

**Migration run:** 46 Phase 0 rows imported, 0 invalid, 0 duplicates, source hash unchanged; 22-period gap (`...10302 → ...10325`) reported, never filled.

---

## 5. Collector behaviour

* Exactly one request per feed per minute minimum (`HMX_POLL_INTERVAL_SECONDS`, clamped to ≥60). Three feeds per cycle.
* Conditional GET with stored ETag; HTTP 304 handled as `not_modified` with no body.
* Timeout 15 s; exponential backoff with jitter (2→120 s cap, 4 retries) on network errors/5xx; 429 respects `Retry-After`; 4xx not retried.
* Graceful shutdown via `threading.Event`; background thread in server or standalone CLI loop.
* Strict schema validation for all three feeds; schema errors are logged and never corrupt the store.
* **Leakage-safe ordering:** all three snapshots are fetched first. A prediction is created for the current server-provided period only if its result is absent from both the store *and* the current result snapshot.
* Duplicates are no-ops; conflicting result values are logged, never overwrite.
* Feed health and events persisted; missing periods reported descriptively.
* `result_timestamp` is derived from the server-provided `issueNumber` (Phase 0-verified formula) and labelled accordingly in `verification_status`.

**Live smoke tests:** one-cycle runs against the real public feeds parsed KV, schedule and 10 results successfully (ETags captured). With the Phase 0 dataset present, a prediction for period `20261121100010353` was published with cutoff `20261121100010337` (46 records) before the result was available; a later cycle ingested that result and evaluated the prediction (`exact 0`, `colour 1`, `size 0`, log loss 2.172). With an empty database, the engine correctly returned `insufficient_data` and stored no prediction.

---

## 6. Prediction methodology

Four modular methods, combined by configurable weights (default 0.30 frequency / 0.30 recency / 0.20 transition / 0.20 Bayesian):

1. **Historical frequency** — count/n over the analysis window.
2. **Exponential recency weighting** — `exp(-age/tau)`, τ default 40.
3. **Transition probability** — Laplace-smoothed `P(next | last observed number)` (`+1 / +10`).
4. **Bayesian smoothing** — Dirichlet posterior `(count + α)/(n + 10α)`, α default 1.

Properties:

* Hard `data_cutoff_period` filter inside `predict()` makes future-data leakage structurally impossible.
* Return `insufficient_data` (uniform output, no selection) below `min_history` (default 30).
* Output is a normalized distribution over all ten numbers; ties resolve to the lowest number for determinism.
* `P(Big)=P(5..9)`, `P(Small)=P(0..4)`; colour estimates sum number probabilities for numbers carrying that colour. **0 contributes to red and violet; 5 contributes to green and violet**, so colour probabilities intentionally overlap and do not sum to 1. This is documented in the UI/engine.
* Uniform random baseline is always returned for comparison. No method claims predictive power; descriptive language only.

Prediction records contain all required fields: `prediction_id`, `period_id`, `created_at`, `data_cutoff_period`, `dataset_version`, `algorithm_version`, per-method and combined number probabilities, colour probabilities, Big/Small, selections, sample count, model configuration and status.

---

## 7. Result verification & evaluation

* On result arrival, the published prediction for that period is evaluated exactly once; repeated reconciliation is a no-op.
* Metrics: exact-number hit, colour hit, size hit, multiclass log loss (`-log p_actual`), Brier score (`Σp² − 2p_actual + 1`), uniform baseline (2.303 / 0.900), calibration bucket.
* `walk_forward()` provides strict chronological exploratory replay (train only on periods < t). It is labeled exploratory and is not used for live accuracy claims. The initial 46-record dataset is not used to claim predictive accuracy.

---

## 8. Frontend

Mobile-first dark interface with electric-purple accents and green/red/violet indicators. Five screens — Home (current period, next period, countdown from server timestamps, latest prediction, probability bars, collector status), Analytics (number/colour/size distributions, patterns), History (real results with local-time timestamps), Accuracy (live evaluated metrics + baseline) and Settings (analysis window, CSV/JSON import/export, source status). All data is fetched from the backend API; no fake or hardcoded results/predictions. Empty states are shown when data is unavailable.

---

## 9. Test results

```
python3 -m unittest discover -s tests -v
Ran 41 tests ... OK
```

Coverage includes: feed parsing (documented schemas), ETag/304, throttling, 4xx/5xx and network backoff, schema validation, result number/colour/size mapping, duplicate/conflict prevention, missing-period detection, period transitions, one-prediction-per-period, snapshot-leakage prevention, UTC handling, probability normalization and determinism, insufficient-data status, colour overlap, prediction immutability trigger, evaluation metrics, walk-forward no-future-use, CSV/JSON round-trip with the Phase 0 dataset, full collector pipeline with injected transport, and all API endpoints. `node --check web/app.js` passed. GitHub Actions workflow runs the suite on every push/PR.

---

## 10. Known limitations

1. Public feeds are undocumented, unauthenticated and fragile; they expose only the last 10 results, so history accumulates slowly and gaps remain normal.
2. The 22-period Phase 0 gap and any later gaps are reported, never fabricated.
3. n=46 Phase 0 records (+ a small number of live results) is far too small for inferential claims; all statistics are descriptive.
4. Only one live prediction has been evaluated so far; accuracy figures are not meaningful yet.
5. Countdown uses the browser/server clock difference; no NTP-level synchronization is implemented.
6. Provider host/path changes require editing only `hmx/providers/` or environment variables.
7. No official authorization for the public feed integration has been obtained.

---

## 11. Remaining blockers / next steps

* Obtain an authorized documented result source before any commercial/production deployment; otherwise remain in read-only research/import mode.
* Run the collector continuously for weeks to build a gap-free dataset before taking accuracy figures seriously.
* Add alerting on `feed_failure`, `schema_error` and `late_result_publication` in the deployment environment.
* Optional: add authenticated transport only if explicitly authorized — explicitly out of scope for Phase 1.

---

## 12. Completion criteria checklist

| Criterion | Status |
|---|---|
| Collector works | ✅ unit + live smoke tests |
| Historical results persist | ✅ 46 Phase 0 + live results in SQLite |
| Duplicate records prevented | ✅ UNIQUE keys + tests |
| Period transitions detected | ✅ tracker + tests |
| Upcoming predictions saved before results | ✅ live period 10353 prediction published, then reconciled |
| Actual results reconciled | ✅ live evaluation recorded |
| Prediction evaluation works | ✅ metrics + 41 passing tests |
| Frontend displays real backend data | ✅ API smoke test + no fake data |
| Tests pass | ✅ 41/41 |
| Deployment documentation complete | ✅ `DEPLOYMENT.md`, `.env.example`, CI workflow |

**Phase 1 status: COMPLETE (read-only).**
