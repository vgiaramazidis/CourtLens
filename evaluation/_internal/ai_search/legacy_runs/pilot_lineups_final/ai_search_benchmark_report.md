# AI Search benchmark

Generated: 2026-09-10T11:07:47.045922+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 4/4 across 2 configurations.

Estimated standard API cost: `$0.074127`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 11082 | 5853 | $0.069300 | 20754.1ms |
| openai | gpt-5-mini | ontology | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 10595 | 1406 | $0.004827 | 14659.0ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| lineup | 2 |

## Manual review

Manual decisions are recorded for 4/4 rows in `ai_search_benchmark_results.csv`. Rows marked `not_reviewed` were blocked by provider availability or quota; `not_available` means no generated query was preserved for inspection.
