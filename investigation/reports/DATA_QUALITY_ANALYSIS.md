# WinGo 1M — Data Quality & Statistical Audit
Generated: 2026-11-21T05:37:25+00:00
## 1. Sample and validation
- Records: **46** (periods 20261121100010270 … 20261121100010337).
- Number range 0–9 valid: **True**.
- Unique period IDs: **True**; duplicates: **0**.
- Chronologically ordered: **True**.
- Server `color` vs derived rule mismatches: **0**.
- Missing periods inside observed range: **22** (gaps: [(303, 324, 22)]).
- Public snapshot per fetch: 10 records; `totalCount=500` is authenticated-API metadata, **not** retrieved.
- Timestamps in `result_timestamp` are exact period-end boundaries derived from the verified period-ID schedule and are labelled as derived.
## 2. Distributions
| Number | Count | Share |
|---|---:|---:|
| 0 | 2 | 4.3% |
| 1 | 1 | 2.2% |
| 2 | 5 | 10.9% |
| 3 | 2 | 4.3% |
| 4 | 6 | 13.0% |
| 5 | 4 | 8.7% |
| 6 | 4 | 8.7% |
| 7 | 9 | 19.6% |
| 8 | 6 | 13.0% |
| 9 | 7 | 15.2% |

| Colour | Count | Share |
|---|---:|---:|
| green | 19 | 41.3% |
| green,violet | 4 | 8.7% |
| red | 21 | 45.7% |
| red,violet | 2 | 4.3% |

| Size | Count | Share |
|---|---:|---:|
| Big | 30 | 65.2% |
| Small | 16 | 34.8% |

## 3.Patterns
- Consecutive identical-number events: **4** of 45 transitions (8.7% of transitions).
- Numbers involved in immediate repeats: {7: 2, 9: 1, 8: 1}.
- Longest same-number streak: **2**; same-colour: **4**; same-size: **6**.
- Chi-square vs uniform 0–9: **12.26** on n=46 (df=9). At this sample size the test has very low power; no significance claim is made.
## 4. Interpretation (explicitly limited)
- With n≈43, expected count per number is ≈4.3; observed variation is consistent with ordinary random fluctuation.
- Consecutive repeats are expected at roughly 1/10 of transitions under a uniform i.i.d. model; observed rate is within small-sample noise.
- **No predictive signal is claimed.** Historical patterns do not guarantee future results; this game is a numbered random draw.
- No backtest was performed; if one is added later it must use strict time-ordered walk-forward validation and never use future outcomes.
## 5. Provenance
- Source: `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` (public, unauthenticated).
- Collection: `investigation/scripts/collect_results.py` (ETag-aware, 30 s polling), `normalize_and_backfill.py`.
- Raw observations: `investigation/data/observation_log.jsonl`, `investigation/data/transition_samples.jsonl`.
- No account data, cookies or credentials are stored.
