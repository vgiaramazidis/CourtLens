# OCR production baseline before the final timeline update

This directory contains the complete set of 28 production OCR timeline CSVs
that was active before the final `video_ocr.py` version was promoted on
2026-08-29. The files are retained as a fixed baseline for OCR alignment
evaluation and debugging.

The promotion was performed as one system-level change: all 28 old timelines
were archived here and all 28 candidate timelines became production together.
No per-game cherry-picking was used.

## System comparison

| Metric | Archived baseline | Promoted version |
| --- | ---: | ---: |
| Games | 28 | 28 |
| OCR observations | 54,801 | 60,722 |
| PBP actions synchronized | 14,926 | 14,926 |
| PBP actions unmatched | 7 | 7 |
| Structural validation errors | 0 | 0 |
| Timeline validation warnings | 23 | 12 |

The remaining seven unmatched PBP actions are the same actions in both
versions. They are caused by OCR clock coverage gaps rather than actions lost
from the Play-by-Play artifacts.

## Known evaluation limitation

When the game clock is stopped, several PBP actions can share exactly the same
quarter and clock value—for example a foul, free throws, substitutions and a
timeout. A clock-only OCR timeline cannot assign a different video timestamp
to every such action. These cases require manually annotated ground truth when
calculating Acc@tau and MAE.

The current production timelines are stored in `video_timelines/`. The
candidate-generation logs and local videos remain in the ignored local cache
`tmp/video_ocr_workspace/`.
