# AI Search benchmark

Generated: 2026-09-10T12:10:37.036808+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 1/1 across 1 configurations.

Estimated standard API cost: `$0.000794`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| openai | gpt-5-mini | ontology | 1/1 | 1/1 | 1/1 | 1/1 | 0/0 | 0/0 | 4323 | 332 | $0.000794 | 4582.9ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| player_assist_relation | 1 |

## Manual review

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
