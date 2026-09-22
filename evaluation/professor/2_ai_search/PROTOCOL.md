# AI Search evaluation

This benchmark evaluates the complete natural-language-to-SPARQL path: generated query, database result, Play-by-Play overlay behavior, and end-to-end response time.

## Fixed benchmark

[`evaluation/fixtures/ai_search_questions.json`](../../fixtures/ai_search_questions.json) contains 20 fixed questions for `E2023/333`. They cover event retrieval, player statistics, percentages, assist relations, shot locations, lineups, event chains, and temporal/score conditions.

The available providers and models are:

- Gemini using `gemini-3.5-flash` by default;
- OpenAI using `gpt-5-mini`.

Both providers support the same two prompt variants:

- `simple`: the professor's flat-vocabulary baseline: the permitted properties
  and classes are listed, but their relationships and query templates are not
  explained;
- `ontology`: the complete production ontology-aware prompt.

## Current result status

`results/final_20_ontology/` is the completed 40-request comparison: all 20
questions completed for both Gemini and GPT-5 Mini.

`results/final_20_simple/` currently combines the complementary runs produced
by Vasilis and Teo. All 40 requests completed and received manual semantic
review. With the flat-vocabulary prompt, Gemini produced 10/20 correct queries
and results, while GPT-5 Mini produced 1/20 correct queries and 2/20 correct
results. Overlay compatibility was 7/20 for each provider. These results are
the finalized simple-prompt baseline for comparison with the ontology prompt.

## Configure and start the backend

Keys must be supplied through environment variables and must never be committed.

Gemini as the default frontend provider:

```bash
export GEMINI_API_KEY="your-gemini-key"
export AI_SEARCH_PROVIDER="gemini"
.venv/bin/uvicorn src.backend.app:app --host 127.0.0.1 --port 8000 --env-file .env
```

OpenAI GPT-5 mini as the default frontend provider:

```bash
export OPENAI_API_KEY="your-openai-key"
export AI_SEARCH_PROVIDER="openai"
.venv/bin/uvicorn src.backend.app:app --host 127.0.0.1 --port 8000 --env-file .env
```

The frontend defaults to the configured provider and also offers a per-search provider selector. Configure `SPARQL_ENDPOINT` in `.env`; see the root README for setup.

## Run evaluations

Run the five-question, two-provider ontology pilot before spending credits on the
full benchmark:

```bash
.venv/bin/python -m tools.evaluation.ai_search \
  --question-id Q01 \
  --question-id Q06 \
  --question-id Q09 \
  --question-id Q11 \
  --question-id Q19 \
  --provider gemini \
  --provider openai \
  --prompt-variant ontology \
  --output-dir outputs/evaluation/ai_search/pilot_5_gemini_vs_openai
```

Repeated `--question-id` options preserve the requested order and keep pilot
runs separate from the full 20-question benchmark.

Run the current default OpenAI configuration:

```bash
.venv/bin/python -m tools.evaluation.ai_search
```

Run only OpenAI GPT-5 mini:

```bash
.venv/bin/python -m tools.evaluation.ai_search \
  --provider openai \
  --prompt-variant ontology
```

Run the professor's two-provider/two-prompt comparison using GPT-5 mini:

```bash
.venv/bin/python -m tools.evaluation.ai_search \
  --provider gemini \
  --provider openai \
  --prompt-variant simple \
  --prompt-variant ontology
```

This last command performs 80 model requests: 20 questions × 2 providers × 2 prompts.

When the Gemini project has a five-requests-per-minute quota, add
`--gemini-delay-seconds 13` so a full run does not fail because of the rate
limit. The delay is applied only between Gemini requests.

New results are written to `outputs/evaluation/ai_search/`. The reviewed files in `results/` are preserved historical evidence; do not overwrite them with a new run. Evaluation requests bypass the AI cache and receive query/model metadata. Normal searches retain caching; Video Analysis can display the generated query in its optional editor.

Each evaluation row also records the provider-reported input, cached-input,
output, reasoning, and total token counts. `estimated_standard_cost_usd` applies
the documented standard API rates for the returned model. It is an estimate,
not a billing receipt: Gemini free-tier usage and provider credits can reduce the
amount actually charged. The result CSV stores a five-binding JSON preview so
semantic review does not rely on result counts alone.

## Manual correctness review

Automated checks verify that the query is read-only, contains the selected game/season scope, and produces the expected Play-by-Play filter behavior. They do not prove semantic correctness.

For every completed question, fill in:

- `query_correct_human`: `yes` or `no`;
- `result_correct_human`: `yes` or `no`;
- `review_notes`: the concrete reason for acceptance or failure.

Compare correctness and latency by provider, model, and prompt variant. Use a different `--output-dir` when preserving multiple independent runs.
