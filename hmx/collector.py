"""Background read-only collector: fetch -> validate -> persist -> predict -> reconcile."""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from .config import Config
from .db import Store
from .logging_util import JsonLogger, utcnow
from .providers.http import FeedClient
from .providers.wingo_public import (
    WingoPublicProvider, parse_history, parse_kv_issue, parse_schedule,
)
from .rules import missing_periods
from .scheduler import PeriodTracker


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def collect_once(provider: WingoPublicProvider, store: Store, tracker: PeriodTracker | None,
                 logger: JsonLogger | None = None) -> dict:
    """Perform one polite collection cycle. Never raises on feed failure."""
    now_ms = _now_ms()
    current = schedule = history = None
    statuses: dict[str, str] = {}

    # 1. Fetch ALL public snapshots first. No prediction is created until the
    #    result snapshot for this same cycle is known (prevents result leakage).
    fr_kv = provider.current_issue()
    statuses["kv_issue"] = fr_kv.status
    if fr_kv.status == "ok":
        try:
            current = parse_kv_issue(fr_kv.data)
        except Exception as exc:
            statuses["kv_issue"] = "schema_error"
            if logger: logger.warn("schema_error", feed="kv_issue", error=str(exc))

    fr_sched = provider.schedule()
    statuses["schedule"] = fr_sched.status
    if fr_sched.status == "ok":
        try:
            schedule = parse_schedule(fr_sched.data)
        except Exception as exc:
            statuses["schedule"] = "schema_error"
            if logger: logger.warn("schema_error", feed="schedule", error=str(exc))

    fr_hist = provider.history()
    statuses["history"] = fr_hist.status
    raw_results: list[dict] = []
    if fr_hist.status == "ok":
        try:
            raw_results = parse_history(fr_hist.data, source_url=fr_hist.url, retrieved_at=utcnow())
        except Exception as exc:
            statuses["history"] = "schema_error"
            if logger: logger.warn("schema_error", feed="history", error=str(exc))

    snapshot_latest = max((r["period_id"] for r in raw_results), default=None)

    # 2. Observe the server-provided period and create a prediction only if its
    #    result is not already present in the store or in this snapshot.
    if current and tracker:
        try:
            tracker.observe(current, schedule, now_ms=now_ms,
                            latest_result_period=snapshot_latest)
        except Exception as exc:
            if logger: logger.error("scheduler_error", error=str(exc))

    # 3. Persist new results, then reconcile published predictions.
    created: list[dict] = []
    new_results: list[dict] = []
    if raw_results:
        for raw in raw_results:
            outcome = store.insert_result(raw)
            if outcome == "inserted":
                new_results.append(raw)
            elif outcome == "conflict":
                if logger: logger.error("result_conflict", period_id=raw["period_id"])
        if logger and new_results:
            logger.info("results_inserted", count=len(new_results),
                        first=new_results[0]["period_id"], last=new_results[-1]["period_id"])
        if tracker and new_results:
            try:
                created = tracker.reconcile(new_results, now_ms=now_ms)
            except Exception as exc:
                if logger: logger.error("reconcile_error", error=str(exc))

    # 4. persist feed health
    for key in ("kv_issue", "schedule", "history"):
        snap = provider.client.snapshot(key) or {}
        store.set_feed_state(
            key,
            etag=snap.get("etag"),
            last_modified=snap.get("last_modified"),
            last_request_at=snap.get("last"),
            last_request_epoch=snap.get("last_epoch"),
            last_success_at=utcnow() if statuses.get(key) in ("ok", "not_modified") else None,
            consecutive_failures=snap.get("failures", 0),
            last_status=statuses.get(key),
            last_error=None,
        )

    # 5. missing-period audit (descriptive only, never filled in)
    gaps = missing_periods(r["period_id"] for r in store.all_results())
    if gaps and logger:
        logger.info("missing_periods_detected", gap_count=len(gaps),
                    total_missing=sum(g[2] for g in gaps), last_gap=gaps[-1])

    return {
        "at": utcnow(),
        "statuses": statuses,
        "current": current.to_dict() if current else None,
        "schedule": schedule.to_dict() if schedule else None,
        "new_results": [r["period_id"] for r in new_results],
        "evaluated": [e["period_id"] for e in created],
        "result_count": store.result_count(),
    }


