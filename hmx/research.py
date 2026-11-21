"""Phase 3.2 exploratory research: pattern discovery with honest caveats."""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from .engine import EngineConfig
from .rules import colour_for, size_for
from .stats import (benjamini_hochberg, binary_segmentation, chi_square_gof,
                    chi_square_homogeneity, chi_square_uniform, counter_stats,
                    autocorrelation, entropy, runs_test, transition_matrix)

COLOUR_STATES = ["red", "green", "red,violet", "green,violet"]
SIZE_STATES = ["Small", "Big"]


def _by_period(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: str(r["period_id"]))


def explore(rows: list[dict], config: EngineConfig | dict | None = None) -> dict:
    cfg = config if isinstance(config, EngineConfig) else EngineConfig.from_dict(config)
    ordered = _by_period(rows)
    nums = [int(r["result_number"]) for r in ordered]
    colours = [str(r["result_colour"]) for r in ordered]
    sizes = [str(r["result_size"]) for r in ordered]
    odd_even = [n % 2 for n in nums]
    repeat = [int(b == a) for a, b in zip(nums, nums[1:])]
    n = len(nums)

    dist_number = counter_stats(nums, list(range(10)))
    dist_colour = counter_stats(colours, COLOUR_STATES)
    dist_size = counter_stats(sizes, SIZE_STATES)
    dist_odd = counter_stats(odd_even, [0, 1])

    # ---------- transitions ----------
    colour_idx = {c: i for i, c in enumerate(COLOUR_STATES)}
    size_idx = {s: i for i, s in enumerate(SIZE_STATES)}
    transitions = {
        "number": transition_matrix(nums, 10),
        "colour": transition_matrix([colour_idx.get(c, 0) for c in colours], len(COLOUR_STATES)),
        "size": transition_matrix([size_idx.get(s, 0) for s in sizes], len(SIZE_STATES)),
    }

    # ---------- runs / serial dependence ----------
    runs = {
        "odd_even": runs_test(odd_even),
        "big_small": runs_test([1 if s == "Big" else 0 for s in sizes]),
        "same_as_previous_number": runs_test(repeat),
    }
    autocorr = [autocorrelation(nums, lag) for lag in range(1, 6)]

    # ---------- recent vs older ----------
    half = n // 2
    stability = {
        "number_first_vs_second_half": chi_square_homogeneity(
            [Counter(nums[:half]).get(i, 0) for i in range(10)],
            [Counter(nums[half:]).get(i, 0) for i in range(10)]),
        "first_half_entropy": entropy([Counter(nums[:half]).get(i, 0) for i in range(10)]),
        "second_half_entropy": entropy([Counter(nums[half:]).get(i, 0) for i in range(10)]),
    }

    # ---------- rolling windows ----------
    window = 20
    rolling = []
    for start in range(0, max(0, n - window + 1), window):
        chunk = nums[start:start + window]
        c = Counter(chunk)
        top = max(range(10), key=lambda i: (c.get(i, 0), -i))
        rolling.append({"start_index": start, "end_index": start + len(chunk) - 1,
                        "size": len(chunk), "top_number": top,
                        "top_count": c.get(top, 0), "entropy": entropy([c.get(i, 0) for i in range(10)])})

    change_points = binary_segmentation([float(v) for v in nums], min_segment=8, max_changes=3)

    # ---------- candidate patterns + multiple-testing correction ----------
    # Correct baselines matter: under a uniform 0-9 draw, the four disjoint
    # colour labels have probabilities 0.4/0.4/0.1/0.1, NOT 0.25 each.
    colour_gof = chi_square_gof(
        [Counter(colours).get(c, 0) for c in COLOUR_STATES], [0.4, 0.4, 0.1, 0.1])
    size_gof = chi_square_gof([Counter(sizes).get(s, 0) for s in SIZE_STATES], [0.5, 0.5])
    odd_gof = chi_square_gof([Counter(odd_even).get(i, 0) for i in (0, 1)], [0.5, 0.5])
    candidates = [
        {"name": "number_distribution_not_uniform", **dist_number["chi_square"]},
        {"name": "colour_distribution_vs_uniform_number_baseline", **colour_gof},
        {"name": "big_small_distribution_not_50_50", **size_gof},
        {"name": "odd_even_distribution_not_50_50", **odd_gof},
        {"name": "runs_odd_even", **runs["odd_even"]},
        {"name": "runs_big_small", **runs["big_small"]},
        {"name": "runs_repeat_number", **runs["same_as_previous_number"]},
        {"name": "number_transition_dependence", **transitions["number"]},
        {"name": "colour_transition_dependence", **transitions["colour"]},
        {"name": "size_transition_dependence", **transitions["size"]},
        {"name": "distribution_stability_halves", **stability["number_first_vs_second_half"]},
    ]
    for item in autocorr:
        candidates.append({"name": f"autocorrelation_lag_{item['lag']}",
                           "p_value": item["p_value"], "statistic": item["r"],
                           "sample_size": item["n"], "limitation": item.get("limitation", "")})
    usable = [c for c in candidates if c.get("p_value") is not None]
    adjusted = benjamini_hochberg([c["p_value"] for c in usable])
    for c, adj in zip(usable, adjusted):
        c["p_value_adjusted_bh"] = adj["adjusted_p"]
        c["significant_after_bh"] = adj["significant"]
        c["validation_status"] = ("candidate_only_needs_out_of_sample_confirmation"
                                  if adj["significant"] else "not_significant")
    for c in [x for x in candidates if x.get("p_value") is None]:
        c["validation_status"] = "insufficient_data"

    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "sample_size": n,
        "period_range": [ordered[0]["period_id"], ordered[-1]["period_id"]] if ordered else [],
        "config": cfg.to_dict(),
        "distributions": {"number": dist_number,
                          "colour": {**dist_colour, "chi_square": colour_gof},
                          "size": {**dist_size, "chi_square": size_gof},
                          "odd_even": {**dist_odd, "chi_square": odd_gof}},
        "transitions": transitions,
        "runs": runs,
        "autocorrelation": autocorr,
        "recent_vs_older": stability,
        "rolling_windows": rolling,
        "change_points": change_points,
        "candidate_patterns": candidates,
        "multiple_testing": {"method": "Benjamini-Hochberg FDR", "alpha": 0.05,
                             "tests": len(usable)},
        "limitations": [
            "Small, gappy sample: most tests have low statistical power.",
            "A significant historical pattern is not proof of future predictability.",
            "Change-point scans are exploratory and not corrected for repeated scanning.",
            "Colour categories overlap (0 and 5 include violet), so colour tests are not independent.",
        ],
    }
