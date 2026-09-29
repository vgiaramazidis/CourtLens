# OCR synchronization evaluation

Start with [REPORT.md](REPORT.md) for the methodology, accuracy, coverage and efficiency findings.

- [Combined summary](results/combined_summary.csv).
- [Per-action evidence](results/per_action_results.csv).
- [Temporal error bands](results/temporal_error_bands.csv).
- [Failure analysis](results/failure_analysis.md).
- [Controlled efficiency record](efficiency/E2023_170_metrics.json).
- [Human annotation CSVs](../../fixtures/ocr/ground_truth/).
- [All 28 baseline timelines](../../fixtures/ocr/baseline/).

The results describe the recorded study. The preserved ground truth and baseline fixtures are shared with the evaluator.

To reproduce from the repository root:

```bash
.venv/bin/python -m tools.evaluation.ocr --output-dir outputs/evaluation/ocr
```

This requires the local generated action artifacts described in the [data pipeline guide](../../../README.md#data-pipeline), as well as the versioned runtime timelines. A source clone alone does not include all generated input data.

The versioned ground-truth CSVs contain the final annotation status, video timestamp and row notes for all three games. Local working spreadsheets and generated exports under `outputs/` are supplementary, and are not included in a new clone. Do not overwrite recorded results with a new evaluator run.

## Annotation Protocol

Ground truth records elapsed seconds in the source video, checked against the live action and available audio. Reference timestamps are navigation hints. Each PBP row is reviewed individually, including actions with the same game clock. The conventions below combine the annotator’s confirmed rules and the final row notes.

| Group and codes | Full event names | Timestamp rule |
| --- | --- | --- |
| Field goals | 2FGM / 2FGA: two-point shot made / missed. 3FGM / 3FGA: three-point shot made / missed. | Ball release from the shooter’s hands. |
| Free throws | FTM / FTA: free throw made / missed. | Ball release from the shooter’s hands. |
| Assists | AS: assist. | Ball release on the decisive pass. One free-throw-linked assist uses the ball entering the basket (E2024/220, event 17). |
| Rebounds | O / D: offensive / defensive rebound. | The player catches or controls the ball. Team rebounds use the relevant touch, whistle, out-of-bounds or jump-ball event. A tip-in can share its shot timestamp. |
| Possession loss | TO / ST: turnover / steal. | The decisive loss or dislodging touch. A linked steal and turnover share that instant. Violations use the whistle or expiry buzzer. |
| Blocks | FV: block. | The defender contacts the ball to block the shot. |
| Fouls | CM: defensive foul. OF: offensive foul. RV: foul drawn. CMU: unsportsmanlike foul. CMT: technical foul. C: coach foul. B: bench foul. | The referee’s whistle. Linked committed/drawn fouls share a timestamp. An offensive foul can share its turnover timestamp. |
| Substitutions | IN / OUT: player in / player out. | The substitution buzzer. After a timeout or period break, use the next restart, marked by the whistle and ball delivery to the inbounder. Row notes also record visible signals. |
| Timeouts | TOUT: timeout. TOUT_TV: television timeout. | The whistle or signal starting the timeout. |
| Period boundaries | JB: jump ball. BP: period start. EP: period end. EG: game end. | JB uses the jump-ball touch. First-period BP shares JB. Later BP uses ball delivery for the restart. EP and EG use the ending buzzer. |
| Reviews | CCH: coach challenge. | The visible challenge gesture when identifiable. One recorded case uses the buzzer shared with the first substitution (E2023/170, event 300). |

### Exceptions and annotation quality

The final CSVs retain 1,841 rows, including 1,833 Annotated and eight Exclude records. Some included notes describe approximate timing when sound or visibility is insufficient, so these labels are not uniformly frame-exact. Notes also flag PBP clock discrepancies. Exclusions, estimates and shared timestamps must remain visible when interpreting timing error. This documentation does not re-annotate events or change the reported metrics.

The final notes document these examples:

- E2023/333, events 4–5: shot release and assist pass release. Event 36 also uses release for a free throw.
- E2024/220, events 14–15: committed and drawn foul share the whistle. Event 17 is a free-throw-linked assist timed at the made basket.
- E2023/333, events 141, 143 and 357: team rebounds use a touch, foul whistle or jump ball. E2023/170, event 174 shares the tip-in timestamp.
- E2024/220, events 146 and 181: turnover from clock expiry uses the buzzer or whistle.
- E2023/333, events 34 and 294: substitution buzzer and substitutions at the next period start. E2023/170, event 62 records substitutions after a timeout.
- E2023/333, event 220 uses the challenge gesture. E2023/170, event 300 uses the buzzer with the first substitution.
- Some retained annotations are estimates, including E2023/170 events 90, 266 and 577, and E2023/333 events 23, 64, 65, 483 and 578. Their notes must not be treated as evidence of frame-level precision.
- The eight exclusions are E2023/170 events 117–123 and E2024/220 event 211. Notes flag PBP clock discrepancies in these sequences, but not every excluded row has an individual explanation.

### Recording and source precedence

Store the verified elapsed video time in `ground_truth_video_seconds`, retain `original_event_id`, and record `annotation_status` as `Annotated` or `Exclude`. Preserve the original PBP and synchronization clocks. Record ambiguity and exceptions in `notes`. The evaluator includes only `Annotated` rows. Identical game clocks do not require identical video timestamps.

The final CSV notes and the annotator’s confirmed conventions define this protocol. An older unfilled workbook template describes shot-motion onset and generic visual cues. It is not the final event-specific procedure. The available corrected E2024/220 workbook contains the notes in its `notes` column, rather than Excel cell comments. The completed CSV exports preserve the final notes for all three games. No annotation timestamps or statuses were changed while documenting this protocol.
