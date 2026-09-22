# AI Search evaluation

Start with [REPORT.md](REPORT.md) for the final comparison and [PROTOCOL.md](PROTOCOL.md) for the method and current run commands.

- [Ontology prompt results](results/final_20_ontology/ai_search_benchmark_report.md).
- [Simple prompt results](results/final_20_simple/ai_search_benchmark_report.md).
- [Fixed benchmark questions](../../fixtures/ai_search_questions.json).

Each results folder includes a CSV with generated queries, result previews, timings, token usage and manual review notes. These are historical measurements of the evaluated models and prompts. Later prompt and interface changes have not been re-evaluated by this restoration; the recorded scores must not be presented as fresh results for the current application.

New runs go to `outputs/evaluation/ai_search/`. Pilot runs, retries and intermediate merges remain in the local research archive. The question fixture is shared with the evaluator rather than duplicated here.
