# AI Search benchmark

Generated: 2026-09-10T12:03:56.017898+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 33/40 across 2 configurations.

Estimated standard API cost: `$0.335420`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 14/20 | 14/14 | 14/14 | 14/14 | 0/0 | 0/0 | 64820 | 28334 | $0.316574 | 8177.1ms |
| openai | gpt-5-mini | ontology | 19/20 | 19/19 | 19/19 | 19/19 | 0/0 | 0/0 | 86462 | 8119 | $0.018846 | 6626.8ms |
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

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
