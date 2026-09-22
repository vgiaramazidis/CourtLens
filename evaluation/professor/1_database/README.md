# Database evaluation

Start with [REPORT.md](REPORT.md) for the dataset counts and SPARQL response-time results.

- [benchmark_runs.csv](benchmark_runs.csv): all measured executions.
- [benchmark_summary.csv](benchmark_summary.csv): aggregate timings.
- [queries_and_samples.json](queries_and_samples.json): queries and sample responses.

These files preserve the completed study, not a fresh measurement of the current server. The deployment address was removed from the public-facing report and JSON; queries, samples and measurements are unchanged.

To run a new benchmark from the repository root, export `SPARQL_ENDPOINT` in your shell and run:

```bash
.venv/bin/python -m tools.evaluation.database --output-dir outputs/evaluation/database
```

The CLI also accepts `--endpoint`. Keep new runs separate from this reviewed evidence.
