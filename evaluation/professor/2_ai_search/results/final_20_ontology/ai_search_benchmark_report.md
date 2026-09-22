# AI Search benchmark

Generated: 2026-09-10T15:42:00.529315+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `evaluation/fixtures/ai_search_questions.json`

Completed: 40/40 across 2 configurations.

Estimated standard API cost: `$0.473622`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 92603 | 40889 | $0.454785 | 8125.3ms |
| openai | gpt-5-mini | ontology | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 86462 | 8115 | $0.018838 | 6524.6ms |
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

Manual decisions are recorded for 40/40 rows in `ai_search_benchmark_results.csv`. Rows marked `not_reviewed` were blocked by provider availability or quota; `not_available` means no generated query was preserved for inspection.
