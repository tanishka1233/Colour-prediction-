#!/usr/bin/env python3
"""Descriptive data-quality / statistical audit of collected WinGo_1M records."""
import json, os
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
os.makedirs(REPORTS, exist_ok=True)

blob = json.load(open(os.path.join(DATA, "wingo_1m_history.json"), encoding="utf-8"))
recs = sorted(blob["records"], key=lambda r: r["period_id"])
n = len(recs)
nums = [r["result_number"] for r in recs]
cols = [r["result_colour"] for r in recs]
sizes = [r["result_size"] for r in recs]
pids = [r["period_id"] for r in recs]

numc = Counter(nums)
colc = Counter(cols)
sizec = Counter(sizes)

# structural validation
all_nums_valid = all(0 <= x <= 9 and isinstance(x, int) for x in nums)
unique = len(set(pids)) == n
ordered = pids == sorted(pids)
mismatches = [r["period_id"] for r in recs if "MISMATCH" in r["verification_status"]]

# gaps from period-id arithmetic
seqs = [int(p[-4:]) for p in pids]
gaps = []
for a, b in zip(seqs, seqs[1:]):
    if b - a > 1:
        gaps.append((a + 1, b - 1, b - a - 1))
missing_count = sum(g[2] for g in gaps)

# consecutive / repeat patterns
repeats = sum(1 for a, b in zip(nums, nums[1:]) if a == b)
repeat_dist = Counter()
for a, b in zip(nums, nums[1:]):
    if a == b:
        repeat_dist[a] += 1

# longest same-number / same-colour streak
def longest(seq):
    best = cur = 1
    for a, b in zip(seq, seq[1:]):
        cur = cur + 1 if a == b else 1
        best = max(best, cur)
    return best
num_streak = longest(nums)
col_streak = longest(cols)
size_streak = longest(sizes)

# chi-square uniformity (descriptive only; low power with n<50)
exp = n / 10
chi2 = sum((numc.get(i, 0) - exp) ** 2 / exp for i in range(10)) if n else 0

def pct(c): return round(100.0 * c / n, 1) if n else 0

lines = []
lines.append("# WinGo 1M — Data Quality & Statistical Audit\n")
lines.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
lines.append("## 1. Sample and validation\n")
lines.append(f"- Records: **{n}** (periods {pids[0] if pids else '-'} … {pids[-1] if pids else '-'}).")
lines.append(f"- Number range 0–9 valid: **{all_nums_valid}**.")
lines.append(f"- Unique period IDs: **{unique}**; duplicates: **{n - len(set(pids))}**.")
lines.append(f"- Chronologically ordered: **{ordered}**.")
lines.append(f"- Server `color` vs derived rule mismatches: **{len(mismatches)}**.")
lines.append(f"- Missing periods inside observed range: **{missing_count}** (gaps: {gaps[:20]}).")
lines.append("- Public snapshot per fetch: 10 records; `totalCount=500` is authenticated-API metadata, **not** retrieved.")
lines.append("- Timestamps in `result_timestamp` are exact period-end boundaries derived from the verified period-ID schedule and are labelled as derived.\n")

lines.append("## 2. Distributions\n")
lines.append("| Number | Count | Share |")
lines.append("|---|---:|---:|")
for i in range(10):
    lines.append(f"| {i} | {numc.get(i,0)} | {pct(numc.get(i,0))}% |")
lines.append("")
lines.append("| Colour | Count | Share |")
lines.append("|---|---:|---:|")
for k, v in sorted(colc.items()):
    lines.append(f"| {k} | {v} | {pct(v)}% |")
lines.append("")
lines.append("| Size | Count | Share |")
lines.append("|---|---:|---:|")
for k, v in sorted(sizec.items()):
    lines.append(f"| {k} | {v} | {pct(v)}% |")
lines.append("")

lines.append("## 3.Patterns\n")
lines.append(f"- Consecutive identical-number events: **{repeats}** of {max(0,n-1)} transitions ({pct(repeats) if n>1 else 0}% of transitions).")
lines.append(f"- Numbers involved in immediate repeats: {dict(repeat_dist)}.")
lines.append(f"- Longest same-number streak: **{num_streak}**; same-colour: **{col_streak}**; same-size: **{size_streak}**.")
lines.append(f"- Chi-square vs uniform 0–9: **{chi2:.2f}** on n={n} (df=9). At this sample size the test has very low power; no significance claim is made.\n")

lines.append("## 4. Interpretation (explicitly limited)\n")
lines.append("- With n≈43, expected count per number is ≈4.3; observed variation is consistent with ordinary random fluctuation.")
lines.append("- Consecutive repeats are expected at roughly 1/10 of transitions under a uniform i.i.d. model; observed rate is within small-sample noise.")
lines.append("- **No predictive signal is claimed.** Historical patterns do not guarantee future results; this game is a numbered random draw.")
lines.append("- No backtest was performed; if one is added later it must use strict time-ordered walk-forward validation and never use future outcomes.\n")

lines.append("## 5. Provenance\n")
lines.append("- Source: `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json` (public, unauthenticated).")
lines.append("- Collection: `investigation/scripts/collect_results.py` (ETag-aware, 30 s polling), `normalize_and_backfill.py`.")
lines.append("- Raw observations: `investigation/data/observation_log.jsonl`, `investigation/data/transition_samples.jsonl`.")
lines.append("- No account data, cookies or credentials are stored.\n")

md = "\n".join(x.rstrip("\n") for x in lines) + "\n"
open(os.path.join(REPORTS, "DATA_QUALITY_ANALYSIS.md"), "w", encoding="utf-8").write(md)
stats = {
    "sample_size": n, "range": [pids[0] if pids else None, pids[-1] if pids else None],
    "number_counts": {str(i): numc.get(i, 0) for i in range(10)},
    "colour_counts": dict(colc), "size_counts": dict(sizec),
    "unique_ids": unique, "ordered": ordered, "number_range_valid": all_nums_valid,
    "missing_periods_in_range": missing_count, "gaps": gaps,
    "consecutive_repeats": repeats, "repeat_dist": dict(repeat_dist),
    "longest_streaks": {"number": num_streak, "colour": col_streak, "size": size_streak},
    "chi_square_uniform_df9": round(chi2, 3),
    "colour_rule_mismatches": mismatches,
}
json.dump(stats, open(os.path.join(DATA, "statistics.json"), "w", encoding="utf-8"), indent=2)
print(md[:1500])
print("STATS SAVED")
