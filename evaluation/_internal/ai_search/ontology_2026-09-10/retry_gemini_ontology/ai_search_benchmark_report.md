# AI Search benchmark

Generated: 2026-09-10T12:10:12.841284+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 4/6 across 1 configurations.

Estimated standard API cost: `$0.090262`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 4/6 | 4/4 | 4/4 | 4/4 | 0/0 | 0/0 | 18524 | 8161 | $0.090262 | 7680.7ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| percentage | 2 |
| player_assist_relation | 2 |
| player_retrieval | 1 |
| temporal_score | 1 |

## Manual review

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
