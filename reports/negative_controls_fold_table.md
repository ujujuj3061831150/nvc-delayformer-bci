# Subject-level perturbation results (29 subjects)

Changes are control minus full-model accuracy, in percentage points (pp).

| Subject | Full | Within-class | Across-class | Circular roll 5 s | Added EEG smoothing |
|---|---:|---:|---:|---:|---:|
| Sub-01 | 83.33% | 83.50% | 56.33% | 63.33% | 86.67% |
| Sub-02 | 66.67% | 71.50% | 49.50% | 51.67% | 65.00% |
| Sub-03 | 61.67% | 65.83% | 55.17% | 63.33% | 60.00% |
| Sub-04 | 46.67% | 48.83% | 56.67% | 43.33% | 48.33% |
| Sub-05 | 75.00% | 74.67% | 65.00% | 78.33% | 66.67% |
| Sub-06 | 61.67% | 58.17% | 65.67% | 58.33% | 58.33% |
| Sub-07 | 71.67% | 74.83% | 49.50% | 66.67% | 71.67% |
| Sub-08 | 51.67% | 51.83% | 55.17% | 33.33% | 51.67% |
| Sub-09 | 86.67% | 81.67% | 54.50% | 73.33% | 83.33% |
| Sub-10 | 38.33% | 39.33% | 52.50% | 43.33% | 38.33% |
| Sub-11 | 63.33% | 64.17% | 58.67% | 63.33% | 66.67% |
| Sub-12 | 66.67% | 65.83% | 55.83% | 60.00% | 61.67% |
| Sub-13 | 56.67% | 54.00% | 51.50% | 51.67% | 55.00% |
| Sub-14 | 58.33% | 60.50% | 59.00% | 50.00% | 61.67% |
| Sub-15 | 68.33% | 68.33% | 58.83% | 65.00% | 63.33% |
| Sub-16 | 73.33% | 73.50% | 48.83% | 70.00% | 70.00% |
| Sub-17 | 63.33% | 67.83% | 48.00% | 50.00% | 61.67% |
| Sub-18 | 70.00% | 70.00% | 58.67% | 60.00% | 78.33% |
| Sub-19 | 63.33% | 63.50% | 60.33% | 66.67% | 61.67% |
| Sub-20 | 63.33% | 65.50% | 54.00% | 53.33% | 63.33% |
| Sub-21 | 81.67% | 78.17% | 65.17% | 73.33% | 81.67% |
| Sub-22 | 75.00% | 69.50% | 59.33% | 63.33% | 65.00% |
| Sub-23 | 83.33% | 78.17% | 67.67% | 71.67% | 83.33% |
| Sub-24 | 56.67% | 57.50% | 53.00% | 56.67% | 51.67% |
| Sub-25 | 63.33% | 67.33% | 49.00% | 56.67% | 56.67% |
| Sub-26 | 63.33% | 64.83% | 56.33% | 65.00% | 68.33% |
| Sub-27 | 75.00% | 69.83% | 63.00% | 68.33% | 70.00% |
| Sub-28 | 70.00% | 72.50% | 53.17% | 56.67% | 55.00% |
| Sub-29 | 68.33% | 69.33% | 68.00% | 58.33% | 63.33% |

| Condition | Mean ± sample SD | Change (pp) | t p | Wilcoxon p | BH q |
|---|---:|---:|---:|---:|---:|
| Within-Class Permutation | 66.57% ± 9.84% | +0.13 | 0.814757 | 0.59684 | 0.59684 |
| Across-Class Permutation | 56.84% ± 5.78% | -9.60 | 3.71848e-05 | 0.000168118 | 0.000336236 |
| Temporal Phase Roll (±5s) | 59.83% ± 10.12% | -6.61 | 9.47063e-06 | 7.13107e-05 | 0.000285243 |
| Additional Causal EEG Smoothing | 64.43% ± 11.08% | -2.01 | 0.0295014 | 0.0321761 | 0.0429015 |

The JSON retains full-precision count proportions and the statistical protocol. Fold percentages in this table are display-only rounding.
Causal smoothing uses alpha=0.85 on offline-preprocessed EEG; fNIRS is unchanged. It is an input perturbation, not a replacement of the offline preprocessing pipeline.
For a 1,000-sample epoch, +500 and -500 circular shifts are identical; one unique perturbation is reported.
The archived JSON contains the previous rounded records and pre-reconciliation statistics.
