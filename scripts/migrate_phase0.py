#!/usr/bin/env python3
"""Import the immutable Phase 0 dataset into the HMX database.

The original investigation files are opened read-only and verified by hash
before/after. No Phase 0 artifact is modified.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hmx.config import CONFIG  # noqa: E402
from hmx.db import Store  # noqa: E402
from hmx.importer import import_file  # noqa: E402
from hmx.rules import missing_periods  # noqa: E402

SOURCE = ROOT / "investigation" / "data" / "wingo_1m_history.csv"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    CONFIG.ensure_dirs()
    before = sha(SOURCE)
    store = Store(CONFIG.db_path)
    stats = import_file(store, SOURCE)
    after = sha(SOURCE)
    rows = store.all_results()
    report = {
        "source": str(SOURCE),
        "source_hash_before": before,
        "source_hash_after": after,
        "source_unchanged": before == after,
        "import_stats": stats,
        "stored_results": len(rows),
        "range": [rows[0]["period_id"], rows[-1]["period_id"]] if rows else [],
        "missing_periods": missing_periods(r["period_id"] for r in rows),
    }
    out = ROOT / "data" / "phase0_import_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if before == after and stats["invalid"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
