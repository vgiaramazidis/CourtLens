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

The original annotation workbooks, RDF exports and intermediate per-game reports remain in `archive/research/pre-cleanup-2026-09-20/evaluation/`. That archive is local, ignored by Git and absent from a new clone. RDF regeneration is described in the pipeline guide; do not overwrite the final results here with a new evaluator run.
