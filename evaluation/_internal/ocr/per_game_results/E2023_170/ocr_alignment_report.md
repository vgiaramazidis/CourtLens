# OCR alignment evaluation

Annotated events: 726

Pending annotations: 0; excluded: 7.

## Overall micro-average

| System | N | Mapped | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 726 | 726 | 0.000% | 22.565s | 4.000s | 18.457% | 33.058% | 57.438% |
| production | 726 | 726 | 0.000% | 22.510s | 4.000s | 18.871% | 31.818% | 57.713% |

## Macro-average across games

| System | Games | Mean UER | Mean MAE | Mean median AE | Mean Acc@1s | Mean Acc@2s | Mean Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 0.000% | 22.565s | 4.000s | 18.457% | 33.058% | 57.438% |
| production | 1 | 0.000% | 22.510s | 4.000s | 18.871% | 31.818% | 57.713% |

## Per-game metrics

| System | Game | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | E2023/170 | 726 | 0.000% | 22.565s | 4.000s | 18.457% | 33.058% | 57.438% |
| production | E2023/170 | 726 | 0.000% | 22.510s | 4.000s | 18.871% | 31.818% | 57.713% |

## Per-action-category metrics

| System | Category | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | assist | 44 | 0.000% | 10.091s | 4.000s | 4.545% | 15.909% | 68.182% |
| baseline | defensive_play | 23 | 0.000% | 6.261s | 4.000s | 8.696% | 21.739% | 78.261% |
| baseline | foul | 98 | 0.000% | 10.541s | 1.000s | 60.204% | 70.408% | 74.490% |
| baseline | made_field_goal | 89 | 0.000% | 4.820s | 3.000s | 20.225% | 44.944% | 86.517% |
| baseline | made_free_throw | 49 | 0.000% | 57.327s | 40.000s | 0.000% | 0.000% | 2.041% |
| baseline | missed_field_goal | 106 | 0.000% | 5.858s | 3.000s | 9.434% | 37.736% | 84.906% |
| baseline | missed_free_throw | 14 | 0.000% | 51.357s | 39.500s | 0.000% | 0.000% | 0.000% |
| baseline | period_boundary | 18 | 0.000% | 3.333s | 2.500s | 33.333% | 50.000% | 77.778% |
| baseline | rebound | 105 | 0.000% | 11.152s | 3.000s | 19.048% | 36.190% | 71.429% |
| baseline | review_challenge | 2 | 0.000% | 18.000s | 18.000s | 0.000% | 0.000% | 0.000% |
| baseline | substitution | 136 | 0.000% | 61.971s | 20.000s | 1.471% | 5.882% | 5.882% |
| baseline | timeout | 16 | 0.000% | 17.812s | 2.500s | 43.750% | 50.000% | 62.500% |
| baseline | turnover | 26 | 0.000% | 7.808s | 2.000s | 30.769% | 61.538% | 80.769% |
| production | assist | 44 | 0.000% | 10.273s | 5.000s | 4.545% | 18.182% | 65.909% |
| production | defensive_play | 23 | 0.000% | 6.304s | 4.000s | 8.696% | 17.391% | 78.261% |
| production | foul | 98 | 0.000% | 9.541s | 1.000s | 64.286% | 70.408% | 80.612% |
| production | made_field_goal | 89 | 0.000% | 4.966s | 3.000s | 21.348% | 41.573% | 85.393% |
| production | made_free_throw | 49 | 0.000% | 58.592s | 41.000s | 0.000% | 0.000% | 0.000% |
| production | missed_field_goal | 106 | 0.000% | 5.906s | 3.000s | 6.604% | 34.906% | 84.906% |
| production | missed_free_throw | 14 | 0.000% | 51.429s | 39.500s | 0.000% | 0.000% | 0.000% |
| production | period_boundary | 18 | 0.000% | 3.556s | 2.500s | 33.333% | 50.000% | 66.667% |
| production | rebound | 105 | 0.000% | 10.810s | 3.000s | 20.952% | 35.238% | 72.381% |
| production | review_challenge | 2 | 0.000% | 18.000s | 18.000s | 0.000% | 0.000% | 0.000% |
| production | substitution | 136 | 0.000% | 61.926s | 20.000s | 1.471% | 5.882% | 5.882% |
| production | timeout | 16 | 0.000% | 17.938s | 3.000s | 37.500% | 43.750% | 62.500% |
| production | turnover | 26 | 0.000% | 7.962s | 2.000s | 30.769% | 57.692% | 80.769% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

## Temporal error distribution

| System | Error band | Events | Share |
| --- | --- | ---: | ---: |
| baseline | within_1_second | 134 | 18.457% |
| baseline | over_1_to_2_seconds | 106 | 14.601% |
| baseline | over_2_to_5_seconds | 177 | 24.380% |
| baseline | over_5_to_10_seconds | 71 | 9.780% |
| baseline | over_10_to_30_seconds | 103 | 14.187% |
| baseline | over_30_seconds | 135 | 18.595% |
| baseline | unmapped | 0 | 0.000% |
| production | within_1_second | 137 | 18.871% |
| production | over_1_to_2_seconds | 94 | 12.948% |
| production | over_2_to_5_seconds | 188 | 25.895% |
| production | over_5_to_10_seconds | 72 | 9.917% |
| production | over_10_to_30_seconds | 102 | 14.050% |
| production | over_30_seconds | 133 | 18.320% |
| production | unmapped | 0 | 0.000% |

Acc@tau uses all annotated events as the denominator, so an unmapped event is incorrect at every tolerance. MAE and median absolute error use mapped events only. The macro rows average the corresponding per-game metrics with equal weight per game. Machine-readable results are in `ocr_alignment_summary.csv`; per-event predictions and signed/absolute errors are in `ocr_alignment_detailed.csv`, and the failure-analysis bands are in `ocr_temporal_error_bands.csv`.
