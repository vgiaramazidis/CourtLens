# EuroLeague SPARQL Competency Questions
A Python script for running a collection of SPARQL queries against a EuroLeague knowledge graph, measuring query execution time, and exporting query results and benchmark metrics to CSV.

## Overview

The script:
- Connects to a SPARQL endpoint using `SPARQLWrapper`.
- Runs **14 SPARQL queries (Q1–Q14)** against the EuroLeague knowledge graph and play-by-play dataset.
- Executes each query up to **5 times** by default.
- Measures elapsed query time and summarizes average, median, minimum, maximum, and standard deviation.
- Converts SPARQL JSON bindings into Pandas DataFrames.
- Writes each query's result rows and an overall benchmark summary to CSV files.

## Requirements

- Python 3.9+ (or another Python version compatible with the installed dependencies)
- Access to the configured SPARQL endpoint
- Python packages: `SPARQLWrapper`, `pandas`

Install dependencies:

```bash
python -m pip install SPARQLWrapper pandas
```

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `SPARQL_ENDPOINT` | SPARQL endpoint URL |
| `NUM_RUNS` | `5` | Number of benchmark repetitions per query |
| `OUTPUT_DIR` | `sparql_results` | Directory where CSV files are written |

Check that the endpoint is reachable and that you have permission to query it before running the script.

## How to run

Save the Python code as `benchmark_sparql.py`, then run:

```bash
python benchmark_sparql.py
```

The script creates the `sparql_results/` directory if it does not already exist.

## Output files

- `sparql_results/Q1_results.csv` through `sparql_results/Q14_results.csv`: result table from the final configured iteration for each query, when available.
- `sparql_results/execution_metrics.csv`: benchmark summary with `Query_ID`, `Total_Runs`, `Avg_Time_Sec`, `Median_Time_Sec`, `Min_Time_Sec`, `Max_Time_Sec`, `Std_Dev_Sec`, and `Result_Row_Count`.

**Implementation detail:** results are converted to a DataFrame only when the final configured iteration succeeds. If an earlier iteration succeeds but the final iteration fails, no result CSV is written for that query and its reported row count is `0`. Timing metrics use successful runs only.

## Query catalogue

All queries use the `bball:` namespace (`http://www.ics.forth.gr/isl/Basketball#`). Most explicitly query these named graphs:

- `http://www.ics.forth.gr/isl/EuroleagueKG`
- `http://www.ics.forth.gr/isl/EuroleagueKG_PBP`

Q13 and Q14 do not declare `FROM` graphs, so their results depend on the endpoint's default dataset configuration.

### Q1 — Ranks players by total points scored in the final two minutes of the fourth quarter of the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX xsd: <http\://www\.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?scorer (SUM(?points) AS ?totalPoints)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?action .
    ?season rdfs:label "2025-26" .
    ?action a ?actionType ;
        bball:quarterSecondsRemaining ?secondsRemaining ;
        bball:pointsAwarded ?points ;
        bball:quarter "4th".
    FILTER(?actionType IN (bball:TwoPointShotMade, bball:ThreePointShotMade, bball:FreeThrowMade))
    FILTER(?secondsRemaining <= 120)
    OPTIONAL {
        ?action bball:actionPlayer ?player .
        ?player rdfs:label ?scorer .
    }
}
GROUP BY ?scorer
ORDER BY DESC(?totalPoints)
LIMIT 500
```

### Q2 — Counts made three-point shots by team in the fourth quarter of the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX xsd: <http\://www\.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT ?team (COUNT(?playAction) AS ?totalActions)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?playAction .
    ?season rdfs:label "2025-26" .
    ?playAction a bball:ThreePointShotMade ;
        bball:quarter "4th" ;
        bball:actionTeam ?team ;
        bball:pointsAwarded ?pointsAwarded .
}
GROUP BY ?team
LIMIT 20
```

