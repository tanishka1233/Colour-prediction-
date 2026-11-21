"""Period transition tracking, pre-result prediction creation and reconciliation."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .engine import EngineConfig, predict
from .evaluation import evaluate
from .providers.wingo_public import PeriodState, Schedule
from .rules import colour_for, size_for


class PeriodTracker:
    """Drives one prediction per server-observed period.

    Future period IDs are NEVER guessed: only `current.issue_number` supplied by
    the public server feed is used. A `next` period from the server is used for
    display/transition awareness only.
    """

    def __init__(self, store, config: EngineConfig | dict | None = None,
                 *, late_threshold_seconds: float = 20.0,
                 late_prediction_seconds: float = 30.0):
        self.store = store
        self.config = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
        self.current_period: str | None = None
        self.current_end_ms: int | None = None
        self.seen: set[str] = set()
        self.pending: dict[str, int] = {}     # period -> end_ms
        self.transitions: list[dict] = []
        self.late_threshold_ms = int(late_threshold_seconds * 1000)
        self.late_prediction_ms = int(late_prediction_seconds * 1000)

    # ---------- observation ----------
    def observe(self, current: PeriodState, schedule: Schedule | None,
                *, now_ms: int | None = None, latest_result_period: str | None = None) -> list[dict]:
        """Call on every successful current-period fetch. Returns created predictions.

        `latest_result_period` must include results observed in the *same* feed
        snapshot, so a prediction is never created for a period whose result is
        already known.
        """
        now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        created: list[dict] = []
        issue = current.issue_number

        if issue != self.current_period:
            self.current_period = issue
            self.current_end_ms = current.end_ms
            self.transitions.append({"from": self._previous_observed(), "to": issue,
                                     "at_ms": now_ms, "source": "server_current"})
            if issue not in self.seen:
                self.seen.add(issue)
                created.extend(self._create_prediction(issue, current.start_ms, current.end_ms,
                                                       now_ms, latest_result_period=latest_result_period))
        elif schedule and schedule.next and now_ms >= current.end_ms:
            # Server has a next period but current feed has not advanced yet.
            # Do not invent or pre-create the next period's prediction.
            self.store.log_event("INFO", "awaiting_server_transition",
                                 current=issue, next_issue=schedule.next.issue_number,
                                 end_ms=current.end_ms)
        return created

    def _previous_observed(self) -> str | None:
        return self.transitions[-1]["to"] if self.transitions else None

    def _create_prediction(self, period_id: str, start_ms: int, end_ms: int, now_ms: int,
                           latest_result_period: str | None = None) -> list[dict]:
        store_latest = self.store.latest_period()
        latest_snapshot = max(filter(None, [store_latest, latest_result_period]), default=None)
        # Result already published for this period -> predicting it would leak.
        if latest_snapshot and latest_snapshot >= period_id:
            self.store.log_event("INFO", "prediction_skipped_result_known",
                                 period_id=period_id, latest_result=latest_snapshot)
            return []
        # Guard cutoff is the newest result known to the feed snapshot; the
        # *recorded* cutoff must be the newest result actually stored and used.
        results = self.store.all_results()
        if latest_snapshot:
            results = [r for r in results if str(r["period_id"]) <= latest_snapshot]
        cutoff = results[-1]["period_id"] if results else None
        prediction = predict(results, self.config, data_cutoff_period=cutoff)
        if prediction.status != "ok":
            self.store.log_event("WARN", "prediction_insufficient_data",
                                 period_id=period_id, sample_count=prediction.sample_count)
            return []
        digest = hashlib.sha256(
            f"{period_id}|{prediction.dataset_version}|{prediction.algorithm_version}".encode()
        ).hexdigest()[:16]
        age_ms = max(0, now_ms - start_ms)
        is_late = age_ms > self.late_prediction_ms
        if is_late:
            self.store.log_event("WARN", "late_prediction_created", period_id=period_id,
                                 seconds_after_start=age_ms / 1000)
        record = {
            "is_late": int(is_late),
            "created_after_start_ms": age_ms,
            "prediction_id": f"prd-{digest}",
            "period_id": period_id,
            "created_at": datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(timespec="seconds"),
            "data_cutoff_period": cutoff or "",
            "dataset_version": prediction.dataset_version,
            "algorithm_version": prediction.algorithm_version,
            "number_probs": prediction.number_probs,
            "colour_probs": prediction.colour_probs,
            "big_prob": prediction.big_prob,
            "small_prob": prediction.small_prob,
            "selected_number": prediction.selected_number,
            "selected_colour": prediction.selected_colour,
            "selected_size": prediction.selected_size,
            "sample_count": prediction.sample_count,
            "model_config": prediction.model_config,
            "prediction_status": "draft",
        }
        outcome = self.store.insert_prediction(record)
        if outcome == "inserted":
            self.store.publish_prediction(period_id)
            self.pending[period_id] = end_ms
            self.store.log_event("INFO", "prediction_published",
                                 period_id=period_id, cutoff=cutoff,
                                 sample_count=prediction.sample_count,
                                 selected_number=prediction.selected_number)
            return [record]
        self.store.log_event("INFO", "prediction_duplicate", period_id=period_id)
        return []

    # ---------- reconciliation ----------
    def reconcile(self, result_records: list[dict], *, now_ms: int | None = None) -> list[dict]:
        """Evaluate published predictions when their actual results arrive."""
        now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        evaluated: list[dict] = []
        for result in result_records:
            period_id = result["period_id"]
            prediction = self.store.get_prediction(period_id)
            if not prediction:
                # Only report a problem if we were actively watching this period.
                if self.seen and period_id > min(self.seen):
                    self.store.log_event("WARN", "result_without_prediction",
                                         period_id=period_id, note="started after publication or insufficient data")
                continue
            if prediction["prediction_status"] != "published":
                continue
            ev = evaluate(prediction, int(result["result_number"]))
            ev["evaluated_at"] = datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(timespec="seconds")
            if self.store.insert_evaluation(ev):
                end_ms = self.pending.pop(period_id, None)
                if end_ms and now_ms - end_ms > self.late_threshold_ms:
                    self.store.log_event("WARN", "late_result_publication",
                                         period_id=period_id, seconds_late=(now_ms - end_ms) / 1000)
                evaluated.append(ev)
                self.store.log_event("INFO", "prediction_evaluated", period_id=period_id,
                                     exact_hit=ev["exact_number_hit"],
                                     colour_hit=ev["colour_hit"], size_hit=ev["size_hit"])
        return evaluated

    def health(self) -> dict:
        return {
            "current_period": self.current_period,
            "current_end_ms": self.current_end_ms,
            "observed_periods": len(self.seen),
            "transitions": self.transitions[-5:],
            "pending_predictions": len(self.pending),
            "late_threshold_seconds": self.late_threshold_ms / 1000,
            "late_prediction_seconds": self.late_prediction_ms / 1000,
        }
