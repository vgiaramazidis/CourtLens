# AI Search evaluation results

The benchmark contains 20 fixed English questions for game `E2023/333`. Each
question was evaluated with Gemini 3.5 Flash and GPT-5 Mini using two prompts:

- `simple`: a flat list of permitted ontology classes and properties;
- `ontology`: the production prompt with relationship paths, stored value
  conventions, query patterns, and Play-by-Play overlay requirements.

All 80 provider/prompt/question combinations completed. Every generated query
and returned result received manual semantic review against the verified game
answers.

## Final comparison

| Provider | Prompt | Completed | Correct queries | Correct results | Overlay-compatible | Mean latency | Estimated standard cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.5 Flash | Simple | 20/20 | 10/20 | 10/20 | 7/20 | 28,173.2 ms | $0.531281 |
| GPT-5 Mini | Simple | 20/20 | 1/20 | 2/20 | 7/20 | 6,505.8 ms | $0.016234 |
| Gemini 3.5 Flash | Ontology | 20/20 | 20/20 | 20/20 | 20/20 | 8,125.3 ms | $0.454785 |
| GPT-5 Mini | Ontology | 20/20 | 20/20 | 20/20 | 20/20 | 6,524.6 ms | $0.018838 |

## Interpretation

The flat vocabulary was insufficient for this graph. Its main failures were
incorrect relationship direction, invalid PlayerParticipation/statline paths,
numeric quarter values instead of stored labels such as `2nd` and `4th`, text
filters instead of stored shot-zone codes, and result variables that could not
drive the Play-by-Play overlay.

The ontology prompt resolved those ambiguities for both models. It produced a
correct query, correct result, and compatible overlay for every benchmark
question. This indicates that explicit graph relationships and stored-value
conventions mattered more than model choice on this fixed benchmark.

Latency should be interpreted as an operational observation rather than a
controlled model-speed experiment. Provider demand, quota resets, retries, and
the remote SPARQL endpoint varied across runs. Cost values use recorded token
usage and standard list prices; they are estimates rather than billing
receipts.

The row-level evidence, generated SPARQL, result previews, token usage, and
manual review notes are stored in:

- `results/final_20_simple/ai_search_benchmark_results.csv`
- `results/final_20_ontology/ai_search_benchmark_results.csv`
