"""Chronological evaluation metrics. No future outcome is ever used for training."""
from __future__ import annotations

import math
from typing import Iterable

from .engine import EngineConfig, predict
from .rules import COLOUR_SETS

UNIFORM_LOG_LOSS = math.log(10.0)
UNIFORM_BRIER = 0.9


def evaluate(prediction: dict, actual_number: int) -> dict:
    """Evaluate one stored prediction against the observed result."""
    if prediction.get("selected_number") is None:
        raise ValueError("insufficient-data prediction cannot be evaluated")
    probs = {int(k): float(v) for k, v in prediction["number_probs"].items()}
    p_actual = max(1e-12, probs[actual_number])
    log_loss = -math.log(p_actual)
    brier = sum(p * p for p in probs.values()) - 2.0 * p_actual + 1.0
    actual_colours = set(COLOUR_SETS[actual_number])
    predicted_colours = {c for c, _ in prediction["colour_probs"].items() if _ > 0}
    # A colour is "hit" when it is among the predicted top colours (argmax tie-aware).
    top_colour = prediction.get("selected_colour")
    calibration = {
        "predicted_selected": probs[prediction["selected_number"]],
        "actual_number": actual_number,
        "selected_correct": int(actual_number == prediction["selected_number"]),
        "bucket": min(9, int(probs[prediction["selected_number"]] * 10)),
    }
    return {
        "prediction_id": prediction["prediction_id"],
        "period_id": prediction["period_id"],
        "actual_number": actual_number,
        "exact_number_hit": int(actual_number == prediction["selected_number"]),
        "colour_hit": int(top_colour in actual_colours) if top_colour else 0,
        "size_hit": int(prediction["selected_size"] == ("Big" if actual_number > 4 else "Small")),
        "log_loss": log_loss,
        "brier_score": brier,
        "baseline_log_loss": UNIFORM_LOG_LOSS,
        "baseline_brier": UNIFORM_BRIER,
        "calibration": calibration,
        "late": int(prediction.get("is_late", 0) or 0),
        "evaluated_at": prediction.get("evaluated_at") or "",
    }


def walk_forward(results: list[dict], config: EngineConfig | dict | None = None,
                 min_train: int | None = None) -> list[dict]:
    """Exploratory chronological replay.

    For each target period t, train ONLY on periods < t. This function never
    reads a result at or after t when constructing the prediction. Results are
    labeled exploratory and must not be used as live accuracy claims.
    """
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    ordered = sorted(results, key=lambda r: str(r["period_id"]))
    start = min_train if min_train is not None else cfg.min_history
    out = []
    for idx in range(start, len(ordered)):
        target = ordered[idx]
        past = ordered[:idx]
        p = predict(past, cfg, data_cutoff_period=past[-1]["period_id"])
        if p.status != "ok":
            continue
        record = {
            "prediction_id": f"backtest-{target['period_id']}",
            "period_id": target["period_id"],
            "number_probs": {str(k): v for k, v in p.number_probs.items()},
            "colour_probs": p.colour_probs,
            "selected_number": p.selected_number,
            "selected_colour": p.selected_colour,
            "selected_size": p.selected_size,
        }
        ev = evaluate(record, int(target["result_number"]))
        ev["exploratory"] = True
        out.append(ev)
    return out


def summarize(evaluations: Iterable[dict], *, include_late: bool = False) -> dict:
    """Summarize evaluations. Late-created predictions are excluded by default."""
    all_evs = list(evaluations)
    late = [e for e in all_evs if e.get("late")]
    evs = all_evs if include_late else [e for e in all_evs if not e.get("late")]
    if not evs:
        return {
            "count": 0, "evaluated": 0, "late_excluded": len(late),
            "exact_accuracy": None, "colour_accuracy": None, "size_accuracy": None,
            "mean_log_loss": None, "mean_brier": None,
            "baseline_log_loss": UNIFORM_LOG_LOSS, "baseline_brier": UNIFORM_BRIER,
            "calibration": [], "insufficient_data": True,
            "note": "No valid evaluated predictions yet (late predictions excluded).",
        }
    n = len(evs)
    buckets: dict[int, list[int]] = {}
    for e in evs:
        b = e.get("calibration", {}).get("bucket")
        if b is None:
            continue
        buckets.setdefault(int(b), []).append(int(e.get("exact_number_hit", 0)))
    calibration = [{"bucket": b, "count": len(v), "hit_rate": sum(v) / len(v)}
                   for b, v in sorted(buckets.items())]
    return {
        "count": n,
        "evaluated": n,
        "late_excluded": len(late),
        "correct_number": sum(e["exact_number_hit"] for e in evs),
        "incorrect_number": n - sum(e["exact_number_hit"] for e in evs),
        "correct_colour": sum(e["colour_hit"] for e in evs),
        "correct_size": sum(e["size_hit"] for e in evs),
        "exact_accuracy": sum(e["exact_number_hit"] for e in evs) / n,
        "colour_accuracy": sum(e["colour_hit"] for e in evs) / n,
        "size_accuracy": sum(e["size_hit"] for e in evs) / n,
        "mean_log_loss": sum(e["log_loss"] for e in evs) / n,
        "mean_brier": sum(e["brier_score"] for e in evs) / n,
        "baseline_log_loss": UNIFORM_LOG_LOSS,
        "baseline_brier": UNIFORM_BRIER,
        "calibration": calibration,
        "insufficient_data": n < 30,
        "note": ("Too few evaluated predictions for meaningful accuracy claims."
                 if n < 30 else
                 "Descriptive metrics only; no guarantee of predictive advantage."),
    }


def evaluation_report(predictions: list[dict], evaluations: list[dict],
                      *, min_samples: int = 30, walk_forward_summary: dict | None = None) -> dict:
    """Full lifecycle report: totals, pending, late exclusion, metrics and baseline."""
    valid = [e for e in evaluations if not e.get("late")]
    late_created = sum(1 for p in predictions if p.get("is_late"))
    evaluated_ids = {e.get("period_id") for e in evaluations}
    pending = [p for p in predictions if p.get("period_id") not in evaluated_ids]
    report = summarize(evaluations, include_late=False)
    report.update({
        "total_predictions": len(predictions),
        "evaluated_predictions": len(evaluations),
        "pending_predictions": len(pending),
        "late_predictions_created": late_created,
        "late_evaluations_excluded": len(evaluations) - len(valid),
        "minimum_samples_for_claims": min_samples,
        "walk_forward": walk_forward_summary,
        "lifecycle": (
            "1 results collected -> 2 validated -> 3 stored -> 4 server period read "
            "-> 5 prediction from past data only -> 6 persisted -> 7 result reconciled "
            "-> 8 evaluated chronologically"
        ),
        "disclaimer": "Statistical analysis and experimental predictions. Results are random; "
                      "predictions are not guaranteed.",
    })
    return report
