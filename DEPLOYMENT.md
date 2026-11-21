# Deployment & Operations

## Requirements

- Python 3.11+ (tested on 3.14). **No third-party packages.**
- No Node/npm build step; `web/` is served directly.
- Works on low-RAM Android/Termux; no resource-intensive local builds.

## Local / single-host

```bash
python3 scripts/migrate_phase0.py
HMX_HOST=127.0.0.1 HMX_PORT=8765 python3 -m hmx.cli serve
```

For continuous polling, set `HMX_COLLECTOR_AUTOSTART=1` in the environment.
Keep `HMX_POLL_INTERVAL_SECONDS>=60` (the config clamps below 60 to 60).

To expose beyond localhost, put a reverse proxy with TLS in front and restrict
access. The built-in API rate limiter allows 120 requests/minute per client IP
by default (`HMX_RATE_LIMIT_PER_MINUTE`).

## Environment variables

See `.env.example`. No credentials are required or accepted. Never place
cookies, Bearer tokens or website credentials in the environment or database.

## Health monitoring

- `GET /api/health` → liveness, version, result count, collector thread state.
- `GET /api/status` → per-feed ETag/last status/failure count, last 10 structured
  events, collector cycle count and tracker state.
- Structured logs: `logs/server.jsonl`, `logs/collector.jsonl`, `logs/cli.jsonl`.
- Watch for events: `feed_failure`, `schema_error`, `result_conflict`,
  `late_result_publication`, `prediction_skipped_result_known`,
  `missing_periods_detected`.

## Backups

Back up `data/hmx.sqlite3` (SQLite WAL mode; use `sqlite3 .backup` or copy all
of `hmx.sqlite3`, `-wal`, `-shm` while stopped). The original Phase 0 CSV/JSON
in `investigation/data/` must remain untouched; `scripts/migrate_phase0.py`
verifies its SHA-256 before and after import.

## Security notes

- Input validation on all imported rows (number range, colour mapping, period
  format); conflicts are logged and never overwrite stored results.
- Rate limiting, `no-store` responses, `X-Content-Type-Options: nosniff`.
- Published predictions are immutable at the database-trigger level. Only the
  controlled `published → evaluated` transition with outcome metadata is legal.
- No secrets in code or repo. CI runs without secrets.

## Source limitations (must be acknowledged)

The public feeds are undocumented, unauthenticated and may change without
notice. They return only the latest 10 results per snapshot, so history is
accumulated over time and gaps are normal and reported. Do not deploy the
undocumented provider integration commercially without authorization from the
source operator; use the CSV import path or an authorized documented feed.
