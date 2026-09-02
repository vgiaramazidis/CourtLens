# OCR alignment evaluation

This evaluation compares complete OCR timeline versions against the same set
of manually verified Play-by-Play video timestamps. It implements the metrics
requested for the project:

- Acc@1s and Acc@2s: percentage of all evaluated events whose predicted video
  timestamp is within the selected tolerance. Unmapped events count as errors.
- MAE: mean absolute timestamp error over successfully mapped events.
- UER: percentage of valid PBP events for which no OCR match is available.
- Overall micro results, macro-average across games, and results by action
  category.

## 1. Create the annotation sample

The command below selects a deterministic, stratified sample of 20 PBP actions
per category across the games with video:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py sample
```

This creates `evaluation/ground_truth/ocr_alignment_ground_truth.csv`. The
Excel version in the same directory contains the same rows with formatting,
filters, frozen headers, and validation for annotation status.

The command refuses to overwrite an existing sample. This protects completed
annotations. Only use `--force` when you deliberately want to replace the
sample and discard its existing annotation values.

### Full-game case study

For a complete manual review of every PBP action in one game, use
`--all-actions` together with a season and game code:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py sample \
  --season-code E2023 \
  --game-code 333 \
  --all-actions \
  --output evaluation/ground_truth/E2023_333_full_pbp_ground_truth.csv
```

This repository also includes completed, formatted full-game annotation
workbooks for `E2023/333` (534 actions) and `E2024/220` (574 rows: 573
annotated and one excluded). The rows remain in `original_event_id` order so
annotation follows each game chronologically. Full-game case studies are
separate from, and do not replace, the 260-action stratified sample.

## 2. Annotate the video timestamp

For every selected row:

1. Open `youtube_review_url`.
2. Locate the exact start of the PBP action—not the scoreboard update, replay,
   or close-up after the action.
3. Enter the YouTube timestamp in seconds in
   `ground_truth_video_seconds`.
4. Set `annotation_status` to `Annotated`.
5. Use `Exclude` only when the official video does not contain enough evidence
   to establish ground truth, and explain why in `notes`.

The CSV is the evaluator's canonical input. If annotation is performed in the
provided Excel workbook, export only its `Ground Truth` sheet as UTF-8 CSV and
replace `evaluation/ground_truth/ocr_alignment_ground_truth.csv` before running
the evaluator. Do not change the column names.

For a full-game case study, export its `Ground Truth` sheet to the corresponding
`evaluation/ground_truth/<SEASON>_<GAME>_full_pbp_ground_truth.csv` file.
Preserve every row and event identifier.

Do not change the event identifiers or the PBP/synchronization columns. Use the
same annotation convention for the archived baseline and current production;
the evaluator compares both automatically.

## 3. Run the evaluation

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py evaluate
```

To evaluate the completed `E2023/333` case study without changing the default
stratified-sample workflow:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py evaluate \
  --ground-truth evaluation/ground_truth/E2023_333_full_pbp_ground_truth.csv \
  --output-dir evaluation/results/E2023_333_full_game
```

Evaluate the completed `E2024/220` case study in the same way:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py evaluate \
  --ground-truth evaluation/ground_truth/E2024_220_full_pbp_ground_truth.csv \
  --output-dir evaluation/results/E2024_220_full_game
```

Default systems:

- `baseline`: `evaluation/ocr_baselines/production_before_final_ocr/`
- `production`: `video_timelines/`

Generated outputs in `evaluation/results/`:

- `ocr_alignment_report.md`: concise overall comparison.
- `ocr_alignment_summary.csv`: overall, per-category, macro-game, and full-PBP
  metrics.
- `ocr_alignment_detailed.csv`: prediction and error for every annotated event.

Custom systems and tolerances may be supplied explicitly:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py evaluate \
  --system baseline=evaluation/ocr_baselines/production_before_final_ocr \
  --system production=video_timelines \
  --tolerance 1 \
  --tolerance 2
```

The local `data/processed/all_actions/` files are required. Generate them with
`parser.py` or `ocr_triplets.py` before creating the sample on a fresh clone.
