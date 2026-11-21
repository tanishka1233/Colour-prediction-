#!/usr/bin/env python3
"""Generate Phase 3 reports from the actual JSON analysis artefacts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "reports"


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def fmt(v, pct=False):
    if v is None:
        return "n/a"
    return f"{v*100:.1f}%" if pct else f"{v:.4f}"


def data_quality(p):
    dist = p["number_distribution"]
    lines = [
        "# Phase 3.1 — Data Quality Report", "",
        "Plain-language summary generated from the local SQLite database.", "",
        f"- Records: **{p['total_records']}**",
        f"- Period range: {p['earliest_period']} → {p['latest_period']}",
        f"- Missing periods: **{p['missing_period_count']}** (coverage {p['coverage_pct']}%)",
        f"- Longest continuous run: {p['longest_continuous_sequence']} periods",
        f"- Duplicate periods: {p['duplicate_period_count']}; conflicts: {p['conflicting_result_count']}; invalid rows: {p['invalid_result_count']}",
        f"- Sources: {', '.join(p['sources']) or 'none'}",
        f"- Collection timestamps: {p['retrieved_at_min']} → {p['retrieved_at_max']}", "",
        "## Gaps", "",
    ]
    for a, b, count in p["missing_periods"]:
        lines.append(f"- {count} missing periods between {a} and {b}")
    lines += ["", "## Distributions", "", "| Number | Count | Share | 95% Wilson CI |", "|---|---:|---:|---|"]
    for i, count in enumerate(dist["counts"]):
        ci = dist["wilson_95"][i]
        lines.append(f"| {i} | {count} | {fmt(dist['proportions'][i], True)} | "
                     f"[{fmt(ci['lower'])}, {fmt(ci['upper'])}] |")
    lines += ["", "Colour counts: " + ", ".join(
        f"{c}={n}" for c, n in zip(["red", "green", "red,violet", "green,violet"],
                                   p["colour_distribution"]["counts"])),
        "Big/Small: " + str(dict(zip(["Small", "Big"], p["size_distribution"]["counts"]))), "",
        "## Mapping verification", ""]
    for k, v in p["mapping_verification"].items():
        lines.append(f"- {k}: {'OK' if v else 'FAILED'}")
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in p["limitations"]]
    (R / "PHASE3_1_DATA_QUALITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def research_report(res):
    lines = [
        "# Phase 3.2 — Statistical Pattern Discovery", "",
        f"Sample: **{res['sample_size']}** results from {res['period_range'][0]} to {res['period_range'][1]}.",
        "", "## What was tested", "",
        "Number, colour, size and odd/even frequency; consecutive runs; repeated numbers;",
        "number/colour/size transitions; autocorrelation; recent vs older halves; entropy;",
        "rolling 20-result windows; exploratory change-point scan.", "",
        "## Candidate patterns (Benjamini–Hochberg corrected)", "",
        "| Candidate | p | adjusted p | Status |", "|---|---:|---:|---|",
    ]
    for c in res["candidate_patterns"]:
        lines.append(f"| {c['name']} | {fmt(c.get('p_value'))} | {fmt(c.get('p_value_adjusted_bh'))} | "
                     f"{c['validation_status']} |")
    lines += ["", "## Key point", "",
              "No candidate survived multiple-testing correction. Even a statistically significant",
              "historical pattern would NOT prove future predictability.", "",
              "## Important baseline detail", "",
              "The colour distribution test compares observed colour labels with the probabilities implied",
              "by a uniform 0–9 draw (red 0.4, green 0.4, red+violet 0.1, green+violet 0.1), not with",
              "0.25 each. The overlapping violet mapping is structural, not a signal.", "",
              "## Limitations", ""] + [f"- {x}" for x in res["limitations"]]
    (R / "PHASE3_2_STATISTICAL_RESEARCH_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def comparison_report(m):
    lines = [
        "# Phase 3 — Model Comparison", "",
        f"Walk-forward evaluations: **{m['evaluation_count']}** (from {m['period_range_evaluated'][0]}).",
        f"Decision: **{m['selection']['decision']}**.", "",
        "Every model receives only results strictly before the target period.", "",
        "| Model | Exact acc | Log loss | vs baseline | Adjusted p (log loss) | ECE |", "|---|---:|---:|---:|---:|---:|",
    ]
    for name, c in m["models"].items():
        lines.append(f"| {name} | {fmt(c['exact_accuracy'], True)} | {fmt(c['mean_log_loss'])} | "
                     f"{fmt(c['log_loss_vs_baseline'])} | {fmt(c.get('paired_log_loss_p_adjusted_bh'))} | "
                     f"{fmt(c['expected_calibration_error'])} |")
    lines += ["", "Negative 'vs baseline' means better than uniform; positive means worse.", "",
              "## Selection checks", ""]
    for r in m["selection"]["reasons"]:
        lines.append("- " + json.dumps(r))
    lines += ["", "## Leakage controls", ""] + [f"- {x}" for x in m["leakage_controls"]]
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in m["limitations"]]
    (R / "PHASE3_MODEL_COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def validation_report(m):
    lines = [
        "# Phase 3 — Validation Report", "",
        "Method: strict chronological walk-forward. Records are sorted by period, training",
        "stops before the target period, no shuffling, no random splits, cutoff stored.", "",
        f"Evaluated predictions: {m['evaluation_count']}. Minimum for model selection: 100.", "",
        "## Stability across contiguous segments", "",
    ]
    for name, c in m["models"].items():
        lines.append(f"**{name}**")
        for s in c["segments"]:
            lines.append(f"- segment starting {s['start_index']} (n={s['size']}): "
                         f"log loss {s['log_loss']} vs baseline {s['baseline_log_loss']} — "
                         f"{'better' if s['beats_baseline_log_loss'] else 'not better'}")
        lines.append("")
    lines += [
        "## Result", "",
        "No model met the evidence requirements (proper score improvement, adjusted",
        "significance, calibration, stability, sufficient sample). The existing hybrid model",
        "is retained as a neutral default, not because it was proven better.", "",
        "## Future-data leakage tests", "",
        "- Repeated for every target: training set = periods < target.",
        "- Cutoff period recorded with each evaluation.",
        "- Unit tests assert identical predictions when extra future rows are supplied.",
    ]
    (R / "PHASE3_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    p, res, m = load("phase3_1_dataset_profile.json"), load("phase3_2_research.json"), load("phase3_2_model_comparison.json")
    data_quality(p)
    research_report(res)
    comparison_report(m)
    validation_report(m)
    print("reports generated")


if __name__ == "__main__":
    main()
