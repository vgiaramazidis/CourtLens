# AI Search benchmark

Generated: 2026-09-17T08:21:36.320541+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 1/1 across 1 configurations.

Estimated standard API cost: `$0.001538`. This estimate uses recorded token usage; free-tier credits or provider billing adjustments can make the charged amount lower.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Query correct | Result correct | Input tokens | Output tokens | Est. cost | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| openai | gpt-5-mini | simple | 1/1 | 1/1 | 1/1 | 0/1 | 0/0 | 0/0 | 1568 | 573 | $0.001538 | 10602.8ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| lineup | 1 |

## Manual review

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
