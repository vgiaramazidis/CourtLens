"""Validate OCR timeline CSVs referenced by the video game catalog."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

try:
    from .video_ocr import (
        DEFAULT_CATALOG_FILE,
        clock_to_seconds,
        load_game_catalog,
        remove_temporally_impossible_results,
        resolve_repo_path,
        sanitize_timeline_results,
    )
except ImportError:  # Direct script execution from the repository root.
    from video_ocr import (
        DEFAULT_CATALOG_FILE,
        clock_to_seconds,
        load_game_catalog,
        remove_temporally_impossible_results,
        resolve_repo_path,
        sanitize_timeline_results,
    )


REQUIRED_QUARTERS = ("1st", "2nd", "3rd", "4th")


def validate_timeline(path: Path) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError:
        return {"rows": 0, "quarters": {}}, ["file is missing"]

    by_quarter: dict[str, list[dict[str, str]]] = defaultdict(list)
    previous_video_time = -1.0
    for index, row in enumerate(rows, start=2):
        try:
            video_time = float(row["video_time_sec"])
            clock_seconds = clock_to_seconds(row["game_clock"])
            quarter = row["quarter"]
        except (KeyError, TypeError, ValueError):
            errors.append(f"row {index} has invalid columns")
            continue
        if clock_seconds is None:
            errors.append(f"row {index} has invalid clock")
            continue
        if video_time <= previous_video_time:
            errors.append(f"row {index} video time is not increasing")
        previous_video_time = video_time
        by_quarter[quarter].append(row)

    if len(rows) < 1200:
        errors.append(f"only {len(rows)} timeline points (minimum 1200)")

    summary: dict[str, dict[str, object]] = {}
    for quarter, quarter_rows in by_quarter.items():
        clocks = [clock_to_seconds(row["game_clock"]) for row in quarter_rows]
        valid_clocks = [value for value in clocks if value is not None]
        start_clock = valid_clocks[0]
        end_clock = valid_clocks[-1]
        expected_start = 600 if quarter in REQUIRED_QUARTERS else 300
        if any(clock > expected_start + 1 for clock in valid_clocks):
            errors.append(f"{quarter} clock exceeds its period duration")
        if start_clock < expected_start - 60:
            errors.append(f"{quarter} starts too late at {quarter_rows[0]['game_clock']}")
        if end_clock > 15:
            errors.append(f"{quarter} ends too early at {quarter_rows[-1]['game_clock']}")
        if any(current > previous for previous, current in zip(valid_clocks, valid_clocks[1:])):
            errors.append(f"{quarter} clock is not monotonic")
        for previous_row, current_row in zip(quarter_rows, quarter_rows[1:]):
            previous_clock = clock_to_seconds(previous_row["game_clock"])
            current_clock = clock_to_seconds(current_row["game_clock"])
            video_elapsed = (
                float(current_row["video_time_sec"])
                - float(previous_row["video_time_sec"])
            )
            if (
                previous_clock is not None
                and current_clock is not None
                and previous_clock - current_clock > video_elapsed + 5
            ):
                errors.append(f"{quarter} clock drops faster than video time")
                break
        summary[quarter] = {
            "points": len(quarter_rows),
            "start": quarter_rows[0]["game_clock"],
            "end": quarter_rows[-1]["game_clock"],
        }

    for quarter in REQUIRED_QUARTERS:
        if quarter not in by_quarter:
            errors.append(f"missing {quarter}")

    return {"rows": len(rows), "quarters": summary}, errors


def repair_timeline(input_path: Path, output_path: Path) -> tuple[int, int]:
    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    results = [
        (float(row["video_time_sec"]), row["quarter"], row["game_clock"])
        for row in rows
    ]
    results, monotonic_removed = sanitize_timeline_results(results)
    results, temporal_removed = remove_temporally_impossible_results(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["video_time_sec", "quarter", "game_clock"])
        writer.writerows(results)
    return len(results), monotonic_removed + temporal_removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-file", type=Path, default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--enabled-only", action="store_true")
    parser.add_argument("--existing-only", action="store_true")
    parser.add_argument("--repair-file", type=Path)
    parser.add_argument("--repair-output", type=Path)
    args = parser.parse_args()

    if args.repair_file:
        if not args.repair_output:
            parser.error("--repair-output is required with --repair-file")
        rows, removed = repair_timeline(args.repair_file, args.repair_output)
        print(f"Repaired {args.repair_output}: {rows} points ({removed} removed)")
        return 0

    failures = 0
    for game in load_game_catalog(args.catalog_file.resolve()):
        if args.enabled_only and not game.get("enabled"):
            continue
        path = resolve_repo_path(str(game.get("timeline_file", "")))
        if args.existing_only and not path.is_file():
            continue
        summary, errors = validate_timeline(path)
        label = f"{game.get('season_code')}/{game.get('game_code')}"
        if errors:
            failures += 1
            print(f"FAIL {label}: {'; '.join(errors)}")
            continue
        quarters = summary["quarters"]
        coverage = ", ".join(
            f"{quarter} {details['start']}->{details['end']} ({details['points']})"
            for quarter, details in quarters.items()
        )
        print(f"OK {label}: {summary['rows']} points; {coverage}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