def collect_history_once(provider: WingoPublicProvider, store: Store,
                         logger: JsonLogger | None = None) -> dict:
    """Historical-only collection from the public read-only result feed.

    The feed documents only the latest 10 results; older history is
    unavailable. This function never invents or guesses period IDs.
    """
    fr = provider.history()
    summary = {
        "collected_at": utcnow(),
        "source_url": fr.url,
        "http_status": fr.http_status,
        "feed_status": fr.status,
        "snapshot_count": 0,
        "inserted": 0, "duplicate": 0, "conflict": 0, "invalid": 0,
        "new_periods": [], "errors": [],
        "missing_periods": [], "total_stored": store.result_count(),
        "limitation": ("The public feed exposes only the latest 10 results. "
                       "Older history cannot be fetched from this endpoint; "
                       "import a CSV/JSON file as a fallback."),
    }
    if fr.status != "ok" or not isinstance(fr.data, dict):
        summary["errors"].append(fr.error or "no data returned")
        return summary
    try:
        rows = parse_history(fr.data, source_url=fr.url, retrieved_at=utcnow())
    except Exception as exc:
        summary["errors"].append(f"schema error: {exc}")
        return summary
    summary["snapshot_count"] = len(rows)
    for row in rows:
        try:
            outcome = store.insert_result(row)
        except Exception as exc:  # validation failure must not abort the cycle
            summary["invalid"] += 1
            summary["errors"].append(f"{row.get('period_id')}: {exc}")
            continue
        summary[{"inserted": "inserted", "duplicate": "duplicate",
                 "conflict": "conflict"}[outcome]] += 1
        if outcome == "inserted":
            summary["new_periods"].append(row["period_id"])
        elif outcome == "conflict":
            summary["errors"].append(f"conflicting result for {row['period_id']} (kept original)")
    gaps = missing_periods(r["period_id"] for r in store.all_results())
    summary["missing_periods"] = gaps
    summary["missing_period_count"] = sum(g[2] for g in gaps)
    summary["total_stored"] = store.result_count()
    if logger:
        logger.info("history_collection", inserted=summary["inserted"],
                    duplicate=summary["duplicate"], conflict=summary["conflict"],
                    snapshot=summary["snapshot_count"])
    return summary


class Collector:
    """Polite background collector with graceful shutdown."""

    def __init__(self, config: Config, store: Store, *, scheduler: PeriodTracker | None = None,
                 logger: JsonLogger | None = None, client: FeedClient | None = None):
        self.config = config
        self.store = store
        self.logger = logger
        self.tracker = scheduler or PeriodTracker(store, config={
            "min_history": config.min_history,
            "analysis_window": config.analysis_window,
            "recency_tau": config.recency_tau,
            "dirichlet_alpha": config.dirichlet_alpha,
            "weights": config.engine_weights,
        })
        self.client = client or FeedClient(
            min_interval=config.poll_interval_seconds, timeout=config.request_timeout_seconds,
            max_retries=config.max_retries, backoff_base=config.backoff_base_seconds,
            backoff_cap=config.backoff_cap_seconds, logger=logger,
        )
        self.provider = WingoPublicProvider(
            self.client, kv_url=config.kv_issue_url, schedule_url=config.schedule_url,
            history_url=config.history_url,
        )
        # Recover ETag + throttle window from persisted feed health after restart.
        for feed in ("kv_issue", "schedule", "history"):
            row = store.get_feed_state(feed) or {}
            self.client.seed(feed, etag=row.get("etag"),
                             last_request_epoch=row.get("last_request_epoch"))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_cycle: dict | None = None
        self.cycles = 0

    def run_once(self) -> dict:
        self.last_cycle = collect_once(self.provider, self.store, self.tracker, self.logger)
        self.cycles += 1
        return self.last_cycle

    def start(self) -> None:
        if not self.config.provider_enabled:
            if self.logger: self.logger.warn("collector_disabled", reason="HMX_PROVIDER_ENABLED=0")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="hmx-collector", daemon=True)
        self._thread.start()
        if self.logger: self.logger.info("collector_started", interval=self.config.poll_interval_seconds)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self.logger: self.logger.info("collector_stopped")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                if self.logger: self.logger.error("collector_cycle_failed", error=str(exc))
            # wait in small slices so stop() is responsive
            waited = 0.0
            while waited < self.config.poll_interval_seconds and not self._stop.is_set():
                self._stop.wait(min(1.0, self.config.poll_interval_seconds - waited))
                waited += 1.0

    def health(self) -> dict:
        return {
            "enabled": self.config.provider_enabled,
            "running": bool(self._thread and self._thread.is_alive()),
            "cycles": self.cycles,
            "last_cycle": self.last_cycle,
            "tracker": self.tracker.health(),
            "feeds": [dict(r) for r in (
                self.store._conn().execute("SELECT * FROM feed_state ORDER BY feed_key")
            ).fetchall()],
        }
