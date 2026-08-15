"""Validate generated AllActions JSON and Play-by-Play N-Triples artifacts."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    from .parser import convert_action_info
except ImportError:  # Direct script execution from the repository root.
    from parser import convert_action_info


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_ALL_ACTIONS_DIR = DEFAULT_PROCESSED_DIR / "all_actions"
DEFAULT_PLAYBYPLAY_TRIPLETS_DIR = (
    DEFAULT_PROCESSED_DIR / "playbyplay_triplets"
)
BASKETBALL_NS = "http://www.ics.forth.gr/isl/Basketball#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
NTRIPLE_PATTERN = re.compile(
    r'^<[^>]+> <[^>]+> (?:<[^>]+>|"(?:[^"\\]|\\.)*"'
    r'(?:@[A-Za-z]+(?:-[A-Za-z0-9]+)*|\^\^<[^>]+>)?) \.$'
)
TRIPLE_PARTS_PATTERN = re.compile(r"^<([^>]+)> <([^>]+)> (.+) \.$")
FILE_PATTERN = re.compile(r"^AllActions_(E\d{4})_(\d+)\.json$")


@dataclass(frozen=True)
class ActionValidationResult:
    season_code: str
    game_code: str
    actions: int
    triples: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def season_label_from_code(season_code: str) -> str:
    if not re.fullmatch(r"E\d{4}", season_code):
        raise ValueError(f"Invalid season code: {season_code}")
    start_year = int(season_code[1:])
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def game_uri(season_code: str, game_code: str) -> str:
    return (
        "https://www.euroleaguebasketball.net/euroleague/game-center/"
        f"{season_label_from_code(season_code)}/-/{season_code}/{game_code}"
    )


def clock_to_seconds(clock: object) -> float:
    value = str(clock or "").strip()
    if not value:
        raise ValueError("empty clock")
    if ":" in value:
        minutes, seconds = value.split(":", 1)
        return int(minutes) * 60 + float(seconds)
    return float(value)


def maximum_period_seconds(quarter: object) -> int | None:
    normalized = re.sub(r"\s+", "", str(quarter or "").upper())
    if normalized in {"1ST", "2ND", "3RD", "4TH"}:
        return 600
    if normalized in {"OT", "1OT", "OT1"}:
        return 300
    if re.fullmatch(r"(?:(?:\d+)OT|OT(?:\d+))", normalized):
        return 300
    return None


def validate_action_payload(payload: object) -> tuple[list[dict[str, object]], list[str]]:
    errors = []
    if not isinstance(payload, dict):
        return [], ["JSON root must be an object"]
    actions = payload.get("AllActions")
    possessions = payload.get("Possessions")
    if not isinstance(actions, list):
        return [], ["JSON must contain an AllActions list"]
    if not isinstance(possessions, list):
        errors.append("JSON must contain a Possessions list")
        possessions = []
    action_rows = [action for action in actions if isinstance(action, dict)]
    if len(action_rows) != len(actions):
        errors.append("AllActions contains a non-object entry")
    if not action_rows:
        errors.append("AllActions is empty")
        return action_rows, errors

    sequences = [action.get("hasPlayByPlaySequence") for action in action_rows]
    expected_sequences = list(range(1, len(action_rows) + 1))
    if sequences != expected_sequences:
        errors.append("hasPlayByPlaySequence is not continuous from 1")

    event_ids = [action.get("originalEventId") for action in action_rows]
    if any(not isinstance(event_id, int) for event_id in event_ids):
        errors.append("Every action must have an integer originalEventId")
    duplicate_ids = [
        event_id
        for event_id, count in Counter(event_ids).items()
        if event_id is not None and count > 1
    ]
    if duplicate_ids:
        errors.append(f"Duplicate originalEventId values: {duplicate_ids[:10]}")
    valid_event_ids = {event_id for event_id in event_ids if isinstance(event_id, int)}

    for position, action in enumerate(action_rows, start=1):
        quarter = action.get("quarter")
        maximum = maximum_period_seconds(quarter)
        if maximum is None:
            errors.append(f"Action {position} has invalid quarter {quarter!r}")
            continue
        try:
            seconds = float(action.get("quarterSecondsRemaining"))
        except (TypeError, ValueError):
            errors.append(f"Action {position} has invalid quarterSecondsRemaining")
            continue
        if not 0 <= seconds <= maximum:
            errors.append(
                f"Action {position} has {seconds:g} seconds in {quarter}; "
                f"allowed range is 0-{maximum}"
            )
        try:
            clock_seconds = clock_to_seconds(action.get("clock"))
        except (TypeError, ValueError) as exc:
            errors.append(f"Action {position} has invalid clock: {exc}")
        else:
            if abs(clock_seconds - seconds) > 0.001:
                errors.append(
                    f"Action {position} clock does not match "
                    "quarterSecondsRemaining"
                )

    possession_reference_fields = (
        "startsAfterAction",
        "endsWithAction",
    )
    for position, possession in enumerate(possessions, start=1):
        if not isinstance(possession, dict):
            errors.append(f"Possession {position} is not an object")
            continue
        references = []
        for field in possession_reference_fields:
            value = possession.get(field)
            if value is not None:
                references.append(value)
        contains = possession.get("containsAction", [])
        if not isinstance(contains, list):
            errors.append(f"Possession {position} containsAction is not a list")
        else:
            references.extend(contains)
        missing = [value for value in references if value not in valid_event_ids]
        if missing:
            errors.append(
                f"Possession {position} references missing actions: {missing[:10]}"
            )
    return action_rows, errors


def validate_action_artifacts(
    json_path: Path,
    triples_path: Path,
    season_code: str,
    game_code: str,
) -> ActionValidationResult:
    errors = []
    if not json_path.exists():
        errors.append(f"Missing JSON file: {json_path}")
        return ActionValidationResult(season_code, game_code, 0, 0, tuple(errors))
    if not triples_path.exists():
        errors.append(f"Missing N-Triples file: {triples_path}")
        return ActionValidationResult(season_code, game_code, 0, 0, tuple(errors))

    try:
        with json_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Could not read JSON: {exc}")
        return ActionValidationResult(season_code, game_code, 0, 0, tuple(errors))
    actions, payload_errors = validate_action_payload(payload)
    errors.extend(payload_errors)

    try:
        lines = [
            line.strip()
            for line in triples_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        errors.append(f"Could not read N-Triples: {exc}")
        return ActionValidationResult(
            season_code, game_code, len(actions), 0, tuple(errors)
        )

    malformed = [number for number, line in enumerate(lines, start=1) if not NTRIPLE_PATTERN.fullmatch(line)]
    if malformed:
        errors.append(f"Malformed N-Triples lines: {malformed[:10]}")
    duplicate_count = len(lines) - len(set(lines))
    if duplicate_count:
        errors.append(f"N-Triples contains {duplicate_count} duplicate lines")

    records = []
    for line in lines:
        match = TRIPLE_PARTS_PATTERN.fullmatch(line)
        if match:
            records.append(match.groups())
    current_game_uri = game_uri(season_code, game_code)
    has_action = f"{BASKETBALL_NS}hasPlayByPlayAction"
    expected_action_uris = {
        f"{current_game_uri}#PlayByPlay_J{action['originalEventId']}"
        for action in actions
        if isinstance(action.get("originalEventId"), int)
    }
    linked_action_uris = {
        object_value[1:-1]
        for subject, predicate, object_value in records
        if subject == current_game_uri
        and predicate == has_action
        and object_value.startswith("<")
        and object_value.endswith(">")
    }
    missing_links = expected_action_uris - linked_action_uris
    unexpected_links = linked_action_uris - expected_action_uris
    if missing_links:
        errors.append(f"RDF is missing {len(missing_links)} game-to-action links")
    if unexpected_links:
        errors.append(f"RDF has {len(unexpected_links)} unexpected action links")

    sequence_predicate = f"{BASKETBALL_NS}hasPlayByPlaySequence"
    typed_actions = {
        subject
        for subject, predicate, _object_value in records
        if predicate == RDF_TYPE and subject in expected_action_uris
    }
    actual_action_types = {
        (subject, object_value[1:-1])
        for subject, predicate, object_value in records
        if predicate == RDF_TYPE
        and subject in expected_action_uris
        and object_value.startswith("<")
        and object_value.endswith(">")
    }
    expected_action_types = {
        (
            f"{current_game_uri}#PlayByPlay_J{action['originalEventId']}",
            f"{BASKETBALL_NS}{convert_action_info(action.get('actionInfo', ''))}",
        )
        for action in actions
        if isinstance(action.get("originalEventId"), int)
    }
    sequenced_actions = {
        subject
        for subject, predicate, _object_value in records
        if predicate == sequence_predicate and subject in expected_action_uris
    }
    if typed_actions != expected_action_uris:
        errors.append(
            f"RDF is missing types for {len(expected_action_uris - typed_actions)} actions"
        )
    missing_types = expected_action_types - actual_action_types
    unexpected_types = actual_action_types - expected_action_types
    if missing_types:
        errors.append(f"RDF has {len(missing_types)} missing or incorrect action types")
    if unexpected_types:
        errors.append(f"RDF has {len(unexpected_types)} unexpected action types")
    if sequenced_actions != expected_action_uris:
        errors.append(
            "RDF is missing sequences for "
            f"{len(expected_action_uris - sequenced_actions)} actions"
        )
    return ActionValidationResult(
        season_code,
        game_code,
        len(actions),
        len(lines),
        tuple(errors),
    )


def discover_artifacts(
    all_actions_dir: Path,
    triplets_dir: Path,
    season_code: str | None = None,
    game_code: str | None = None,
) -> list[tuple[Path, Path, str, str]]:
    results = []
    for json_path in sorted(all_actions_dir.glob("AllActions_*.json")):
        match = FILE_PATTERN.fullmatch(json_path.name)
        if not match:
            continue
        current_season, current_game = match.groups()
        if season_code and current_season != season_code:
            continue
        if game_code and current_game != str(game_code):
            continue
        triples_path = triplets_dir / f"Triplets_{current_season}_{current_game}.nt"
        results.append((json_path, triples_path, current_season, current_game))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated AllActions JSON and Play-by-Play N-Triples."
    )
    parser.add_argument("season_code", nargs="?")
    parser.add_argument("game_code", nargs="?")
    parser.add_argument(
        "--all-actions-dir",
        type=Path,
        default=DEFAULT_ALL_ACTIONS_DIR,
    )
    parser.add_argument(
        "--playbyplay-triplets-dir",
        type=Path,
        default=DEFAULT_PLAYBYPLAY_TRIPLETS_DIR,
    )
    args = parser.parse_args(argv)
    artifacts = discover_artifacts(
        args.all_actions_dir,
        args.playbyplay_triplets_dir,
        args.season_code,
        args.game_code,
    )
    if not artifacts:
        parser.error("No matching AllActions files were found")

    failures = 0
    total_actions = total_triples = 0
    for json_path, triples_path, season_code, game_code in artifacts:
        result = validate_action_artifacts(
            json_path,
            triples_path,
            season_code,
            game_code,
        )
        total_actions += result.actions
        total_triples += result.triples
        if result.ok:
            print(
                f"OK {season_code}/{game_code}: "
                f"{result.actions} actions, {result.triples} triples"
            )
        else:
            failures += 1
            print(f"FAIL {season_code}/{game_code}")
            for error in result.errors:
                print(f"  - {error}")
    print(
        f"Validated {len(artifacts)} games: {total_actions} actions, "
        f"{total_triples} triples, {failures} failures."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
