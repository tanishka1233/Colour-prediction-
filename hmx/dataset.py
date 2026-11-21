"""Phase 3.1 dataset profiling, quality checks and safe metadata exports."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from .rules import COLOUR_SETS, NUMBERS, colour_for, missing_periods, size_for
from .stats import counter_stats

FIELDS = ["period_id", "result_number", "result_colour", "result_size",
          "result_timestamp", "source_url", "retrieved_at", "verification_status"]


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def profile(rows: list[dict]) -> dict:
    """Descriptive dataset-quality profile. No result is modified."""
    ordered = sorted(rows, key=lambda r: str(r["period_id"]))
    ids = [str(r["period_id"]) for r in ordered]
    numbers = [int(r["result_number"]) for r in ordered]
    colours = [str(r["result_colour"]) for r in ordered]
    sizes = [str(r["result_size"]) for r in ordered]
    gaps = missing_periods(ids)

    invalid = []
    for r in ordered:
        n = int(r["result_number"])
        if (n not in NUMBERS or r["result_colour"] != colour_for(n)
                or r["result_size"] != size_for(n) or len(str(r["period_id"])) != 17):
            invalid.append(r["period_id"])

    seq = [int(p[-4:]) for p in ids if len(p) == 17 and p[:13] == (ids[0][:13] if ids else "")]
    longest = 1 if seq else 0
    cur = 1 if seq else 0
    for a, b in zip(seq, seq[1:]):
        cur = cur + 1 if b == a + 1 else 1
        longest = max(longest, cur)

    sources = Counter(r.get("source_url", "") for r in ordered)
    retrieved = sorted(str(r.get("retrieved_at", "")) for r in ordered if r.get("retrieved_at"))
    total_span = (int(ids[-1][-4:]) - int(ids[0][-4:]) + 1) if len(ids) >= 2 else len(ids)
    return {
        "generated_at": _iso(),
        "total_records": len(ordered),
        "earliest_period": ids[0] if ids else None,
        "latest_period": ids[-1] if ids else None,
        "period_span": total_span,
        "missing_periods": gaps,
        "missing_period_count": sum(g[2] for g in gaps),
        "coverage_pct": round(100.0 * len(ordered) / total_span, 2) if total_span else None,
        "longest_continuous_sequence": longest,
        "duplicate_period_count": len(ids) - len(set(ids)),
        "conflicting_result_count": 0,  # uniqueness constraint prevents stored conflicts
        "invalid_result_count": len(invalid),
        "invalid_periods": invalid,
        "number_distribution": counter_stats(numbers, list(NUMBERS)),
        "colour_distribution": counter_stats(colours, ["red", "green", "red,violet", "green,violet"]),
        "size_distribution": counter_stats(sizes, ["Small", "Big"]),
        "odd_even_distribution": counter_stats([n % 2 for n in numbers], [0, 1]),
        "sources": dict(sources),
        "retrieved_at_min": retrieved[0] if retrieved else None,
        "retrieved_at_max": retrieved[-1] if retrieved else None,
        "mapping_verification": {
            "odd_green_even_red": all(
                colour_for(n) == ("red,violet" if n == 0 else
                                  "green,violet" if n == 5 else
                                  "green" if n % 2 else "red") for n in NUMBERS),
            "zero_red_violet": COLOUR_SETS[0] == ("red", "violet"),
            "five_green_violet": COLOUR_SETS[5] == ("green", "violet"),
            "small_0_4_big_5_9": all(size_for(n) == ("Small" if n <= 4 else "Big") for n in NUMBERS),
            "stored_rows_conform": not invalid,
        },
        "limitations": [
            "Public feed exposes only the latest 10 results; gaps are expected.",
            "Missing periods are reported, never filled with invented data.",
            "Small samples make distribution tests low-powered.",
        ],
    }


def export_csv_with_metadata(rows: Iterable[dict], metadata: dict) -> str:
    lines = [f"# {k}: {json.dumps(v, ensure_ascii=False)}" for k, v in metadata.items()]
    lines.append(",".join(FIELDS))
    for row in rows:
        import csv, io
        buf = io.StringIO()
        csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore").writerow(
            {k: row.get(k, "") for k in FIELDS})
        lines.append(buf.getvalue().rstrip("\n"))
    return "\n".join(lines) + "\n"


def export_json_with_metadata(rows: Iterable[dict], metadata: dict) -> str:
    return json.dumps({"metadata": metadata,
                       "records": [{k: r.get(k, "") for k in FIELDS} for r in rows]},
                      indent=2, ensure_ascii=False)


def export_metadata(rows: list[dict]) -> dict:
    p = profile(rows)
    return {
        "dataset_generation_time": p["generated_at"],
        "record_count": p["total_records"],
        "period_range": [p["earliest_period"], p["latest_period"]],
        "data_source": p["sources"],
        "validation_summary": {
            "invalid": p["invalid_result_count"],
            "duplicates": p["duplicate_period_count"],
            "conflicts": p["conflicting_result_count"],
            "missing_periods": p["missing_period_count"],
            "coverage_pct": p["coverage_pct"],
        },
    }
