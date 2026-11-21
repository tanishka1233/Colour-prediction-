# Phase 3.1 — Data Quality Report

Plain-language summary generated from the local SQLite database.

- Records: **68**
- Period range: 20261121100010270 → 20261121100010434
- Missing periods: **97** (coverage 41.21%)
- Longest continuous run: 33 periods
- Duplicate periods: 0; conflicts: 0; invalid rows: 0
- Sources: https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json
- Collection timestamps: 2026-11-21T04:39:05+00:00 → 2026-11-21T07:14:09.607+00:00

## Gaps

- 22 missing periods between 20261121100010302 and 20261121100010325
- 5 missing periods between 20261121100010337 and 20261121100010343
- 70 missing periods between 20261121100010354 and 20261121100010425

## Distributions

| Number | Count | Share | 95% Wilson CI |
|---|---:|---:|---|
| 0 | 5 | 7.3% | [0.0318, 0.1609] |
| 1 | 3 | 4.4% | [0.0151, 0.1219] |
| 2 | 9 | 13.2% | [0.0712, 0.2328] |
| 3 | 2 | 2.9% | [0.0081, 0.1010] |
| 4 | 9 | 13.2% | [0.0712, 0.2328] |
| 5 | 5 | 7.3% | [0.0318, 0.1609] |
| 6 | 9 | 13.2% | [0.0712, 0.2328] |
| 7 | 10 | 14.7% | [0.0819, 0.2500] |
| 8 | 7 | 10.3% | [0.0508, 0.1976] |
| 9 | 9 | 13.2% | [0.0712, 0.2328] |

Colour counts: red=34, green=24, red,violet=5, green,violet=5
Big/Small: {'Small': 28, 'Big': 40}

## Mapping verification

- odd_green_even_red: OK
- zero_red_violet: OK
- five_green_violet: OK
- small_0_4_big_5_9: OK
- stored_rows_conform: OK

## Limitations

- Public feed exposes only the latest 10 results; gaps are expected.
- Missing periods are reported, never filled with invented data.
- Small samples make distribution tests low-powered.
