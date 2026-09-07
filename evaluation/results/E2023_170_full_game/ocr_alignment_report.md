# OCR alignment evaluation

Annotated events: 726

Pending annotations: 0; excluded: 7.

## Ground-truth metrics

| System | N | Mapped | UER | MAE | Acc@1s | Acc@2s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 726 | 726 | 0.000% | 22.565s | 18.457% | 33.058% |
| production | 726 | 726 | 0.000% | 22.510s | 18.871% | 31.818% |

## Full-catalog UER

| System | PBP actions | Mapped | Unmapped | UER |
| --- | ---: | ---: | ---: | ---: |
| baseline | 14933 | 14926 | 7 | 0.047% |
| production | 14933 | 14926 | 7 | 0.047% |

Per-category and macro-by-game results are available in `ocr_alignment_summary.csv`; per-event predictions and errors are available in `ocr_alignment_detailed.csv`.
