# OCR alignment evaluation

Annotated events: 534

Pending annotations: 0; excluded: 0.

## Ground-truth metrics

| System | N | Mapped | UER | MAE | Acc@1s | Acc@2s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 534 | 534 | 0.000% | 16.193s | 19.288% | 25.655% |
| production | 534 | 534 | 0.000% | 16.367s | 18.914% | 24.532% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

Per-category and macro-by-game results are available in `ocr_alignment_summary.csv`; per-event predictions and errors are available in `ocr_alignment_detailed.csv`.
