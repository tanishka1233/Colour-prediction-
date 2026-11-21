"""Deterministic modular probability engine.

No method claims predictive power. Historical frequency is descriptive only.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Iterable

from .rules import COLOURS, COLOUR_SETS, NUMBERS, SIZES, colour_for, size_for

ALGORITHM_VERSION = "hmx-engine-1.0.0"
UNIFORM = {i: 1.0 / 10 for i in NUMBERS}


@dataclass(frozen=True)
class EngineConfig:
    min_history: int = 30
    analysis_window: int = 200
    recency_tau: float = 40.0
    dirichlet_alpha: float = 1.0
    weights: dict = field(default_factory=lambda: {
        "frequency": 0.30, "recency": 0.30, "transition": 0.20, "bayesian": 0.20,
    })

    @classmethod
    def from_dict(cls, d: dict | None) -> "EngineConfig":
        d = dict(d or {})
        weights = dict(d.pop("weights", {}))
        allowed = {"frequency", "recency", "transition", "bayesian"}
        weights = {k: float(v) for k, v in weights.items() if k in allowed}
        known = {"min_history", "analysis_window", "recency_tau", "dirichlet_alpha"}
        return cls(**{k: v for k, v in d.items() if k in known}, weights=weights or cls().weights)

    def to_dict(self) -> dict:
        return {"min_history": self.min_history, "analysis_window": self.analysis_window,
                "recency_tau": self.recency_tau, "dirichlet_alpha": self.dirichlet_alpha,
                "weights": dict(self.weights)}


@dataclass(frozen=True)
class Prediction:
    status: str                       # ok | insufficient_data
    number_probs: dict[int, float]
    colour_probs: dict[str, float]
    big_prob: float
    small_prob: float
    selected_number: int | None
    selected_colour: str | None
    selected_size: str | None
    sample_count: int
    dataset_version: str
    algorithm_version: str = ALGORITHM_VERSION
    method_probs: dict[str, dict[int, float]] = field(default_factory=dict)
    uniform_baseline: dict[int, float] = field(default_factory=lambda: dict(UNIFORM))
    model_config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "number_probs": {str(k): v for k, v in self.number_probs.items()},
            "colour_probs": dict(self.colour_probs),
            "big_prob": self.big_prob, "small_prob": self.small_prob,
            "selected_number": self.selected_number, "selected_colour": self.selected_colour,
            "selected_size": self.selected_size, "sample_count": self.sample_count,
            "dataset_version": self.dataset_version, "algorithm_version": self.algorithm_version,
            "method_probs": {k: {str(i): p for i, p in v.items()} for k, v in self.method_probs.items()},
            "uniform_baseline": {str(k): v for k, v in self.uniform_baseline.items()},
            "model_config": self.model_config,
        }


def dataset_version(rows: Iterable[dict]) -> str:
    payload = "|".join(f"{r['period_id']}:{r['result_number']}" for r in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize(values: dict[int, float]) -> dict[int, float]:
    total = sum(values.values())
    if total <= 0:
        return dict(UNIFORM)
    out = {i: values.get(i, 0.0) / total for i in NUMBERS}
    # force exact sum of 1.0 while keeping deterministic order
    drift = 1.0 - sum(out.values())
    out[9] += drift
    return out


def _frequency(counts: dict[int, int], n: int) -> dict[int, float]:
    return {i: counts.get(i, 0) / n for i in NUMBERS} if n else dict(UNIFORM)


def _recency(numbers: list[int], tau: float) -> dict[int, float]:
    if not numbers:
        return dict(UNIFORM)
    tau = max(1e-6, float(tau))
    weights = {}
    for idx, number in enumerate(numbers):
        age = len(numbers) - 1 - idx
        weights[number] = weights.get(number, 0.0) + math.exp(-age / tau)
    return _normalize(weights)


def _transition(numbers: list[int]) -> dict[int, float]:
    if len(numbers) < 2:
        return dict(UNIFORM)
    prev = numbers[-1]
    counts = {i: 0 for i in NUMBERS}
    for a, b in zip(numbers, numbers[1:]):
        if a == prev:
            counts[b] += 1
    total = sum(counts.values())
    return {i: (counts[i] + 1.0) / (total + 10.0) for i in NUMBERS}  # Laplace smoothing


def _bayesian(counts: dict[int, int], n: int, alpha: float) -> dict[int, float]:
    a = max(1e-6, float(alpha))
    return {i: (counts.get(i, 0) + a) / (n + 10.0 * a) for i in NUMBERS}


def predict(results: list[dict], config: EngineConfig | dict | None = None,
            *, data_cutoff_period: str | None = None) -> Prediction:
    """Generate a prediction using ONLY results with period_id <= data_cutoff_period.

    This hard cutoff makes future-data leakage impossible even if the caller
    accidentally supplies a larger dataset.
    """
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    ordered = sorted(results, key=lambda r: str(r["period_id"]))
    if data_cutoff_period is not None:
        ordered = [r for r in ordered if str(r["period_id"]) <= str(data_cutoff_period)]
    window = ordered[-cfg.analysis_window:] if cfg.analysis_window > 0 else ordered
    numbers = [int(r["result_number"]) for r in window]
    version = dataset_version(ordered)
    model_config = cfg.to_dict()

    if len(numbers) < cfg.min_history:
        return Prediction(
            status="insufficient_data", number_probs=dict(UNIFORM),
            colour_probs={c: sum(UNIFORM[i] for i in NUMBERS if c in COLOUR_SETS[i]) for c in COLOURS},
            big_prob=sum(UNIFORM[i] for i in range(5, 10)),
            small_prob=sum(UNIFORM[i] for i in range(5)),
            selected_number=None, selected_colour=None, selected_size=None,
            sample_count=len(numbers), dataset_version=version,
            model_config=model_config,
        )

    counts = {i: 0 for i in NUMBERS}
    for n in numbers:
        counts[n] += 1
    methods = {
        "frequency": _frequency(counts, len(numbers)),
        "recency": _recency(numbers, cfg.recency_tau),
        "transition": _transition(numbers),
        "bayesian": _bayesian(counts, len(numbers), cfg.dirichlet_alpha),
    }
    weights = {k: max(0.0, float(cfg.weights.get(k, 0.0))) for k in methods}
    wsum = sum(weights.values())
    if wsum <= 0:
        combined = dict(UNIFORM)
    else:
        combined = _normalize({
            i: sum(methods[k][i] * weights[k] for k in methods) / wsum for i in NUMBERS
        })
    combined = {i: round(combined[i], 12) for i in NUMBERS}
    drift = 1.0 - sum(combined.values())
    combined[9] = round(combined[9] + drift, 12)

    colour_probs = {
        c: round(sum(combined[i] for i in NUMBERS if c in COLOUR_SETS[i]), 12) for c in COLOURS
    }
    big = round(sum(combined[i] for i in range(5, 10)), 12)
    small = round(1.0 - big, 12)
    selected_number = max(NUMBERS, key=lambda i: (combined[i], -i))
    selected_colour = max(COLOURS, key=lambda c: (colour_probs[c], -COLOURS.index(c)))
    selected_size = "Big" if big >= small else "Small"

    return Prediction(
        status="ok", number_probs=combined, colour_probs=colour_probs,
        big_prob=big, small_prob=small, selected_number=selected_number,
        selected_colour=selected_colour, selected_size=selected_size,
        sample_count=len(numbers), dataset_version=version,
        method_probs=methods, model_config=model_config,
    )
