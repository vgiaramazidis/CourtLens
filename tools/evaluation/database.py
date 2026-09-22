"""Benchmark representative EuroLeague SPARQL queries and dataset statistics."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.backend.database import get_sparql_endpoint
from src.backend.queries import (
    get_filtered_shots_query,
    get_game_lineups_query,
    get_games_list_query,
    get_match_playbyplay_query,
    get_timeouts_query,
    get_top_assist_duos_query,
)

DEFAULT_ENDPOINT = get_sparql_endpoint()
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "evaluation" / "database"


@dataclass(frozen=True)
class QuerySpec:
    name: str
    category: str
    description: str
    query: str


def benchmark_queries() -> list[QuerySpec]:
    prefixes = """
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
""".strip()
    return [
        QuerySpec(
            "dataset_totals",
            "statistics",
            "Count distinct games and Play-by-Play actions.",
            prefixes
            + """
SELECT (COUNT(DISTINCT ?game) AS ?games)
       (COUNT(DISTINCT ?action) AS ?actions)
WHERE {
  ?game rdf:type bball:Game ;
        bball:hasPlayByPlayAction ?action .
}
""",
        ),
        QuerySpec(
            "games_by_season",
            "statistics",
            "Count games and actions by season.",
            prefixes
            + """
SELECT ?seasonCode (COUNT(DISTINCT ?game) AS ?games)
       (COUNT(DISTINCT ?action) AS ?actions)
WHERE {
  ?game rdf:type bball:Game ;
        bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?action .
  ?season bball:hasCode ?seasonCode .
}
GROUP BY ?seasonCode
ORDER BY ?seasonCode
""",
        ),
        QuerySpec(
            "actions_by_type",
            "statistics",
            "Count PBP actions by RDF class.",
            prefixes
            + """
SELECT ?actionType (COUNT(DISTINCT ?action) AS ?actions)
WHERE {
  ?game rdf:type bball:Game ;
        bball:hasPlayByPlayAction ?action .
  ?action rdf:type ?actionType .
}
GROUP BY ?actionType
ORDER BY DESC(?actions)
LIMIT 100
""",
        ),
        QuerySpec(
            "actions_per_game",
            "statistics",
            "Count PBP actions for every game.",
            prefixes
            + """
