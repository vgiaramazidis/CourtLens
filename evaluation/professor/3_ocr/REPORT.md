# OCR video synchronization evaluation

## Objective

The system reads the visible game clock from full-game EuroLeague broadcasts
and creates a mapping from official Play-by-Play (PBP) actions to YouTube video
timestamps. This evaluation measures catalog coverage, temporal accuracy
against human annotations, processing efficiency, and known failure modes.

## Evaluation data

Three complete games were annotated manually using the start of the real action
in the broadcast rather than the later scoreboard update or replay.

| Game | Included actions | Excluded rows |
| --- | ---: | ---: |
| E2023/333 | 534 | 0 |
| E2024/220 | 573 | 1 |
| E2023/170 | 726 | 7 |
| **Total** | **1,833** | **8** |

The eight excluded rows remain in the annotation files. They are omitted from
temporal metrics because the video does not provide enough evidence for a
defensible timestamp. Exclusion does not modify the official PBP or production
RDF.

Two timeline versions are evaluated against exactly the same ground truth:

- `baseline`: the archived timelines before the final OCR synchronization
  changes.
- `production`: the timelines currently used by the application and RDF
  generator.

## Metrics

- **Coverage** is the percentage of eligible PBP actions linked to an OCR
  observation.
- **UER** is the unmapped event rate: unmatched eligible PBP actions divided by
  all eligible PBP actions.
- **Acc@tau** is the percentage of annotated actions whose predicted video time
  is within tau seconds of human ground truth. Unmapped actions count as
  incorrect.
- **MAE** is the mean absolute temporal error over mapped annotated actions.
- **Median AE** is the median absolute temporal error over mapped annotated
  actions.
- **Micro-average** pools all annotated actions. **Macro-average** gives each
  annotated game equal weight.

## Combined temporal results

| System | N | Mapped | UER | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 1,833 | 1,833 | 0.000% | 20.542s | 4.000s | 17.567% | 29.078% | 57.665% |
| Production | 1,833 | 1,833 | 0.000% | 20.435s | 4.000s | 17.621% | 28.369% | 57.720% |

| System | Games | Mean UER | Mean MAE | Mean median AE | Mean Acc@1s | Mean Acc@2s | Mean Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 3 | 0.000% | 20.263s | 4.000s | 17.527% | 28.646% | 57.686% |
| Production | 3 | 0.000% | 20.158s | 4.167s | 17.540% | 27.975% | 57.702% |

Production is marginally better in micro MAE, Acc@1, and Acc@5, while baseline
is better in Acc@2. Of the 1,833 annotated actions, 1,630 have equal absolute
error, production is better for 75, and baseline is better for 128. The result
is therefore mixed, with no evidence of a uniform improvement across every
action or game.

## Production results by game

| Game | N | MAE | Median AE | Acc@1s | Acc@2s | Acc@5s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E2023/170 | 726 | 22.510s | 4.000s | 18.871% | 31.818% | 57.713% |
| E2023/333 | 534 | 16.367s | 4.500s | 18.914% | 24.532% | 56.929% |
| E2024/220 | 573 | 21.599s | 4.000s | 14.834% | 27.574% | 58.464% |

## Production results by action type

| Action category | N | MAE | Median AE | Acc@5s |
| --- | ---: | ---: | ---: | ---: |
| Made field goal | 208 | 5.245s | 3.000s | 87.500% |
| Missed field goal | 242 | 5.764s | 3.000s | 87.603% |
| Foul | 262 | 11.550s | 1.000s | 80.534% |
| Rebound | 247 | 9.279s | 4.000s | 77.328% |
| Assist | 114 | 9.544s | 4.500s | 71.930% |
| Timeout | 36 | 15.917s | 2.000s | 69.444% |
| Made free throw | 122 | 58.066s | 47.500s | 0.820% |
| Missed free throw | 31 | 55.000s | 40.000s | 6.452% |
| Substitution | 416 | 42.712s | 20.000s | 12.500% |
| Review/challenge | 7 | 30.714s | 23.000s | 0.000% |

Field goals are localized reliably because the game clock normally moves near
the action. Free throws, substitutions, and reviews occur mainly while the
clock is stopped. A single OCR clock can therefore correspond to several PBP
actions spread across a much longer section of video.

