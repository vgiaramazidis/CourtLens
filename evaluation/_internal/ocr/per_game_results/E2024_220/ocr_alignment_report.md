# OCR alignment evaluation

Annotated events: 573

Pending annotations: 0; excluded: 1.

## Overall micro-average

| System | N | Mapped | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 573 | 573 | 0.000% | 22.031s | 4.000s | 14.834% | 27.225% | 57.941% |
| production | 573 | 573 | 0.000% | 21.599s | 4.000s | 14.834% | 27.574% | 58.464% |

## Macro-average across games

| System | Games | Mean UER | Mean MAE | Mean median AE | Mean Acc@1s | Mean Acc@2s | Mean Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 1 | 0.000% | 22.031s | 4.000s | 14.834% | 27.225% | 57.941% |
| production | 1 | 0.000% | 21.599s | 4.000s | 14.834% | 27.574% | 58.464% |

## Per-game metrics

| System | Game | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | E2024/220 | 573 | 0.000% | 22.031s | 4.000s | 14.834% | 27.225% | 57.941% |
| production | E2024/220 | 573 | 0.000% | 21.599s | 4.000s | 14.834% | 27.574% | 58.464% |

## Per-action-category metrics

| System | Category | N | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | assist | 40 | 0.000% | 12.500s | 4.000s | 2.500% | 10.000% | 72.500% |
| baseline | defensive_play | 16 | 0.000% | 12.062s | 4.000s | 6.250% | 18.750% | 68.750% |
| baseline | foul | 74 | 0.000% | 14.162s | 2.000s | 45.946% | 70.270% | 81.081% |
| baseline | made_field_goal | 62 | 0.000% | 7.226s | 3.000s | 12.903% | 38.710% | 85.484% |
| baseline | made_free_throw | 35 | 0.000% | 64.886s | 47.000s | 0.000% | 0.000% | 0.000% |
| baseline | missed_field_goal | 71 | 0.000% | 4.761s | 3.000s | 7.042% | 21.127% | 91.549% |
| baseline | missed_free_throw | 7 | 0.000% | 67.143s | 40.000s | 0.000% | 0.000% | 14.286% |
| baseline | period_boundary | 9 | 0.000% | 4.444s | 6.000s | 44.444% | 44.444% | 44.444% |
| baseline | rebound | 74 | 0.000% | 6.365s | 4.000s | 8.108% | 27.027% | 85.135% |
| baseline | review_challenge | 3 | 0.000% | 16.667s | 10.000s | 0.000% | 0.000% | 0.000% |
| baseline | substitution | 148 | 0.000% | 41.892s | 40.000s | 9.459% | 10.811% | 14.865% |
| baseline | timeout | 13 | 0.000% | 20.615s | 2.000s | 46.154% | 53.846% | 69.231% |
| baseline | turnover | 21 | 0.000% | 15.571s | 2.000s | 28.571% | 52.381% | 71.429% |
| production | assist | 40 | 0.000% | 12.550s | 4.000s | 2.500% | 10.000% | 72.500% |
| production | defensive_play | 16 | 0.000% | 12.375s | 4.500s | 6.250% | 12.500% | 62.500% |
| production | foul | 74 | 0.000% | 12.054s | 1.000s | 59.459% | 78.378% | 83.784% |
| production | made_field_goal | 62 | 0.000% | 7.274s | 3.000s | 12.903% | 35.484% | 85.484% |
| production | made_free_throw | 35 | 0.000% | 65.914s | 48.000s | 0.000% | 0.000% | 0.000% |
| production | missed_field_goal | 71 | 0.000% | 4.859s | 4.000s | 4.225% | 21.127% | 91.549% |
| production | missed_free_throw | 7 | 0.000% | 67.714s | 40.000s | 0.000% | 0.000% | 14.286% |
| production | period_boundary | 9 | 0.000% | 4.333s | 6.000s | 44.444% | 44.444% | 44.444% |
| production | rebound | 74 | 0.000% | 6.486s | 4.000s | 6.757% | 24.324% | 82.432% |
| production | review_challenge | 3 | 0.000% | 16.667s | 10.000s | 0.000% | 0.000% | 0.000% |
| production | substitution | 148 | 0.000% | 40.838s | 39.000s | 4.054% | 10.811% | 17.568% |
| production | timeout | 13 | 0.000% | 20.615s | 2.000s | 46.154% | 53.846% | 69.231% |
| production | turnover | 21 | 0.000% | 15.524s | 2.000s | 33.333% | 57.143% | 71.429% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

## Temporal error distribution

| System | Error band | Events | Share |
| --- | --- | ---: | ---: |
| baseline | within_1_second | 85 | 14.834% |
| baseline | over_1_to_2_seconds | 71 | 12.391% |
| baseline | over_2_to_5_seconds | 176 | 30.716% |
| baseline | over_5_to_10_seconds | 43 | 7.504% |
| baseline | over_10_to_30_seconds | 60 | 10.471% |
| baseline | over_30_seconds | 138 | 24.084% |
| baseline | unmapped | 0 | 0.000% |
| production | within_1_second | 85 | 14.834% |
| production | over_1_to_2_seconds | 73 | 12.740% |
| production | over_2_to_5_seconds | 177 | 30.890% |
| production | over_5_to_10_seconds | 47 | 8.202% |
| production | over_10_to_30_seconds | 56 | 9.773% |
| production | over_30_seconds | 135 | 23.560% |
| production | unmapped | 0 | 0.000% |

Acc@tau uses all annotated events as the denominator, so an unmapped event is incorrect at every tolerance. MAE and median absolute error use mapped events only. The macro rows average the corresponding per-game metrics with equal weight per game. Machine-readable results are in `ocr_alignment_summary.csv`; per-event predictions and signed/absolute errors are in `ocr_alignment_detailed.csv`, and the failure-analysis bands are in `ocr_temporal_error_bands.csv`.