SELECT ?seasonCode ?gameCode (COUNT(DISTINCT ?action) AS ?actions)
WHERE {
  ?game rdf:type bball:Game ;
        bball:hasCode ?gameCode ;
        bball:hasSeason ?season ;
        bball:hasPlayByPlayAction ?action .
  ?season bball:hasCode ?seasonCode .
}
GROUP BY ?seasonCode ?gameCode
ORDER BY ?seasonCode xsd:integer(?gameCode)
LIMIT 2000
""",
        ),
        QuerySpec(
            "games_E2023",
            "application",
            "List E2023 games for the season selector.",
            get_games_list_query("E2023"),
        ),
        QuerySpec(
            "playbyplay_E2023_333",
            "application",
            "Retrieve ordered PBP actions for one complete video game.",
            get_match_playbyplay_query("333", "E2023"),
        ),
        QuerySpec(
            "shots_E2023_333",
            "application",
            "Retrieve shot actions and coordinates for one game.",
            get_filtered_shots_query(game_code="333", season_code="E2023"),
        ),
        QuerySpec(
            "lineups_E2023_333",
            "application",
            "Retrieve available lineups for one game.",
            get_game_lineups_query("333", "E2023"),
        ),
        QuerySpec(
            "assist_duos_E2023_333",
            "analytics",
            "Retrieve top passer-scorer combinations for one game.",
            get_top_assist_duos_query(game_code="333", season_code="E2023"),
        ),
        QuerySpec(
            "timeouts_E2023",
            "analytics",
            "Retrieve timeout data used by the simulator.",
            get_timeouts_query("E2023"),
        ),
    ]


def execute_query(
    session: requests.Session,
    endpoint: str,
    query: str,
    timeout_seconds: float,
) -> tuple[float, int, list[dict[str, object]]]:
    started = time.perf_counter()
    response = session.get(
        endpoint,
        params={
            "query": query,
            "format": "application/sparql-results+json",
        },
        timeout=timeout_seconds,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    payload = response.json()
    bindings = payload.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        raise ValueError("SPARQL response does not contain a bindings list")
    return elapsed_ms, len(bindings), bindings


def literal_binding(binding: dict[str, object]) -> dict[str, str]:
    result = {}
    for key, value in binding.items():
        if isinstance(value, dict):
            result[key] = str(value.get("value", ""))
    return result


def run_benchmark(
    endpoint: str,
    repetitions: int,
    timeout_seconds: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    specs = benchmark_queries()
    raw_runs: list[dict[str, object]] = []
    samples: dict[str, list[dict[str, str]]] = {}
    with requests.Session() as session:
        for spec in specs:
            for run_index in range(1, repetitions + 1):
                try:
                    elapsed_ms, result_rows, bindings = execute_query(
                        session, endpoint, spec.query, timeout_seconds
                    )
                    raw_runs.append(
                        {
                            "query": spec.name,
                            "category": spec.category,
                            "run": run_index,
                            "success": True,
                            "result_rows": result_rows,
                            "elapsed_ms": elapsed_ms,
                            "error": "",
                        }
                    )
                    if spec.name not in samples:
                        samples[spec.name] = [literal_binding(binding) for binding in bindings[:5]]
                except (requests.RequestException, ValueError) as exc:
                    raw_runs.append(
                        {
                            "query": spec.name,
                            "category": spec.category,
                            "run": run_index,
                            "success": False,
                            "result_rows": 0,
                            "elapsed_ms": None,
                            "error": str(exc),
                        }
                    )

    summaries = []
    for spec in specs:
        runs = [row for row in raw_runs if row["query"] == spec.name]
        successful = [row for row in runs if row["success"]]
        timings = [float(row["elapsed_ms"]) for row in successful]
        summaries.append(
            {
                "query": spec.name,
                "category": spec.category,
                "description": spec.description,
                "runs": len(runs),
                "successful_runs": len(successful),
                "result_rows": (int(successful[0]["result_rows"]) if successful else None),
                "mean_ms": statistics.fmean(timings) if timings else None,
                "median_ms": statistics.median(timings) if timings else None,
                "min_ms": min(timings) if timings else None,
                "max_ms": max(timings) if timings else None,
            }
        )
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "repetitions": repetitions,
        "timeout_seconds": timeout_seconds,
        "query_samples": samples,
        "queries": [
            {
                "name": spec.name,
                "category": spec.category,
                "description": spec.description,
                "sparql": spec.query,
            }
            for spec in specs
        ],
    }
    return raw_runs, summaries, metadata


def write_outputs(
    output_dir: Path,
    raw_runs: list[dict[str, object]],
    summaries: list[dict[str, object]],
    metadata: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "benchmark_runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(raw_runs[0]))
        writer.writeheader()
        writer.writerows(raw_runs)
    with (output_dir / "benchmark_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    with (output_dir / "queries_and_samples.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")

    report = output_dir / "REPORT.md"
    with report.open("w", encoding="utf-8") as handle:
        handle.write("# Database and SPARQL query benchmark\n\n")
        handle.write(
            f"Endpoint: `{metadata['endpoint']}`. "
            f"Repetitions per query: {metadata['repetitions']}.\n\n"
        )
        handle.write(
            "Times are client-observed HTTP response times and include network "
            "latency plus SPARQL execution and JSON transfer.\n\n"
        )
        samples = metadata.get("query_samples", {})
        totals = samples.get("dataset_totals", [])
        if totals:
            handle.write("## Dataset statistics\n\n")
            handle.write(
                f"The endpoint contains {totals[0].get('games', '—')} games "
                f"and {totals[0].get('actions', '—')} distinct PBP actions.\n\n"
            )
            handle.write("| Season | Games | PBP actions |\n")
            handle.write("| --- | ---: | ---: |\n")
            for row in samples.get("games_by_season", []):
                handle.write(
                    f"| {row.get('seasonCode', '—')} | "
                    f"{row.get('games', '—')} | {row.get('actions', '—')} |\n"
                )
            handle.write("\n## Query response times\n\n")
        handle.write("| Query | Category | Rows | Successful | Median | Mean | Min | Max |\n")
        handle.write("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n")
        for row in summaries:

            def timing(key: str) -> str:
                value = row[key]
                return "—" if value is None else f"{float(value):.1f}ms"

            handle.write(
                f"| {row['query']} | {row['category']} | "
                f"{row['result_rows'] if row['result_rows'] is not None else '—'} | "
                f"{row['successful_runs']}/{row['runs']} | "
                f"{timing('median_ms')} | {timing('mean_ms')} | "
                f"{timing('min_ms')} | {timing('max_ms')} |\n"
            )
        failed = [row for row in raw_runs if not row["success"]]
        handle.write(f"\nFailed executions: {len(failed)} of {len(raw_runs)}.\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    raw_runs, summaries, metadata = run_benchmark(
        args.endpoint, args.repetitions, args.timeout_seconds
    )
    write_outputs(args.output_dir.resolve(), raw_runs, summaries, metadata)
    failed = sum(not row["success"] for row in raw_runs)
    print(
        f"Executed {len(raw_runs)} benchmark requests; {failed} failed. "
        f"Results saved to {args.output_dir.resolve()}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
