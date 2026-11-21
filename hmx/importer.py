"""CSV / JSON import and export for the results store."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .db import Store
from .rules import validate_result

FIELDS = [
    "period_id", "result_number", "result_colour", "result_size",
    "result_timestamp", "source_url", "retrieved_at", "verification_status",
]


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "period_id" not in reader.fieldnames:
        raise ValueError("CSV must contain a period_id column")
    return [dict(row) for row in reader]


def parse_json(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        rows = data.get("records", data.get("data", []))
    else:
        rows = data
    if not isinstance(rows, list):
        raise ValueError("JSON must contain a list of records")
    return rows


def export_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in FIELDS})
    return out.getvalue()


def export_json(rows: list[dict]) -> str:
    return json.dumps({"records": [{k: r.get(k, "") for k in FIELDS} for r in rows]}, indent=2)


def import_rows(store: Store, rows: list[dict], *, default_source: str = "manual_import") -> dict:
    stats = {"inserted": 0, "duplicate": 0, "conflict": 0, "invalid": 0, "errors": []}
    for idx, raw in enumerate(rows, 1):
        prepared = dict(raw)
        if not prepared.get("source_url"):
            prepared["source_url"] = default_source
        try:
            validate_result(prepared)
        except ValueError as exc:
            stats["invalid"] += 1
            stats["errors"].append(f"row {idx}: {exc}")
            continue
        outcome = store.insert_result(prepared)
        stats[outcome] += 1
    return stats


def import_file(store: Store, path: str | Path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    rows = parse_csv(text) if p.suffix.lower() == ".csv" else parse_json(text)
    return import_rows(store, rows)
