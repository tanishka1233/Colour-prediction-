# Data Collection Guide

## Where data comes from

Three **public, read-only** objects discovered in Phase 0:

| Purpose | URL (configurable in `.env`) |
|---|---|
| Current period + countdown | `https://maanwin29.com/webapi/kv/issue/WinGo_1M` |
| Schedule (current/next) | `https://draw.ar-lottery01.com/WinGo/WinGo_1M.json` |
| Last 10 results | `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` |

These are undocumented and may change or disappear. They are isolated in `hmx/providers/`.
They are **not** official APIs and must not be used commercially without authorization.

## Collect normally

```bash
python3 -m hmx.cli collect-once       # results + prediction + reconciliation
python3 -m hmx.cli collect-loop       # continuous, polite
```

The collector:
- sends at most one request per feed per minute,
- uses ETag / `If-None-Match`; HTTP 304 means "nothing changed",
- retries transient failures with exponential backoff,
- validates every result before storing,
- records source URL and collection time,
- never invents or guesses period IDs,
- reports duplicate, conflicting and missing periods.

## Collect history only

```bash
python3 -m hmx.cli collect-history --output history_summary.json
```

The summary tells you how many records were new/duplicate/conflicting, and repeats the
important limitation: **this public endpoint only returns the latest 10 results**.
Older history cannot be fetched from it.

## Import a historical file as fallback

```bash
python3 -m hmx.cli import investigation/data/wingo_1m_history.csv
python3 -m hmx.cli collect-history --file my_results.csv
```

CSV must have: `period_id, result_number, result_colour, result_size, result_timestamp,
source_url, retrieved_at, verification_status`. JSON can be a list or `{"records": [...]}`.

Bad rows are rejected. Existing periods are never overwritten.

## Check and protect the database

```bash
python3 -m hmx.cli db-check
python3 -m hmx.cli backup
python3 -m hmx.cli restore path/to/backup.sqlite3 --force   # only on a TEST database
```

`restore` always makes a safety backup first. Without `--force` it refuses to overwrite
a non-empty database.

## Data fields stored

`period_id`, `result_number`, `result_colour`, `result_size`, `result_timestamp`,
`source_url`, `retrieved_at`, `verification_status`.

No cookies, tokens, account data or personal information are stored.
