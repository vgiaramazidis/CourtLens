# AI Search benchmark

Generated: 2026-09-10T10:54:15.176233+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 18/22 across 2 configurations.

Estimated standard API cost: `$0.235351`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

Warning: 2 failed requests have no usage metadata, so the cost total excludes them. Provider failures before generation normally report no billable tokens.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 9/11 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 39575 | 20220 | $0.222150 | 14561.7ms |
| openai | gpt-5-mini | ontology | 9/11 | 9/9 | 9/9 | 9/9 | 8/11 | 8/11 | 46015 | 5169 | $0.013202 | 6651.0ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| event_chain | 2 |
| lineup | 2 |
| player_assist_relation | 1 |
| player_retrieval | 1 |
| shot_location | 2 |
| simple_event_retrieval | 2 |
| temporal_score | 1 |

## Manual review

Manual decisions are recorded for 20/22 rows in `ai_search_benchmark_results.csv`. Rows marked `not_reviewed` were blocked by provider availability or quota; `not_available` means no generated query was preserved for inspection.
