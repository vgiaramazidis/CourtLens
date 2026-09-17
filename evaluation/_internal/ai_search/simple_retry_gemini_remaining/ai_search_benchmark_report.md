# AI Search benchmark

Generated: 2026-09-17T08:18:17.167434+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 0/8 across 1 configurations.

Estimated standard API cost: `$0.000000`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

Warning: 1 failed requests have no usage metadata, so the cost total excludes them. Provider failures before generation normally report no billable tokens.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | simple | 0/8 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0 | 0 | $0.000000 | — |
## Question coverage

| Category | Questions |
| --- | ---: |
| event_chain | 1 |
| lineup | 1 |
| percentage | 2 |
| shot_location | 1 |
| simple_event_retrieval | 2 |
| temporal_score | 1 |

## Manual review

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
