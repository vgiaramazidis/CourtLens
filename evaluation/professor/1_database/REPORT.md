# Database and SPARQL query benchmark

Endpoint: `http://93.115.20.167:8890/sparql`. Repetitions per query: 3.

Times are client-observed HTTP response times and include network latency plus SPARQL execution and JSON transfer.

## Dataset statistics

The endpoint contains 1,063 games and 566,336 distinct PBP actions.

| Season | Games | PBP actions |
| --- | ---: | ---: |
| E2023 | 331 | 170,669 |
| E2024 | 330 | 174,750 |
| E2025 | 402 | 220,917 |

## Query response times

| Query | Category | Rows | Successful | Median | Mean | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dataset_totals | statistics | 1 | 3/3 | 1092.4ms | 1087.3ms | 1059.2ms | 1110.1ms |
| games_by_season | statistics | 3 | 3/3 | 1883.5ms | 1867.0ms | 1750.0ms | 1967.5ms |
| actions_by_type | statistics | 44 | 3/3 | 1384.6ms | 1407.8ms | 1304.6ms | 1534.3ms |
| actions_per_game | statistics | 1063 | 3/3 | 2279.9ms | 2278.7ms | 2156.5ms | 2399.6ms |
| games_E2023 | application | 331 | 3/3 | 199.4ms | 230.8ms | 195.9ms | 297.2ms |
| playbyplay_E2023_333 | application | 534 | 3/3 | 1538.2ms | 2174.7ms | 1460.9ms | 3524.8ms |
| shots_E2023_333 | application | 122 | 3/3 | 392.4ms | 467.4ms | 355.1ms | 654.7ms |
| lineups_E2023_333 | application | 2 | 3/3 | 277.8ms | 355.1ms | 225.6ms | 561.8ms |
| assist_duos_E2023_333 | analytics | 10 | 3/3 | 193.9ms | 192.4ms | 188.1ms | 195.3ms |
| timeouts_E2023 | analytics | 200 | 3/3 | 396.9ms | 442.0ms | 318.1ms | 611.1ms |

Failed executions: 0 of 30.
