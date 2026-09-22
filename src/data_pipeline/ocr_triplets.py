"""Link Play-by-Play actions to OCR video timestamps and export N-Triples.

The timeline CSV remains the complete OCR source. Production RDF contains only
the OCR observations referenced by a synchronized Play-by-Play action. Missing
or invalid local action artifacts are generated and validated automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

try:
    from parser import (
        create_api_session,
        season_label_from_code,
    )
    from parser import (
        process_game as generate_action_artifacts,
    )
    from validate_action_artifacts import validate_action_artifacts
except ImportError:  # Direct execution from the repository root.
    from parser import (
        create_api_session,
        season_label_from_code,
    )
    from parser import (
        process_game as generate_action_artifacts,
    )
    from validate_action_artifacts import validate_action_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_FILE = Path(__file__).resolve().with_name("video_games.json")
DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_ALL_ACTIONS_DIR = DEFAULT_PROCESSED_DIR / "all_actions"
DEFAULT_PLAYBYPLAY_TRIPLETS_DIR = DEFAULT_PROCESSED_DIR / "playbyplay_triplets"
DEFAULT_OCR_OUTPUT_DIR = DEFAULT_PROCESSED_DIR / "ocr_triplets"

BASKETBALL_NS = "http://www.ics.forth.gr/isl/Basketball#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"
MAX_SYNC_DIFFERENCE_SECONDS = 5.0
PERIOD_START_SYNC_DIFFERENCE_SECONDS = 12.0
PERIOD_START_ACTION_TYPES = frozenset({"BP", "IN", "OUT"})
OPENING_JUMP_BALL_MAX_ELAPSED_SECONDS = 1.0


@dataclass(frozen=True)
class OCRObservation:
    sequence: int
    uri: str
    video_seconds: float
    quarter: str
    game_clock: str
    quarter_seconds_remaining: float


@dataclass(frozen=True)
class PlayByPlayAction:
    uri: str
    quarter: str
    quarter_seconds_remaining: float
    action_info: str = ""


def normalize_quarter(value: object) -> str:
    """Return one canonical label for Play-by-Play and OCR period aliases."""
    normalized = re.sub(r"\s+", "", str(value or "").upper())
    regulation = {
        "1": "1st",
        "Q1": "1st",
        "1ST": "1st",
        "2": "2nd",
        "Q2": "2nd",
        "2ND": "2nd",
        "3": "3rd",
        "Q3": "3rd",
        "3RD": "3rd",
        "4": "4th",
        "Q4": "4th",
        "4TH": "4th",
    }
    if normalized in regulation:
        return regulation[normalized]
    if normalized in {"OT", "1OT", "OT1"}:
        return "OT"

    overtime_match = re.fullmatch(r"(?:(\d+)OT|OT(\d+))", normalized)
    if overtime_match:
        overtime_number = int(overtime_match.group(1) or overtime_match.group(2))
        return "OT" if overtime_number <= 1 else f"{overtime_number}OT"
    return str(value or "").strip()


def clock_to_seconds(value: object) -> float:
    """Parse both MM:SS(.s) and OCR decimal-second clock values."""
    clock = str(value or "").strip()
    if not clock:
        raise ValueError("game_clock is empty")
    if ":" in clock:
        minutes, seconds = clock.split(":", 1)
        result = int(minutes) * 60 + float(seconds)
    else:
        result = float(clock)
    if result < 0:
        raise ValueError(f"game_clock cannot be negative: {clock}")
    return result


def game_uri(season_code: str, game_code: str) -> str:
    season_label = season_label_from_code(season_code)
    return (
        "https://www.euroleaguebasketball.net/euroleague/game-center/"
        f"{season_label}/-/{season_code}/{game_code}"
    )


def literal(value: object, datatype: str | None = None) -> str:
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    result = f'"{escaped}"'
    return f"{result}^^<{datatype}>" if datatype else result


def triple(subject: str, predicate: str, object_value: str) -> str:
    return f"<{subject}> <{predicate}> {object_value} ."


def iri(value: str) -> str:
    return f"<{value}>"


def decimal_text(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text}.0" if "." not in text else text


def load_selected_games(
    path: Path,
    season_code: str,
    game_code: str | None = None,
) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    games = payload.get("games") if isinstance(payload, dict) else None
    if not isinstance(games, list):
        raise ValueError(f"Catalog {path} must contain a games list")
    selected = [
        game
        for game in games
        if isinstance(game, dict)
        if str(game.get("season_code", "")).strip() == season_code
        and (game_code is None or str(game.get("game_code", "")).strip() == str(game_code))
    ]
    selected.sort(key=lambda game: int(str(game.get("game_code", "0"))))
    if game_code is not None and not selected:
        raise ValueError(f"Game {season_code}/{game_code} is not in the video catalog")
    if game_code is None and not selected:
        raise ValueError(f"Season {season_code} has no games in the video catalog")
    return selected


def load_observations(
    timeline_path: Path,
    video_uri: str,
) -> list[OCRObservation]:
    observations = []
    with timeline_path.open(newline="", encoding="utf-8") as handle:
        for sequence, row in enumerate(csv.DictReader(handle), start=1):
            try:
                video_seconds = float(row["video_time_sec"])
                game_clock = str(row["game_clock"]).strip()
                seconds_remaining = clock_to_seconds(game_clock)
                quarter = normalize_quarter(row["quarter"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid OCR row {sequence} in {timeline_path}: {exc}") from exc
            observations.append(
                OCRObservation(
                    sequence=sequence,
                    uri=f"{video_uri}/ocr-observation/{sequence}",
                    video_seconds=video_seconds,
                    quarter=quarter,
                    game_clock=game_clock,
                    quarter_seconds_remaining=seconds_remaining,
                )
            )
    if not observations:
        raise ValueError(f"OCR timeline {timeline_path} is empty")
    return observations


def build_observation_index(
    observations: Iterable[OCRObservation],
) -> dict[str, tuple[tuple[float, ...], tuple[OCRObservation, ...]]]:
    """Index the first video observation of every distinct period clock."""
    by_quarter: dict[str, dict[float, OCRObservation]] = defaultdict(dict)
    for observation in observations:
        by_quarter[observation.quarter].setdefault(
            observation.quarter_seconds_remaining,
            observation,
        )

    result = {}
    for quarter, clock_map in by_quarter.items():
        ordered = sorted(clock_map.items())
        result[quarter] = (
            tuple(clock for clock, _observation in ordered),
            tuple(observation for _clock, observation in ordered),
        )
    return result


def find_nearest_observation(
    index: dict[str, tuple[tuple[float, ...], tuple[OCRObservation, ...]]],
    quarter: object,
    seconds_remaining: object,
    max_difference: float = MAX_SYNC_DIFFERENCE_SECONDS,
) -> tuple[OCRObservation | None, float | None]:
    try:
        target = float(seconds_remaining)
    except (TypeError, ValueError):
        return None, None
    quarter_index = index.get(normalize_quarter(quarter))
    if not quarter_index:
        return None, None

    clocks, observations = quarter_index
    insertion = bisect_left(clocks, target)
    candidates = []
    if insertion < len(clocks):
        candidates.append(insertion)
    if insertion > 0:
        candidates.append(insertion - 1)
    closest = min(
        candidates,
        key=lambda position: (abs(clocks[position] - target), -clocks[position]),
    )
    difference = abs(clocks[closest] - target)
    if difference > max_difference:
        return None, difference
    return observations[closest], difference


def synchronization_tolerance(action: PlayByPlayAction) -> float:
    """Allow opening metadata to use the first visible clock of a period."""
    normalized_quarter = normalize_quarter(action.quarter)
    period_seconds = 600.0 if normalized_quarter in {"1st", "2nd", "3rd", "4th"} else 300.0
    is_period_start_metadata = (
        action.action_info in PERIOD_START_ACTION_TYPES
        and abs(action.quarter_seconds_remaining - period_seconds) < 0.001
    )
    elapsed_seconds = period_seconds - action.quarter_seconds_remaining
    is_opening_jump_ball = (
        action.action_info == "JB" and 0 <= elapsed_seconds <= OPENING_JUMP_BALL_MAX_ELAPSED_SECONDS
    )
    if is_period_start_metadata or is_opening_jump_ball:
        return PERIOD_START_SYNC_DIFFERENCE_SECONDS
    return MAX_SYNC_DIFFERENCE_SECONDS


def load_actions(
    path: Path,
    current_game_uri: str,
) -> list[PlayByPlayAction]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("AllActions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"Actions file {path} must contain an AllActions list")

    # An Assist is written to the official feed shortly after the scoring play.
    # Synchronize it to that clock so the RDF points to the moment where the
    # pass appears in the video. FIBA can award an assist when a pass leads to
    # a shooting foul and at least one resulting free throw is made, so FTM is
    # a valid anchor alongside made two- and three-point shots.
    action_timings: dict[str, tuple[str, float]] = {}
    for row in rows:
        try:
            event_id = int(row["originalEventId"])
            action_timings[f"{current_game_uri}#PlayByPlay_J{event_id}"] = (
                str(row["quarter"]).strip(),
                float(row["quarterSecondsRemaining"]),
            )
        except (KeyError, TypeError, ValueError):
            continue

    assist_anchors: dict[str, tuple[str, float]] = {}
    for row in rows:
        assist_uri = str(row.get("hasAssist", "")).strip()
        if not assist_uri or row.get("actionInfo") not in ("2FGM", "3FGM", "FTM"):
            continue
        try:
            shot_timing = (
                str(row["quarter"]).strip(),
                float(row["quarterSecondsRemaining"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        assist_timing = action_timings.get(assist_uri)
        if (
            assist_timing
            and normalize_quarter(assist_timing[0]) == normalize_quarter(shot_timing[0])
            and abs(assist_timing[1] - shot_timing[1]) <= 5
        ):
            assist_anchors[assist_uri] = shot_timing

    actions = []
    for position, row in enumerate(rows, start=1):
        try:
            event_id = int(row["originalEventId"])
            quarter = str(row["quarter"]).strip()
            seconds = float(row["quarterSecondsRemaining"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid local Play-by-Play action {position}: {exc}") from exc
        if not quarter:
            raise ValueError(f"Invalid local Play-by-Play action {position}: empty quarter")
        action_uri = f"{current_game_uri}#PlayByPlay_J{event_id}"
        sync_quarter, sync_seconds = assist_anchors.get(action_uri, (quarter, seconds))
        actions.append(
            PlayByPlayAction(
                uri=action_uri,
                quarter=sync_quarter,
                quarter_seconds_remaining=sync_seconds,
                action_info=str(row.get("actionInfo", "")).strip(),
            )
        )
    return actions


def ensure_action_artifacts(
    game: dict[str, object],
    all_actions_dir: Path,
    triplets_dir: Path,
    api_session: object,
    refresh: bool = False,
) -> tuple[list[PlayByPlayAction], bool]:
    season_code = str(game.get("season_code", "")).strip()
    game_code = str(game.get("game_code", "")).strip()
    season_label = season_label_from_code(season_code)
    json_path = all_actions_dir / f"AllActions_{season_code}_{game_code}.json"
    triples_path = triplets_dir / f"Triplets_{season_code}_{game_code}.nt"
    all_actions_dir.mkdir(parents=True, exist_ok=True)
    triplets_dir.mkdir(parents=True, exist_ok=True)
    regenerate = refresh or not (json_path.exists() and triples_path.exists())
    if not regenerate:
        validation = validate_action_artifacts(
            json_path,
            triples_path,
            season_code,
            game_code,
        )
        if not validation.ok:
            print("  -> Existing action artifacts failed validation; regenerating.")
            for error in validation.errors[:5]:
                print(f"     - {error}")
            regenerate = True

    generated = False
    if regenerate:
        print("  -> Generating Play-by-Play JSON and N-Triples first...")
        status = generate_action_artifacts(
            api_session,
            season_code,
            season_label,
            game_code,
            str(all_actions_dir),
            str(triplets_dir),
            overwrite=True,
        )
        if status != "generated":
            raise ValueError(f"Could not generate action artifacts for {season_code}/{game_code}")
        generated = True

    validation = validate_action_artifacts(
        json_path,
        triples_path,
        season_code,
        game_code,
    )
    if not validation.ok:
        raise ValueError(
            "Generated action artifacts failed validation: " + "; ".join(validation.errors[:5])
        )
    print(
        f"  -> Action artifacts valid: {validation.actions} actions, {validation.triples} triples."
    )
    return load_actions(json_path, game_uri(season_code, game_code)), generated


def generate_game_triplets(
    game: dict[str, object],
    observations: list[OCRObservation],
    actions: list[PlayByPlayAction],
) -> tuple[list[str], int, int, int]:
    season_code = str(game["season_code"]).strip()
    game_code = str(game["game_code"]).strip()
    current_game_uri = game_uri(season_code, game_code)
    video_uri = f"{current_game_uri}#BroadcastVideo"
    youtube_url = str(game.get("youtube_url", "")).strip()
    if not re.fullmatch(r"https?://[^\s<>]+", youtube_url):
        raise ValueError(f"Invalid youtube_url for {season_code}/{game_code}: {youtube_url!r}")
    observation_index = build_observation_index(observations)
    matches: list[tuple[PlayByPlayAction, OCRObservation]] = []
    unmatched_actions = 0
    for action in actions:
        observation, _difference = find_nearest_observation(
            observation_index,
            action.quarter,
            action.quarter_seconds_remaining,
            max_difference=synchronization_tolerance(action),
        )
        if observation is None:
            unmatched_actions += 1
        else:
            matches.append((action, observation))

    linked_uris = {observation.uri for _action, observation in matches}
    linked_observations = [
        observation for observation in observations if observation.uri in linked_uris
    ]

    bball = BASKETBALL_NS
    triples = [
        triple(current_game_uri, f"{bball}hasBroadcastVideo", iri(video_uri)),
        triple(video_uri, RDF_TYPE, iri(f"{bball}BroadcastVideo")),
        triple(
            video_uri,
            f"{bball}youtubeURL",
            iri(youtube_url),
        ),
        triple(
            video_uri,
            f"{bball}ocrProfile",
            literal(str(game.get("ocr_profile", ""))),
        ),
        triple(
            video_uri,
            f"{bball}playbackLeadSeconds",
            literal(
                decimal_text(float(game.get("playback_lead_seconds", 5))),
                f"{XSD_NS}decimal",
            ),
        ),
        triple(
            video_uri,
            f"{bball}isVideoEnabled",
            literal(
                "true" if game.get("enabled", True) else "false",
                f"{XSD_NS}boolean",
            ),
        ),
    ]

    for observation in linked_observations:
        triples.extend(
            [
                triple(video_uri, f"{bball}hasOCRObservation", iri(observation.uri)),
                triple(observation.uri, RDF_TYPE, iri(f"{bball}OCRObservation")),
                triple(
                    observation.uri,
                    f"{bball}ocrSequence",
                    literal(observation.sequence, f"{XSD_NS}integer"),
                ),
                triple(
                    observation.uri,
                    f"{bball}videoTimeSeconds",
                    literal(
                        decimal_text(observation.video_seconds),
                        f"{XSD_NS}decimal",
                    ),
                ),
                triple(
                    observation.uri,
                    f"{bball}ocrQuarter",
                    literal(observation.quarter),
                ),
                triple(
                    observation.uri,
                    f"{bball}ocrClock",
                    literal(observation.game_clock),
                ),
            ]
        )

    for action, observation in matches:
        triples.append(
            triple(
                action.uri,
                f"{bball}correspondsToOCRObservation",
                iri(observation.uri),
            )
        )
    return (
        triples,
        len(linked_observations),
        len(matches),
        unmatched_actions,
    )


def process_game(
    game: dict[str, object],
    output_dir: Path,
    all_actions_dir: Path,
    triplets_dir: Path,
    api_session: object,
    overwrite: bool = False,
    refresh_actions: bool = False,
) -> tuple[str, int, int, int, bool]:
    season_code = str(game.get("season_code", "")).strip()
    game_code = str(game.get("game_code", "")).strip()
    timeline_path = Path(str(game.get("timeline_file", ""))).expanduser()
    if not timeline_path.is_absolute():
        timeline_path = REPO_ROOT / timeline_path
    output_path = output_dir / f"OCRTriplets_{season_code}_{game_code}.nt"
    actions, actions_generated = ensure_action_artifacts(
        game,
        all_actions_dir,
        triplets_dir,
        api_session,
        refresh=refresh_actions,
    )
    if output_path.exists() and not overwrite and not actions_generated:
        print(f"  -> {output_path.name} already exists; skipping.")
        return "skipped", 0, 0, 0, False
    if not timeline_path.exists():
        print(f"  -> Timeline does not exist: {timeline_path}")
        return "unavailable", 0, 0, 0, actions_generated

    current_video_uri = f"{game_uri(season_code, game_code)}#BroadcastVideo"
    observations = load_observations(timeline_path, current_video_uri)
    triples, linked_observations, matched, unmatched = generate_game_triplets(
        game,
        observations,
        actions,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(triples))
        handle.write("\n")

    print(
        f"  -> Saved {linked_observations} linked OCR observations "
        f"from {len(observations)} CSV rows and {len(triples)} triples to "
        f"{output_path}, {matched} actions synchronized and "
        f"{unmatched} unmatched."
    )
    return "generated", linked_observations, matched, unmatched, actions_generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate RDF N-Triples from video catalog metadata and OCR timeline "
            "CSVs for one game or every catalog game in a season."
        )
    )
    parser.add_argument("season_code", help="Season code, for example E2023")
    parser.add_argument(
        "game_code",
        nargs="?",
        help="Optional game code. Omit it to process all catalog games in the season.",
    )
    parser.add_argument(
        "--catalog-file",
        type=Path,
        default=DEFAULT_CATALOG_FILE,
        help="Video game catalog JSON path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OCR_OUTPUT_DIR,
        help="Destination directory for OCRTriplets_*.nt files.",
    )
    parser.add_argument(
        "--all-actions-dir",
        type=Path,
        default=DEFAULT_ALL_ACTIONS_DIR,
        help="Directory containing generated AllActions JSON files.",
    )
    parser.add_argument(
        "--playbyplay-triplets-dir",
        type=Path,
        default=DEFAULT_PLAYBYPLAY_TRIPLETS_DIR,
        help="Directory containing generated Play-by-Play N-Triples files.",
    )
    parser.add_argument(
        "--refresh-actions",
        action="store_true",
        help="Regenerate Play-by-Play JSON and N-Triples from the EuroLeague API.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing OCR triples file.",
    )
    args = parser.parse_args(argv)
    try:
        season_label_from_code(args.season_code)
        games = load_selected_games(
            args.catalog_file,
            args.season_code,
            args.game_code,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    generated = skipped = unavailable = failed = 0
    api_session = create_api_session()
    print(f"Generating OCR triples for {args.season_code}: {len(games)} catalog game(s)...")
    for index, game in enumerate(games, start=1):
        game_code = str(game.get("game_code", ""))
        print(f"\n[{index}/{len(games)}] Game {game_code}")
        try:
            status, _observations, _matched, _unmatched, actions_generated = process_game(
                game,
                args.output_dir,
                args.all_actions_dir,
                args.playbyplay_triplets_dir,
                api_session,
                overwrite=args.overwrite,
                refresh_actions=args.refresh_actions,
            )
            if status == "generated":
                generated += 1
            elif status == "skipped":
                skipped += 1
            else:
                unavailable += 1
            if actions_generated and index < len(games):
                time.sleep(random.uniform(2.5, 4.5))
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            requests.RequestException,
        ) as exc:
            failed += 1
            print(f"  -> Failed: {exc}")

    print(
        "\nOCR triple generation complete: "
        f"{generated} generated, {skipped} skipped, "
        f"{unavailable} unavailable, {failed} failed."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
