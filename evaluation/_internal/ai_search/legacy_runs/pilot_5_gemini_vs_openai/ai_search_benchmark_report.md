# AI Search benchmark

Generated: 2026-09-09T20:08:58.424534+00:00

API: `http://127.0.0.1:8000/api/chat`  
Questions: `/Users/vgiaramazidis/EuroleagueProject/evaluation/professor/2_ai_search/benchmark_questions.json`

Completed: 10/10 across 2 configurations.

## Results by configuration

| Provider | Model | Prompt | Completed | Read-only | Scoped | Overlay match | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| gemini | gemini-3.5-flash | ontology | 5/5 | 5/5 | 5/5 | 5/5 | 15515.0ms |
| openai | gpt-5-mini | ontology | 5/5 | 5/5 | 5/5 | 5/5 | 5884.4ms |
## Question coverage

| Category | Questions |
| --- | ---: |
| percentage | 1 |
| player_assist_relation | 1 |
| player_retrieval | 1 |
| simple_event_retrieval | 1 |
| temporal_score | 1 |

## Required manual review

Open `ai_search_benchmark_results.csv` and complete `query_correct_human`, `result_correct_human`, and `review_notes`. Automated safety and scope checks do not prove semantic correctness.
