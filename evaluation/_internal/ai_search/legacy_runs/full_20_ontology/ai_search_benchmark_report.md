# AI Search benchmark

Generated: 2026-09-10T10:49:50.064549+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 26/40 across 2 configurations.

Estimated standard API cost: `$0.206568`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

Warning: 5 failed generated requests have no preserved usage metadata, so this total is a lower bound.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 8/20 | 8/8 | 8/8 | 8/8 | 7/8 | 7/11 | 24248 | 16674 | $0.186438 | 20902.0ms |
| openai | gpt-5-mini | ontology | 18/20 | 18/18 | 18/18 | 17/18 | 9/18 | 10/20 | 51991 | 7771 | $0.020130 | 6988.0ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| event_chain | 2 |
| lineup | 2 |
| percentage | 2 |
| player_assist_relation | 2 |
| player_retrieval | 3 |
| shot_location | 2 |
| simple_event_retrieval | 5 |
| temporal_score | 2 |

## Manual review

Manual decisions are recorded for 31/40 rows in `ai_search_benchmark_results.csv`. Rows marked `not_reviewed` were blocked by provider quota; `not_available` means no generated query was preserved for inspection.
