# AI Search benchmark

Generated: 2026-09-10T11:29:10.892513+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 8/12 across 2 configurations.

Estimated standard API cost: `$0.057040`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

Warning: 1 failed requests have no usage metadata, so the cost total excludes them. Provider failures before generation normally report no billable tokens.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 2/6 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 9265 | 4279 | $0.049665 | 17330.2ms |
| openai | gpt-5-mini | ontology | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 25954 | 2819 | $0.007374 | 7136.3ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| event_chain | 1 |
| lineup | 2 |
| percentage | 1 |
| player_assist_relation | 1 |
| simple_event_retrieval | 1 |

## Manual review

Manual decisions are recorded for 8/12 rows in `ai_search_benchmark_results.csv`. Rows marked `not_reviewed` were blocked by provider availability or quota; `not_available` means no generated query was preserved for inspection.
