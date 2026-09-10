"""Evaluate the final OCR timelines against the three annotated games.

The project has one fixed comparison: the archived baseline versus the current
production timelines. The evaluator writes the three machine-readable files
used by the professor-facing OCR report.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from .ocr_triplets import (
        DEFAULT_ALL_ACTIONS_DIR,
        DEFAULT_CATALOG_FILE,
        PlayByPlayAction,
        build_observation_index,
        find_nearest_observation,
        game_uri,
        load_actions,
        load_observations,
        synchronization_tolerance,
    )
except ImportError:  # Direct execution from the repository root.
    from ocr_triplets import (
        DEFAULT_ALL_ACTIONS_DIR,
        DEFAULT_CATALOG_FILE,
        PlayByPlayAction,
        build_observation_index,
        find_nearest_observation,
        game_uri,
        load_actions,
        load_observations,
        synchronization_tolerance,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
OCR_DIR = REPO_ROOT / "evaluation" / "professor" / "3_ocr"
GROUND_TRUTH_FILES = (
    OCR_DIR / "ground_truth" / "E2023_333.csv",
    OCR_DIR / "ground_truth" / "E2024_220.csv",
    OCR_DIR / "ground_truth" / "E2023_170.csv",
)
SYSTEMS = {
    "baseline": (
        REPO_ROOT
        / "evaluation"
        / "_internal"
        / "ocr"
        / "baselines"
        / "production_before_final_ocr"
    ),
    "production": REPO_ROOT / "video_timelines",
}
OUTPUT_DIR = OCR_DIR / "results"
TOLERANCES = (1.0, 2.0, 5.0)


@dataclass(frozen=True)
class CatalogAction:
    season_code: str
    game_code: str
    event_id: int
    action_info: str
    action: PlayByPlayAction


@dataclass(frozen=True)
class GroundTruthAction:
    season_code: str
    game_code: str
    event_id: int
    category: str
    video_seconds: float


@dataclass(frozen=True)
class EvaluationResult:
    system: str
    ground_truth: GroundTruthAction
    action_info: str
    predicted_video_seconds: float | None

    @property
    def signed_error_seconds(self) -> float | None:
        if self.predicted_video_seconds is None:
            return None
        return self.predicted_video_seconds - self.ground_truth.video_seconds

    @property
    def absolute_error_seconds(self) -> float | None:
        error = self.signed_error_seconds
        return None if error is None else abs(error)


def event_id(uri: str) -> int:
    try:
        return int(uri.rsplit("#PlayByPlay_J", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid Play-by-Play URI: {uri}") from exc


def load_catalog_actions() -> dict[tuple[str, str, int], CatalogAction]:
    """Load the official PBP actions for all games that have OCR video."""
    with DEFAULT_CATALOG_FILE.open(encoding="utf-8") as handle:
        catalog = json.load(handle).get("games", [])

    actions: dict[tuple[str, str, int], CatalogAction] = {}
    for game in catalog:
        season_code = str(game["season_code"])
        game_code = str(game["game_code"])
        path = DEFAULT_ALL_ACTIONS_DIR / f"AllActions_{season_code}_{game_code}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"Missing Play-by-Play actions for {season_code}/{game_code}: {path}"
            )

        current_game_uri = game_uri(season_code, game_code)
        synchronized = {
            event_id(action.uri): action
            for action in load_actions(path, current_game_uri)
        }
        with path.open(encoding="utf-8") as handle:
            rows = json.load(handle).get("AllActions", [])

        for row in rows:
            current_event_id = int(row["originalEventId"])
            key = (season_code, game_code, current_event_id)
            actions[key] = CatalogAction(
                season_code=season_code,
                game_code=game_code,
                event_id=current_event_id,
                action_info=str(row.get("actionInfo", "")).strip(),
                action=synchronized[current_event_id],
            )
    return actions


def load_ground_truth(
    paths: Iterable[Path],
) -> tuple[list[GroundTruthAction], int, int]:
    """Load annotated rows and count pending/excluded rows."""
    annotated: list[GroundTruthAction] = []
    pending = 0
    excluded = 0
    seen: set[tuple[str, str, int]] = set()
    required = {
        "season_code",
        "game_code",
        "original_event_id",
        "action_category",
        "annotation_status",
        "ground_truth_video_seconds",
    }

    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    f"Ground-truth file {path} is missing columns: "
                    f"{', '.join(sorted(missing))}"
                )
            for row_number, row in enumerate(reader, start=2):
                status = str(row.get("annotation_status", "Pending")).strip().lower()
                if status in {"exclude", "excluded"}:
                    excluded += 1
                    continue
                if status not in {"annotated", "complete", "completed"}:
                    pending += 1
                    continue
                try:
                    item = GroundTruthAction(
                        season_code=str(row["season_code"]).strip(),
                        game_code=str(row["game_code"]).strip(),
                        event_id=int(row["original_event_id"]),
                        category=str(row["action_category"]).strip() or "other",
                        video_seconds=float(row["ground_truth_video_seconds"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid annotated row {row_number} in {path}: {exc}"
                    ) from exc
                if item.video_seconds < 0:
                    raise ValueError(
                        f"Ground-truth time cannot be negative at row "
                        f"{row_number} in {path}"
                    )
                key = (item.season_code, item.game_code, item.event_id)
                if key in seen:
                    raise ValueError(f"Duplicate ground-truth event: {key}")
                seen.add(key)
                annotated.append(item)
    return annotated, pending, excluded


def evaluate(
    ground_truth: list[GroundTruthAction],
    actions: dict[tuple[str, str, int], CatalogAction],
) -> list[EvaluationResult]:
    """Match every annotated action against baseline and production OCR."""
    results = []
    timeline_cache: dict[tuple[str, str, str], dict[str, object]] = {}
    for system, timeline_directory in SYSTEMS.items():
        for item in ground_truth:
            key = (item.season_code, item.game_code, item.event_id)
            catalog_action = actions.get(key)
            if catalog_action is None:
                raise ValueError(f"Ground-truth event is missing from AllActions: {key}")

            game_key = (system, item.season_code, item.game_code)
            if game_key not in timeline_cache:
                current_game_uri = game_uri(item.season_code, item.game_code)
                timeline_path = (
                    timeline_directory / f"{item.season_code}_{item.game_code}.csv"
                )
                observations = load_observations(
                    timeline_path,
                    f"{current_game_uri}#BroadcastVideo",
                )
                timeline_cache[game_key] = build_observation_index(observations)

            observation, _difference = find_nearest_observation(
                timeline_cache[game_key],
                catalog_action.action.quarter,
                catalog_action.action.quarter_seconds_remaining,
                max_difference=synchronization_tolerance(catalog_action.action),
            )
            results.append(EvaluationResult(
                system=system,
                ground_truth=item,
                action_info=catalog_action.action_info,
                predicted_video_seconds=(
                    observation.video_seconds if observation else None
                ),
            ))
    return results


def metric_summary(
    results: Iterable[EvaluationResult],
) -> dict[str, float | int | None]:
    """Calculate the exact metrics requested for the OCR evaluation."""
    results = list(results)
    errors = [
        result.absolute_error_seconds
        for result in results
        if result.absolute_error_seconds is not None
    ]
    total = len(results)
    mapped = len(errors)
    metrics: dict[str, float | int | None] = {
        "total": total,
        "mapped": mapped,
        "unmapped": total - mapped,
        "uer_pct": (total - mapped) / total * 100 if total else 0.0,
        "mae_seconds": statistics.fmean(errors) if errors else None,
        "median_absolute_error_seconds": statistics.median(errors) if errors else None,
    }
    for tolerance in TOLERANCES:
        metrics[f"acc_at_{tolerance:g}_pct"] = (
            sum(error <= tolerance for error in errors) / total * 100
            if total
            else 0.0
        )
    return metrics


def temporal_error_band(result: EvaluationResult) -> str:
    error = result.absolute_error_seconds
    if error is None:
        return "unmapped"
    for limit, label in (
        (1, "within_1_second"),
        (2, "over_1_to_2_seconds"),
        (5, "over_2_to_5_seconds"),
        (10, "over_5_to_10_seconds"),
        (30, "over_10_to_30_seconds"),
    ):
        if error <= limit:
            return label
    return "over_30_seconds"


def catalog_coverage(
    actions: dict[tuple[str, str, int], CatalogAction],
) -> dict[str, dict[str, float | int]]:
    """Calculate UER across all 28 games with video."""
    games: dict[tuple[str, str], list[CatalogAction]] = defaultdict(list)
    for action in actions.values():
        games[(action.season_code, action.game_code)].append(action)

    coverage = {}
    for system, timeline_directory in SYSTEMS.items():
        total = 0
        mapped = 0
        for (season_code, game_code), game_actions in games.items():
            current_game_uri = game_uri(season_code, game_code)
            observations = load_observations(
                timeline_directory / f"{season_code}_{game_code}.csv",
                f"{current_game_uri}#BroadcastVideo",
            )
            index = build_observation_index(observations)
            for item in game_actions:
                total += 1
                observation, _difference = find_nearest_observation(
                    index,
                    item.action.quarter,
                    item.action.quarter_seconds_remaining,
                    max_difference=synchronization_tolerance(item.action),
                )
                mapped += observation is not None
        coverage[system] = {
            "total": total,
            "mapped": mapped,
            "unmapped": total - mapped,
            "uer_pct": (total - mapped) / total * 100 if total else 0.0,
        }
    return coverage


def write_results(
    results: list[EvaluationResult],
    coverage: dict[str, dict[str, float | int]],
    output_directory: Path,
) -> None:
    """Write only the three data files used by the final OCR report."""
    output_directory.mkdir(parents=True, exist_ok=True)

    detail_fields = [
        "system",
        "season_code",
        "game_code",
        "original_event_id",
        "action_info",
        "action_category",
        "ground_truth_video_seconds",
        "predicted_video_seconds",
        "signed_error_seconds",
        "absolute_error_seconds",
        "within_1_seconds",
        "within_2_seconds",
        "within_5_seconds",
    ]
    with (output_directory / "per_action_results.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=detail_fields, lineterminator="\n")
        writer.writeheader()
        for result in results:
            error = result.absolute_error_seconds
            writer.writerow({
                "system": result.system,
                "season_code": result.ground_truth.season_code,
                "game_code": result.ground_truth.game_code,
                "original_event_id": result.ground_truth.event_id,
                "action_info": result.action_info,
                "action_category": result.ground_truth.category,
                "ground_truth_video_seconds": result.ground_truth.video_seconds,
                "predicted_video_seconds": result.predicted_video_seconds,
                "signed_error_seconds": result.signed_error_seconds,
                "absolute_error_seconds": error,
                "within_1_seconds": error is not None and error <= 1,
                "within_2_seconds": error is not None and error <= 2,
                "within_5_seconds": error is not None and error <= 5,
            })

    error_band_rows = []
    for system in SYSTEMS:
        system_results = [result for result in results if result.system == system]
        counts = defaultdict(int)
        for result in system_results:
            counts[temporal_error_band(result)] += 1
        for band in (
            "within_1_second",
            "over_1_to_2_seconds",
            "over_2_to_5_seconds",
            "over_5_to_10_seconds",
            "over_10_to_30_seconds",
            "over_30_seconds",
            "unmapped",
        ):
            count = counts[band]
            error_band_rows.append({
                "system": system,
                "error_band": band,
                "count": count,
                "percentage_of_annotated_events": (
                    count / len(system_results) * 100 if system_results else 0.0
                ),
            })
    with (output_directory / "temporal_error_bands.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "system",
                "error_band",
                "count",
                "percentage_of_annotated_events",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(error_band_rows)

    summary_rows = []
    for system in SYSTEMS:
        system_results = [result for result in results if result.system == system]
        summary_rows.append(
            (system, "ground_truth", "overall", "all", metric_summary(system_results))
        )
        for category in sorted({result.ground_truth.category for result in system_results}):
            grouped = [
                result
                for result in system_results
                if result.ground_truth.category == category
            ]
            summary_rows.append(
                (system, "ground_truth", "action_category", category, metric_summary(grouped))
            )

        games: dict[tuple[str, str], list[EvaluationResult]] = defaultdict(list)
        for result in system_results:
            games[(result.ground_truth.season_code, result.ground_truth.game_code)].append(result)
        game_metrics = []
        for (season_code, game_code), grouped in sorted(games.items()):
            metrics = metric_summary(grouped)
            game_metrics.append(metrics)
            summary_rows.append(
                (system, "ground_truth", "game", f"{season_code}/{game_code}", metrics)
            )

        macro = {
            "total": len(game_metrics),
            "mapped": None,
            "unmapped": None,
            "uer_pct": statistics.fmean(float(item["uer_pct"]) for item in game_metrics),
            "mae_seconds": statistics.fmean(
                float(item["mae_seconds"]) for item in game_metrics
            ),
            "median_absolute_error_seconds": statistics.fmean(
                float(item["median_absolute_error_seconds"]) for item in game_metrics
            ),
        }
        for tolerance in TOLERANCES:
            key = f"acc_at_{tolerance:g}_pct"
            macro[key] = statistics.fmean(float(item[key]) for item in game_metrics)
        summary_rows.append(
            (system, "ground_truth", "macro_games", "all_games", macro)
        )

        full = coverage[system]
        summary_rows.append((
            system,
            "full_pbp",
            "overall",
            "all",
            {
                "total": full["total"],
                "mapped": full["mapped"],
                "unmapped": full["unmapped"],
                "uer_pct": full["uer_pct"],
                "mae_seconds": None,
                "median_absolute_error_seconds": None,
                "acc_at_1_pct": None,
                "acc_at_2_pct": None,
                "acc_at_5_pct": None,
            },
        ))

    metric_fields = [
        "total",
        "mapped",
        "unmapped",
        "uer_pct",
        "mae_seconds",
        "median_absolute_error_seconds",
        "acc_at_1_pct",
        "acc_at_2_pct",
        "acc_at_5_pct",
    ]
    with (output_directory / "combined_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["system", "dataset_scope", "group_by", "group"]
            + metric_fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for system, scope, group_by, group, metrics in summary_rows:
            writer.writerow({
                "system": system,
                "dataset_scope": scope,
                "group_by": group_by,
                "group": group,
                **metrics,
            })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ground-truth",
        action="append",
        type=Path,
        help="Optional annotated CSV; repeat for multiple games",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    ground_truth_paths = tuple(args.ground_truth or GROUND_TRUTH_FILES)
    ground_truth, pending, excluded = load_ground_truth(ground_truth_paths)
    if not ground_truth:
        raise ValueError("No annotated ground-truth actions were found")

    actions = load_catalog_actions()
    results = evaluate(ground_truth, actions)
    coverage = catalog_coverage(actions)
    write_results(results, coverage, args.output_dir.expanduser().resolve())
    print(
        f"Evaluated {len(ground_truth)} actions from {len(ground_truth_paths)} games "
        f"({pending} pending, {excluded} excluded) against baseline and production."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
