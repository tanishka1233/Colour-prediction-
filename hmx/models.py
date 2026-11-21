"""Lightweight probability models for Phase 3.2 research.

Every model returns a normalized distribution over 0..9. Larger/size and colour
probabilities are always DERIVED from that one joint number distribution, so the
outputs cannot contradict each other. Colour sets for 0 and 5 overlap violet by
design (a number can carry two colours).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, Sequence

from . import engine
from .engine import EngineConfig, Prediction, UNIFORM
from .rules import COLOUR_SETS, COLOURS, NUMBERS

MODEL_VERSION = "hmx-models-1.0.0"
MODEL_NAMES = ("uniform", "frequency", "laplace", "bayesian", "recency",
               "transition", "hybrid")
EPS = 1e-9


def _normalize(values: dict[int, float]) -> dict[int, float]:
    total = sum(max(0.0, float(v)) for v in values.values())
    if total <= 0:
        return dict(UNIFORM)
    out = {i: max(0.0, float(values.get(i, 0.0))) / total for i in NUMBERS}
    out[9] += 1.0 - sum(out.values())
    return {i: round(out[i], 12) for i in NUMBERS}


def model_probs(name: str, numbers: Sequence[int], config: EngineConfig | dict | None = None) -> dict[int, float]:
    """Return P(0..9) for one model from a training sequence only."""
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    nums = [int(n) for n in numbers]
    n = len(nums)
    if name not in MODEL_NAMES:
        raise ValueError(f"unknown model: {name}")
    if n == 0 or name == "uniform":
        return dict(UNIFORM)
    counts = {i: 0 for i in NUMBERS}
    for v in nums:
        counts[v] += 1
    if name == "frequency":
        return _normalize({i: counts[i] / n + EPS for i in NUMBERS})
    if name == "laplace":
        return _normalize({i: counts[i] + 1.0 for i in NUMBERS})
    if name == "bayesian":
        a = max(1e-6, cfg.dirichlet_alpha)
        return _normalize({i: counts[i] + a for i in NUMBERS})
    if name == "recency":
        tau = max(1e-6, cfg.recency_tau)
        weights = {i: 0.0 for i in NUMBERS}
        for idx, value in enumerate(nums):
            age = n - 1 - idx
            weights[value] += math.exp(-age / tau)
        return _normalize(weights)
    if name == "transition":
        last = nums[-1]
        row = {i: 0 for i in NUMBERS}
        for a, b in zip(nums, nums[1:]):
            if a == last:
                row[b] += 1
        total = sum(row.values())
        return _normalize({i: row[i] + 1.0 for i in NUMBERS}) if total else dict(UNIFORM)
    # hybrid: same canonicalised combination as the Phase 1 engine
    methods = {
        "frequency": engine._frequency(counts, n),
        "recency": engine._recency(nums, cfg.recency_tau),
        "transition": engine._transition(nums),
        "bayesian": engine._bayesian(counts, n, cfg.dirichlet_alpha),
    }
    weights = {k: max(0.0, float(cfg.weights.get(k, 0.0))) for k in methods}
    wsum = sum(weights.values())
    if wsum <= 0:
        return dict(UNIFORM)
    return _normalize({i: sum(methods[k][i] * weights[k] for k in methods) / wsum
                       for i in NUMBERS})


def derive_outputs(number_probs: dict[int, float]) -> dict:
    """Derive colour/size outputs and selections from a joint number distribution."""
    p = {int(k): float(v) for k, v in number_probs.items()}
    colour_probs = {c: round(sum(p[i] for i in NUMBERS if c in COLOUR_SETS[i]), 12)
                    for c in COLOURS}
    big = round(sum(p[i] for i in range(5, 10)), 12)
    small = round(1.0 - big, 12)
    return {
        "number_probs": p,
        "colour_probs": colour_probs,
        "big_prob": big,
        "small_prob": small,
        "selected_number": max(NUMBERS, key=lambda i: (p[i], -i)),
        "selected_colour": max(COLOURS, key=lambda c: (colour_probs[c], -COLOURS.index(c))),
        "selected_size": "Big" if big >= small else "Small",
    }


def _window_numbers(results: Iterable[dict], cfg: EngineConfig,
                    cutoff: str | None) -> list[int]:
    ordered = sorted(results, key=lambda r: str(r["period_id"]))
    if cutoff:
        ordered = [r for r in ordered if str(r["period_id"]) <= str(cutoff)]
    if cfg.analysis_window > 0:
        ordered = ordered[-cfg.analysis_window:]
    return [int(r["result_number"]) for r in ordered]


def build_prediction(results: list[dict], *, model_name: str = "hybrid",
                     config: EngineConfig | dict | None = None,
                     data_cutoff_period: str | None = None,
                     data_quality_status: str = "unverified",
                     validation_status: str = "unproven") -> Prediction:
    """Build a prediction with explicit model/confidence/validation metadata.

    The hard cutoff is re-applied here; future results cannot enter training.
    """
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    base = engine.predict(results, cfg, data_cutoff_period=data_cutoff_period)
    if base.status != "ok":
        return base
    numbers = _window_numbers(results, cfg, data_cutoff_period)
    probs = model_probs(model_name, numbers, cfg)
    out = derive_outputs(probs)
    confidence = max(probs.values())
    norm_entropy = -sum(p * math.log(p) for p in probs.values() if p > 0) / math.log(10)
    meta = dict(cfg.to_dict())
    meta.update({
        "model_name": model_name,
        "model_version": MODEL_VERSION,
        "model_confidence_top_probability": round(confidence, 6),
        "model_uncertainty_normalized_entropy": round(norm_entropy, 6),
        "confidence_note": "Top probability is not the probability of being correct.",
        "data_quality_status": data_quality_status,
        "validation_status": validation_status,
    })
    return replace(base, number_probs=out["number_probs"],
                   colour_probs=out["colour_probs"], big_prob=out["big_prob"],
                   small_prob=out["small_prob"], selected_number=out["selected_number"],
                   selected_colour=out["selected_colour"], selected_size=out["selected_size"],
                   method_probs={model_name: probs}, model_config=meta)
