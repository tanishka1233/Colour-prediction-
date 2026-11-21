# Phase 3.1 + 3.2 Implementation Report

Plain-language summary. All numbers below come from the local SQLite database and the generated JSON/Markdown reports in `reports/`.

## Answer to the main research question

**Predictive advantage is still unproven.** No model beat the uniform random baseline on unseen chronological data, and no historical candidate pattern survived multiple-testing correction. The software work is complete; the prediction research result is negative so far.

## Dataset (Phase 3.1)

- 68 valid records, period 20261121100010270 → 20261121100010434.
- 97 missing periods; coverage 41.21%%; longest continuous run 33 periods.
- 0 duplicates, 0 conflicts, 0 invalid rows.
- Source: the existing read-only public feed; collection timestamps 2026-11-21T04:39:05+00:00 → 2026-11-21T07:14:09.607+00:00.
- All verified mappings (odd green / even red, 0 red+violet, 5 green+violet, 0–4 Small / 5–9 Big) passed.
- Distribution: numbers {0: 5, 1: 3, 2: 9, 3: 2, 4: 9, 5: 5, 6: 9, 7: 10, 8: 7, 9: 9}; colours {'red': 34, 'green': 24, 'red+violet': 5, 'green+violet': 5}; Big/Small {'Small': 28, 'Big': 40}.

GitHub Actions HTTP 403: investigated. Local requests to the same feed return HTTP 200 with Cloudflare headers (`server: cloudflare`, `__cf_bm` bot cookie). GitHub-hosted runner requests returned HTTP 403 in two manual runs. Most likely IP/datacentre-based bot protection or source restriction. No bypass, identity rotation or unauthorized access was attempted. Local collection remains primary.

## Statistical research (Phase 3.2)

Tests completed: chi-square goodness-of-fit with correct baselines, chi-square homogeneity, runs tests (odd/even, big/small, repeats), lag-1..5 autocorrelation, transition-matrix independence tests for number/colour/size, Shannon entropy, recent-vs-older halves, rolling 20-result windows, exploratory change-point scan, Wilson confidence intervals, Benjamini–Hochberg FDR correction.

Candidate patterns discovered: **16**. After correction, **0** significant.

A key correction was made during research: the colour goodness-of-fit test uses the probabilities implied by a uniform 0–9 draw (red 0.4, green 0.4, red+violet 0.1, green+violet 0.1), not 0.25 each. Without this, the overlapping violet mapping creates a false "signal".

## Model comparison

38 strict walk-forward evaluations. Decision: **no_predictive_advantage_retain_existing_model**.

| Model | Exact accuracy | Log loss | vs baseline | Adjusted p | ECE |
|---|---:|---:|---:|---:|---:|
| uniform | 7.9% | 2.303 | +0.000 | n/a | 0.071 |
| frequency | 7.9% | 3.316 | +1.014 | 0.208839 | 0.084 |
| laplace | 7.9% | 2.401 | +0.098 | 0.248837 | 0.071 |
| bayesian | 7.9% | 2.401 | +0.098 | 0.248837 | 0.071 |
| recency | 10.5% | 3.680 | +1.378 | 0.208839 | 0.068 |
| transition | 2.6% | 2.519 | +0.216 | 7e-06 | 0.134 |
| hybrid | 2.6% | 2.440 | +0.138 | 0.208839 | 0.129 |

All models had log loss at or above the uniform baseline. Recency and frequency models were notably worse. The transition model was significantly worse (adjusted p ≈ 0.000007). No model met the selection rules.

## Files created or modified

Created: `hmx/stats.py`, `hmx/dataset.py`, `hmx/models.py`, `hmx/research.py`, `hmx/validation.py`, `scripts/phase3_reports.py`, five Phase 3 test modules, four generated research reports plus three JSON artifacts under `reports/`, and this report.

Modified: `hmx/scheduler.py` (uses new model builder with explicit model/confidence/validation metadata), `hmx/config.py` (model name + validation status env settings), `hmx/app.py`, `hmx/collector.py`, `hmx/importer.py` (metadata CSV comments), `hmx/cli.py` (new commands: `dataset-report`, `export-dataset`, `research`, `model-compare`).

New CLI commands:
```
python3 -m hmx.cli dataset-report --output reports/phase3_1_dataset_profile.json
python3 -m hmx.cli research --output reports/phase3_2_research.json
python3 -m hmx.cli model-compare --min-train 30 --output reports/phase3_2_model_comparison.json
python3 -m hmx.cli export-dataset --format json --output dataset.json
python3 scripts/phase3_reports.py
```

## Tests

`python3 -m unittest discover -s tests -v` → **84 tests, OK** (61 Phase 1/2 regression tests + 23 new Phase 3 tests). `python3 scripts/secret_scan.py` → 137 files scanned, 0 findings. No runtime database or credentials staged.

## Git

- Branch: `feature/phase3-statistical-research`
- Commits: `a3a5afa` (implementation) and this report commit on the feature branch.
- Not merged into main; no force-push.

## Limitations / remaining research needs

1. Only 38 walk-forward evaluations, far below the 100 needed for model selection.
2. 97 missing periods — the dataset is gappy and not a continuous timeline.
3. Low statistical power; absence of a signal is not proof of absence.
4. Need months of continuous local collection to reach a meaningful sample.
5. Actions collection remains blocked by HTTP 403 from the public feed.
6. No claim of financial performance or guaranteed results is made.
