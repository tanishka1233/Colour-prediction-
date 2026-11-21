# Local Runtime Guide (your phone / computer)

The local app is the most important part. It works **without GitHub Actions**.

## Start the app

```bash
cd /storage/emulated/0/AIProjects/prediction-ai   # your project folder
python3 scripts/migrate_phase0.py                 # only needed once
python3 -m hmx.cli serve
```

Then open `http://127.0.0.1:8765` in a browser.

## Start automatic local collection

Option A — collector inside the web server:

```bash
HMX_COLLECTOR_AUTOSTART=1 python3 -m hmx.cli serve
```

Option B — collector alone in another terminal:

```bash
python3 -m hmx.cli collect-loop
```

Press `Ctrl-C` to stop. The collector waits politely (at least 60 seconds between
requests to each feed) and stops safely.

## One-off actions

```bash
python3 -m hmx.cli collect-once       # one polite cycle: results + prediction + reconciliation
python3 -m hmx.cli collect-history    # history-only collection summary
python3 -m hmx.cli db-check           # database health
python3 -m hmx.cli backup             # make a safe copy of the database
python3 -m hmx.cli stats              # full prediction/evaluation report
python3 -m hmx.cli status             # feed health and collector state
```

## How predictions are made locally

1. Results are collected from the read-only public feed and stored in SQLite.
2. Each result is validated (number 0–9, colour mapping, period ID, no duplicates).
3. The current period is read from the server. We never guess future period IDs.
4. A prediction is created using **only results older than that period**.
5. The prediction is saved immediately with its creation time and marked late if needed.
6. When the real result appears, the prediction is reconciled and evaluated once.
7. Late predictions are excluded from valid accuracy numbers.

If the feed is down, the app uses the data already in SQLite. Nothing is lost.
After a restart, ETag and the polling timer are restored from the database.

## Stop/start safely

- Stop with `Ctrl-C`; no destructive action occurs.
- Never delete `data/hmx.sqlite3` manually. Use `backup` first.
- If you want a clean test, set a different database path with `HMX_DB_PATH`.

## Common problems

| Problem | What to do |
|---|---|
| "backend offline" in the page | The `serve` command is not running. |
| Feed idle / offline | Internet may be down; local data still works. |
| No prediction yet | Need at least 30 stored results (configurable). |
| Accuracy shows "insufficient data" | Too few evaluated predictions; keep collecting. |
| Database check fails | Stop the app, run `backup`, then investigate. |
