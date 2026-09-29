# Evaluation

Keep final academic reports and their supporting evidence under `professor/`, and shared reproducible inputs under `fixtures/`. New runs write to the ignored `outputs/evaluation/` directory.

## Final academic deliverables

| Evaluation | Start here | Contents |
| --- | --- | --- |
| Database | [Database README](professor/1_database/README.md) | Dataset statistics, measured queries, samples and response times |
| AI Search | [AI Search README](professor/2_ai_search/README.md) | Methodology, reviewed final comparison and row-level results |
| OCR | [OCR README](professor/3_ocr/README.md) | Accuracy, coverage, efficiency and failure analysis |
| User study | [User evaluation README](professor/4_user_evaluation/README.md) | Completed ten-participant study, nine tasks, five ratings and qualitative feedback |

These reports preserve the completed historical evaluations. They do not claim that the current application, prompts or remote services have been benchmarked again. The technical benchmark results remain historical measurements. The user-study folder contains the completed participant evaluation.

## Shared inputs

| Input | Purpose |
| --- | --- |
| `fixtures/ai_search_questions.json` | Fixed natural-language Search benchmark |
| `fixtures/ai_search_complex_questions.json` | Complex lineup, height, presence/absence and counting questions with independently checked reference results |
| `fixtures/ocr/ground_truth/*.csv` | Human-annotated actions for the three reference games |
| `fixtures/ocr/baseline/*.csv` | Earlier timelines for all 28 games used by the full-catalog coverage comparison |

Run commands from the repository root:

```bash
# Inspect options; these do not make network requests.
.venv/bin/python -m tools.evaluation.database --help
.venv/bin/python -m tools.evaluation.ai_search --help
.venv/bin/python -m tools.evaluation.ocr --help
```

The database benchmark uses `SPARQL_ENDPOINT` or `--endpoint`. AI Search evaluation calls the running backend, defaults to OpenAI, and can incur provider costs. OCR evaluation requires the local generated action artifacts described in [the pipeline guide](../README.md#data-pipeline), plus the versioned runtime timelines.

```bash
.venv/bin/python -m tools.evaluation.database
.venv/bin/python -m tools.evaluation.ai_search
.venv/bin/python -m tools.evaluation.ocr
```

To repeat the complex Search regression suite against the running backend:

```bash
.venv/bin/python -m tools.evaluation.ai_search --questions evaluation/fixtures/ai_search_complex_questions.json --output-dir outputs/evaluation/ai_search_complex
```

These cases compare exact action sets, requested totals and five-player ranking results against references calculated independently from the selected game's actions and lineups. A mismatch makes the command fail even when the API returns HTTP 200. The references cover E2023 game 333 and must be rechecked if its source data changes. Matching results alone do not prove that every generated query or explanation is correct.

Use `--output-dir` to keep individual runs separate. Final reports, protocols and selected supporting results are retained under `professor/` and are intended for version control. The versioned fixtures preserve the inputs used by the evaluators. Local working files and intermediate exports under `outputs/` are not required in the public evaluation tree. The user-study workbook uses pseudonymous participant IDs. Recruitment records and personal identifiers do not belong in this folder.
