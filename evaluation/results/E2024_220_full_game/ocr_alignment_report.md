# OCR alignment evaluation

Annotated events: 573

Pending annotations: 0; excluded: 1.

## Ground-truth metrics

| System | N | Mapped | UER | MAE | Acc@1s | Acc@2s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 573 | 573 | 0.000% | 22.031s | 14.834% | 27.225% |
| production | 573 | 573 | 0.000% | 21.599s | 14.834% | 27.574% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

Per-category and macro-by-game results are available in `ocr_alignment_summary.csv`; per-event predictions and errors are available in `ocr_alignment_detailed.csv`.
