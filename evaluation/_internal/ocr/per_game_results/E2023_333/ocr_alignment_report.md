# OCR alignment evaluation

Annotated events: 534

Pending annotations: 0; excluded: 0.

## Overall micro-average

| System | N | Mapped | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 534 | 534 | 0.000% | 16.193s | 4.000s | 19.288% | 25.655% | 57.678% |
| production | 534 | 534 | 0.000% | 16.367s | 4.500s | 18.914% | 24.532% | 56.929% |

## Macro-average across games

| System | Games | Mean UER | Mean MAE | Mean median AE | Mean Acc@1s | Mean Acc@2s | Mean Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 0.000% | 16.193s | 4.000s | 19.288% | 25.655% | 57.678% |
| production | 1 | 0.000% | 16.367s | 4.500s | 18.914% | 24.532% | 56.929% |

## Per-game metrics

| System | Game | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | E2023/333 | 534 | 0.000% | 16.193s | 4.000s | 19.288% | 25.655% | 57.678% |
| production | E2023/333 | 534 | 0.000% | 16.367s | 4.500s | 18.914% | 24.532% | 56.929% |

## Per-action-category metrics

| System | Category | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | assist | 30 | 0.000% | 4.467s | 4.500s | 0.000% | 13.333% | 80.000% |
| baseline | defensive_play | 10 | 0.000% | 4.800s | 5.500s | 20.000% | 20.000% | 50.000% |
| baseline | foul | 90 | 0.000% | 13.122s | 1.000s | 71.111% | 77.778% | 77.778% |
| baseline | made_field_goal | 57 | 0.000% | 3.474s | 3.000s | 8.772% | 24.561% | 92.982% |
| baseline | made_free_throw | 38 | 0.000% | 49.605s | 50.000s | 0.000% | 0.000% | 2.632% |
| baseline | missed_field_goal | 65 | 0.000% | 6.508s | 4.000s | 1.538% | 6.154% | 87.692% |
| baseline | missed_free_throw | 10 | 0.000% | 49.000s | 42.500s | 10.000% | 10.000% | 20.000% |
| baseline | period_boundary | 9 | 0.000% | 4.556s | 5.000s | 33.333% | 33.333% | 55.556% |
| baseline | rebound | 68 | 0.000% | 9.882s | 4.000s | 8.824% | 17.647% | 80.882% |
| baseline | review_challenge | 2 | 0.000% | 64.500s | 64.500s | 0.000% | 0.000% | 0.000% |
| baseline | substitution | 132 | 0.000% | 24.833s | 14.000s | 9.091% | 10.606% | 13.636% |
| baseline | timeout | 7 | 0.000% | 2.571s | 1.000s | 57.143% | 71.429% | 85.714% |
| baseline | turnover | 16 | 0.000% | 9.375s | 2.500s | 31.250% | 50.000% | 75.000% |
| production | assist | 30 | 0.000% | 4.467s | 5.000s | 0.000% | 13.333% | 80.000% |
| production | defensive_play | 10 | 0.000% | 4.700s | 5.500s | 20.000% | 20.000% | 50.000% |
| production | foul | 90 | 0.000% | 13.322s | 1.000s | 71.111% | 75.556% | 77.778% |
| production | made_field_goal | 57 | 0.000% | 3.474s | 3.000s | 7.018% | 22.807% | 92.982% |
| production | made_free_throw | 38 | 0.000% | 50.158s | 50.000s | 0.000% | 0.000% | 2.632% |
| production | missed_field_goal | 65 | 0.000% | 6.523s | 4.000s | 1.538% | 6.154% | 87.692% |
| production | missed_free_throw | 10 | 0.000% | 51.100s | 42.500s | 0.000% | 0.000% | 10.000% |
| production | period_boundary | 9 | 0.000% | 5.000s | 7.000s | 33.333% | 33.333% | 33.333% |
| production | rebound | 68 | 0.000% | 9.956s | 4.000s | 8.824% | 14.706% | 79.412% |
| production | review_challenge | 2 | 0.000% | 64.500s | 64.500s | 0.000% | 0.000% | 0.000% |
| production | substitution | 132 | 0.000% | 25.015s | 14.000s | 9.091% | 10.606% | 13.636% |
| production | timeout | 7 | 0.000% | 2.571s | 1.000s | 57.143% | 71.429% | 85.714% |
| production | turnover | 16 | 0.000% | 9.375s | 2.500s | 31.250% | 50.000% | 75.000% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

## Temporal error distribution

| System | Error band | Events | Share |
| --- | --- | ---: | ---: |
| baseline | within_1_second | 103 | 19.288% |
| baseline | over_1_to_2_seconds | 34 | 6.367% |
| baseline | over_2_to_5_seconds | 171 | 32.022% |
| baseline | over_5_to_10_seconds | 75 | 14.045% |
| baseline | over_10_to_30_seconds | 53 | 9.925% |
| baseline | over_30_seconds | 98 | 18.352% |
| baseline | unmapped | 0 | 0.000% |
| production | within_1_second | 101 | 18.914% |
| production | over_1_to_2_seconds | 30 | 5.618% |
| production | over_2_to_5_seconds | 173 | 32.397% |
| production | over_5_to_10_seconds | 78 | 14.607% |
| production | over_10_to_30_seconds | 51 | 9.551% |
| production | over_30_seconds | 101 | 18.914% |
| production | unmapped | 0 | 0.000% |

Acc@tau uses all annotated events as the denominator, so an unmapped event is incorrect at every tolerance. MAE and median absolute error use mapped events only. The macro rows average the corresponding per-game metrics with equal weight per game. Machine-readable results are in `ocr_alignment_summary.csv`; per-event predictions and signed/absolute errors are in `ocr_alignment_detailed.csv`, and the failure-analysis bands are in `ocr_temporal_error_bands.csv`.
