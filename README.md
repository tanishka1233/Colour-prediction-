# HMX Predictor — Phase 2

Read-only statistical analysis application for Maanwin WinGo 1M, built from the
completed Phase 0 investigation in `investigation/`.

## Scope (hard limits)

- **Read-only.** No login, CAPTCHA, betting, wagers, deposits, withdrawals,
  account automation or authenticated lottery APIs.
- The three public result objects are undocumented and fragile. They live only
  in `hmx/providers/` and are **not for commercial production** without
  authorization.
- No credentials, cookies or tokens are used or stored.

## Quick start

```bash
# 1) initialize database and import the immutable Phase 0 dataset
python3 scripts/migrate_phase0.py

# 2) one polite collection cycle (3 GET requests, read-only)
python3 -m hmx.cli collect-once

# 3) start local API + mobile web UI
python3 -m hmx.cli serve
# open http://127.0.0.1:8765
```

Optional continuous collection (minimum 60 s between requests per feed):

```bash
HMX_COLLECTOR_AUTOSTART=1 python3 -m hmx.cli serve
# or: python3 -m hmx.cli collect-loop
```

## Commands

| Command | Purpose |
|---|---|
| `python3 -m hmx.cli migrate` | initialize/verify SQLite schema |
| `python3 -m hmx.cli collect-once` | one read-only collection cycle |
| `python3 -m hmx.cli collect-loop` | continuous polite polling |
| `python3 -m hmx.cli import FILE.csv` | import a result CSV/JSON |
| `python3 -m hmx.cli status` | collector + feed health |
| `python3 -m hmx.cli backtest` | exploratory walk-forward replay |
| `python3 -m hmx.cli serve` | API + web UI |
| `python3 -m hmx.cli collect-history` | historical-only read-only collection summary |
| `python3 -m hmx.cli db-check` | SQLite integrity + consistency check |
| `python3 -m hmx.cli backup` | consistent database backup |
| `python3 -m hmx.cli restore FILE --force` | restore a backup (test DB recommended) |
| `python3 -m hmx.cli stats` | full prediction/evaluation lifecycle report |
| `python3 scripts/secret_scan.py` | scan files before committing |

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | liveness |
| `/api/status` | GET | collector/feed health, events |
| `/api/results?limit=` | GET | stored results + missing-period gaps |
| `/api/predictions?limit=` | GET | immutable prediction records |
| `/api/evaluations?limit=` | GET | evaluated predictions |
| `/api/stats` | GET | descriptive distributions + accuracy summary |
| `/api/config` | GET/POST | analysis window setting |
| `/api/export?format=csv\|json` | GET | full export |
| `/api/import` | POST | import `{text, format}` or `{rows}` |
| `/api/collector/once` | GET | trigger one collection cycle |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

61 tests cover feed parsing, ETag/304, backoff, throttling, restart recovery,
schema validation, duplicate/conflict handling, missing periods, period
transitions, late-prediction exclusion, leakage prevention, probability
normalization, immutability, evaluation, backup/restore, CLI commands,
import/export, the HTTP API and workflow sanity. CI runs the same command via
GitHub Actions.

## Directory map

```
hmx/                 backend (stdlib only)
  providers/         isolated public feeds (fragile, undocumented)
  collector.py       ETag-aware read-only collector
  db.py              SQLite append-only store + immutable predictions
  scheduler.py       one prediction per server-observed period
  engine.py          deterministic modular probability engine
  evaluation.py      chronological evaluation + walk-forward replay
  app.py             HTTP API + static frontend
web/                 mobile-first dark UI (vanilla JS, no build step)
tests/               unittest suite
scripts/             Phase 0 migration
data/                SQLite DB (gitignored), import report
logs/                structured JSONL logs (gitignored)
investigation/       original Phase 0 artifacts (read-only, untouched)
```

## Phase 2 documentation

- `PHASE2_IMPLEMENTATION_REPORT.md`
- `GITHUB_SETUP_GUIDE.md`
- `GITHUB_ACTIONS_GUIDE.md`
- `LOCAL_RUNTIME_GUIDE.md`
- `DATA_COLLECTION_GUIDE.md`

See `DEPLOYMENT.md` and `IMPLEMENTATION_REPORT.md` for Phase 1 details and limitations.
