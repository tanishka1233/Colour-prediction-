# GitHub Actions Guide

Three workflow files are in `.github/workflows/`. They run on GitHub's computers, not on your phone.

## 1. CI — `.github/workflows/ci.yml`

Runs when:
- you push code,
- you open/update a pull request,
- you click "Run workflow" manually.

It:
1. downloads the code,
2. sets up Python 3.12 (no packages to install — we only use the standard library),
3. checks Python syntax (`compileall`),
4. validates configuration and a **temporary** database (`scripts/ci_check.py`),
5. runs all unit tests (`python3 -m unittest discover -s tests -v`),
6. prints a clear pass/fail result.

## 2. Scheduled maintenance — `.github/workflows/maintenance.yml`

Runs:
- automatically every day at 03:17 UTC (cron `17 3 * * *`),
- or manually.

It runs syntax checks, a temporary-DB integrity check, the tests, and uploads a small JSON report.
It **does not assume any database persists** between runs. GitHub destroys the runner after each job.

## 3. Optional historical collection — `.github/workflows/collect-history.yml`

Runs:
- manually whenever you click "Run workflow",
- automatically once a week at 04:23 UTC on Sunday (cron `23 4 * * 0`).

It:
1. uses only the existing **read-only public history feed**,
2. stores results in a temporary database on the runner,
3. writes `history_summary.json`,
4. exports `collected_results.csv` as a downloadable artifact,
5. prints a reminder to import that CSV into your local app.

**Important:** the runner's database is temporary. Do not treat it as your main database.
Your phone/local app keeps the real SQLite database and keeps working even if Actions is off.

It does **not**:
- log in, use authenticated endpoints, bet, deposit or withdraw,
- run the one-minute prediction scheduler,
- commit database files to the repository.

## How to read a failed run

Open the workflow run on GitHub and expand the failing step. Common fixes:

- `compileall` failed → Python syntax error; fix the reported file and line.
- `ci_check.py` failed → database/config validation problem.
- `unittest` failed → read the failing test name, reproduce locally with the same command.

## Optional external persistent storage

There is no paid infrastructure in this project. If you later add external storage,
set a server-side environment variable (for example `HMX_EXTERNAL_DB_URL`) in GitHub
Actions **Secrets**, and extend the collection workflow to upload there. Never put
the secret in the YAML file or in logs. This is intentionally left as a future option.
