"""Public Maanwin WinGo result provider.

The three public objects below were identified in Phase 0 and are UNDOCUMENTED,
UNOFFICIAL and FRAGILE. They are isolated here so they can be replaced by an
authorized feed without touching the rest of the application. No credentials,
cookies, login, wagering or write requests are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..rules import ValidationError
from .http import FeedClient, FeedResult


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class PeriodState:
    issue_number: str
    start_ms: int
    end_ms: int
    countdown: int | None = None

    def to_dict(self) -> dict:
        return {"issue_number": self.issue_number, "start_ms": self.start_ms,
                "end_ms": self.end_ms, "countdown": self.countdown}


@dataclass(frozen=True)
class Schedule:
    game_code: str
    state: int
    interval_minutes: float
    previous: PeriodState | None
    current: PeriodState
    next: PeriodState | None

    def to_dict(self) -> dict:
        return {"game_code": self.game_code, "state": self.state,
                "interval_minutes": self.interval_minutes,
                "previous": self.previous.to_dict() if self.previous else None,
                "current": self.current.to_dict(),
                "next": self.next.to_dict() if self.next else None}


def _period(obj: Any, label: str) -> PeriodState | None:
    if not obj:
        return None
    if not isinstance(obj, dict):
        raise SchemaError(f"{label} must be an object")
    issue = str(obj.get("issueNumber") or "")
    if len(issue) != 17 or not issue.isdigit():
        raise SchemaError(f"{label}.issueNumber invalid: {issue!r}")
    try:
        start = int(obj["startTime"]); end = int(obj["endTime"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SchemaError(f"{label} start/end invalid: {exc}") from None
    if end <= start:
        raise SchemaError(f"{label} endTime must be after startTime")
    return PeriodState(issue, start, end)


def parse_kv_issue(payload: dict) -> PeriodState:
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise SchemaError("kv issue response code is not 0")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SchemaError("kv issue data missing")
    state = _period(data, "kv.data")
    if state is None:
        raise SchemaError("kv issue data empty")
    countdown = data.get("countdown")
    try:
        countdown = int(countdown) if countdown is not None else None
    except (TypeError, ValueError):
        countdown = None
    return PeriodState(state.issue_number, state.start_ms, state.end_ms, countdown)


def parse_schedule(payload: dict) -> Schedule:
    if not isinstance(payload, dict):
        raise SchemaError("schedule payload must be an object")
    current = _period(payload.get("current"), "current")
    if current is None:
        raise SchemaError("schedule.current missing")
    try:
        interval = float(payload.get("intervalMinute", 0))
    except (TypeError, ValueError):
        interval = 0.0
    return Schedule(
        game_code=str(payload.get("gameCode") or ""),
        state=int(payload.get("state") or 0),
        interval_minutes=interval,
        previous=_period(payload.get("previous"), "previous"),
        current=current,
        next=_period(payload.get("next"), "next"),
    )


def parse_history(payload: dict, *, source_url: str = "", retrieved_at: str = "") -> list[dict]:
    """Parse a history snapshot into raw result records (timestamps derived from ID)."""
    if not isinstance(payload, dict) or payload.get("code") not in (0, None):
        raise SchemaError("history response code is not 0")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        raise SchemaError("history.data.list missing")
    out = []
    for item in data["list"]:
        if not isinstance(item, dict):
            raise SchemaError("history item must be an object")
        issue = str(item.get("issueNumber") or "")
        if len(issue) != 17 or not issue.isdigit():
            raise SchemaError(f"history issueNumber invalid: {issue!r}")
        # End time is derived ONLY from server-provided issueNumber (Phase 0 verified).
        from datetime import datetime, timedelta, timezone
        from ..rules import COLOUR_SETS, colour_for, size_for
        end = datetime.strptime(issue[:8], "%Y%m%d").replace(tzinfo=timezone.utc) + timedelta(minutes=int(issue[-4:]))
        try:
            number = int(item["number"])
        except (KeyError, TypeError, ValueError):
            raise SchemaError(f"history number invalid: {item.get('number')!r}") from None
        if number not in COLOUR_SETS:
            raise SchemaError(f"history number out of range: {number}")
        raw_colour = item.get("color")
        expected = colour_for(number)
        if raw_colour and str(raw_colour).lower() != expected:
            raise SchemaError(f"history colour mismatch for {issue}: {raw_colour!r} != {expected!r}")
        out.append({
            "period_id": issue,
            "result_number": number,
            "result_colour": expected,
            "result_size": size_for(number),
            "result_timestamp": end.isoformat().replace("+00:00", "Z"),
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "verification_status": "verified_public_feed; timestamp_derived_from_period_id",
        })
    return out


class WingoPublicProvider:
    """Thin wrapper around FeedClient for the three public feeds."""

    def __init__(self, client: FeedClient, *, kv_url: str, schedule_url: str, history_url: str):
        self.client = client
        self.kv_url = kv_url
        self.schedule_url = schedule_url
        self.history_url = history_url

    def current_issue(self) -> FeedResult:
        return self.client.get("kv_issue", self.kv_url)

    def schedule(self) -> FeedResult:
        return self.client.get("schedule", self.schedule_url)

    def history(self) -> FeedResult:
        return self.client.get("history", self.history_url)