### Q3 — Counts made three-point shots by quarter in the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT ?quarter (COUNT(?action) AS ?total)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game bball:hasSeason ?season .
    ?season rdfs:label "2025-26" .
    ?game bball:hasPlayByPlayAction ?action .
    ?action a bball:ThreePointShotMade .
    ?action bball:quarter ?quarter .
    ?action bball:pointsAwarded ?pointsAwarded .
}
GROUP BY ?quarter
ORDER BY DESC(?total)
LIMIT 7
```

### Q4 — Counts turnovers by quarter in the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT ?quarter (COUNT(DISTINCT ?turnover) AS ?turnoverCount)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasSeason ?season;
        bball:hasPlayByPlayAction ?turnover.
    ?turnover a bball:Turnover ;
        bball:quarter ?quarter .
    ?season rdfs:label "2025-26".
}
GROUP BY ?quarter
ORDER BY DESC(?turnoverCount)
LIMIT 10
```

### Q5 — Finds lineups appearing in the fourth quarter of the 2023–24 season, ranked by number of distinct games.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT ?lineup (COUNT(DISTINCT ?game) AS ?appearances)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasSeason ?season .
    ?season rdfs:label "2023-24" .
    ?game bball:hasPlayByPlayAction ?action .
    ?action a ?actionType ;
        bball:quarter "4th" ;
        (bball:runningHomeTeamLineup|bball:runningRoadTeamLineup) ?lineup .
}
GROUP BY ?lineup
ORDER BY DESC(?appearances)
LIMIT 10
```

### Q6 — Calculates field-goal shooting percentage for teammates on the lineup when Kendrick Nunn takes a shot in the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs:  <http\://www\.w3.org/2000/01/rdf-schema#>
PREFIX xsd:   <http\://www\.w3.org/2001/XMLSchema#>
SELECT ?teammate
?teammateLabel
(SUM(?made) AS ?madeShots)
(SUM(?missed) AS ?missedShots)
(COUNT(?shot) AS ?totalAttempts)
(100.0 * SUM(?made) / xsd:double(COUNT(?shot)) AS ?shootingPercentage)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    {
        SELECT DISTINCT ?shot ?teammate ?made ?missed
        WHERE {
            ?player rdfs:label "Kendrick Nunn" .
            ?game bball:hasSeason ?season ;
                bball:hasPlayByPlayAction ?shot .
            ?season rdfs:label "2025-26" .
            ?shot bball:actionPlayer ?player ;
                bball:actionTeam ?team .
            {
                ?shot a bball:ThreePointShotMade .
                BIND(1 AS ?made)
                BIND(0 AS ?missed)
            }
            UNION
            {
                ?shot a bball:ThreePointShotMissed .
                BIND(0 AS ?made)
                BIND(1 AS ?missed)
            }
            UNION
            {
                ?shot a bball:TwoPointShotMade .
                BIND(1 AS ?made)
                BIND(0 AS ?missed)
            }
            UNION
            {
                ?shot a bball:TwoPointShotMissed .
                BIND(0 AS ?made)
                BIND(1 AS ?missed)
            }
            {
                ?shot bball:runningHomeTeamLineup ?lineup .
            }
            UNION
            {
                ?shot bball:runningRoadTeamLineup ?lineup .
            }
            ?lineup bball:lineupTeam ?team ;
                bball:includesPlayer ?teammate .
        }
    }
    ?teammate rdfs:label ?teammateLabel .
}
GROUP BY ?teammate ?teammateLabel
ORDER BY DESC(?shootingPercentage)
LIMIT 500
```

### Q7 — Counts made three-pointers by team and shot zone in the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?teamLabel ?shotZone (COUNT(?threePointMade) AS ?threePointers)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasSeason ?season ;
        bball:hasTeamBoxscore ?teamBoxscore .
    ?season rdfs:label "2025-26" .
    ?teamBoxscore bball:overTeam ?team .
    ?team rdfs:label ?teamLabel .
    ?game bball:hasPlayByPlayAction ?threePointMade .
    ?threePointMade a bball:ThreePointShotMade ;
        bball:actionTeam ?team ;
        bball:shotZone ?shotZone .
}
GROUP BY ?shotZone ?teamLabel
ORDER BY DESC(?threePointers)
LIMIT 500
```

### Q8 — Ranks players by two-point field-goal percentage in zones A, B, and C during the 2025–26 season, requiring at least 30 attempts.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http\://www\.w3.org/2001/XMLSchema#>
SELECT ?playerName
?totalMade
?totalAttempted
?fgPercentage
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    {
        SELECT ?player
        (SUM(?made) AS ?totalMade)
        (SUM(?attempted) AS ?totalAttempted)
        (100.0 * SUM(?made) / xsd:double(SUM(?attempted)) AS ?fgPercentage)
        WHERE {
            ?game bball:hasSeason ?season ;
                bball:hasPlayByPlayAction ?action .
            ?season rdfs:label "2025-26" .
            ?action a ?actionType ;
                bball:actionPlayer ?player ;
                bball:shotZone ?zone .
            FILTER(?zone="A" || ?zone="B" || ?zone="C")
            VALUES ?actionType { bball:TwoPointShotMade bball:TwoPointShotMissed }
            BIND(IF(?actionType = bball:TwoPointShotMade, 1, 0) AS ?made)
            BIND(1 AS ?attempted)
        }
        GROUP BY ?player
        HAVING (SUM(?attempted) >= 30)
    }
    ?player rdfs:label ?playerName .
}
ORDER BY DESC(?fgPercentage)
LIMIT 100
```

