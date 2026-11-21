# Phase 3.2 — Statistical Pattern Discovery

Sample: **68** results from 20261121100010270 to 20261121100010434.

## What was tested

Number, colour, size and odd/even frequency; consecutive runs; repeated numbers;
number/colour/size transitions; autocorrelation; recent vs older halves; entropy;
rolling 20-result windows; exploratory change-point scan.

## Candidate patterns (Benjamini–Hochberg corrected)

| Candidate | p | adjusted p | Status |
|---|---:|---:|---|
| number_distribution_not_uniform | 0.2880 | 0.8848 | not_significant |
| colour_distribution_vs_uniform_number_baseline | 0.3871 | 0.8848 | not_significant |
| big_small_distribution_not_50_50 | 0.1456 | 0.8848 | not_significant |
| odd_even_distribution_not_50_50 | 0.2253 | 0.8848 | not_significant |
| runs_odd_even | 0.2866 | 0.8848 | not_significant |
| runs_big_small | 0.6242 | 0.9958 | not_significant |
| runs_repeat_number | 0.3231 | 0.8848 | not_significant |
| number_transition_dependence | 0.9958 | 0.9958 | not_significant |
| colour_transition_dependence | 0.7913 | 0.9958 | not_significant |
| size_transition_dependence | 0.7175 | 0.9958 | not_significant |
| distribution_stability_halves | 0.3525 | 0.8848 | not_significant |
| autocorrelation_lag_1 | 0.9385 | 0.9958 | not_significant |
| autocorrelation_lag_2 | 0.8570 | 0.9958 | not_significant |
| autocorrelation_lag_3 | 0.9253 | 0.9958 | not_significant |
| autocorrelation_lag_4 | 0.4975 | 0.9950 | not_significant |
| autocorrelation_lag_5 | 0.6749 | 0.9958 | not_significant |

## Key point

No candidate survived multiple-testing correction. Even a statistically significant
historical pattern would NOT prove future predictability.

## Important baseline detail

The colour distribution test compares observed colour labels with the probabilities implied
by a uniform 0–9 draw (red 0.4, green 0.4, red+violet 0.1, green+violet 0.1), not with
0.25 each. The overlapping violet mapping is structural, not a signal.

## Limitations

- Small, gappy sample: most tests have low statistical power.
- A significant historical pattern is not proof of future predictability.
- Change-point scans are exploratory and not corrected for repeated scanning.
- Colour categories overlap (0 and 5 include violet), so colour tests are not independent.
