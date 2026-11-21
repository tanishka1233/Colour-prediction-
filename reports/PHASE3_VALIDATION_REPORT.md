# Phase 3 — Validation Report

Method: strict chronological walk-forward. Records are sorted by period, training
stops before the target period, no shuffling, no random splits, cutoff stored.

Evaluated predictions: 38. Minimum for model selection: 100.

## Stability across contiguous segments

**uniform**
- segment starting 0 (n=12): log loss 2.3026 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 2.3026 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.3026 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.3026 vs baseline 2.3026 — not better

**frequency**
- segment starting 0 (n=12): log loss 3.7868 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 3.8078 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.4959 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.4643 vs baseline 2.3026 — not better

**laplace**
- segment starting 0 (n=12): log loss 2.3612 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 2.4034 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.4325 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.4339 vs baseline 2.3026 — not better

**bayesian**
- segment starting 0 (n=12): log loss 2.3612 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 2.4034 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.4325 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.4339 vs baseline 2.3026 — not better

**recency**
- segment starting 0 (n=12): log loss 4.3665 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 4.4224 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.4592 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.4329 vs baseline 2.3026 — not better

**transition**
- segment starting 0 (n=12): log loss 2.6037 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 2.4896 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.431 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.7058 vs baseline 2.3026 — not better

**hybrid**
- segment starting 0 (n=12): log loss 2.4386 vs baseline 2.3026 — not better
- segment starting 12 (n=12): log loss 2.4426 vs baseline 2.3026 — not better
- segment starting 24 (n=12): log loss 2.4317 vs baseline 2.3026 — not better
- segment starting 36 (n=2): log loss 2.4877 vs baseline 2.3026 — not better

## Result

No model met the evidence requirements (proper score improvement, adjusted
significance, calibration, stability, sufficient sample). The existing hybrid model
is retained as a neutral default, not because it was proven better.

## Future-data leakage tests

- Repeated for every target: training set = periods < target.
- Cutoff period recorded with each evaluation.
- Unit tests assert identical predictions when extra future rows are supplied.
