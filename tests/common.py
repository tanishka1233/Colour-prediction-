"""Shared test helpers. Synthetic fixtures here are clearly isolated unit-test data."""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hmx.db import Store


def temp_store() -> tuple[Store, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    return Store(Path(tmp.name) / "test.sqlite3"), tmp


def synthetic_result(period_id: str, number: int) -> dict:
    from hmx.rules import colour_for, size_for
    end = datetime.strptime(period_id[:8], "%Y%m%d").replace(tzinfo=timezone.utc) + timedelta(minutes=int(period_id[-4:]))
    return {"period_id": period_id, "result_number": number,
            "result_colour": colour_for(number), "result_size": size_for(number),
            "result_timestamp": end.isoformat().replace("+00:00", "Z"),
            "source_url": "synthetic://unit-test", "retrieved_at": "2026-11-21T05:00:00Z",
            "verification_status": "synthetic_unit_test_fixture"}


def synthetic_series(start_seq: int, numbers: list[int], date: str = "20261121") -> list[dict]:
    return [synthetic_result(f"{date}10001{seq:04d}", n) for seq, n in zip(range(start_seq, start_seq + len(numbers)), numbers)]


PHASE0_CSV = Path(__file__).resolve().parent.parent / "investigation" / "data" / "wingo_1m_history.csv"
