"""Small, dependency-free statistical toolkit for Phase 3 research.

Only standard-library math/random is used. Functions are deliberately explicit
and return both the statistic and its limitations/sample size so callers cannot
accidentally present a small-sample fluctuation as evidence.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from typing import Iterable, Sequence

EPS = 1e-12


# ---------- distributions ----------
def _gser(a: float, x: float) -> float:
    ap, s, delta = a, 1.0 / a, 1.0 / a
    for _ in range(300):
        ap += 1.0
        delta *= x / ap
        s += delta
        if abs(delta) < abs(s) * 1e-13:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a: float, x: float) -> float:
    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1.0 / tiny, 1.0 / max(tiny, x + 1.0 - a)
    h = d
    for i in range(1, 300):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-13:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(stat: float, df: int) -> float:
    """Upper tail probability of chi-square with df degrees of freedom."""
    if stat <= 0 or df <= 0:
        return 1.0
    a, x = df / 2.0, stat / 2.0
    p = 1.0 - _gser(a, x) if x < a + 1.0 else _gcf(a, x)
    return min(1.0, max(0.0, p))


def normal_two_sided_p(z: float) -> float:
    return min(1.0, max(0.0, math.erfc(abs(z) / math.sqrt(2.0))))


def wilson_interval(successes: int, n: int, z: float = 1.96) -> dict:
    if n <= 0:
        return {"lower": None, "upper": None, "n": 0}
    p = successes / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"lower": max(0.0, centre - half), "upper": min(1.0, centre + half), "n": n}


def chi_square_uniform(counts: Sequence[int]) -> dict:
    k = len(counts)
    n = sum(counts)
    expected = n / k if k else 0.0
    stat = sum((c - expected) ** 2 / expected for c in counts) if expected > 0 else 0.0
    return {"statistic": round(stat, 4), "df": k - 1,
            "p_value": round(chi2_sf(stat, k - 1), 6),
            "expected_per_category": round(expected, 3), "sample_size": n,
            "limitation": "Low expected counts make the chi-square approximation unreliable." if expected < 5 else ""}


def chi_square_gof(counts: Sequence[int], expected_probs: Sequence[float]) -> dict:
    """Goodness-of-fit against a specified probability vector (not necessarily uniform)."""
    k = len(counts)
    n = sum(counts)
    probs = list(expected_probs)
    total_p = sum(probs)
    probs = [p / total_p for p in probs] if total_p > 0 else [1.0 / k] * k
    expected = [n * p for p in probs]
    stat = sum((c - e) ** 2 / e for c, e in zip(counts, expected) if e > 0)
    df = max(1, k - 1)
    return {"statistic": round(stat, 4), "df": df,
            "p_value": round(chi2_sf(stat, df), 6),
            "expected_counts": [round(e, 2) for e in expected],
            "sample_size": n,
            "limitation": "Chi-square approximation unreliable when expected counts < 5."
                          if min(expected or [0]) < 5 else ""}


def chi_square_homogeneity(counts_a: Sequence[int], counts_b: Sequence[int]) -> dict:
    k = min(len(counts_a), len(counts_b))
    a, b = list(counts_a[:k]), list(counts_b[:k])
    totals = [a[i] + b[i] for i in range(k)]
    na, nb = sum(a), sum(b)
    if na == 0 or nb == 0:
        return {"statistic": None, "p_value": None, "limitation": "empty sample"}
    stat, min_exp = 0.0, float("inf")
    for i in range(k):
        total = totals[i]
        ea, eb = total * na / (na + nb), total * nb / (na + nb)
        min_exp = min(min_exp, ea, eb)
        if ea > 0:
            stat += (a[i] - ea) ** 2 / ea
        if eb > 0:
            stat += (b[i] - eb) ** 2 / eb
    df = max(1, k - 1)
    return {"statistic": round(stat, 4), "df": df,
            "p_value": round(chi2_sf(stat, df), 6),
            "min_expected": round(min_exp, 2), "sample_sizes": [na, nb],
            "limitation": "Expected counts below 5 invalidate the approximation." if min_exp < 5 else ""}


def entropy(counts: Sequence[int]) -> dict:
    total = sum(counts)
    if total <= 0:
        return {"entropy": None, "normalized": None, "effective_outcomes": None}
    ps = [c / total for c in counts if c > 0]
    h = -sum(p * math.log(p) for p in ps)
    k = len(counts)
    norm = h / math.log(k) if k > 1 else 1.0
    return {"entropy": round(h, 4), "normalized": round(norm, 4),
            "effective_outcomes": round(math.exp(h), 3), "max_entropy": round(math.log(k), 4)}


def runs_test(binary: Sequence[int]) -> dict:
    seq = [int(x) for x in binary]
    n = len(seq)
    n1, n0 = sum(seq), n - sum(seq)
    if n < 20 or min(n1, n0) < 5:
        return {"runs": None, "p_value": None, "limitation": "sample too small for runs test", "n": n}
    runs = 1 + sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    expected = 2.0 * n1 * n0 / n + 1.0
    var = (expected - 1) * (expected - 2) / max(1, n - 1)
    if var <= 0:
        return {"runs": runs, "p_value": None, "limitation": "zero variance", "n": n}
    z = (runs - expected) / math.sqrt(var)
    return {"runs": runs, "expected_runs": round(expected, 2), "z": round(z, 4),
            "p_value": round(normal_two_sided_p(z), 6), "n": n,
            "limitation": "Tests only the binary recoding supplied; not the full outcome space."}


def autocorrelation(values: Sequence[float], lag: int) -> dict:
    x, y = list(values[:-lag]), list(values[lag:])
    n = len(x)
    if n < 10:
        return {"lag": lag, "r": None, "p_value": None, "n": n, "limitation": "sample too small"}
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx < EPS or dy < EPS:
        return {"lag": lag, "r": None, "p_value": None, "n": n, "limitation": "zero variance"}
    r = max(-1.0, min(1.0, num / (dx * dy)))
    if n > 3 and abs(r) < 1:
        z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(n - 3)
        p = normal_two_sided_p(z)
    else:
        z, p = 0.0, 1.0
    return {"lag": lag, "r": round(r, 4), "z": round(z, 4),
            "p_value": round(p, 6), "n": n,
            "limitation": "Approximate Fisher transform; multiple lags require correction."}


def transition_matrix(sequence: Sequence[int], states: int) -> dict:
    obs = [[0] * states for _ in range(states)]
    for a, b in zip(sequence, sequence[1:]):
        obs[int(a)][int(b)] += 1
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(states)) for j in range(states)]
    n = sum(row)
    expected = [[row[i] * col[j] / n if n else 0 for j in range(states)] for i in range(states)]
    stat = min_exp = 0.0
    min_exp = float("inf")
    for i in range(states):
        for j in range(states):
            e = expected[i][j]
            min_exp = min(min_exp, e)
            if e > 0:
                stat += (obs[i][j] - e) ** 2 / e
    df = (states - 1) ** 2
    result = {"observed": obs, "expected": [[round(v, 2) for v in r] for r in expected],
              "transitions": n, "statistic": round(stat, 4), "df": df,
              "p_value": round(chi2_sf(stat, df), 6) if n else None,
              "min_expected": round(min_exp, 2) if n else 0,
              "limitation": "Transition chi-square is unreliable when expected counts < 5."}
    return result


def benjamini_hochberg(p_values: Sequence[float], alpha: float = 0.05) -> list[dict]:
    pairs = sorted((float(p), i) for i, p in enumerate(p_values))
    m = len(pairs)
    adjusted = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        p, idx = pairs[rank - 1]
        prev = min(prev, p * m / rank)
        adjusted[idx] = min(1.0, prev)
    return [{"p_value": round(p, 6), "adjusted_p": round(adjusted[i], 6),
             "significant": adjusted[i] < alpha} for i, p in enumerate(p_values)]


def paired_bootstrap_ci(diffs: Sequence[float], *, iterations: int = 2000,
                        seed: int = 0, alpha: float = 0.05) -> dict:
    """Deterministic bootstrap CI for the paired mean difference (model - baseline)."""
    vals = list(diffs)
    n = len(vals)
    if n < 2:
        return {"lower": None, "upper": None, "n": n}
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = int(alpha / 2 * iterations)
    hi = min(iterations - 1, int((1 - alpha / 2) * iterations))
    return {"lower": round(means[lo], 6), "upper": round(means[hi], 6), "n": n}


def binary_segmentation(values: Sequence[float], *, min_segment: int = 8,
                        max_changes: int = 3) -> list[dict]:
    """Exploratory change-point scan using a two-sample t-like statistic.

    This is a screening tool only: with small samples it will find spurious
    changes, so results must be interpreted with caution and corrected.
    """
    pts: list[dict] = []

    def scan(segment: list[float], offset: int, depth: int) -> None:
        if depth >= max_changes or len(segment) < 2 * min_segment:
            return
        n = len(segment)
        best = None
        for i in range(min_segment, n - min_segment + 1):
            a, b = segment[:i], segment[i:]
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            va = sum((x - ma) ** 2 for x in a) / len(a)
            vb = sum((x - mb) ** 2 for x in b) / len(b)
            se = math.sqrt(va / len(a) + vb / len(b))
            if se < EPS:
                continue
            t = (mb - ma) / se
            if best is None or abs(t) > abs(best[1]):
                best = (i, t)
        if best and abs(best[1]) > 2.5:
            idx, t = best
            pts.append({"index": offset + idx, "t_statistic": round(t, 3),
                        "note": "exploratory; not corrected for multiple scans"})
            scan(segment[:idx], offset, depth + 1)
            scan(segment[idx:], offset + idx, depth + 1)

    scan(list(values), 0, 0)
    return pts


def counter_stats(values: Iterable, labels: Sequence) -> dict:
    c = Counter(values)
    counts = [c.get(label, 0) for label in labels]
    n = sum(counts)
    return {"counts": counts, "sample_size": n,
            "proportions": [round(v / n, 4) if n else None for v in counts],
            "expected_uniform": round(n / len(labels), 3) if n else 0,
            "chi_square": chi_square_uniform(counts),
            "entropy": entropy(counts),
            "wilson_95": [wilson_interval(v, n) for v in counts]}
