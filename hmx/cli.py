"""Command-line entry points (no external dependencies)."""
from __future__ import annotations

import argparse
import json
import sys

from .app import AppState, serve
from .collector import collect_history_once
from .config import CONFIG
from .db import Store
from .dataset import export_csv_with_metadata, export_json_with_metadata, export_metadata, profile
from .evaluation import evaluation_report, summarize, walk_forward
from .models import MODEL_NAMES
from .research import explore
from .validation import walk_forward_compare
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
    p_ds = sub.add_parser("dataset-report", help="Phase 3.1 dataset quality profile")
    p_ds.add_argument("--output")
    p_exp = sub.add_parser("export-dataset", help="export results with metadata")
    p_exp.add_argument("--format", choices=["csv", "json"], default="json")
    p_exp.add_argument("--output")
    p_res = sub.add_parser("research", help="Phase 3.2 exploratory pattern analysis")
    p_res.add_argument("--output")
    p_cmp = sub.add_parser("model-compare", help="Phase 3.2 chronological model comparison")
    p_cmp.add_argument("--min-train", type=int, default=30)
    p_cmp.add_argument("--output")
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
    elif args.command == "dataset-report":
        text = json.dumps(profile(store.all_results()), indent=2)
        print(text)
        if args.output:
            from pathlib import Path
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    elif args.command == "export-dataset":
        rows = store.all_results()
        meta = export_metadata(rows)
        text = export_csv_with_metadata(rows, meta) if args.format == "csv" else export_json_with_metadata(rows, meta)
        if args.output:
            from pathlib import Path
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(json.dumps({"output": str(out), "records": len(rows), "format": args.format}, indent=2))
        else:
            print(text)
    elif args.command == "research":
        text = json.dumps(explore(store.all_results()), indent=2)
        print(text)
        if args.output:
            from pathlib import Path
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    elif args.command == "model-compare":
        text = json.dumps(walk_forward_compare(
            store.all_results(), min_train=args.min_train,
            config={"min_history": CONFIG.min_history, "analysis_window": CONFIG.analysis_window,
                    "recency_tau": CONFIG.recency_tau, "dirichlet_alpha": CONFIG.dirichlet_alpha,
                    "weights": CONFIG.engine_weights}), indent=2)
        print(text)
        if args.output:
            from pathlib import Path
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
