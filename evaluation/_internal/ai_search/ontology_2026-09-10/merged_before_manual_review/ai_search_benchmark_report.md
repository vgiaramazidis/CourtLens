# AI Search benchmark

Generated: 2026-09-10T12:27:45.727341+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 40/40 across 2 configurations.

Estimated standard API cost: `$0.473622`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 20/20 | 20/20 | 20/20 | 20/20 | 0/0 | 0/0 | 92603 | 40889 | $0.454785 | 8125.3ms |
| openai | gpt-5-mini | ontology | 20/20 | 20/20 | 20/20 | 20/20 | 0/0 | 0/0 | 86462 | 8115 | $0.018838 | 6524.6ms |
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
