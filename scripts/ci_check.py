#!/usr/bin/env python3
"""Lightweight configuration + database validation for CI/maintenance runners.

Uses a TEMPORARY database; never assumes a persistent SQLite file exists.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hmx.config import Config  # noqa: E402
from hmx.db import Store  # noqa: E402
from hmx.importer import import_file  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        cfg = Config(data_dir=base / "data", log_dir=base / "logs",
                     db_path=base / "data" / "ci.sqlite3", provider_enabled=False,
                     collector_autostart=False)
        cfg.ensure_dirs()
        store = Store(cfg.db_path)
        check = store.integrity_check()
        sample = ROOT / "investigation" / "data" / "wingo_1m_history.csv"
        imported = import_file(store, sample) if sample.is_file() else None
        after = store.integrity_check()
        report = {
            "ts": check["ts"],
            "config": {"game_code": cfg.game_code,
                       "poll_interval_seconds": cfg.poll_interval_seconds,
                       "provider_enabled": cfg.provider_enabled,
                       "min_history": cfg.min_history},
            "fresh_db_integrity": check,
            "phase0_import": imported,
            "after_import_integrity": after,
            "ok": check["ok"] and after["ok"] and (imported is None or imported["invalid"] == 0),
        }
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
