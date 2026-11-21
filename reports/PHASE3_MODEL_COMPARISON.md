# Phase 3 — Model Comparison

Walk-forward evaluations: **38** (from 20261121100010300).
Decision: **no_predictive_advantage_retain_existing_model**.

Every model receives only results strictly before the target period.

| Model | Exact acc | Log loss | vs baseline | Adjusted p (log loss) | ECE |
|---|---:|---:|---:|---:|---:|
| uniform | 7.9% | 2.3026 | 0.0000 | n/a | 0.0711 |
| frequency | 7.9% | 3.3161 | 1.0136 | 0.2088 | 0.0842 |
| laplace | 7.9% | 2.4009 | 0.0983 | 0.2488 | 0.0711 |
| bayesian | 7.9% | 2.4009 | 0.0983 | 0.2488 | 0.0711 |
| recency | 10.5% | 3.6801 | 1.3775 | 0.2088 | 0.0684 |
| transition | 2.6% | 2.5185 | 0.2159 | 0.0000 | 0.1342 |
| hybrid | 2.6% | 2.4402 | 0.1377 | 0.2088 | 0.1289 |

Negative 'vs baseline' means better than uniform; positive means worse.

## Selection checks

- {"model": null, "meets_criteria": false, "reason": "only 38 evaluated predictions; need >= 100 for model selection"}

## Leakage controls

- records sorted by period_id
- training set ends strictly before target period
- no shuffling or random splits
- cutoff period stored with every evaluation

## Limitations

- Small chronological sample gives very low power.
- Bootstrap and normal approximations are unreliable at small n.
- No significance found does not prove absence of an effect.
