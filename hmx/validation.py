"""Strict chronological walk-forward model comparison (Phase 3.2).

Training data for target period t is ALWAYS restricted to periods < t.
No shuffling, no random splits, no future outcomes in training.
"""
from __future__ import annotations

import math
from typing import Sequence

from .engine import EngineConfig, UNIFORM
from .evaluation import evaluate, summarize
from .models import MODEL_NAMES, MODEL_VERSION, derive_outputs, model_probs
from .stats import benjamini_hochberg, paired_bootstrap_ci

BASELINE = "uniform"


def _metrics_from_probs(probs: dict, actual: int, period_id: str) -> dict:
    out = derive_outputs(probs)
    record = {
        "prediction_id": f"wf-{period_id}",
        "period_id": period_id,
        "number_probs": out["number_probs"],
        "colour_probs": out["colour_probs"],
        "selected_number": out["selected_number"],
        "selected_colour": out["selected_colour"],
        "selected_size": out["selected_size"],
    }
    return evaluate(record, actual)


def walk_forward_compare(
    results: list[dict],
    *,
    models: Sequence[str] = MODEL_NAMES,
    config: EngineConfig | dict | None = None,
    min_train: int = 30,
    window_size: int | None = None,
    segments: int = 3,
    min_samples_for_selection: int = 100,
) -> dict:
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    models = tuple(dict.fromkeys([BASELINE, *models]))  # baseline is always required
    ordered = sorted(results, key=lambda r: str(r["period_id"]))
    n = len(ordered)
    if n <= min_train:
        return {"evaluation_count": 0, "decision": "insufficient_data",
                "note": f"Need more than {min_train} records for walk-forward evaluation."}

    per_model: dict[str, list[dict]] = {m: [] for m in models}
    for idx in range(min_train, n):
        target = ordered[idx]
        train = ordered[:idx]
        if window_size and window_size > 0:
            train = train[-window_size:]
        cutoff = train[-1]["period_id"]
        numbers = [int(r["result_number"]) for r in train]
        actual = int(target["result_number"])
        for name in models:
            probs = dict(UNIFORM) if name == BASELINE else model_probs(name, numbers, cfg)
            ev = _metrics_from_probs(probs, actual, target["period_id"])
            ev["data_cutoff_period"] = cutoff
            ev["training_size"] = len(numbers)
            per_model[name].append(ev)

    base = per_model.get(BASELINE, [])
    base_ll = [e["log_loss"] for e in base]
    base_brier = [e["brier_score"] for e in base]
    evaluation_count = len(base)

    comparison = {}
    for name, evals in per_model.items():
        if not evals:
            continue
        ll = [e["log_loss"] for e in evals]
        brier = [e["brier_score"] for e in evals]
        ll_diff = [a - b for a, b in zip(ll, base_ll)]      # negative = better
        brier_diff = [a - b for a, b in zip(brier, base_brier)]
        ece = _expected_calibration_error(evals)
        seg_stats = []
        step = max(1, evaluation_count // segments)
        for s in range(0, evaluation_count, step):
            chunk = evals[s:s + step]
            bchunk = base[s:s + step]
            if not chunk:
                continue
            seg_stats.append({
                "start_index": s, "size": len(chunk),
                "log_loss": round(sum(e["log_loss"] for e in chunk) / len(chunk), 4),
                "baseline_log_loss": round(sum(e["log_loss"] for e in bchunk) / len(bchunk), 4),
                "beats_baseline_log_loss": sum(e["log_loss"] for e in chunk) < sum(e["log_loss"] for e in bchunk),
            })
        comparison[name] = {
            "evaluation_count": len(evals),
            "exact_accuracy": sum(e["exact_number_hit"] for e in evals) / len(evals),
            "colour_accuracy": sum(e["colour_hit"] for e in evals) / len(evals),
            "size_accuracy": sum(e["size_hit"] for e in evals) / len(evals),
            "mean_log_loss": round(sum(ll) / len(ll), 6),
            "mean_brier": round(sum(brier) / len(brier), 6),
            "log_loss_vs_baseline": round(sum(ll_diff) / len(ll_diff), 6),
            "brier_vs_baseline": round(sum(brier_diff) / len(brier_diff), 6),
            "bootstrap_ci_log_loss_diff": paired_bootstrap_ci(ll_diff),
            "bootstrap_ci_brier_diff": paired_bootstrap_ci(brier_diff),
            "expected_calibration_error": round(ece, 4),
            "segments": seg_stats,
            "summary": summarize(evals),
        }

    # paired bootstrap p-value approximation: two-sided from CI crossing zero is
    # conservative; we report the CI and a normal approximation from the mean/SE.
    names = [m for m in comparison if m != BASELINE]
    p_values = []
    for name in names:
        diffs = [a - b for a, b in zip(
            [e["log_loss"] for e in per_model[name]], base_ll)]
        p_values.append(_paired_normal_p(diffs))
    adjusted = benjamini_hochberg(p_values)
    for name, adj in zip(names, adjusted):
        comparison[name]["paired_log_loss_p"] = round(adj["p_value"], 6)
        comparison[name]["paired_log_loss_p_adjusted_bh"] = round(adj["adjusted_p"], 6)

    selected, reasons = None, []
    if evaluation_count >= min_samples_for_selection:
        for name in names:
            c = comparison[name]
            ci = c["bootstrap_ci_log_loss_diff"]
            stable = sum(1 for s in c["segments"] if s["beats_baseline_log_loss"]) >= max(2, segments - 1)
            ok = (c["paired_log_loss_p_adjusted_bh"] < 0.05
                  and ci["upper"] is not None and ci["upper"] < 0
                  and c["expected_calibration_error"] <= 0.10 and stable)
            reasons.append({"model": name, "meets_criteria": bool(ok),
                            "adjusted_p": c["paired_log_loss_p_adjusted_bh"],
                            "ci_upper": ci["upper"], "ece": c["expected_calibration_error"],
                            "stable_segments": stable})
            if ok and selected is None:
                selected = name
    else:
        reasons.append({"model": None, "meets_criteria": False,
                        "reason": f"only {evaluation_count} evaluated predictions; need "
                                  f">= {min_samples_for_selection} for model selection"})

    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "evaluation_count": evaluation_count,
        "min_train": min_train,
        "window_size": window_size,
        "period_range_evaluated": [
            base[0]["period_id"] if base else None,
            base[-1]["period_id"] if base else None],
        "baseline": BASELINE,
        "models": comparison,
        "selection": {
            "selected_model": selected,
            "decision": ("candidate_selected" if selected else
                         "no_predictive_advantage_retain_existing_model"),
            "reasons": reasons,
        },
        "leakage_controls": [
            "records sorted by period_id",
            "training set ends strictly before target period",
            "no shuffling or random splits",
            "cutoff period stored with every evaluation",
        ],
        "limitations": [
            "Small chronological sample gives very low power.",
            "Bootstrap and normal approximations are unreliable at small n.",
            "No significance found does not prove absence of an effect.",
        ],
    }


def _expected_calibration_error(evals: list[dict]) -> float:
    buckets: dict[int, list[float]] = {}
    for e in evals:
        cal = e.get("calibration", {})
        conf, hit = cal.get("predicted_selected"), cal.get("selected_correct")
        if conf is None or hit is None:
            continue
        b = min(9, int(conf * 10))
        buckets.setdefault(b, []).append(float(hit))
    n = sum(len(v) for v in buckets.values())
    if not n:
        return 0.0
    return sum(len(v) / n * abs(sum(v) / len(v) - (b + 0.5) / 10)
               for b, v in buckets.items())


def _paired_normal_p(diffs: list[float]) -> float:
    n = len(diffs)
    if n < 2:
        return 1.0
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    if var <= 0:
        return 1.0
    z = mean / math.sqrt(var / n)
    return min(1.0, max(0.0, math.erfc(abs(z) / math.sqrt(2.0))))
