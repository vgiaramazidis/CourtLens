# OCR failure analysis

## Scope

This analysis uses 1,833 manually annotated Play-by-Play actions from three
complete games: E2023/333, E2024/220, and E2023/170. Eight additional rows were
excluded during annotation. Notes flag PBP clock discrepancies in the excluded sequences. Some included rows also retain approximate timestamps. See the [Annotation Protocol](../README.md#annotation-protocol) for event-specific rules, row examples and limitations.

The OCR system detects game-clock observations and then links official
Play-by-Play actions to the nearest valid observation. It does not independently
classify basketball actions from video. Consequently, coverage and temporal
error are the primary quantitative measures; conventional object-detection
precision is not applicable.

## Quantitative findings

All 1,833 annotated actions were linked by both systems. For production, the
median absolute error is 4.000 seconds and 57.720% of actions are within five
seconds of human ground truth.

| Production error band | Events | Share |
| --- | ---: | ---: |
| Within 1 second | 323 | 17.621% |
| Over 1 to 2 seconds | 197 | 10.747% |
| Over 2 to 5 seconds | 538 | 29.351% |
| Over 5 to 10 seconds | 197 | 10.747% |
| Over 10 to 30 seconds | 209 | 11.402% |
| Over 30 seconds | 369 | 20.131% |
| Unmapped | 0 | 0.000% |

The full 28-game catalog contains 14,933 eligible PBP actions. Production links
14,926 and leaves seven unmatched, for 99.953% coverage and 0.046876% UER.
Four unmatched actions have no OCR clock within the normal five-second window;
three are period-opening actions without an OCR clock inside the extended
twelve-second window.

## Results by problem-sensitive action type

| Action type | N | Error over 5s | Error over 30s | Main interpretation |
| --- | ---: | ---: | ---: | --- |
| Substitution | 416 | 364 | 175 | Several IN/OUT rows share one dead-ball clock, while the visible substitution can occur much later. |
| Made free throw | 122 | 121 | 90 | The game clock is stopped; the same clock can cover the foul, preparation, multiple attempts, and the score update. |
| Missed free throw | 31 | 29 | 24 | The stopped clock cannot locate an individual attempt precisely. |
| Rebound | 247 | 56 | 19 | The official timestamp and control of the ball can differ by several seconds. |
| Foul | 262 | 51 | 30 | Whistle time and PBP registration/scorebug time are not always identical. |
| Assist | 114 | 32 | 7 | The linked shot clock locates the possession, but the decisive pass occurs before the basket. |
| Made field goal | 208 | 26 | 3 | Usually localized well because the clock is moving near the release/basket. |
| Missed field goal | 242 | 30 | 8 | Usually localized well, with ambiguity between release, rim contact, and rebound. |

There are 334 ground-truth timestamps shared by multiple PBP actions, covering
849 of the 1,833 annotated events. This confirms that simultaneous or
dead-ball action sequences are a major limitation of clock-only alignment.

## Broadcast and OCR failure categories

| Category | Observed behavior | Current handling | Remaining limitation |
| --- | --- | --- | --- |
| Scorebug occlusion or absence | No clock is readable during a possession or broadcast graphic. | The nearest observation is used only inside the action-specific tolerance. | E2023/160 retains two unmatched actions where the gap is 8–9 seconds. |
| Late period scorebug | A period begins before the clock overlay appears. | Opening metadata receives a guarded twelve-second tolerance. | E2023/331 starts its fourth-quarter OCR coverage at 9:44, leaving five actions unmatched. |
| Replay or halftime highlights | A replay can show a plausible clock from an earlier game segment. | Period changes require plausible reset and multi-frame temporal confirmation; compressed false periods can be rolled back. | A visually plausible replay clock can still be ambiguous without team score recognition. |
| Clock correction or challenge | The broadcast briefly animates through incorrect intermediate clock values. | Large post-gap changes require a confirmed descending sequence before acceptance. | The exact review decision/action time remains a semantic annotation choice. |
| Frozen clock | The displayed clock can remain fixed during a table problem, timeout, foul, or free throws. | Confirmed opening anchors and repeated stopped clocks are retained without treating them as moving time. | One clock value cannot distinguish several events that occur while time is stopped. |
| Camera cut | The scorebug disappears or becomes unreadable when the camera changes. | Missing frames are skipped; valid observations resume after the cut. | Long cuts create a coverage gap that cannot be reconstructed from clock OCR alone. |
| Assist timing | The PBP assist appears near or after the scoring row. | The assist is synchronized to its related made 2PT, 3PT, or FTM clock. | The decisive pass is earlier than the scoring clock, so video playback needs a lead offset. |
| Duplicate action | Multiple PBP rows can legitimately share one OCR observation. | RDF stores one observation and permits multiple PBP-to-observation links. | These are not OCR duplicates and must not be counted as false positives. |

## Baseline comparison

Production has lower absolute error for 75 actions, baseline has lower error for
128, and 1,630 actions are unchanged. Despite more individually changed actions
favoring the baseline, production has slightly lower overall MAE (20.435s versus
20.542s) and slightly higher Acc@5 (57.720% versus 57.665%). The improvement is
therefore small and should be reported as mixed rather than as a uniform gain.

## Interpretation

The seven catalog-level unmatched actions are genuine OCR coverage gaps. Most
large errors in the manually annotated games are different: an OCR clock exists
and produces a valid link, but a stopped clock or shared PBP timestamp cannot
identify the exact real-world instant of each action. Improving those cases
requires additional visual signals or event-specific playback offsets, not a
wider clock-matching tolerance.

Frame-level causes such as replay, camera cut, and occlusion are documented as
case studies rather than automatically assigned to every high-error row. A time
difference alone is insufficient evidence to infer the broadcast cause.
