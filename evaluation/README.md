# Evaluation deliverables

For the professor, use only the four numbered folders inside `professor/`:

| Folder | What it contains | Status |
| --- | --- | --- |
| `1_database/` | Dataset statistics, representative SPARQL queries/results, and response times | Complete |
| `2_ai_search/` | Twenty natural-language benchmark questions and the Gemini/OpenAI comparison protocol | Complete; both prompts and both providers manually reviewed |
| `3_ocr/` | Final OCR report, human ground truth, per-action results, efficiency, failure analysis, and RDF triples | Complete |
| `4_user_evaluation/` | The professor's 10 tasks/questions, one open question, protocol, and response sheet | Ready; participant collection pending |

The `_internal/` folder contains baselines, per-game generated reports, the old stratified sample, and drafts. These files support reproducibility but are **not part of the professor-facing evaluation**.

The main OCR/RDF delivery ZIP is available at:

`outputs/019fd09c-406e-7fb2-bb27-12d197d6758e/ocr_rdf_evaluation_package_2026-09-07.zip`

## What remains

1. Complete the user study with real participants.

The OCR and database evaluations do not require additional work.

To reproduce the three-game OCR comparison, run the single command:

```bash
.venv/bin/python src/data_pipeline/ocr_evaluation.py
```