### Q9 — Retrieves possessions in the 2023 championship game that contain an offensive rebound.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
SELECT DISTINCT ?possession ?possessionTeam ?possessionSequence ?containsAction ?endsWithAction ?startsAfterAction
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasPhaseGroup "CHAMPIONSHIP GAME" ;
        bball:hasSeason ?season ;
        bball:hasPossession ?possession .
    ?season bball:hasCode "E2023" .
    ?possession bball:possessionTeam ?possessionTeam ;
        bball:hasPossessionSequence ?possessionSequence ;
        bball:containsAction ?containsAction ;
        bball:endsWithAction ?endsWithAction ;
        bball:startsAfterAction ?startsAfterAction .
    ?containsAction a bball:OffensiveRebound .
}
LIMIT 500
```

### Q10 — Counts possessions with an offensive rebound by team in the 2025–26 season.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT ?team (COUNT(DISTINCT ?possession) AS ?numPossessionsWithOffensiveRebounds)
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game bball:hasSeason ?season .
    ?season rdfs:label "2025-26" .
    ?game bball:hasPossession ?possession .
    ?possession bball:possessionTeam ?team .
    ?possession bball:containsAction ?action .
    ?action a bball:OffensiveRebound .
}
GROUP BY ?team
ORDER BY DESC(?numPossessionsWithOffensiveRebounds)
LIMIT 500
```

### Q11 — Finds baskets made by Kendrick Nunn when Walter Tavares and Mathias Lessort are on opposing lineups in the 2023 championship game.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?basket
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasPhaseGroup 'CHAMPIONSHIP GAME' ;
        bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?basket .
    ?season bball:hasCode 'E2023' .
    ?basket a ?basketType ;
        bball:actionPlayer ?player ;
        bball:runningHomeTeamLineup ?homeLineup ;
        bball:runningRoadTeamLineup ?roadLineup .
    VALUES ?basketType { bball:TwoPointShotMade bball:ThreePointShotMade bball:FreeThrowMade }
    ?player rdfs:label "Kendrick Nunn" .
    {
        ?homeLineup bball:includesPlayer ?player1 .
        ?roadLineup bball:includesPlayer ?player2 .
    }
    UNION
    {
        ?homeLineup bball:includesPlayer ?player2 .
        ?roadLineup bball:includesPlayer ?player1 .
    }
    ?player1 rdfs:label "Walter Tavares" .
    ?player2 rdfs:label "Mathias Lessort" .
}
LIMIT 500
```

### Q12 — Finds fourth-quarter scoring actions in the 2025 championship game where the score difference changes sign between consecutive play-by-play actions.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
SELECT DISTINCT ?game ?action ?player ?team ?points ?homeScoreBefore ?roadScoreBefore ?homeScoreAfter ?roadScoreAfter
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasPhaseGroup "CHAMPIONSHIP GAME" ;
        bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?action, ?previousAction .
    ?season bball:hasCode "E2025" .
    ?action a ?actionType ;
        bball:quarter "4th" ;
        bball:actionPlayer ?player ;
        bball:actionTeam ?team ;
        bball:pointsAwarded ?points ;
        bball:runningHomeTeamScore ?homeScoreAfter ;
        bball:runningRoadTeamScore ?roadScoreAfter ;
        bball:hasPlayByPlaySequence ?sequence .
    FILTER (?actionType IN (bball:TwoPointShotMade, bball:ThreePointShotMade, bball:FreeThrowMade))
    ?previousAction bball:hasPlayByPlaySequence ?prevSequence ;
        bball:runningHomeTeamScore ?homeScoreBefore ;
        bball:runningRoadTeamScore ?roadScoreBefore .
    FILTER (?prevSequence = ?sequence - 1)
    FILTER ((?homeScoreBefore <= ?roadScoreBefore && ?homeScoreAfter > ?roadScoreAfter) ||
    (?homeScoreBefore >= ?roadScoreBefore && ?homeScoreAfter < ?roadScoreAfter))
}
LIMIT 500
```

