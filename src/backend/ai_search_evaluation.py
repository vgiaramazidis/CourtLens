"""Run the fixed AI Search question set and save machine/human review tables."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = (
    REPO_ROOT
    / "evaluation"
    / "professor"
    / "2_ai_search"
    / "benchmark_questions.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "evaluation" / "professor" / "2_ai_search" / "results"
)
FORBIDDEN_SPARQL = re.compile(
    r"\b(LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|INSERT|DELETE|WITH|SERVICE)\b",
    flags=re.IGNORECASE,
)
MODEL_PRICING_USD_PER_MILLION = {
    ("openai", "gpt-5-mini"): {
        "input": 0.25,
        "cached_input": 0.025,
        "output": 2.00,
    },
    ("gemini", "gemini-3.5-flash"): {
        "input": 1.50,
        "cached_input": 0.15,
        "output": 9.00,
    },
}
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def estimate_standard_cost_usd(
    provider: str,
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float | str:
    """Estimate standard API cost; an active free tier can make actual cost lower."""
    pricing = MODEL_PRICING_USD_PER_MILLION.get((provider, model))
    if pricing is None:
        return ""
    cached_tokens = min(max(0, cached_input_tokens), max(0, input_tokens))
    uncached_tokens = max(0, input_tokens - cached_tokens)
    cost = (
        uncached_tokens * pricing["input"]
        + cached_tokens * pricing["cached_input"]
        + max(0, output_tokens) * pricing["output"]
    ) / 1_000_000
    return round(cost, 8)


def load_questions(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    questions = payload.get("questions", [])
    if not isinstance(questions, list) or not questions:
        raise ValueError("The benchmark file must contain a non-empty questions list")
    identifiers = [str(question.get("id", "")) for question in questions]
    if any(not identifier for identifier in identifiers):
        raise ValueError("Every benchmark question needs an id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Benchmark question ids must be unique")
    return questions


def select_questions(
    questions: list[dict[str, object]], question_ids: list[str] | None
) -> list[dict[str, object]]:
    """Return a stable subset for low-cost pilot runs."""
    if not question_ids:
        return questions
    requested = list(dict.fromkeys(question_ids))
    available = {str(question["id"]): question for question in questions}
    unknown = [question_id for question_id in requested if question_id not in available]
    if unknown:
        raise ValueError(f"Unknown benchmark question id(s): {', '.join(unknown)}")
    return [available[question_id] for question_id in requested]


def is_read_only_query(query: str) -> bool:
    body = query.strip()
    body = re.sub(
        r"^(?:(?:PREFIX\s+[A-Za-z][\w-]*:\s*<[^>]+>|BASE\s+<[^>]+>)\s*)+",
        "",
        body,
        flags=re.IGNORECASE,
    )
    return bool(re.match(r"^(SELECT|ASK)\b", body, flags=re.IGNORECASE)) and not bool(
        FORBIDDEN_SPARQL.search(query)
    )


def query_contains_scope(query: str, season_code: str, game_code: str) -> bool:
    quoted_literals = set(re.findall(r'["\']([^"\']+)["\']', query))
    return season_code in quoted_literals and game_code in quoted_literals


def result_count(payload: dict[str, object]) -> int:
    results = payload.get("results", [])
    return len(results) if isinstance(results, list) else 0


def is_true_value(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


def usage_columns(
    payload: dict[str, object], provider: str, model: str
) -> dict[str, object]:
    usage = payload.get("ai_usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    cached_input_tokens = int(usage.get("cached_input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning_tokens = int(usage.get("reasoning_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "estimated_standard_cost_usd": estimate_standard_cost_usd(
            provider,
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        ),
    }


def execute_question(
    session: requests.Session,
    api_url: str,
    question: dict[str, object],
    provider: str,
    prompt_variant: str,
    openai_model: str | None,
    timeout_seconds: float,
) -> dict[str, object]:
    request_payload = {
        "message": question["message"],
        "season_code": question["season_code"],
        "game_code": question["game_code"],
        "provider": provider,
        "prompt_variant": prompt_variant,
        "include_query": True,
    }
    if openai_model:
        request_payload["openai_model"] = openai_model
    started = time.perf_counter()
    response = session.post(api_url, json=request_payload, timeout=timeout_seconds)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    payload = response.json()
    query = str(payload.get("sparql_query", ""))
    resolved_provider = str(payload.get("ai_provider", provider))
    resolved_model = str(payload.get("ai_model", openai_model or ""))
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    action_uris = payload.get("action_uris", [])
    if not isinstance(action_uris, list):
        action_uris = []
    actual_filter = bool(payload.get("playbyplay_filter", False))
    expected_filter = bool(question.get("expected_playbyplay_filter", False))
    return {
        "id": question["id"],
        "provider": resolved_provider,
        "model": resolved_model,
        "prompt_variant": payload.get("prompt_variant", prompt_variant),
        "category": question["category"],
        "question": question["message"],
        "season_code": question["season_code"],
        "game_code": question["game_code"],
        "status": "completed",
        "http_status": response.status_code,
        "latency_ms": round(elapsed_ms, 3),
        **usage_columns(payload, resolved_provider, resolved_model),
        "result_count": len(results),
        "result_preview_json": json.dumps(
            results[:5], ensure_ascii=False, sort_keys=True
        ),
        "boolean_result": payload.get("boolean", ""),
        "expected_playbyplay_filter": expected_filter,
        "actual_playbyplay_filter": actual_filter,
        "playbyplay_filter_matches_expectation": actual_filter == expected_filter,
        "action_uri_count": len(action_uris),
        "query_is_read_only": is_read_only_query(query),
        "query_contains_selected_scope": query_contains_scope(
            query, str(question["season_code"]), str(question["game_code"])
        ),
        "generated_sparql": query,
        "query_correct_human": "",
        "result_correct_human": "",
        "review_notes": "",
        "error": "",
    }


def failed_row(
    question: dict[str, object],
    provider: str,
    prompt_variant: str,
    openai_model: str | None,
    elapsed_ms: float,
    error: Exception,
    http_status: int | str = "",
) -> dict[str, object]:
    return {
        "id": question["id"],
        "provider": provider,
        "model": openai_model or (
            DEFAULT_GEMINI_MODEL if provider == "gemini" else ""
        ),
        "prompt_variant": prompt_variant,
        "category": question["category"],
        "question": question["message"],
        "season_code": question["season_code"],
        "game_code": question["game_code"],
        "status": "failed",
        "http_status": http_status,
        "latency_ms": round(elapsed_ms, 3),
        "input_tokens": "",
        "cached_input_tokens": "",
        "output_tokens": "",
        "reasoning_tokens": "",
        "total_tokens": "",
        "estimated_standard_cost_usd": "",
        "result_count": "",
        "result_preview_json": "",
        "boolean_result": "",
        "expected_playbyplay_filter": question.get("expected_playbyplay_filter", False),
        "actual_playbyplay_filter": "",
        "playbyplay_filter_matches_expectation": "",
        "action_uri_count": "",
        "query_is_read_only": "",
        "query_contains_selected_scope": "",
        "generated_sparql": "",
        "query_correct_human": "",
        "result_correct_human": "",
        "review_notes": "",
        "error": str(error),
    }


def run_benchmark(
    questions: list[dict[str, object]],
    api_url: str,
    timeout_seconds: float,
    providers: list[str],
    prompt_variants: list[str],
    gemini_delay_seconds: float = 0.0,
) -> list[dict[str, object]]:
    rows = []
    with requests.Session() as session:
        for provider in providers:
            models = ["gpt-5-mini"] if provider == "openai" else [None]
            for prompt_variant in prompt_variants:
                for openai_model in models:
                    configuration = (
                        f"{provider}/{openai_model or 'configured-model'}/"
                        f"{prompt_variant}"
                    )
                    for question_index, question in enumerate(questions):
                        if (
                            provider == "gemini"
                            and question_index > 0
                            and gemini_delay_seconds > 0
                        ):
                            time.sleep(gemini_delay_seconds)
                        started = time.perf_counter()
                        try:
                            row = execute_question(
                                session,
                                api_url,
                                question,
                                provider,
                                prompt_variant,
                                openai_model,
                                timeout_seconds,
                            )
                        except requests.HTTPError as exc:
                            elapsed_ms = (time.perf_counter() - started) * 1000
                            status = (
                                exc.response.status_code
                                if exc.response is not None
                                else ""
                            )
                            response_payload = {}
                            if exc.response is not None:
                                try:
                                    parsed_payload = exc.response.json()
                                    if isinstance(parsed_payload, dict):
                                        response_payload = parsed_payload
                                except (requests.JSONDecodeError, ValueError):
                                    pass
                            detail = response_payload.get("detail")
                            diagnostics = detail if isinstance(detail, dict) else {}
                            error_message = (
                                diagnostics.get("message")
                                if diagnostics
                                else detail
                            )
                            if not error_message:
                                error_message = (
                                    exc.response.text
                                    if exc.response is not None
                                    else str(exc)
                                )
                            row = failed_row(
                                question,
                                provider,
                                prompt_variant,
                                openai_model,
                                elapsed_ms,
                                RuntimeError(str(error_message)),
                                status,
                            )
                            if diagnostics:
                                resolved_provider = str(
                                    diagnostics.get("ai_provider", provider)
                                )
                                resolved_model = str(
                                    diagnostics.get(
                                        "ai_model",
                                        openai_model or DEFAULT_GEMINI_MODEL,
                                    )
                                )
                                row["provider"] = resolved_provider
                                row["model"] = resolved_model
                                row["prompt_variant"] = diagnostics.get(
                                    "prompt_variant", prompt_variant
                                )
                                row["generated_sparql"] = diagnostics.get(
                                    "sparql_query", ""
                                )
                                row.update(
                                    usage_columns(
                                        diagnostics,
                                        resolved_provider,
                                        resolved_model,
                                    )
                                )
                        except (
                            requests.RequestException,
                            ValueError,
                            TypeError,
                            KeyError,
                        ) as exc:
                            elapsed_ms = (time.perf_counter() - started) * 1000
                            row = failed_row(
                                question,
                                provider,
                                prompt_variant,
                                openai_model,
                                elapsed_ms,
                                exc,
                            )
                        rows.append(row)
                        line = f"{configuration} {row['id']}: {row['status']}"
                        if row["status"] != "completed" and row["error"]:
                            line += f" — {row['error']}"
                        print(line)
    return rows


def write_outputs(
    output_dir: Path,
    api_url: str,
    questions_path: Path,
    rows: list[dict[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "ai_search_benchmark_results.csv"
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    completed = [row for row in rows if row["status"] == "completed"]
    configurations = sorted({
        (str(row["provider"]), str(row["model"]), str(row["prompt_variant"]))
        for row in rows
    })
    first_configuration = configurations[0]
    categories = Counter(
        str(row["category"])
        for row in rows
        if (
            str(row["provider"]),
            str(row["model"]),
            str(row["prompt_variant"]),
        ) == first_configuration
    )
    report_path = output_dir / "ai_search_benchmark_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# AI Search benchmark\n\n")
        handle.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
        handle.write(f"API: `{api_url}`  \nQuestions: `{questions_path}`\n\n")
        handle.write(
            f"Completed: {len(completed)}/{len(rows)} across "
            f"{len(configurations)} configurations.\n\n"
        )
        total_estimated_cost = sum(
            float(row["estimated_standard_cost_usd"])
            for row in rows
            if row["estimated_standard_cost_usd"] != ""
        )
        handle.write(
            f"Estimated standard API cost: `${total_estimated_cost:.6f}`. "
            "This estimate uses recorded token usage; free-tier credits or provider "
            "billing adjustments can make the charged amount lower.\n\n"
        )
        unmetered_failures = [
            row
            for row in rows
            if row["status"] == "failed"
            and row["total_tokens"] == ""
            and "όριο χρήσης" not in str(row["error"])
        ]
        if unmetered_failures:
            handle.write(
                f"Warning: {len(unmetered_failures)} failed requests have no usage "
                "metadata, so the cost total excludes them. Provider failures before "
                "generation normally report no billable tokens.\n\n"
            )
        handle.write("## Results by configuration\n\n")
        handle.write(
            "| Provider | Model | Prompt | Completed | Read-only | Scoped | "
            "Overlay match | Query correct | Result correct | Input tokens | "
            "Output tokens | Est. cost | Mean latency |\n"
        )
        handle.write(
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: | ---: |\n"
        )
        for provider, model, prompt_variant in configurations:
            configuration_rows = [
                row
                for row in rows
                if (
                    str(row["provider"]),
                    str(row["model"]),
                    str(row["prompt_variant"]),
                ) == (provider, model, prompt_variant)
            ]
            successful = [
                row for row in configuration_rows if row["status"] == "completed"
            ]
            read_only = sum(
                is_true_value(row["query_is_read_only"]) for row in successful
            )
            scoped = sum(
                is_true_value(row["query_contains_selected_scope"])
                for row in successful
            )
            overlay = sum(
                is_true_value(row["playbyplay_filter_matches_expectation"])
                for row in successful
            )
            reviewed_queries = [
                row for row in configuration_rows
                if row["query_correct_human"] in {"yes", "no"}
            ]
            reviewed_results = [
                row for row in configuration_rows
                if row["result_correct_human"] in {"yes", "no"}
            ]
            correct_queries = sum(
                row["query_correct_human"] == "yes" for row in reviewed_queries
            )
            correct_results = sum(
                row["result_correct_human"] == "yes" for row in reviewed_results
            )
            mean_latency = (
                sum(float(row["latency_ms"]) for row in successful) / len(successful)
                if successful
                else None
            )
            input_tokens = sum(
                int(row["input_tokens"] or 0) for row in configuration_rows
            )
            output_tokens = sum(
                int(row["output_tokens"] or 0) for row in configuration_rows
            )
            estimated_cost = sum(
                float(row["estimated_standard_cost_usd"])
                for row in configuration_rows
                if row["estimated_standard_cost_usd"] != ""
            )
            handle.write(
                f"| {provider} | {model or 'configured default'} | "
                f"{prompt_variant} | {len(successful)}/{len(configuration_rows)} | "
                f"{read_only}/{len(successful)} | {scoped}/{len(successful)} | "
                f"{overlay}/{len(successful)} | "
                f"{correct_queries}/{len(reviewed_queries)} | "
                f"{correct_results}/{len(reviewed_results)} | "
                f"{input_tokens} | {output_tokens} | ${estimated_cost:.6f} | "
                f"{'—' if mean_latency is None else f'{mean_latency:.1f}ms'} |\n"
            )
        handle.write("## Question coverage\n\n")
        handle.write("| Category | Questions |\n| --- | ---: |\n")
        for category, count in sorted(categories.items()):
            handle.write(f"| {category} | {count} |\n")
        manually_reviewed = sum(
            row["query_correct_human"] in {"yes", "no"}
            or row["result_correct_human"] in {"yes", "no"}
            for row in rows
        )
        handle.write("\n## Manual review\n\n")
        if manually_reviewed:
            handle.write(
                f"Manual decisions are recorded for {manually_reviewed}/{len(rows)} "
                "rows in `ai_search_benchmark_results.csv`. Rows marked "
                "`not_reviewed` were blocked by provider availability or quota; "
                "`not_available` means no generated query was preserved for "
                "inspection.\n"
            )
        else:
            handle.write(
                "Open `ai_search_benchmark_results.csv` and complete "
                "`query_correct_human`, `result_correct_human`, and `review_notes`. "
                "Automated safety and scope checks do not prove semantic correctness.\n"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument(
        "--question-id",
        action="append",
        help="Run one benchmark question id; repeat for a low-cost pilot",
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/chat")
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument(
        "--gemini-delay-seconds",
        type=float,
        default=0,
        help="Pause between Gemini requests to respect a requests-per-minute quota",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--provider",
        action="append",
        choices=("gemini", "openai"),
        help="AI provider; repeat to compare both (default: gemini)",
    )
    parser.add_argument(
        "--prompt-variant",
        action="append",
        choices=("simple", "ontology"),
        help="Prompt version; repeat to compare both (default: ontology)",
    )
    args = parser.parse_args(argv)

    questions = select_questions(
        load_questions(args.questions.resolve()), args.question_id
    )
    rows = run_benchmark(
        questions,
        args.api_url,
        args.timeout_seconds,
        args.provider or ["gemini"],
        args.prompt_variant or ["ontology"],
        max(0.0, args.gemini_delay_seconds),
    )
    write_outputs(
        args.output_dir.resolve(), args.api_url, args.questions.resolve(), rows
    )
    failed = sum(row["status"] != "completed" for row in rows)
    print(f"Saved {len(rows)} question results to {args.output_dir.resolve()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
