# Phase 2 Implementation Report — HMX Predictor

Plain-language summary of what changed, what was tested, and what is still pending.

## 1. Before we started (audit)

- The project had **no Git repository**, no remote, and no branches.
- Baseline test result: **41 tests passed**.
- A complete backup was made before any changes (copied to `/tmp/opencode/hmx_phase2_backup`, 146 files).
- Phase 0 investigation files, the original CSV/JSON history, the existing database, engine, frontend and tests were all preserved.
- The GitHub URL you supplied was inspected read-only. It exists, but contains only two unrelated placeholder files (`1.html`, `README.md`) on branch `main-/-root`. We did **not** overwrite that branch.

## 2. What changed and why

| Change | Why |
|---|---|
| SQLite schema upgraded to version 2 (non-destructive) | Added `is_late`, `created_after_start_ms`, `last_request_epoch`, extra indexes. Existing data was kept. |
| Collector restores ETag and throttle window after restart | Prevents duplicate/extra requests after an app or device restart. |
| New `collect-history` command | Historical-only collection with a clear summary and a statement that only the latest 10 results are available. |
| New `db-check`, `backup`, `restore`, `stats` commands | Lets you verify the database, make safe copies, restore them, and see the whole prediction lifecycle. |
| Late predictions are marked and excluded from accuracy | A prediction created too late must not be counted as a valid prediction. |
| Better evaluation report | Totals, pending, correct/incorrect, number/colour/size accuracy, log loss, Brier, calibration, uniform baseline, insufficient-data status. |
| Frontend screens improved | Home shows latest result, prediction status and data freshness; Accuracy shows lifecycle/calibration; Settings has manual collection, backup and provider status. A clear "not guaranteed" notice was added. |
| Three GitHub Actions workflows | CI runs on every push/PR; maintenance runs tests and integrity checks; optional history collection is manual/weekly and never treats runner storage as permanent. |
| Secret scan script | Checks files before committing for keys, tokens, cookies and passwords. |

No betting, login, deposit, withdrawal or authenticated endpoint was added.

## 3. Files created or modified

Created: `scripts/ci_check.py`, `scripts/secret_scan.py`, `.github/workflows/ci.yml`, `.github/workflows/maintenance.yml`, `.github/workflows/collect-history.yml`, `tests/test_phase2_db.py`, `tests/test_phase2_collector.py`, `tests/test_phase2_lifecycle.py`, `tests/test_phase2_cli.py`, `tests/test_phase2_workflows.py`, and the five documentation files in section 7.

Modified: `hmx/db.py`, `hmx/collector.py`, `hmx/scheduler.py`, `hmx/evaluation.py`, `hmx/cli.py`, `hmx/app.py`, `hmx/providers/http.py`, `web/index.html`, `web/styles.css`, `web/app.js`, `.gitignore`.

## 4. Tests actually executed

```
python3 -m unittest discover -s tests -v
Ran 61 tests ... OK            (baseline was 41; 20 new Phase 2 tests)
python3 -m compileall -q hmx tests scripts    -> OK
python3 scripts/ci_check.py                  -> ok: true
python3 -m hmx.cli db-check                  -> integrity: ok, schema_version: 2
python3 scripts/secret_scan.py               -> 115 files scanned, 0 findings
node --check web/app.js                      -> OK
```

Acceptance checks covered: Phase 0 import (46 records, source hash unchanged), duplicate rejection, missing-period detection, backup/restore with a test database, collector recovery after simulated network failure, ETag/304 handling, restart throttle recovery, leak-free predictions, no duplicate predictions, late-prediction exclusion, chronological walk-forward, uniform baseline, frontend API endpoints, workflow file sanity, and ignored runtime files.

## 5. Git and GitHub status

- Git initialized locally on branch `main`.
- Initial commit: `0d6672f` — "Initial import: HMX Predictor Phase 1 + Phase 2 reliability, SQLite integrity, CI workflows".
- Remote was added as `origin` pointing to the URL you supplied.
- **Push succeeded.** Our code is on remote branch `main` at commit `7a3e276`.
  The old remote branch `main-/-root` was left untouched. During final verification
  the repository default branch was changed from `main-/-root` to `main`.
- No secrets, runtime SQLite files, logs or backups were committed.
- GitHub Actions: configured (files present). Actual cloud run status must be confirmed
  on GitHub; no Actions job was executed locally in this session.

## 6. Known limitations / blockers

- The public result feed only returns the latest 10 results. Older history must be imported from CSV/JSON or accumulated over time.
- GitHub Actions runners have **temporary** storage. The optional collection workflow exports a CSV artifact; it is not permanent primary storage.
- The remote repository already has an unrelated branch; we did not delete or overwrite it.
- Accuracy figures are not meaningful yet (very small sample). No predictive advantage is claimed.
- The public feed is undocumented and not authorized for commercial use.

## 7. Documentation files

- `GITHUB_SETUP_GUIDE.md`
- `GITHUB_ACTIONS_GUIDE.md`
- `LOCAL_RUNTIME_GUIDE.md`
- `DATA_COLLECTION_GUIDE.md`
- `PHASE2_IMPLEMENTATION_REPORT.md` (this file)
