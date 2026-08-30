"""Create and evaluate manually annotated OCR-to-video ground truth.

The evaluator compares complete OCR timeline versions against the same set of
manually verified Play-by-Play video timestamps. It reports Acc@tau, MAE and
UER both overall and by action category. Full-catalog UER is also calculated
without requiring every action to be manually annotated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
except ImportError:  # Direct script execution from the repository root.
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
DEFAULT_GROUND_TRUTH = (
    REPO_ROOT / "evaluation" / "ground_truth" / "ocr_alignment_ground_truth.csv"
)
DEFAULT_RESULTS_DIR = REPO_ROOT / "evaluation" / "results"
DEFAULT_BASELINE_DIR = (
    REPO_ROOT
    / "evaluation"
    / "ocr_baselines"
    / "production_before_final_ocr"
)
DEFAULT_PRODUCTION_DIR = REPO_ROOT / "video_timelines"
DEFAULT_TOLERANCES = (1.0, 2.0)

GROUND_TRUTH_COLUMNS = (
    "season_code",
    "game_code",
    "original_event_id",
    "action_info",
    "action_category",
    "pbp_quarter",
    "pbp_game_clock",
    "sync_quarter",
    "sync_game_clock",
    "reference_video_seconds",
    "youtube_review_url",
    "annotation_status",
    "ground_truth_video_seconds",
    "annotator",
    "notes",
)


@dataclass(frozen=True)
class ActionRecord:
    season_code: str
    game_code: str
    event_id: int
    action: PlayByPlayAction
    action_info: str
    category: str
    pbp_quarter: str
    pbp_clock: str
    youtube_url: str


@dataclass(frozen=True)
class GroundTruthEvent:
    season_code: str
    game_code: str
    event_id: int
    category: str
    ground_truth_video_seconds: float


@dataclass(frozen=True)
class EvaluationRow:
    system: str
    event: GroundTruthEvent
    action_info: str
    predicted_video_seconds: float | None

    @property
    def absolute_error_seconds(self) -> float | None:
        if self.predicted_video_seconds is None:
            return None
        return abs(
            self.predicted_video_seconds
            - self.event.ground_truth_video_seconds
        )


def action_category(action_info: str) -> str:
    """Map compact EuroLeague action codes to evaluation categories."""
    code = str(action_info or "").strip().upper()
    if code in {"2FGM", "3FGM"}:
        return "made_field_goal"
    if code in {"2FGA", "3FGA"}:
        return "missed_field_goal"
    if code == "FTM":
        return "made_free_throw"
    if code == "FTA":
        return "missed_free_throw"
    if code in {"O", "D"}:
        return "rebound"
    if code in {"TOUT", "TOUT_TV"}:
        return "timeout"
    if code in {"CM", "B", "CMU", "CMT", "C", "OF", "RV"}:
        return "foul"
    if code == "AS":
        return "assist"
    if code == "TO":
        return "turnover"
    if code in {"IN", "OUT"}:
        return "substitution"
    if code in {"BP", "EP", "EG", "JB"}:
        return "period_boundary"
    if code in {"ST", "FV"}:
        return "defensive_play"
    if code in {"CCH"}:
        return "review_challenge"
    return "other"


def format_game_clock(seconds: float) -> str:
    if seconds < 60 and abs(seconds - round(seconds)) > 0.001:
        return f"{seconds:.1f}"
    whole_seconds = int(round(seconds))
    return f"{whole_seconds // 60:02d}:{whole_seconds % 60:02d}"


def event_id_from_uri(uri: str) -> int:
    try:
        return int(uri.rsplit("#PlayByPlay_J", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid Play-by-Play URI: {uri}") from exc


def catalog_games(catalog_path: Path) -> list[dict[str, object]]:
    """Load every catalog game so future seasons need no code changes."""
    with catalog_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    games = payload.get("games") if isinstance(payload, dict) else None
    if not isinstance(games, list):
        raise ValueError(f"Catalog {catalog_path} must contain a games list")
    selected = [game for game in games if isinstance(game, dict)]
    selected.sort(key=lambda game: (
        str(game.get("season_code", "")),
        int(str(game.get("game_code", "0"))),
    ))
    return selected


def load_action_records(
    catalog_path: Path,
    all_actions_dir: Path,
) -> list[ActionRecord]:
    records = []
    for game in catalog_games(catalog_path):
        season_code = str(game["season_code"])
        game_code = str(game["game_code"])
        actions_path = (
            all_actions_dir / f"AllActions_{season_code}_{game_code}.json"
        )
        if not actions_path.is_file():
            raise FileNotFoundError(
                f"Missing Play-by-Play actions for {season_code}/{game_code}: "
                f"{actions_path}"
            )
        current_game_uri = game_uri(season_code, game_code)
        synchronized_actions = {
            event_id_from_uri(action.uri): action
            for action in load_actions(actions_path, current_game_uri)
        }
        with actions_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        rows = payload.get("AllActions", [])
        for row in rows:
            event_id = int(row["originalEventId"])
            action = synchronized_actions[event_id]
            action_info = str(row.get("actionInfo", "")).strip()
            records.append(ActionRecord(
                season_code=season_code,
                game_code=game_code,
                event_id=event_id,
                action=action,
                action_info=action_info,
                category=action_category(action_info),
                pbp_quarter=str(row.get("quarter", "")).strip(),
                pbp_clock=str(row.get("clock", "")).strip()
                or format_game_clock(float(row["quarterSecondsRemaining"])),
                youtube_url=str(game.get("youtube_url", "")).strip(),
            ))
    return records


def deterministic_stratified_sample(
    records: Iterable[ActionRecord],
    per_category: int,
    seed: str,
) -> list[ActionRecord]:
    if per_category <= 0:
        raise ValueError("per_category must be positive")
    grouped: dict[str, list[ActionRecord]] = defaultdict(list)
    for record in records:
        grouped[record.category].append(record)

    selected = []
    for category, category_records in sorted(grouped.items()):
        ordered = sorted(
            category_records,
            key=lambda record: hashlib.sha256(
                (
                    f"{seed}:{record.season_code}:{record.game_code}:"
                    f"{record.event_id}"
                ).encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ordered[:per_category])
    return sorted(
        selected,
        key=lambda record: (
            record.category,
            record.season_code,
            int(record.game_code),
            record.event_id,
        ),
    )


def timeline_path(timeline_dir: Path, season_code: str, game_code: str) -> Path:
    return timeline_dir / f"{season_code}_{game_code}.csv"


def prediction_for_action(
    action: PlayByPlayAction,
    observation_index: dict[str, object],
) -> float | None:
    observation, _difference = find_nearest_observation(
        observation_index,
        action.quarter,
        action.quarter_seconds_remaining,
        max_difference=synchronization_tolerance(action),
    )
    return observation.video_seconds if observation else None


def write_ground_truth_sample(
    records: list[ActionRecord],
    reference_dir: Path,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    index_cache: dict[tuple[str, str], dict[str, object]] = {}
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=GROUND_TRUTH_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        for record in records:
            current_game_uri = game_uri(record.season_code, record.game_code)
            game_key = (record.season_code, record.game_code)
            if game_key not in index_cache:
                observations = load_observations(
                    timeline_path(
                        reference_dir, record.season_code, record.game_code
                    ),
                    f"{current_game_uri}#BroadcastVideo",
                )
                index_cache[game_key] = build_observation_index(observations)
            reference = prediction_for_action(
                record.action,
                index_cache[game_key],
            )
            review_seconds = max(0, int((reference or 0) - 8))
            separator = "&" if "?" in record.youtube_url else "?"
            review_url = (
                f"{record.youtube_url}{separator}t={review_seconds}s"
                if record.youtube_url
                else ""
            )
            writer.writerow({
                "season_code": record.season_code,
                "game_code": record.game_code,
                "original_event_id": record.event_id,
                "action_info": record.action_info,
                "action_category": record.category,
                "pbp_quarter": record.pbp_quarter,
                "pbp_game_clock": record.pbp_clock,
                "sync_quarter": record.action.quarter,
                "sync_game_clock": format_game_clock(
                    record.action.quarter_seconds_remaining
                ),
                "reference_video_seconds": (
                    "" if reference is None else f"{reference:.3f}"
                ),
                "youtube_review_url": review_url,
                "annotation_status": "Pending",
                "ground_truth_video_seconds": "",
                "annotator": "",
                "notes": "",
            })


def load_ground_truth(
    path: Path,
) -> tuple[list[GroundTruthEvent], int, int]:
    annotated = []
    pending = 0
    excluded = 0
    seen = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "season_code", "game_code", "original_event_id",
            "action_category", "annotation_status",
            "ground_truth_video_seconds",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"Ground-truth file is missing columns: {', '.join(sorted(missing))}"
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
                season_code = str(row["season_code"]).strip()
                game_code = str(row["game_code"]).strip()
                event_id = int(row["original_event_id"])
                ground_truth = float(row["ground_truth_video_seconds"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid annotated ground-truth row {row_number}: {exc}"
                ) from exc
            if ground_truth < 0:
                raise ValueError(
                    f"Ground-truth time cannot be negative at row {row_number}"
                )
            key = (season_code, game_code, event_id)
            if key in seen:
                raise ValueError(f"Duplicate ground-truth event at row {row_number}: {key}")
            seen.add(key)
            annotated.append(GroundTruthEvent(
                season_code=season_code,
                game_code=game_code,
                event_id=event_id,
                category=str(row.get("action_category", "")).strip() or "other",
                ground_truth_video_seconds=ground_truth,
            ))
    return annotated, pending, excluded


def metric_summary(
    rows: Iterable[EvaluationRow],
    tolerances: tuple[float, ...] = DEFAULT_TOLERANCES,
) -> dict[str, float | int | None]:
    rows = list(rows)
    total = len(rows)
    errors = [
        row.absolute_error_seconds
        for row in rows
        if row.absolute_error_seconds is not None
    ]
    mapped = len(errors)
    result: dict[str, float | int | None] = {
        "total": total,
        "mapped": mapped,
        "unmapped": total - mapped,
        "uer_pct": ((total - mapped) / total * 100) if total else 0.0,
        "mae_seconds": statistics.fmean(errors) if errors else None,
    }
    for tolerance in tolerances:
        key = f"acc_at_{tolerance:g}_pct"
        result[key] = (
            sum(error <= tolerance for error in errors) / total * 100
            if total
            else 0.0
        )
    return result


def action_lookup(
    catalog_path: Path,
    all_actions_dir: Path,
) -> dict[tuple[str, str, int], ActionRecord]:
    return {
        (record.season_code, record.game_code, record.event_id): record
        for record in load_action_records(catalog_path, all_actions_dir)
    }


def evaluate_ground_truth(
    events: list[GroundTruthEvent],
    systems: dict[str, Path],
    records: dict[tuple[str, str, int], ActionRecord],
) -> list[EvaluationRow]:
    rows = []
    index_cache = {}
    for system, timeline_dir in systems.items():
        for event in events:
            key = (event.season_code, event.game_code, event.event_id)
            record = records.get(key)
            if record is None:
                raise ValueError(f"Ground-truth event is missing from AllActions: {key}")
            game_key = (system, event.season_code, event.game_code)
            if game_key not in index_cache:
                current_game_uri = game_uri(event.season_code, event.game_code)
                observations = load_observations(
                    timeline_path(
                        timeline_dir, event.season_code, event.game_code
                    ),
                    f"{current_game_uri}#BroadcastVideo",
                )
                index_cache[game_key] = build_observation_index(observations)
            observation, _difference = find_nearest_observation(
                index_cache[game_key],
                record.action.quarter,
                record.action.quarter_seconds_remaining,
                max_difference=synchronization_tolerance(record.action),
            )
            rows.append(EvaluationRow(
                system=system,
                event=event,
                action_info=record.action_info,
                predicted_video_seconds=(
                    observation.video_seconds if observation else None
                ),
            ))
    return rows


def full_catalog_coverage(
    systems: dict[str, Path],
    records: dict[tuple[str, str, int], ActionRecord],
) -> dict[str, dict[str, float | int]]:
    result = {}
    grouped_records: dict[tuple[str, str], list[ActionRecord]] = defaultdict(list)
    for record in records.values():
        grouped_records[(record.season_code, record.game_code)].append(record)
    for system, timeline_dir in systems.items():
        total = 0
        mapped = 0
        for (season_code, game_code), game_records in grouped_records.items():
            current_game_uri = game_uri(season_code, game_code)
            observations = load_observations(
                timeline_path(timeline_dir, season_code, game_code),
                f"{current_game_uri}#BroadcastVideo",
            )
            index = build_observation_index(observations)
            for record in game_records:
                total += 1
                observation, _difference = find_nearest_observation(
                    index,
                    record.action.quarter,
                    record.action.quarter_seconds_remaining,
                    max_difference=synchronization_tolerance(record.action),
                )
                mapped += observation is not None
        result[system] = {
            "total": total,
            "mapped": mapped,
            "unmapped": total - mapped,
            "uer_pct": (total - mapped) / total * 100 if total else 0.0,
        }
    return result


def write_evaluation_outputs(
    rows: list[EvaluationRow],
    coverage: dict[str, dict[str, float | int]],
    output_dir: Path,
    tolerances: tuple[float, ...],
    pending: int,
    excluded: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    detailed_path = output_dir / "ocr_alignment_detailed.csv"
    with detailed_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "system", "season_code", "game_code", "original_event_id",
            "action_info", "action_category", "ground_truth_video_seconds",
            "predicted_video_seconds", "absolute_error_seconds",
        ] + [f"within_{tolerance:g}_seconds" for tolerance in tolerances]
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            error = row.absolute_error_seconds
            values = {
                "system": row.system,
                "season_code": row.event.season_code,
                "game_code": row.event.game_code,
                "original_event_id": row.event.event_id,
                "action_info": row.action_info,
                "action_category": row.event.category,
                "ground_truth_video_seconds": row.event.ground_truth_video_seconds,
                "predicted_video_seconds": row.predicted_video_seconds,
                "absolute_error_seconds": error,
            }
            for tolerance in tolerances:
                values[f"within_{tolerance:g}_seconds"] = (
                    error is not None and error <= tolerance
                )
            writer.writerow(values)

    summary_rows = []
    systems = sorted({row.system for row in rows} | set(coverage))
    for system in systems:
        system_rows = [row for row in rows if row.system == system]
        summary_rows.append((system, "ground_truth", "overall", "all", metric_summary(system_rows, tolerances)))
        categories = sorted({row.event.category for row in system_rows})
        for category in categories:
            category_rows = [
                row for row in system_rows if row.event.category == category
            ]
            summary_rows.append((system, "ground_truth", "action_category", category, metric_summary(category_rows, tolerances)))
        per_game = defaultdict(list)
        for row in system_rows:
            per_game[(row.event.season_code, row.event.game_code)].append(row)
        if per_game:
            game_metrics = [metric_summary(items, tolerances) for items in per_game.values()]
            available_mae = [
                float(item["mae_seconds"])
                for item in game_metrics
                if item["mae_seconds"] is not None
            ]
            macro = {
                "total": len(game_metrics),
                "mapped": None,
                "unmapped": None,
                "uer_pct": statistics.fmean(float(item["uer_pct"]) for item in game_metrics),
                "mae_seconds": (
                    statistics.fmean(available_mae) if available_mae else None
                ),
            }
            for tolerance in tolerances:
                key = f"acc_at_{tolerance:g}_pct"
                macro[key] = statistics.fmean(float(item[key]) for item in game_metrics)
            summary_rows.append((system, "ground_truth", "macro_games", "all_games", macro))

        full = coverage[system]
        full_metrics = {
            "total": full["total"],
            "mapped": full["mapped"],
            "unmapped": full["unmapped"],
            "uer_pct": full["uer_pct"],
            "mae_seconds": None,
        }
        for tolerance in tolerances:
            full_metrics[f"acc_at_{tolerance:g}_pct"] = None
        summary_rows.append((system, "full_pbp", "overall", "all", full_metrics))

    summary_path = output_dir / "ocr_alignment_summary.csv"
    metric_fields = [
        "total", "mapped", "unmapped", "uer_pct", "mae_seconds",
    ] + [f"acc_at_{tolerance:g}_pct" for tolerance in tolerances]
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["system", "dataset_scope", "group_by", "group"] + metric_fields,
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

    report_path = output_dir / "ocr_alignment_report.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# OCR alignment evaluation\n\n")
        handle.write(f"Annotated events: {len(rows) // max(1, len(systems))}\n\n")
        handle.write(f"Pending annotations: {pending}; excluded: {excluded}.\n\n")
        handle.write("## Ground-truth metrics\n\n")
        headers = ["System", "N", "Mapped", "UER", "MAE"] + [
            f"Acc@{tolerance:g}s" for tolerance in tolerances
        ]
        handle.write("| " + " | ".join(headers) + " |\n")
        handle.write("| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |\n")
        for system in systems:
            metrics = metric_summary(
                [row for row in rows if row.system == system], tolerances
            )
            values = [
                system,
                str(metrics["total"]),
                str(metrics["mapped"]),
                f"{float(metrics['uer_pct']):.3f}%",
                "—" if metrics["mae_seconds"] is None else f"{float(metrics['mae_seconds']):.3f}s",
            ] + [
                f"{float(metrics[f'acc_at_{tolerance:g}_pct']):.3f}%"
                for tolerance in tolerances
            ]
            handle.write("| " + " | ".join(values) + " |\n")
        handle.write("\n## Full-catalog UER\n\n")
        handle.write("| System | PBP actions | Mapped | Unmapped | UER |\n")
        handle.write("| --- | ---: | ---: | ---: | ---: |\n")
        for system in systems:
            metrics = coverage[system]
            handle.write(
                f"| {system} | {metrics['total']} | {metrics['mapped']} | "
                f"{metrics['unmapped']} | {float(metrics['uer_pct']):.3f}% |\n"
            )
        handle.write(
            "\nPer-category and macro-by-game results are available in "
            "`ocr_alignment_summary.csv`; per-event predictions and errors are "
            "available in `ocr_alignment_detailed.csv`.\n"
        )


def parse_systems(values: list[str] | None) -> dict[str, Path]:
    if not values:
        return {
            "baseline": DEFAULT_BASELINE_DIR,
            "production": DEFAULT_PRODUCTION_DIR,
        }
    systems = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--system must use LABEL=TIMELINE_DIRECTORY")
        label, directory = value.split("=", 1)
        if not label.strip() or not directory.strip():
            raise ValueError("--system must use LABEL=TIMELINE_DIRECTORY")
        systems[label.strip()] = Path(directory).expanduser().resolve()
    return systems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample = subparsers.add_parser(
        "sample", help="Create a deterministic stratified annotation CSV"
    )
    sample.add_argument("--catalog-file", type=Path, default=DEFAULT_CATALOG_FILE)
    sample.add_argument("--all-actions-dir", type=Path, default=DEFAULT_ALL_ACTIONS_DIR)
    sample.add_argument("--reference-dir", type=Path, default=DEFAULT_PRODUCTION_DIR)
    sample.add_argument("--per-category", type=int, default=20)
    sample.add_argument("--seed", default="euroleague-ocr-evaluation-v1")
    sample.add_argument("--output", type=Path, default=DEFAULT_GROUND_TRUTH)
    sample.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing sample, including any annotations",
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="Evaluate annotated timestamps against timeline systems"
    )
    evaluate.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    evaluate.add_argument("--catalog-file", type=Path, default=DEFAULT_CATALOG_FILE)
    evaluate.add_argument("--all-actions-dir", type=Path, default=DEFAULT_ALL_ACTIONS_DIR)
    evaluate.add_argument(
        "--system",
        action="append",
        help="Timeline version in LABEL=DIRECTORY form; may be repeated",
    )
    evaluate.add_argument(
        "--tolerance",
        type=float,
        action="append",
        help="Accuracy tolerance in seconds; defaults to 1 and 2",
    )
    evaluate.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog_path = args.catalog_file.expanduser().resolve()
    all_actions_dir = args.all_actions_dir.expanduser().resolve()
    if args.command == "sample":
        records = load_action_records(catalog_path, all_actions_dir)
        sample = deterministic_stratified_sample(
            records, args.per_category, args.seed
        )
        output = args.output.expanduser().resolve()
        if output.exists() and not args.force:
            raise FileExistsError(
                f"Ground-truth sample already exists: {output}. Use --force "
                "only if you intend to discard its annotations."
            )
        write_ground_truth_sample(
            sample,
            args.reference_dir.expanduser().resolve(),
            output,
        )
        print(
            f"Saved {len(sample)} actions across "
            f"{len({record.category for record in sample})} categories to {output}"
        )
        return 0

    systems = parse_systems(args.system)
    tolerances = tuple(sorted(set(args.tolerance or DEFAULT_TOLERANCES)))
    if any(tolerance < 0 for tolerance in tolerances):
        raise ValueError("Tolerances cannot be negative")
    events, pending, excluded = load_ground_truth(
        args.ground_truth.expanduser().resolve()
    )
    if not events:
        raise ValueError(
            "No annotated ground-truth rows found. Set annotation_status to "
            "Annotated and provide ground_truth_video_seconds first."
        )
    records = action_lookup(catalog_path, all_actions_dir)
    rows = evaluate_ground_truth(events, systems, records)
    coverage = full_catalog_coverage(systems, records)
    output_dir = args.output_dir.expanduser().resolve()
    write_evaluation_outputs(
        rows, coverage, output_dir, tolerances, pending, excluded
    )
    print(
        f"Evaluated {len(events)} annotated events across {len(systems)} "
        f"systems. Results saved to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
