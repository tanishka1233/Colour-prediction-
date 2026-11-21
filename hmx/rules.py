"""Verified WinGo 1M rules (Phase 0) and strict schema validation."""
from __future__ import annotations

from typing import Any, Iterable

NUMBERS = tuple(range(10))
COLOUR_SETS = {
    0: ("red", "violet"),
    1: ("green",),
    2: ("red",),
    3: ("green",),
    4: ("red",),
    5: ("green", "violet"),
    6: ("red",),
    7: ("green",),
    8: ("red",),
    9: ("green",),
}
# Colour sets may overlap: 0 is red+violet and 5 is green+violet.
# Therefore colour probabilities do NOT sum to 1 across colours.
COLOURS = ("red", "green", "violet")
SIZES = ("Small", "Big")


class ValidationError(ValueError):
    pass


def colour_for(number: int) -> str:
    n = _as_number(number)
    return ",".join(COLOUR_SETS[n])


def size_for(number: int) -> str:
    return "Big" if _as_number(number) > 4 else "Small"


def _as_number(value: Any) -> int:
    if isinstance(value, bool):
        raise ValidationError("boolean is not a valid result number")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"invalid result number: {value!r}") from None
    if n not in NUMBERS:
        raise ValidationError(f"result number out of range 0-9: {n}")
    return n


def normalize_colour(value: Any) -> str:
    """Normalize a feed colour string to canonical 'red,violet' style."""
    if not isinstance(value, str):
        raise ValidationError(f"colour must be a string: {value!r}")
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    found = [c for c in COLOURS if c in parts]
    if not found:
        raise ValidationError(f"unrecognised colour: {value!r}")
    # Preserve canonical ordering (red, green, violet)
    return ",".join(c for c in COLOURS if c in found)


def validate_result(record: dict) -> dict:
    """Validate and normalize a raw result record. Raises ValidationError."""
    if not isinstance(record, dict):
        raise ValidationError("result record must be an object")
    period = str(record.get("period_id") or record.get("issueNumber") or "").strip()
    if len(period) != 17 or not period.isdigit():
        raise ValidationError(f"invalid period_id: {period!r}")
    number = _as_number(record.get("result_number", record.get("number")))
    expected_colour = colour_for(number)
    server_colour = record.get("result_colour", record.get("color"))
    normalized = normalize_colour(server_colour) if server_colour else expected_colour
    if normalized != expected_colour:
        raise ValidationError(
            f"colour mismatch for number {number}: server={normalized!r} expected={expected_colour!r}"
        )
    ts = record.get("result_timestamp") or record.get("timestamp") or ""
    if not isinstance(ts, str) or len(ts) < 10:
        raise ValidationError(f"invalid result_timestamp: {ts!r}")
    return {
        "period_id": period,
        "result_number": number,
        "result_colour": expected_colour,
        "result_size": size_for(number),
        "result_timestamp": ts,
        "source_url": str(record.get("source_url") or ""),
        "retrieved_at": str(record.get("retrieved_at") or ""),
        "verification_status": str(record.get("verification_status") or "validated"),
    }


def missing_periods(period_ids: Iterable[str]) -> list[tuple[str, str, int]]:
    """Find gaps between consecutive 17-digit IDs sharing the same prefix."""
    ids = sorted(set(str(x) for x in period_ids))
    gaps: list[tuple[str, str, int]] = []
    for a, b in zip(ids, ids[1:]):
        if len(a) != 17 or len(b) != 17 or not a.isdigit() or not b.isdigit():
            continue
        if a[:13] != b[:13]:  # date + family + interval part must match
            continue
        sa, sb = int(a[-4:]), int(b[-4:])
        if sb > sa + 1:
            gaps.append((a, b, sb - sa - 1))
    return gaps
