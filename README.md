# HMX Predictor — Phase 1

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

41 tests cover feed parsing, ETag/304, backoff, throttling, schema validation,
duplicate/conflict handling, missing periods, period transitions, leakage
prevention, probability normalization, immutability, evaluation, import/export
and the HTTP API. CI runs the same command via GitHub Actions.

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

See `DEPLOYMENT.md` and `IMPLEMENTATION_REPORT.md` for details and limitations.