## Full-catalog coverage

Across the 28 video games, there are 14,933 eligible PBP actions. Production
links 14,926 actions and leaves seven unmatched:

- Coverage: **99.953%**.
- UER: **0.046876%**.
- E2023/160: two unmatched actions caused by a clock gap greater than five
  seconds.
- E2023/331: five unmatched fourth-quarter actions; the first readable OCR
  clock is 9:44, outside the permitted period-opening and normal tolerances.

## Temporal error distribution

| Production error band | Events | Share |
| --- | ---: | ---: |
| Within 1 second | 323 | 17.621% |
| Over 1 to 2 seconds | 197 | 10.747% |
| Over 2 to 5 seconds | 538 | 29.351% |
| Over 5 to 10 seconds | 197 | 10.747% |
| Over 10 to 30 seconds | 209 | 11.402% |
| Over 30 seconds | 369 | 20.131% |

There are 334 human-ground-truth timestamps shared by multiple PBP actions,
covering 849 annotated events. These simultaneous or dead-ball groups explain
why very high mapping coverage can coexist with lower exact temporal accuracy.

## OCR processing efficiency

A controlled CPU benchmark used the cached local E2023/170 MP4 so network and
download time were excluded.

| Measure | Result |
| --- | ---: |
| Full media duration | 213.051 min |
| Video duration scanned | 197.717 min |
| End-to-end OCR processing time | 521.556s (8.693 min) |
| Processing time per scanned video minute | 2.638s |
| Processing speed | 22.745× real-time |
| Sampling interval | 1.000s |
| Timeline points | 3,103 |

Environment: Apple silicon arm64, 10 CPU cores, 16 GB memory, macOS 26.6.2,
Python 3.13.7, EasyOCR 1.7.2, OpenCV 5.0.0.93, and PyTorch 2.13.0. The candidate
passed structural validation and was byte-for-byte identical to the production
E2023/170 timeline.

## Failure analysis

The main observed failure categories are:

1. Scorebug occlusion or absence during a possession.
2. Late scorebug appearance at the beginning of a period.
3. Replay or halftime-highlight clocks that resemble a new live period.
4. Clock corrections that briefly show invalid intermediate values.
5. Frozen clocks during free throws, substitutions, timeouts, and reviews.
6. Camera cuts that create long periods without readable clock graphics.
7. Assists whose decisive pass occurs before the related scoring clock.
8. Multiple legitimate PBP actions sharing one OCR observation.

The production tracker uses initial-clock confirmation, guarded period reset,
multi-frame confirmation after long gaps, replay/compressed-period rejection,
and action-specific synchronization tolerances. Increasing tolerance globally
would recover some gaps but would also increase incorrect links around stopped
clocks and replays, so it is not used as a general solution.

The full quantitative and qualitative breakdown is available in
`results/failure_analysis.md`.

## RDF output and validation

Production RDF stores only OCR observations linked to at least one PBP action;
all raw OCR observations remain in timeline CSV files for evaluation and
debugging. The delivery contains 28 RDF files with:

- 57,412 RDF triples.
- 7,053 linked OCR observations.
- 14,926 PBP-to-OCR links.
- Zero malformed lines, duplicate triples, untyped link targets, or references
  missing from `hasOCRObservation`.

## Limitations

- The human temporal benchmark contains three complete games, not all 28 video
  games.
- The system aligns PBP actions through the game clock; it does not detect the
  visual action class independently. Conventional object-detection precision is
  therefore not reported.
- Exact timing for stopped-clock actions cannot be recovered from clock OCR
  alone. Additional visual signals would be required for individual free throws
  and substitutions.
- Broadcast-cause labels such as replay and camera cut are based on reviewed
  cases. They are not inferred automatically from temporal error alone.

## Reproducibility

Machine-readable results are stored in `results/`, the human annotations are in
`ground_truth/`, and the controlled runtime record is in `efficiency/`. Older
baselines and generated per-game reports are preserved in
`evaluation/_internal/ocr/` for reproducibility and are not part of the main
professor-facing deliverables.
