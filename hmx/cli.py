"""Command-line entry points (no external dependencies)."""
from __future__ import annotations

import argparse
import json
import sys

from .app import AppState, serve
from .collector import collect_history_once
from .config import CONFIG
from .db import Store
from .evaluation import evaluation_report, summarize, walk_forward
from .importer import import_file
from .logging_util import JsonLogger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hmx", description="HMX Predictor (read-only)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="initialize/verify database schema (non-destructive)")
    sub.add_parser("serve", help="run the local API + web UI")
    sub.add_parser("collect-once", help="one polite read-only collection cycle")
    sub.add_parser("collect-loop", help="continuous collection (60s minimum interval)")
    p_hist = sub.add_parser("collect-history", help="historical-only read-only collection")
    p_hist.add_argument("--file", help="import a CSV/JSON file instead of the public feed")
    p_hist.add_argument("--output", help="write the collection summary to this JSON file")
    p_import = sub.add_parser("import", help="import a result CSV/JSON file")
    p_import.add_argument("path")
    sub.add_parser("status", help="collector + feed health")
    p_bt = sub.add_parser("backtest", help="exploratory chronological walk-forward replay")
    p_bt.add_argument("--min-train", type=int, default=None)
    sub.add_parser("db-check", help="run SQLite integrity and consistency checks")
    p_bk = sub.add_parser("backup", help="create a consistent database backup")
    p_bk.add_argument("--output", help="backup file path")
    p_rs = sub.add_parser("restore", help="restore a database backup")
    p_rs.add_argument("source")
    p_rs.add_argument("--force", action="store_true", help="overwrite a non-empty database")
    sub.add_parser("stats", help="print full prediction/evaluation lifecycle report")
    args = parser.parse_args(argv)

    CONFIG.ensure_dirs()
    store = Store(CONFIG.db_path)
    logger = JsonLogger(CONFIG.log_dir / "cli.jsonl", "cli")

    if args.command == "migrate":
        print(json.dumps({"schema_version": store.integrity_check()["schema_version"],
                          "db": str(CONFIG.db_path), "results": store.result_count()}, indent=2))
    elif args.command == "serve":
        serve()
    elif args.command == "collect-once":
        state = AppState()
        print(json.dumps(state.collector.run_once(), indent=2, default=str))
        state.shutdown()
    elif args.command == "collect-loop":
        state = AppState()
        state.collector.start()
        print("collector running; press Ctrl-C to stop")
        try:
            import time
            while state.collector.health()["running"]:
                time.sleep(2)
        except KeyboardInterrupt:
            state.collector.stop()
    elif args.command == "collect-history":
        if args.file:
            summary = import_file(store, args.file)
            summary["source"] = args.file
            summary["limitation"] = "Imported from local file; no feed polling performed."
        else:
            state = AppState()
            summary = collect_history_once(state.collector.provider, store,
                                           JsonLogger(CONFIG.log_dir / "collector.jsonl", "collector"))
            state.shutdown()
        text = json.dumps(summary, indent=2)
        print(text)
        if args.output:
            from pathlib import Path
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    elif args.command == "import":
        print(json.dumps(import_file(store, args.path), indent=2))
    elif args.command == "status":
        state = AppState()
        print(json.dumps(state.collector.health(), indent=2, default=str))
        state.shutdown()
    elif args.command == "backtest":
        rows = store.all_results()
        evals = walk_forward(rows, min_train=args.min_train)
        print(json.dumps({"exploratory": True, "summary": summarize(evals),
                          "evaluations": evals}, indent=2))
    elif args.command == "db-check":
        result = store.integrity_check()
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    elif args.command == "backup":
        print(json.dumps({"backup": str(store.backup(args.output))}, indent=2))
    elif args.command == "restore":
        print(json.dumps(store.restore(args.source, force=args.force), indent=2))
    elif args.command == "stats":
        predictions = store.get_predictions(1000)
        evaluations = store.get_evaluations(1000)
        wf = summarize(walk_forward(store.all_results()))
        print(json.dumps(evaluation_report(predictions, evaluations, walk_forward_summary=wf), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