### Q13 — Finds made three-pointers in the final minute of the fourth quarter by Greece-born players shorter than 2.00 m when the score margin is under five points.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?playerName ?teamName ?game ?quarter ?clock ?runningHomeTeamScore ?
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game bball:hasPlayByPlayAction ?action.
    ?action a bball:ThreePointShotMade;
        bball:actionPlayer ?player;
        bball:actionTeam ?team;
        bball:quarter ?quarter;
        bball:quarterSecondsRemaining ?secondsRemaining;
        bball:runningHomeTeamScore ?runningHomeTeamScore;
        bball:runningRoadTeamScore ?runningRoadTeamScore.
    FILTER(?quarter = "4th" && ?secondsRemaining <= 60)
    ?player rdfs:label ?playerName;
        bball:hasHeight ?height;
        bball:wasBornIn ?country.
    FILTER(?height < 2.00)
    ?country rdfs:label "Greece".
    ?team rdfs:label ?teamName.
    BIND(ABS(?runningHomeTeamScore - ?runningRoadTeamScore) AS ?scoreDifference)
    FILTER(?scoreDifference < 5)
}
```

### Q14 — Finds fourth-quarter actions in the final minute by players born after 2000 where the lead changes between consecutive play-by-play actions.

```sparql
PREFIX bball: <http\://www\.ics.forth.gr/isl/Basketball#>
PREFIX xsd: <http\://www\.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http\://www\.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?playerName ?type ?teamName ?game ?quarterSecondsRemaining
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG>
FROM <http\://www\.ics.forth.gr/isl/EuroleagueKG_PBP>
WHERE {
    ?game a bball:Game ;
        bball:hasPlayByPlayAction ?action, ?prevAction .
    ?action a ?type;
        bball:actionPlayer ?player ;
        bball:actionTeam ?team ;
        bball:quarterSecondsRemaining ?quarterSecondsRemaining ;
        bball:quarter "4th" ;
        bball:runningHomeTeamScore ?homeScore ;
        bball:runningRoadTeamScore ?roadScore ;
        bball:hasPlayByPlaySequence ?seq .
    FILTER(?quarterSecondsRemaining <= 60)
    ?player bball:hasBirthDate ?birthDate ;
        rdfs:label ?playerName .
    FILTER(xsd:date(?birthDate) > "2000-01-01"^^xsd:date)
    ?team rdfs:label ?teamName .
    ?prevAction bball:runningHomeTeamScore ?prevHomeScore ;
        bball:runningRoadTeamScore ?prevRoadScore ;
        bball:hasPlayByPlaySequence ?prevSeq .
    FILTER(xsd:integer(?seq) = xsd:integer(?prevSeq) + 1)
    FILTER(
    (?prevHomeScore > ?prevRoadScore && ?homeScore < ?roadScore) ||
    (?prevRoadScore > ?prevHomeScore && ?roadScore < ?homeScore)
    )
}
```

## Benchmarking notes

- Timing surrounds `sparql.query().convert()`, so it includes the endpoint request and response conversion.
- The script does not clear endpoint caches between repetitions. Repeated runs may be affected by caching, server load, and network conditions.
- Failed runs are printed to the console and excluded from timing calculations.
- Some queries are season- or game-specific. Review season labels and codes before adapting the queries.
- Result interpretation depends on the ontology and the data available at the endpoint; this README documents the query logic, not actual returned results.

## GitHub repository layout

```text
.
├── README.md
├── benchmark_sparql.py
└── results/       
```
