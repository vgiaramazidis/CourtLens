# AI Search benchmark

Generated: 2026-09-17T08:45:43.768889+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `evaluation/fixtures/ai_search_questions.json`

Completed: 40/40 across 2 configurations.

Estimated standard API cost: `$0.547515`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | simple | 20/20 | 20/20 | 20/20 | 7/20 | 10/20 | 10/20 | 32083 | 53684 | $0.531281 | 28173.2ms |
| openai | gpt-5-mini | simple | 20/20 | 20/20 | 20/20 | 7/20 | 1/20 | 2/20 | 31242 | 7063 | $0.016234 | 6505.8ms |
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
