"""Serve CourtLens analysis, synchronized video and basketball game APIs."""

import asyncio
import csv
import json
import math
import os
import random
import re
import threading
import time
from bisect import bisect_left
from collections import OrderedDict, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Literal

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from database import query_sparql_requests
from prompts import AI_SEARCH_PROMPTS
from queries import (
    AnalysisFilterError,
    get_clutch_time_performers_query,
    get_defensive_anchors_query,
    get_fast_break_specialists_query,
    get_filtered_player_query,
    get_filtered_shots_query,
    get_foul_drawn_gravity_query,
    get_game_lineups_query,
    get_game_roster_query,
    get_games_list_query,
    get_match_playbyplay_query,
    get_play_context_query,
    get_player_name_query,
    get_points_off_turnovers_query,
    get_second_chance_points_query,
    get_simulator_crunch_time_query,
    get_team_roster_query,
    get_timeouts_query,
    get_top_assist_duos_query,
    get_top_lineups_query,
)
from quiz_support import game_stage, missing_lineup, quiz_player_profile
from search_answers import (
    ANSWER_PROMPT,
    action_answer,
    evidence_for_answer,
    profile_answer,
    profile_query,
    profile_subject,
)
from search_validation import bounded_editor_query, unsupported_shot_style, validate_read_only

REPO_ROOT = Path(__file__).resolve().parents[2]
VIDEO_CATALOG_PATH = REPO_ROOT / "src" / "data_pipeline" / "video_games.json"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://euroleague-project.vercel.app",
    ).split(",")
    if origin.strip()
]
SPARQL_CACHE_TTL_SECONDS = max(0, int(os.getenv("SPARQL_CACHE_TTL_SECONDS", "300")))
SPARQL_CACHE_MAX_ENTRIES = 256
_sparql_cache = OrderedDict()
_sparql_cache_lock = threading.Lock()
AI_SEARCH_CACHE_TTL_SECONDS = max(0, int(os.getenv("AI_SEARCH_CACHE_TTL_SECONDS", "600")))
AI_SEARCH_CACHE_MAX_ENTRIES = 128
_ai_search_cache = OrderedDict()
_ai_search_cache_lock = threading.Lock()


@lru_cache(maxsize=8)
def _load_video_catalog(catalog_mtime_ns):
    """Cache the catalog until its file modification time changes."""
    try:
        with VIDEO_CATALOG_PATH.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        games = payload.get("games", []) if isinstance(payload, dict) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"Attention: Could not load video catalog {VIDEO_CATALOG_PATH}: {exc}")
        return {}

    catalog = {}
    for game in games:
        if not isinstance(game, dict):
            continue
        season_code = str(game.get("season_code", "")).strip()
        game_code = str(game.get("game_code", "")).strip()
        if season_code and game_code and game.get("enabled", True):
            catalog[(season_code, game_code)] = game
    return catalog


def load_video_catalog():
    try:
        catalog_mtime_ns = VIDEO_CATALOG_PATH.stat().st_mtime_ns
    except OSError:
        catalog_mtime_ns = 0
    return _load_video_catalog(catalog_mtime_ns)


def get_video_game_config(season_code, game_code):
    if not season_code or not game_code:
        return None
    return load_video_catalog().get((str(season_code).strip(), str(game_code).strip()))


def resolve_timeline_path(timeline_file):
    if not timeline_file:
        return None
    path = Path(str(timeline_file)).expanduser()
    path = path if path.is_absolute() else REPO_ROOT / path
    try:
        resolved = path.resolve()
        resolved.relative_to(REPO_ROOT)
    except (OSError, ValueError):
        return None
    return resolved


@lru_cache(maxsize=64)
def _load_video_timeline(path_string, timeline_mtime_ns):
    """Cache parsed rows until the timeline file changes."""
    path = Path(path_string)
    timeline = []
    try:
        with path.open(mode="r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                timeline.append(
                    {
                        "video_sec": float(row["video_time_sec"]),
                        "clock": row["game_clock"].strip(),
                        "quarter": row["quarter"].strip(),
                    }
                )
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f"Attention: Could not load video timeline {path}: {exc}")
        return ()
    return tuple(timeline)


def load_video_timeline(timeline_file):
    path = resolve_timeline_path(timeline_file)
    if path is None or not path.exists():
        return ()
    try:
        timeline_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return ()
    return _load_video_timeline(str(path), timeline_mtime_ns)


def normalize_quarter(value):
    """Return the canonical period label shared by OCR and play-by-play data."""
    normalized = re.sub(r"\s+", "", str(value or "").upper())
    regular_quarters = {"1ST": "1st", "2ND": "2nd", "3RD": "3rd", "4TH": "4th"}
    if normalized in regular_quarters:
        return regular_quarters[normalized]
    if normalized in {"OT", "1OT", "OT1"}:
        return "OT"

    overtime_match = re.fullmatch(r"(?:(\d+)OT|OT(\d+))", normalized)
    if overtime_match:
        overtime_number = int(overtime_match.group(1) or overtime_match.group(2))
        return "OT" if overtime_number <= 1 else f"{overtime_number}OT"
    return str(value or "").strip()


@lru_cache(maxsize=64)
def _load_video_timeline_index(path_string, timeline_mtime_ns):
    """Index one timeline by canonical quarter and clock for fast nearest lookup."""
    indexed_entries = defaultdict(dict)
    for entry in _load_video_timeline(path_string, timeline_mtime_ns):
        clock_seconds = time_to_seconds(entry["clock"])
        if clock_seconds is None:
            continue
        quarter = normalize_quarter(entry["quarter"])
        # Preserve the first OCR observation for a clock so playback starts at
        # the beginning of the play rather than at the end of a stopped clock.
        indexed_entries[quarter].setdefault(clock_seconds, entry["video_sec"])

    timeline_index = {}
    for quarter, entries in indexed_entries.items():
        sorted_entries = sorted(entries.items())
        timeline_index[quarter] = (
            tuple(clock for clock, _video_seconds in sorted_entries),
            tuple(video_seconds for _clock, video_seconds in sorted_entries),
        )
    return timeline_index


def load_video_timeline_index(timeline_file):
    path = resolve_timeline_path(timeline_file)
    if path is None or not path.exists():
        return {}
    try:
        timeline_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return {}
    return _load_video_timeline_index(str(path), timeline_mtime_ns)


def _query_sparql_cached(sparql_query):
    now = time.monotonic()
    with _sparql_cache_lock:
        cached = _sparql_cache.get(sparql_query)
        if cached and now - cached[0] <= SPARQL_CACHE_TTL_SECONDS:
            _sparql_cache.move_to_end(sparql_query)
            return cached[1]
        if cached:
            _sparql_cache.pop(sparql_query, None)

    data = query_sparql_requests(sparql_query)
    if data is None or SPARQL_CACHE_TTL_SECONDS == 0:
        return data

    with _sparql_cache_lock:
        _sparql_cache[sparql_query] = (time.monotonic(), data)
        _sparql_cache.move_to_end(sparql_query)
        while len(_sparql_cache) > SPARQL_CACHE_MAX_ENTRIES:
            _sparql_cache.popitem(last=False)
    return data


async def query_sparql(sparql_query, *, use_cache=True):
    """Run the blocking SPARQL client away from FastAPI's event loop."""
    query_function = _query_sparql_cached if use_cache else query_sparql_requests
    return await asyncio.to_thread(query_function, sparql_query)


app = FastAPI(title="CourtLens API")


@app.exception_handler(AnalysisFilterError)
async def invalid_analysis_filter(_request, error):
    return JSONResponse(status_code=422, content={"detail": str(error)})


async def analysis_data(query):
    data = await query_sparql(query)
    if data is None:
        raise HTTPException(
            status_code=502,
            detail="The basketball database did not respond. Please retry your analysis.",
        )
    return data


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/video/config")
async def get_video_config(
    season_code: str = Query(...),
    game_code: str = Query(...),
):
    game_config = get_video_game_config(season_code, game_code)
    if not game_config:
        return {
            "available": False,
            "timeline_available": False,
            "season_code": season_code,
            "game_code": game_code,
        }

    timeline = load_video_timeline(str(game_config.get("timeline_file", "")))
    return {
        "available": bool(game_config.get("youtube_id")),
        "timeline_available": bool(timeline),
        "season_code": season_code,
        "game_code": game_code,
        "youtube_id": game_config.get("youtube_id"),
        "ocr_profile": game_config.get("ocr_profile"),
        "playback_lead_seconds": max(
            0, min(15, float(game_config.get("playback_lead_seconds", 5)))
        ),
    }


@app.get("/api/video/games")
async def get_available_video_games(season_code: str = Query(None)):
    games = []
    for (catalog_season, catalog_game), game_config in load_video_catalog().items():
        if season_code and catalog_season != season_code:
            continue
        timeline = load_video_timeline(str(game_config.get("timeline_file", "")))
        if not game_config.get("youtube_id") or not timeline:
            continue
        games.append(
            {
                "season_code": catalog_season,
                "game_code": catalog_game,
                "youtube_id": game_config.get("youtube_id"),
                "ocr_profile": game_config.get("ocr_profile"),
            }
        )

    games.sort(key=lambda game: (game["season_code"], int(game["game_code"])))
    return {
        "seasons": sorted({game["season_code"] for game in games}),
        "games": games,
    }


def time_to_seconds(t_str):
    """Parse minute-second or decimal clocks; return None for missing or invalid input."""
    if not t_str:
        return None
    try:
        if ":" in t_str:
            m, s = map(int, t_str.split(":"))
            return m * 60 + s
        elif "." in t_str:
            return float(t_str)
    except ValueError:
        return None


def get_bool(result, field, default=False):
    value = result.get(field, {}).get("value")
    if value is None:
        return default

    return value in ("1", "true", "True")


def find_video_seconds(play_time, quarter, season_code, game_code, action_type=None):
    target_sec = time_to_seconds(play_time)
    if target_sec is None or not quarter:
        return 0

    game_config = get_video_game_config(season_code, game_code)
    if not game_config:
        return 0
    timeline_index = load_video_timeline_index(str(game_config.get("timeline_file", "")))
    quarter_index = timeline_index.get(normalize_quarter(quarter))
    if not quarter_index:
        return 0

    clock_values, video_values = quarter_index
    insertion_index = bisect_left(clock_values, target_sec)
    candidate_indexes = []
    if insertion_index < len(clock_values):
        candidate_indexes.append(insertion_index)
    if insertion_index > 0:
        candidate_indexes.append(insertion_index - 1)

    closest_index = min(
        candidate_indexes,
        key=lambda index: (abs(clock_values[index] - target_sec), -clock_values[index]),
    )
    normalized_quarter = normalize_quarter(quarter)
    period_seconds = 600 if normalized_quarter in {"1st", "2nd", "3rd", "4th"} else 300
    action_name = str(action_type or "")
    is_opening_metadata = (
        action_name in {"PeriodStart", "PlayerIn", "PlayerOut"}
        and abs(target_sec - period_seconds) < 0.001
    )
    elapsed_seconds = period_seconds - target_sec
    is_opening_jump_ball = action_name == "JumpBall" and 0 <= elapsed_seconds <= 1
    tolerance = 12 if is_opening_metadata or is_opening_jump_ball else 5
    return (
        video_values[closest_index]
        if abs(clock_values[closest_index] - target_sec) <= tolerance
        else 0
    )


def video_sync_clock_for_action(action_type, row, play_time, quarter):
    """Use the event that happened on screen, not a delayed PBP annotation.

    EuroLeague records an Assist as a separate action shortly after the scoring
    play. That play already links to the Assist through ``hasAssist``, so its
    clock is a more accurate video anchor for showing the pass. This includes
    FIBA assists awarded after at least one resulting free throw is made.
    """
    if str(action_type) == "Assist":
        shot_clock = row.get("relatedShotClock", {}).get("value", "")
        shot_quarter = normalize_quarter(row.get("relatedShotQuarter", {}).get("value", ""))
        if time_to_seconds(shot_clock) is not None and shot_quarter:
            return shot_clock, shot_quarter
    return play_time, quarter


def playback_lead_for_action(game_config, action_type):
    """Return a contextual lead without changing the synchronized timestamp."""
    base_lead = max(0, min(15, float((game_config or {}).get("playback_lead_seconds", 5))))
    if str(action_type) != "Assist":
        return base_lead
    return max(
        base_lead,
        max(
            0,
            min(
                15,
                float((game_config or {}).get("assist_playback_lead_seconds", 9)),
            ),
        ),
    )


# Player, game and video endpoints.


@app.get("/api/player/{player_id}")
async def get_player_name(player_id: str):
    # A full name is already resolved; only IDs need a database lookup.

    if " " in player_id:
        return {"id": player_id, "name": player_id}

    query = get_player_name_query(player_id)
    data = await query_sparql(query)

    name = player_id

    # Keep the ID as a fallback when the data source is unavailable.
    if data and isinstance(data, dict):
        bindings = data.get("results", {}).get("bindings", [])
        if bindings:
            name = bindings[0].get("name", {}).get("value", name)

    return {"id": player_id, "name": name}


@app.get("/api/shots")
async def get_shots(
    game_code: str = Query(None),
    season_code: str = Query(None),
    player: str = Query(None),
    assist_by: str = Query(None),
    lineup_uri: str = Query(None),
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
):
    sparql_query = get_filtered_shots_query(
        game_code=game_code,
        season_code=season_code,
        player_id=player,
        assist_by_id=assist_by,
        filter_type=filter_type,
        filter_id=filter_id,
        quarter=quarter,
        min_start=min_start,
        min_end=min_end,
        lineup_uri=lineup_uri,
    )
    data = await analysis_data(sparql_query)

    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "shots": []}

    shots = []
    bindings = data.get("results", {}).get("bindings", [])

    for result in bindings:
        raw_coords = result.get("coords", {}).get("value", "")
        try:
            x, y = map(float, raw_coords.split(","))
            if not all(math.isfinite(v) for v in (x, y)):
                x, y = -1, -1
        except (ValueError, TypeError):
            x, y = -1, -1
        action_type_full = result.get("action_type", {}).get("value", "")
        action_type = action_type_full.split("#")[-1]

        home_lineup = result.get("home_lineup", {}).get("value", "Unknown lineup")
        road_lineup = result.get("road_lineup", {}).get("value", "Unknown lineup")

        play_time = result.get("clockTime", {}).get("value", "")
        quarter_val = normalize_quarter(result.get("quarter", {}).get("value", ""))
        player_name = result.get("playerName", {}).get("value", "Unknown player")
        player_img = result.get("playerImg", {}).get("value", "")
        fast_break = get_bool(result, "isFastBreak")
        second_chance = get_bool(result, "isSecondChance")
        from_turnover = get_bool(result, "isFromTurnover")
        home_score = result.get("homeScore", {}).get("value", "0")
        road_score = result.get("roadScore", {}).get("value", "0")
        video_seconds = find_video_seconds(play_time, quarter_val, season_code, game_code)

        shots.append(
            {
                "action_uri": result.get("action", {}).get("value", ""),
                "action_type": action_type,
                "x": float(x),
                "y": float(y),
                "isMade": "Made" in action_type,
                "isFastBreak": fast_break,
                "isSecondChance": second_chance,
                "isFromTurnover": from_turnover,
                "runningHomeTeamLineup": home_lineup,
                "runningRoadTeamLineup": road_lineup,
                "playTime": play_time,
                "quarter": quarter_val,
                "homeScore": int(home_score) if home_score.isdigit() else 0,
                "roadScore": int(road_score) if road_score.isdigit() else 0,
                "videoSeconds": video_seconds,
                "playerName": player_name,
                "playerImg": player_img if player_img else None,
                "teamType": result.get("teamType", {}).get("value", ""),
            }
        )

    return {"shots": shots}


@app.get("/api/player")
async def get_player(player: str = Query(None)):
    sparql_query = get_filtered_player_query(player)
    data = await analysis_data(sparql_query)

    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "player": {}}

    bindings = data.get("results", {}).get("bindings", [])

    if not bindings:
        return {"player": {}}

    raw_player = bindings[0]

    clean_player = {}
    for key, field_data in raw_player.items():
        if isinstance(field_data, dict) and "value" in field_data:
            val = field_data["value"]
            if key == "country" and "/" in val:
                val = val.split("/")[-1]
            clean_player[key] = val
        else:
            clean_player[key] = None

    return {"player": clean_player}


@app.get("/api/match/playbyplay")
async def get_match_pbp(game_code: str = Query(...), season_code: str = Query(...)):
    sparql_query = get_match_playbyplay_query(game_code, season_code)
    data = await analysis_data(sparql_query)

    if not data:
        return {"error": "Failed to fetch play-by-play", "actions": []}

    actions = []
    game_config = get_video_game_config(season_code, game_code)
    for row in data.get("results", {}).get("bindings", []):
        action_type_uri = row.get("actionType", {}).get("value", "")
        action_type_name = action_type_uri.split("#")[-1]
        play_time = row.get("clock", {}).get("value", "")
        quarter = normalize_quarter(row.get("quarter", {}).get("value", ""))
        home_score = row.get("homeScore", {}).get("value", "0")
        road_score = row.get("roadScore", {}).get("value", "0")
        sync_clock, sync_quarter = video_sync_clock_for_action(
            action_type_name, row, play_time, quarter
        )

        actions.append(
            {
                "uri": row.get("action", {}).get("value", ""),
                "action_type": action_type_name,
                "playTime": play_time,
                "quarter": quarter,
                "sequence": int(row.get("sequence", {}).get("value", "0") or 0),
                "teamType": row.get("teamType", {}).get("value", "neutral"),
                "homeScore": int(home_score) if home_score.isdigit() else 0,
                "roadScore": int(road_score) if road_score.isdigit() else 0,
                "playerName": row.get("playerLabel", {}).get("value", ""),
                "homeLineup": row.get("homeLineup", {}).get("value"),
                "roadLineup": row.get("roadLineup", {}).get("value"),
                "isMade": "Made" in action_type_name,
                "isFastBreak": get_bool(row, "isFastBreak"),
                "isSecondChance": get_bool(row, "isSecondChance"),
                "isFromTurnover": get_bool(row, "isFromTurnover"),
                "videoSeconds": find_video_seconds(
                    sync_clock,
                    sync_quarter,
                    season_code,
                    game_code,
                    action_type=action_type_name,
                ),
                "playbackLeadSeconds": playback_lead_for_action(game_config, action_type_name),
            }
        )

    return {"actions": actions}


@app.get("/api/play/context")
async def get_play_context(action_uri: str = Query(...)):
    sparql_query = get_play_context_query(action_uri)
    data = await analysis_data(sparql_query)

    if not data:
        return {"error": "Failed to fetch play context"}

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return {"avgHeight": None, "playersOnCourt": ""}

    row = bindings[0]
    avg_height = row.get("avgHeight", {}).get("value", None)
    players = row.get("playersOnCourt", {}).get("value", "")

    return {
        "avgHeight": round(float(avg_height), 2) if avg_height else None,
        "playersOnCourt": players,
    }


@app.get("/api/teams")
async def get_teams():
    query = """PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    SELECT ?team ?name (SAMPLE(?image) AS ?logo) WHERE {
        ?team a bball:Team ; rdfs:label ?name .
        OPTIONAL { ?team foaf:depiction ?image . }
    } GROUP BY ?team ?name ORDER BY ?name"""
    data = await analysis_data(query)
    teams = []
    for row in data.get("results", {}).get("bindings", []):
        uri = row.get("team", {}).get("value", "")
        logo = row.get("logo", {}).get("value", "")
        teams.append(
            {
                "id": uri.rstrip("/").split("/")[-1],
                "name": row.get("name", {}).get("value", ""),
                "logo": logo if logo.startswith(("https://", "http://")) else None,
            }
        )
    return {"teams": teams}


@app.get("/api/games")
async def get_games(season_code: str = Query(...)):
    sparql_query = get_games_list_query(season_code)
    data = await analysis_data(sparql_query)

    if not data:
        return {"games": []}

    games = []
    for row in data.get("results", {}).get("bindings", []):
        home_label = row.get("homeLabel", {}).get("value", "")
        away_label = row.get("awayLabel", {}).get("value", "")
        games.append(
            {
                "gameCode": row.get("gameCode", {}).get("value", ""),
                "matchup": f"{home_label} vs {away_label}",
                "stage": game_stage(row),
                "round": row.get("round", {}).get("value", ""),
            }
        )

    return {"games": games}


@app.get("/api/game/lineups")
async def get_game_lineups(game_code: str = Query(...), season_code: str = Query(...)):
    sparql_query = get_game_lineups_query(game_code, season_code)
    data = await analysis_data(sparql_query)

    if not data:
        return {"error": "Failed to fetch lineups", "lineups": []}

    lineups = []
    homeScore = roadScore = ""
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        lineup_uri = row.get("lineup", {}).get("value", "")
        team_type = row.get("teamType", {}).get("value", "")
        players_str = row.get("players", {}).get("value", "")
        homeScore = row.get("homeScore", {}).get("value", "")
        roadScore = row.get("roadScore", {}).get("value", "")
        lineups.append({"uri": lineup_uri, "teamType": team_type, "players": players_str})

    return {"homeScore": homeScore, "roadScore": roadScore, "lineups": lineups}


# Statistical reports and coach simulation.


@app.get("/api/analytics/assist-duos")
async def get_assist_duos(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None),
):
    query = get_top_assist_duos_query(
        filter_type, filter_id, quarter, min_start, min_end, game_code, season_code
    )
    data = await analysis_data(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        scorer_id = row.get("scorer", {}).get("value", "").split("/")[-1]
        passer_id = row.get("passer", {}).get("value", "").split("/")[-1]

        results.append(
            {
                "scorer_id": scorer_id,
                "passer_id": passer_id,
                "total_assists": int(row.get("totalAssists", {}).get("value", 0)),
            }
        )

    return {"assist_duos": results}


@app.get("/api/analytics/second-chance")
async def get_second_chance(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None),
    player_id: str = Query(None),
):
    query = get_second_chance_points_query(
        filter_type, filter_id, quarter, min_start, min_end, game_code, season_code, player_id
    )
    data = await analysis_data(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append(
            {
                "player_id": player_id,
                "total_points": int(row.get("totalSecondChancePoints", {}).get("value", 0)),
            }
        )

    return {"second_chance_points": results}


@app.get("/api/analytics/lineups")
async def get_top_lineups(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None),
):
    query = get_top_lineups_query(
        filter_type, filter_id, quarter, min_start, min_end, game_code, season_code
    )
    data = await analysis_data(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        lineup_url = row.get("lineup", {}).get("value", "")
        if "#Lineup_" in lineup_url:
            lineup_ids = lineup_url.split("#Lineup_")[1].split("_")
        else:
            lineup_ids = []

        results.append(
            {
                "lineup_url": lineup_url,
                "players": lineup_ids,
                "total_points": int(row.get("totalPoints", {}).get("value", 0)),
            }
        )

    return {"top_lineups": results}


@app.get("/api/analytics/fouls-drawn")
async def get_fouls_drawn(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    fouled_id: str = Query(None),
    fouling_id: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None),
):
    query = get_foul_drawn_gravity_query(
        filter_type,
        filter_id,
        quarter,
        min_start,
        min_end,
        fouled_id,
        fouling_id,
        game_code,
        season_code,
    )
    data = await analysis_data(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]
        results.append(
            {
                "player_id": player_id,
                "total_fouls_drawn": int(row.get("totalFoulsDrawn", {}).get("value", 0)),
            }
        )

    return {"fouls_drawn": results}


@app.get("/api/analytics/defensive-anchors")
async def get_defensive_anchors(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    shooter_id: str = Query(None),
    blocker_id: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None),
):
    query = get_defensive_anchors_query(
        filter_type,
        filter_id,
        quarter,
        min_start,
        min_end,
        shooter_id,
        blocker_id,
        game_code,
        season_code,
    )
    data = await analysis_data(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]
        results.append(
            {
                "player_id": player_id,
                "total_blocks": int(row.get("totalBlocks", {}).get("value", 0)),
            }
        )

    return {"defensive_anchors": results}


@app.get("/api/analytics/clutch-performers")
async def get_clutch_performers():
    query = get_clutch_time_performers_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append(
            {
                "player_id": player_id,
                "clutch_points": int(row.get("clutchPoints", {}).get("value", 0)),
                "clutch_actions": int(row.get("clutchActions", {}).get("value", 0)),
            }
        )

    return {"clutch_performers": results}


@app.get("/api/analytics/points-off-turnovers")
async def get_points_off_turnovers():
    query = get_points_off_turnovers_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        team_url = row.get("team", {}).get("value", "")
        team_code = team_url.split("/")[-1] if team_url else "Unknown"

        results.append(
            {
                "team": team_code,
                "points_off_turnovers": int(row.get("pointsOffTurnovers", {}).get("value", 0)),
            }
        )

    return {"points_off_turnovers": results}


@app.get("/api/analytics/fast-break")
async def get_fast_break_specialists():
    query = get_fast_break_specialists_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append(
            {
                "player_id": player_id,
                "fast_break_points": int(row.get("fastBreakPoints", {}).get("value", 0)),
                "total_attempts": int(row.get("totalAttempts", {}).get("value", 0)),
            }
        )

    return {"fast_break_specialists": results}


@app.get("/api/simulator/crunch-time")
async def run_simulator(
    p1: str = Query(...),
    p2: str = Query(...),
    p3: str = Query(...),
    p4: str = Query(...),
    p5: str = Query(...),
    game_code: str = Query(None),
    quarter: str = Query(None),
    season_code: str = Query(None),
):
    query = get_simulator_crunch_time_query(game_code, quarter, [p1, p2, p3, p4, p5], season_code)
    data = await query_sparql(query)

    if not data:
        return {"error": "Failed to fetch data"}

    bindings = data.get("results", {}).get("bindings", [])

    if not bindings:
        return {"error": "Lineup never played"}

    points_for = 0
    points_against = 0

    for row in bindings:
        action_team = row.get("actionTeam", {}).get("value", "")
        lineup_team = row.get("lineupTeam", {}).get("value", "")
        points = int(row.get("totalPoints", {}).get("value", 0))

        # Attribute each score to our lineup or its opponent.
        if action_team == lineup_team:
            points_for += points
        else:
            points_against += points

    plus_minus = points_for - points_against

    return {"points_for": points_for, "points_against": points_against, "plus_minus": plus_minus}


@app.get("/api/game/roster")
async def get_game_roster(game_code: str = Query(...)):
    query = get_game_roster_query(game_code)
    data = await query_sparql(query)

    # The data source can return no result after a timeout.
    if not data:
        return {"roster": []}

    player_ids = set()
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        home_uri = row.get("homeLineup", {}).get("value", "")
        road_uri = row.get("roadLineup", {}).get("value", "")

        for uri in [home_uri, road_uri]:
            if "#Lineup_" in uri:
                parts = uri.split("#Lineup_")[1].split("_")
                for pid in parts:
                    if pid:
                        player_ids.add(pid)

    roster = [{"id": pid, "name": "Loading…"} for pid in player_ids]
    return {"roster": roster}


@app.get("/api/simulator/scenario")
async def get_simulator_scenario(season_code: str = Query(...)):
    query = get_timeouts_query(season_code)
    data = await query_sparql(query)

    bindings = data.get("results", {}).get("bindings", []) if data else []
    if not bindings:
        return {"error": "No scenarios found"}

    random_timeout = random.choice(bindings)

    game_uri = random_timeout.get("game", {}).get("value", "")
    game_code = game_uri.split("/")[-1]
    game_season_name = game_uri.split("/")[-4] if len(game_uri.split("/")) > 4 else "Unknown season"
    clock = random_timeout.get("clock", {}).get("value", "00:00")
    home_score = random_timeout.get("homeScore", {}).get("value", "0")
    road_score = random_timeout.get("roadScore", {}).get("value", "0")

    home_lineup = random_timeout.get("homeLineup", {}).get("value", "")
    road_lineup = random_timeout.get("roadLineup", {}).get("value", "")

    home_team = (
        home_lineup.split("teams/-/")[1].split("#")[0] if "teams/-/" in home_lineup else "Home"
    )
    road_team = (
        road_lineup.split("teams/-/")[1].split("#")[0] if "teams/-/" in road_lineup else "Road"
    )

    # Coach the trailing team, or choose either team when the scores are tied.
    h_score_int = int(home_score)
    r_score_int = int(road_score)

    if h_score_int < r_score_int:
        is_home = True
    elif r_score_int < h_score_int:
        is_home = False
    else:
        is_home = random.choice([True, False])

    user_team = home_team if is_home else road_team
    opponent = road_team if is_home else home_team
    user_score = home_score if is_home else road_score
    opp_score = road_score if is_home else home_score

    # Limit available players to this team and game.
    roster_query = get_team_roster_query(game_code, user_team, season_code)
    roster_data = await query_sparql(roster_query)

    player_ids = set()
    roster_bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
    for r in roster_bindings:
        lineup_uri = r.get("lineup", {}).get("value", "")
        if "#Lineup_" in lineup_uri:
            parts = lineup_uri.split("#Lineup_")[1].split("_")
            for pid in parts:
                if pid:
                    player_ids.add(pid)

    roster = [{"id": pid} for pid in player_ids]

    return {
        "game_code": game_code,
        "game_season_name": game_season_name,
        "user_team": user_team,
        "opponent": opponent,
        "user_team_name": random_timeout.get("homeLabel" if is_home else "awayLabel", {}).get(
            "value", user_team
        ),
        "opponent_name": random_timeout.get("awayLabel" if is_home else "homeLabel", {}).get(
            "value", opponent
        ),
        "user_score": user_score,
        "opp_score": opp_score,
        "clock": clock,
        "roster": roster,
    }


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_SEARCH_PROVIDER = os.getenv("AI_SEARCH_PROVIDER", "openai").strip().lower()
AI_SEARCH_PROMPT_VARIANT = os.getenv("AI_SEARCH_PROMPT_VARIANT", "ontology").strip().lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
OPENAI_MODEL = "gpt-5-mini"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_TIMEOUT_SECONDS = max(1, int(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")))
OPENAI_MAX_OUTPUT_TOKENS = max(1000, int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000")))

# The backend can still start without Gemini configured; /api/chat reports a clear 503 instead.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def extract_openai_output_text(payload: dict) -> str:
    """Extract assistant text from a raw Responses API payload."""
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    parts = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict) or content.get("type") != "output_text":
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    result = "\n".join(parts).strip()
    if not result:
        incomplete_details = payload.get("incomplete_details") or {}
        usage = payload.get("usage") or {}
        output_details = usage.get("output_tokens_details") or {}
        raise ValueError(
            "The OpenAI Responses API did not return text "
            f"(status={payload.get('status', 'unknown')}, "
            f"reason={incomplete_details.get('reason', 'unknown')}, "
            f"output_tokens={usage.get('output_tokens', 'unknown')}, "
            "reasoning_tokens="
            f"{output_details.get('reasoning_tokens', 'unknown')})."
        )
    return result


def _non_negative_int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def extract_openai_usage(payload: dict) -> dict[str, int]:
    """Normalize Responses API usage without changing the public frontend payload."""
    usage = payload.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    input_tokens = _non_negative_int(usage.get("input_tokens"))
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": min(
            input_tokens, _non_negative_int(input_details.get("cached_tokens"))
        ),
        "output_tokens": output_tokens,
        "reasoning_tokens": min(
            output_tokens, _non_negative_int(output_details.get("reasoning_tokens"))
        ),
        "total_tokens": _non_negative_int(usage.get("total_tokens", input_tokens + output_tokens)),
    }


def extract_gemini_usage(response) -> dict[str, int]:
    """Normalize Gemini usage; output includes visible candidates and thoughts."""
    usage = getattr(response, "usage_metadata", None)
    input_tokens = _non_negative_int(getattr(usage, "prompt_token_count", 0))
    cached_input_tokens = min(
        input_tokens,
        _non_negative_int(getattr(usage, "cached_content_token_count", 0)),
    )
    visible_output_tokens = _non_negative_int(getattr(usage, "candidates_token_count", 0))
    reasoning_tokens = _non_negative_int(getattr(usage, "thoughts_token_count", 0))
    output_tokens = visible_output_tokens + reasoning_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": _non_negative_int(
            getattr(usage, "total_token_count", input_tokens + output_tokens)
        ),
    }


def request_openai_text(message: str, system_prompt: str, model: str) -> tuple[str, dict[str, int]]:
    response = requests.post(
        f"{OPENAI_BASE_URL}/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "instructions": system_prompt,
            "input": message,
            # SPARQL generation needs only a short final answer. Keeping reasoning
            # minimal prevents GPT-5 mini from spending the whole output budget
            # on hidden reasoning before emitting the query.
            "reasoning": {"effort": "minimal"},
            "text": {"verbosity": "low"},
            "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "store": False,
        },
        timeout=OPENAI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return extract_openai_output_text(payload), extract_openai_usage(payload)


def ai_search_configuration(
    requested_provider: str | None,
    requested_prompt_variant: str | None,
    requested_openai_model: str | None,
) -> tuple[str, str, str]:
    provider = (requested_provider or AI_SEARCH_PROVIDER).strip().lower()
    prompt_variant = (requested_prompt_variant or AI_SEARCH_PROMPT_VARIANT).strip().lower()
    if provider not in {"gemini", "openai"}:
        raise ValueError("AI_SEARCH_PROVIDER must be 'gemini' or 'openai'.")
    if prompt_variant not in AI_SEARCH_PROMPTS:
        raise ValueError("AI_SEARCH_PROMPT_VARIANT must be 'simple' or 'ontology'.")
    if provider == "gemini":
        if requested_openai_model:
            raise ValueError("openai_model can only be used with the OpenAI provider.")
        if client is None:
            raise HTTPException(
                status_code=503,
                detail="Gemini AI Search is unavailable. Configure GEMINI_API_KEY on the server.",
            )
        return provider, prompt_variant, GEMINI_MODEL

    model = requested_openai_model or OPENAI_MODEL
    if model != OPENAI_MODEL:
        raise ValueError("openai_model must be 'gpt-5-mini'.")
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OpenAI Search is unavailable. Configure OPENAI_API_KEY on the server.",
        )
    return provider, prompt_variant, model


def available_ai_search_models() -> list[dict[str, str | bool]]:
    """Return only AI models whose provider key is configured."""
    models = []
    if OPENAI_API_KEY:
        models.append(
            {
                "provider": "openai",
                "model": OPENAI_MODEL,
                "label": "GPT-5 Mini",
                "is_default": AI_SEARCH_PROVIDER == "openai",
            }
        )
    if GEMINI_API_KEY and client is not None:
        models.append(
            {
                "provider": "gemini",
                "model": GEMINI_MODEL,
                "label": f"Gemini ({GEMINI_MODEL})",
                "is_default": AI_SEARCH_PROVIDER == "gemini",
            }
        )

    if models and not any(model["is_default"] for model in models):
        models[0]["is_default"] = True
    return models


@app.get("/api/chat/models")
async def ai_chat_models():
    """Expose configured model choices without exposing API keys."""
    return {"models": available_ai_search_models()}


async def generate_ai_search_text(
    provider: str,
    prompt_variant: str,
    model: str,
    message: str,
) -> tuple[str, dict[str, int]]:
    system_prompt = AI_SEARCH_PROMPTS[prompt_variant]
    if provider == "gemini":
        response = await client.aio.models.generate_content(
            model=model,
            contents=message,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return response.text, extract_gemini_usage(response)
    return await asyncio.to_thread(request_openai_text, message, system_prompt, model)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    game_code: str | None = Field(default=None, max_length=50, pattern=r"^[A-Za-z0-9_,\-]+$")
    season_code: str | None = Field(default=None, max_length=50, pattern=r"^[A-Za-z0-9_,\-]+$")
    provider: Literal["gemini", "openai"] | None = None
    prompt_variant: Literal["simple", "ontology"] | None = None
    openai_model: Literal["gpt-5-mini"] | None = None
    include_query: bool = False
    show_query: bool = False
    include_answer: bool = False
    workspace: Literal["explore", "video"] = "explore"


def ai_search_response(payload: dict, include_query: bool) -> dict:
    """Hide implementation details during normal frontend use."""
    if include_query:
        return payload
    response = dict(payload)
    response.pop("sparql_query", None)
    response.pop("ai_provider", None)
    response.pop("ai_model", None)
    response.pop("prompt_variant", None)
    response.pop("ai_usage", None)
    return response


def build_ai_scope_context(
    season_code: str | None,
    game_code: str | None,
) -> list[str]:
    """Describe only the filters that the user actually selected."""
    context = []
    scopes = (
        ("season", "seasonCode", season_code),
        ("game", "gameCode", game_code),
    )
    for label, variable, raw_value in scopes:
        values = [value.strip() for value in str(raw_value or "").split(",") if value.strip()]
        if not values:
            continue
        if len(values) == 1:
            context.append(
                f'Restrict the query to the selected {label} using bball:hasCode "{values[0]}".'
            )
            continue
        quoted_values = ", ".join(f'"{value}"' for value in values)
        context.append(
            f"Restrict the query to the selected {label} codes using "
            f"FILTER(?{variable} IN ({quoted_values}))."
        )
    return context


def clean_and_validate_sparql(raw_query: str) -> str:
    return validate_read_only(raw_query)


def query_selects_playbyplay_actions(query: str) -> bool:
    select_match = re.search(r"\bSELECT\b(.*?)\bWHERE\b", query, flags=re.IGNORECASE | re.DOTALL)
    if not select_match:
        return False

    select_clause = select_match.group(1)
    depth = 0
    top_level_variables = []
    index = 0
    while index < len(select_clause):
        character = select_clause[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        elif character == "?" and depth == 0:
            variable_match = re.match(r"\?([A-Za-z_][A-Za-z0-9_]*)", select_clause[index:])
            if variable_match:
                top_level_variables.append(variable_match.group(1).lower())
                index += len(variable_match.group(0)) - 1
        index += 1
    return "action" in top_level_variables


def extract_playbyplay_action_uris(results: list[dict]) -> list[str]:
    action_uris = []
    seen = set()
    for result in results:
        for key, binding in result.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized_key not in {
                "action",
                "actionuri",
                "play",
                "playuri",
                "event",
                "eventuri",
            }:
                continue
            value = binding.get("value") if isinstance(binding, dict) else None
            if value and value not in seen:
                seen.add(value)
                action_uris.append(value)
    return action_uris


def query_mentions_assists(message: str) -> bool:
    # Unicode escapes preserve legacy input recognition in this English source.
    return bool(
        re.search(
            r"\bassist(?:s|ed|ing)?\b|\basist(?:s)?\b|\u03b1\u03c3[\u03af\u03b9]\u03c3\u03c4",
            message or "",
            flags=re.IGNORECASE,
        )
    )


def classify_playbyplay_action_kind(message: str) -> str:
    normalized = message or ""
    intent_patterns = [
        (
            "assists",
            r"\bassist(?:s|ed|ing)?\b|\basist(?:s)?\b|\u03b1\u03c3[\u03af\u03b9]\u03c3\u03c4",
        ),
        (
            "rebounds",
            r"\brebound(?:s|ed|ing)?\b|\bribaund(?:s)?\b|\u03c1\u03b9\u03bc\u03c0[\u03ac\u03b1]\u03bf\u03c5\u03bd\u03c4",
        ),
        (
            "turnovers",
            r"\bturnover(?:s)?\b|\blath(?:os|i)\b|\u03bb[\u03ac\u03b1]\u03b8(?:\u03bf\u03c2|\u03b7)",
        ),
        ("fouls", r"\bfoul(?:s|ed)?\b|\bfaoul\b|\u03c6[\u03ac\u03b1]\u03bf\u03c5\u03bb"),
        (
            "steals",
            r"\bsteal(?:s)?\b|\bkleps(?:imo|imata)\b|\u03ba\u03bb[\u03ad\u03b5]\u03c8\u03b9\u03bc\u03bf",
        ),
        ("blocks", r"\bblock(?:s|ed)?\b|\btap(?:a|es)\b|\u03c4[\u03ac\u03b1]\u03c0\u03b1"),
        (
            "shots",
            r"\bshot(?:s)?\b|free[ -]?throw|three-pointer|two-pointer|tripont|dipont|\u03c4\u03c1[\u03af\u03b9]\u03c0\u03bf\u03bd\u03c4|\u03b4[\u03af\u03b9]\u03c0\u03bf\u03bd\u03c4|\u03c3\u03bf\u03c5\u03c4",
        ),
        ("points", r"\bpoint(?:s)?\b|\bpont(?:os|oi|ous|a)\b|\u03c0[\u03cc\u03bf]\u03bd\u03c4"),
    ]
    for action_kind, pattern in intent_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return action_kind
    return ""


def _get_cached_ai_search(cache_key: tuple[str, ...]) -> dict | None:
    if AI_SEARCH_CACHE_TTL_SECONDS == 0:
        return None
    now = time.monotonic()
    with _ai_search_cache_lock:
        cached = _ai_search_cache.get(cache_key)
        if not cached:
            return None
        if now - cached[0] > AI_SEARCH_CACHE_TTL_SECONDS:
            _ai_search_cache.pop(cache_key, None)
            return None
        _ai_search_cache.move_to_end(cache_key)
        return cached[1]


def _cache_ai_search(cache_key: tuple[str, ...], payload: dict) -> None:
    if AI_SEARCH_CACHE_TTL_SECONDS == 0:
        return
    with _ai_search_cache_lock:
        _ai_search_cache[cache_key] = (time.monotonic(), payload)
        _ai_search_cache.move_to_end(cache_key)
        while len(_ai_search_cache) > AI_SEARCH_CACHE_MAX_ENTRIES:
            _ai_search_cache.popitem(last=False)


def build_assist_action_resolution_query(action_uris: list[str]) -> str | None:
    safe_uris = []
    seen = set()
    for uri in action_uris:
        if not isinstance(uri, str) or not re.match(r"^https?://[^\s<>]+$", uri) or uri in seen:
            continue
        seen.add(uri)
        safe_uris.append(uri)
    if not safe_uris:
        return None

    values = " ".join(f"<{uri}>" for uri in safe_uris)
    return f"""
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?action WHERE {{
  VALUES ?candidate {{ {values} }}
  VALUES ?shotType {{ bball:TwoPointShotMade bball:ThreePointShotMade bball:FreeThrowMade }}
  {{ ?candidate rdf:type ?shotType ; bball:hasAssist ?action . }}
  UNION
  {{ ?shot rdf:type ?shotType ; bball:hasAssist ?candidate . BIND(?candidate AS ?action) }}
  ?game bball:hasPlayByPlayAction ?action .
}}
LIMIT 200
""".strip()


async def resolve_assist_action_uris(action_uris: list[str]) -> list[str]:
    resolution_query = build_assist_action_resolution_query(action_uris)
    if not resolution_query:
        return []
    data = await query_sparql(resolution_query)
    if not data:
        return []
    return extract_playbyplay_action_uris(data.get("results", {}).get("bindings", []))


async def readable_answer(request, provider, model, results, boolean):
    if not results and boolean is None:
        return {
            "kind": "analysis",
            "paragraphs": [
                "No matching data was found in the selected scope. Try another spelling or a broader season/game selection."
            ],
        }
    evidence = json.dumps(evidence_for_answer(results, boolean, request), ensure_ascii=False)

    async def generate():
        if provider == "gemini":
            response = await client.aio.models.generate_content(
                model=model,
                contents=evidence,
                config=types.GenerateContentConfig(
                    system_instruction=ANSWER_PROMPT, max_output_tokens=1800
                ),
            )
            return response.text
        result, _usage = await asyncio.to_thread(
            request_openai_text, evidence, ANSWER_PROMPT, model
        )
        return result

    try:
        answer = (await asyncio.wait_for(generate(), timeout=25) or "").strip()
        if not answer or re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", answer):
            return None
        return {
            "kind": "analysis",
            "paragraphs": [p.strip() for p in re.split(r"\n\s*\n", answer) if p.strip()][:3],
            "note": "AI explanation based on the returned basketball data. Check the supporting results below.",
        }
    except Exception:
        # Explanation failure must not discard a successful query or video action matches.
        return None


class SparqlRequest(BaseModel):
    query: str = Field(min_length=1, max_length=16000)


@app.post("/api/query")
async def run_editor_query(request: SparqlRequest):
    try:
        query = bounded_editor_query(request.query)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    data = await query_sparql(query, use_cache=False)
    if data is None:
        raise HTTPException(
            status_code=502,
            detail="The query could not be completed. Check its syntax or try again when the database is available.",
        )
    rows = data.get("results", {}).get("bindings", [])[:200]
    matches_actions = query_selects_playbyplay_actions(request.query)
    return {
        "results": rows,
        "boolean": data.get("boolean"),
        "playbyplay_filter": matches_actions,
        "action_uris": extract_playbyplay_action_uris(rows) if matches_actions else [],
    }


@app.post("/api/chat")
async def ai_chat_handler(request: ChatRequest):
    try:
        shot_styles = unsupported_shot_style(request.message)
        if shot_styles:
            return {
                "results": [],
                "playbyplay_filter": False,
                "action_uris": [],
                "answer": {
                    "kind": "capability",
                    "paragraphs": [
                        "This dataset does not label "
                        + " or ".join(shot_styles)
                        + ", so I cannot reliably identify those plays.",
                        "It records two-pointers, three-pointers, free throws, assists, fast breaks and shot locations. An assisted shot near the basket is not necessarily an alley-oop. Try ‘Show assisted two-point shots in this game’ as a broader search.",
                    ],
                    "note": "Shot-style information is unavailable; this does not mean the game had no such plays.",
                },
            }
        subject = (
            profile_subject(request.message)
            if request.include_answer and request.workspace == "explore"
            else None
        )
        if subject:
            query = profile_query(subject)
            data = await analysis_data(query)
            rows = data.get("results", {}).get("bindings", [])
            if rows:
                payload = {
                    "results": rows,
                    "answer": profile_answer(rows, subject),
                    "playbyplay_filter": False,
                    "action_uris": [],
                    "sparql_query": query,
                }
                return ai_search_response(payload, request.include_query or request.show_query)
        provider, prompt_variant, model = ai_search_configuration(
            request.provider,
            request.prompt_variant,
            request.openai_model,
        )
        cache_key = (
            provider,
            model,
            prompt_variant,
            request.season_code or "",
            request.game_code or "",
            " ".join(request.message.lower().split()),
            str(request.include_answer),
            request.workspace,
        )
        if not request.include_query:
            cached_payload = _get_cached_ai_search(cache_key)
            if cached_payload is not None:
                return ai_search_response(cached_payload, request.show_query)

        context = build_ai_scope_context(
            request.season_code,
            request.game_code,
        )
        contextual_message = request.message
        if context:
            contextual_message += "\n\nRequired request context:\n- " + "\n- ".join(context)

        generated_query, ai_usage = await generate_ai_search_text(
            provider,
            prompt_variant,
            model,
            contextual_message,
        )

        try:
            clean_sparql_query = clean_and_validate_sparql(generated_query)
        except ValueError as validation_error:
            if request.include_query:
                raise
            generated_query, ai_usage = await generate_ai_search_text(
                provider,
                prompt_variant,
                model,
                contextual_message
                + "\nThe previous attempt failed validation: "
                + str(validation_error)
                + "\nReturn exactly one read-only SELECT or ASK query. Do not use update commands or SERVICE.",
            )
            clean_sparql_query = clean_and_validate_sparql(generated_query)
        data = await query_sparql(clean_sparql_query, use_cache=False)

        if data is None:
            if request.include_query:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "The basketball database did not respond.",
                        "sparql_query": clean_sparql_query,
                        "ai_provider": provider,
                        "ai_model": model,
                        "prompt_variant": prompt_variant,
                        "ai_usage": ai_usage,
                    },
                )
            raise HTTPException(status_code=502, detail="The basketball database did not respond.")

        results = data.get("results", {}).get("bindings", [])
        playbyplay_filter = query_selects_playbyplay_actions(clean_sparql_query)
        action_uris = extract_playbyplay_action_uris(results) if playbyplay_filter else []
        playbyplay_action_kind = classify_playbyplay_action_kind(request.message)
        if playbyplay_filter and query_mentions_assists(request.message):
            resolved_assist_uris = await resolve_assist_action_uris(action_uris)
            if resolved_assist_uris:
                action_uris = resolved_assist_uris

        payload = {
            "results": results,
            "boolean": data.get("boolean"),
            "sparql_query": clean_sparql_query,
            "ai_provider": provider,
            "ai_model": model,
            "prompt_variant": prompt_variant,
            "ai_usage": ai_usage,
            "playbyplay_filter": playbyplay_filter,
            "playbyplay_action_kind": playbyplay_action_kind,
            "action_uris": action_uris,
        }
        if request.include_answer:
            if (
                playbyplay_filter
                and request.game_code
                and request.season_code
                and "," not in request.game_code + request.season_code
            ):
                try:
                    pbp = await get_match_pbp(request.game_code, request.season_code)
                    payload["answer"] = action_answer(pbp["actions"], action_uris, request)
                except HTTPException:
                    payload["answer"] = None
            else:
                payload["answer"] = await readable_answer(
                    request, provider, model, results, data.get("boolean")
                )
        if not request.include_query:
            _cache_ai_search(cache_key, payload)
        return ai_search_response(payload, request.include_query or request.show_query)
    except HTTPException:
        raise
    except ValueError as error:
        if request.include_query and "generated_query" in locals():
            raise HTTPException(
                status_code=422,
                detail={
                    "message": str(error),
                    "sparql_query": generated_query,
                    "ai_provider": provider,
                    "ai_model": model,
                    "prompt_variant": prompt_variant,
                    "ai_usage": ai_usage,
                },
            ) from error
        detail = (
            "We couldn't complete this search. Try rephrasing your question or choosing another AI provider in Search options."
            if "generated_query" in locals()
            else str(error)
        )
        raise HTTPException(status_code=422, detail=detail) from error
    except Exception as e:
        print(f"AI Search failed: {e}")
        error_text = str(e).upper()
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text or "RATE LIMIT" in error_text:
            raise HTTPException(
                status_code=429,
                detail="The selected AI provider has reached its usage limit. Try another provider or try again later.",
            ) from e
        if "503" in error_text or "UNAVAILABLE" in error_text:
            raise HTTPException(
                status_code=503,
                detail="The selected AI provider is temporarily unavailable. Choose another provider in Search options or try again later.",
            ) from e
        raise HTTPException(
            status_code=502,
            detail="AI Search could not complete this request. Try another provider in Search options.",
        ) from e


def quiz_generation_error(error):
    message = str(error).upper()
    if any(word in message for word in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")):
        return HTTPException(
            status_code=503,
            detail="The quiz provider is temporarily unavailable. Try Top 5, or try this format again later.",
        )
    return HTTPException(
        status_code=502, detail="This quiz question could not be generated. Please try again."
    )


def parse_english_quiz_response(response_text):
    """Keep generated quiz copy in the site's single supported language."""
    payload = json.loads(response_text.replace("```json", "").replace("```", "").strip())

    def check(value):
        if isinstance(value, str) and re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", value):
            raise ValueError("The quiz provider returned a non-English question. Please try again.")
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    if not isinstance(payload, dict):
        raise ValueError("The quiz provider returned an incomplete question. Please try again.")
    check(payload)
    return payload


def require_quiz_provider():
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Quiz generation is unavailable. Configure OPENAI_API_KEY on the server.",
        )


async def generate_quiz_text(prompt):
    """All generated Quiz Ball copy uses GPT-5 Mini, independently of Search."""
    require_quiz_provider()
    text, _ = await asyncio.to_thread(
        request_openai_text,
        prompt,
        "Write exclusively in English. Return only the requested JSON object. Use only the supplied basketball facts; do not invent facts.",
        OPENAI_MODEL,
    )
    return parse_english_quiz_response(text)


def quiz_player_name(player_id):
    """Resolve quiz identities consistently, preferring the canonical full name."""
    if not player_id:
        return ""
    data = query_sparql_requests(get_player_name_query(player_id))
    rows = (data or {}).get("results", {}).get("bindings", [])
    return rows[0].get("name", {}).get("value", player_id) if rows else player_id


async def load_quiz_player(player_id):
    data = await analysis_data(get_filtered_player_query(player_id))
    return quiz_player_profile(player_id, data)


@app.get("/api/quiz/who-am-i")
async def generate_who_am_i(difficulty: str = Query("medium")):
    require_quiz_provider()

    # Sample a historical game to build the quiz player pool.
    player_ids = set()

    # Bound retries when sampled games have no recorded lineup.
    for _ in range(5):
        random_game = str(random.randint(1, 300))
        roster_query = get_game_roster_query(random_game)
        roster_data = query_sparql_requests(roster_query)

        bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
        for row in bindings:
            home_uri = row.get("homeLineup", {}).get("value", "")
            road_uri = row.get("roadLineup", {}).get("value", "")
            for uri in [home_uri, road_uri]:
                if "#Lineup_" in uri:
                    parts = uri.split("#Lineup_")[1].split("_")
                    for pid in parts:
                        if pid:
                            player_ids.add(pid)

        if player_ids:
            break

    if not player_ids:
        raise HTTPException(
            status_code=404, detail="No players could be found in the database. Please try again."
        )

    secret_player_id = random.choice(list(player_ids))
    player_bio_query = get_filtered_player_query(secret_player_id)
    player_bio = query_sparql_requests(player_bio_query)

    profile = quiz_player_profile(secret_player_id, player_bio)
    if not profile.get("name"):
        raise HTTPException(status_code=404, detail="This player has no profile. Please try again.")

    prompt = f"""
    Write exclusively in English. We are playing 'Who am I?'.
    The secret basketball player's database biography is:
    {player_bio}
    Difficulty: {difficulty.upper()}.
    Create three factual clues using only the supplied data. Never reveal the name in a clue.
    These are stored historical profiles, not a current roster: describe team stints in past tense.
    Avoid present-tense club claims or undated all-time records that may have changed.
    Easy: recognizable team, nationality, or position. Medium: less obvious biography.
    Hard: more specific details supported by this biography. Do not invent records or achievements.
    Return only valid JSON, without Markdown:
    {{"secret_player_name": "Full player name from the data", "hints": ["First clue in English", "Second clue in English", "Third clue in English"]}}
    """

    try:
        result = await generate_quiz_text(prompt)
        result["secret_player_name"] = profile["name"]
        result["secret_player"] = profile
        if (
            not isinstance(result.get("hints"), list)
            or len(result["hints"]) != 3
            or not all(isinstance(hint, str) and hint.strip() for hint in result["hints"])
        ):
            raise ValueError("The quiz needs three clues.")
        return result
    except Exception as e:
        raise quiz_generation_error(e) from e


@app.get("/api/quiz/who-is-missing")
async def generate_who_is_missing(difficulty: str = Query("medium")):
    require_quiz_provider()

    lineup_players = []
    matchup_text = "Unknown game"
    season_text = ""

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]
    random_season_code, season_text = random.choice(seasons)

    games_query = get_games_list_query(random_season_code)
    games_data = query_sparql_requests(games_query)
    games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []

    # Use an actual five-player lineup from a recorded action.
    for _ in range(5):
        if not games_bindings:
            break

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home Team")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road Team")

        roster_query = get_game_roster_query(game_code, random_season_code)
        roster_data = query_sparql_requests(roster_query)

        bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
        if not bindings:
            continue

        random_row = random.choice(bindings)
        lineup_uri = random_row.get("homeLineup", {}).get("value", "")
        if random.choice([True, False]):  # Give home and road lineups equal selection probability.
            lineup_uri = random_row.get("roadLineup", {}).get("value", "")

        if "#Lineup_" in lineup_uri:
            parts = lineup_uri.split("#Lineup_")[1].split("_")
            parts = [p for p in parts if p]
            if len(parts) == 5:
                lineup_players = parts
                matchup_text = f"{home_team} - {away_team}"
                break

    if len(lineup_players) != 5:
        raise HTTPException(
            status_code=404, detail="No complete five-player lineup was found. Please try again."
        )

    profiles = await asyncio.gather(*(load_quiz_player(pid) for pid in lineup_players))
    if any(not profile.get("name") for profile in profiles):
        raise HTTPException(
            status_code=404, detail="This lineup has incomplete player profiles. Please try again."
        )
    player_names = [profile["name"] for profile in profiles]

    # Hide one player while retaining the authoritative identity for scoring.
    secret_index = random.randint(0, 4)
    secret_player = player_names[secret_index]
    known_players = [name for i, name in enumerate(player_names) if i != secret_index]

    # GPT writes the clue; database values remain the answer authority.
    prompt = f"""
    Write exclusively in English. We are playing 'Who is missing?'.
    Four players in a real EuroLeague lineup: {", ".join(known_players)}.
    The secret fifth player is {secret_player}. Difficulty: {difficulty.upper()}.
    Give one short clue without revealing the answer. Use only the supplied names;
    do not invent statistics, nationality, or biographical facts not supplied here.
    A clue about the spelling or initials is acceptable. Easy clues can be more direct.
    Preserve the secret and known player names exactly. Return only valid JSON:
    {{"secret_player_name": "{secret_player}", "known_players": {json.dumps(known_players, ensure_ascii=False)}, "hint": "One short English clue"}}
    """

    try:
        result_data = await generate_quiz_text(prompt)

        # Preserve the sampled game and player identities in the response.
        result_data["secret_player_name"] = secret_player
        result_data["known_players"] = known_players
        result_data["secret_player"] = profiles[secret_index]
        result_data["lineup"] = missing_lineup(profiles, secret_index)
        result_data["game_code"] = game_code
        result_data["matchup"] = matchup_text
        result_data["season"] = f"Euroleague Season {season_text}"

        return result_data
    except Exception as e:
        raise quiz_generation_error(e) from e


@app.get("/api/quiz/higher-or-lower")
async def generate_higher_or_lower(difficulty: str = Query("medium")):
    require_quiz_provider()

    import itertools

    categories = [
        {
            "id": "blocks",
            "name": "blocked shots",
            "func": get_defensive_anchors_query,
            "stat_key": "totalBlocks",
        },
        {
            "id": "fouls",
            "name": "fouls drawn",
            "func": get_foul_drawn_gravity_query,
            "stat_key": "totalFoulsDrawn",
        },
        {
            "id": "second_chance",
            "name": "second-chance points",
            "func": get_second_chance_points_query,
            "stat_key": "totalSecondChancePoints",
        },
    ]
    selected_category = random.choice(categories)

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]

    player_a = player_b = None
    matchup_text = season_text = ""
    quarter_text = ""

    # Difficulty changes the preferred gap between the two statistics.
    def is_valid_gap(stat1, stat2, diff_level, is_quarter):
        gap = abs(stat1 - stat2)
        if gap == 0:
            return False  # A tie has no correct higher/lower answer.

        # Quarter totals are smaller, so accept smaller statistical gaps.
        if is_quarter:
            if diff_level == "easy":
                return gap >= 2
            if diff_level == "medium":
                return gap == 1
            if diff_level == "hard":
                return gap == 1
        else:
            if diff_level == "easy":
                return gap >= 3
            if diff_level == "medium":
                return gap in [1, 2]
            if diff_level == "hard":
                return gap == 1
        return True

    # Bound the search for a usable comparison.
    for _ in range(30):
        random_season_code, season_text = random.choice(seasons)
        games_query = get_games_list_query(random_season_code)
        games_data = query_sparql_requests(games_query)
        games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []

        if not games_bindings:
            continue

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

        target_quarter = None
        quarter_text = "across the full game"
        is_quarter = False

        if random.random() < 0.40:
            target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
            quarter_text = f"during the {target_quarter} quarter only"
            is_quarter = True

        stat_query = selected_category["func"](
            game_code=game_code, season_code=random_season_code, quarter=target_quarter
        )

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        if len(bindings) >= 2:
            valid_pairs = []
            backup_pairs = []  # Fall back to any pair with different totals.

            for b1, b2 in itertools.combinations(bindings, 2):
                s1 = int(b1.get(selected_category["stat_key"], {}).get("value", 0))
                s2 = int(b2.get(selected_category["stat_key"], {}).get("value", 0))

                if s1 != s2:
                    backup_pairs.append((b1, b2))
                    if is_valid_gap(s1, s2, difficulty.lower(), is_quarter):
                        valid_pairs.append((b1, b2))

            # Prefer the requested difficulty, then fall back to an unequal pair.
            if valid_pairs:
                sampled = random.choice(valid_pairs)
            elif backup_pairs:
                sampled = random.choice(backup_pairs)
            else:
                continue

            name_a = quiz_player_name(sampled[0].get("player", {}).get("value", "").split("/")[-1])
            name_b = quiz_player_name(sampled[1].get("player", {}).get("value", "").split("/")[-1])
            stat_a = int(sampled[0].get(selected_category["stat_key"], {}).get("value", 0))
            stat_b = int(sampled[1].get(selected_category["stat_key"], {}).get("value", 0))

            if name_a != name_b:
                if random.choice([True, False]):
                    player_a = {"name": name_a, "stat": stat_a}
                    player_b = {"name": name_b, "stat": stat_b}
                else:
                    player_a = {"name": name_b, "stat": stat_b}
                    player_b = {"name": name_a, "stat": stat_a}

                matchup_text = f"{home_team} - {away_team}"
                break

    if not player_a or not player_b:
        raise HTTPException(
            status_code=404, detail="No suitable player statistics were found. Please try again."
        )

    prompt = f"""
    Write exclusively in English. Create a concise EuroLeague 'Higher or lower' question.
    Category: {selected_category["name"]}. Time frame: {quarter_text}.
    {player_a["name"]} recorded {player_a["stat"]}; {player_b["name"]} recorded {player_b["stat"]}.
    Game: {matchup_text}. Difficulty: {difficulty.upper()}.
    Ask whether player B recorded more or fewer than player A in this exact time frame.
    Do not reveal player B's number in question_text. Use only these facts.
    Return only valid JSON, without Markdown:
    {{
        "question_text": "One or two sentences in English",
        "player_a": {{"name": "{player_a["name"]}", "stat": {player_a["stat"]}}},
        "player_b": {{"name": "{player_b["name"]}", "stat": {player_b["stat"]}}},
        "category_name": "{selected_category["name"]} ({quarter_text})",
        "matchup": "{matchup_text}", "season": "EuroLeague Season {season_text}"
    }}
    """

    try:
        result = await generate_quiz_text(prompt)
        # The model writes the question, never the scoring facts.
        result.update(
            player_a=player_a,
            player_b=player_b,
            category_name=f"{selected_category['name']} ({quarter_text})",
            matchup=matchup_text,
            season=f"EuroLeague Season {season_text}",
            game_code=game_code,
        )
        return result
    except Exception as e:
        raise quiz_generation_error(e) from e


@app.get("/api/quiz/top-5")
async def generate_top_5(difficulty: str = Query("medium")):
    categories = [
        {
            "id": "assist_duos",
            "name": "passing pairs (passer and scorer)",
            "func": get_top_assist_duos_query,
            "stat_key": "totalAssists",
            "stat_label": "assists",
        },
        {
            "id": "blocks",
            "name": "blocked shots",
            "func": get_defensive_anchors_query,
            "stat_key": "totalBlocks",
            "stat_label": "blocks",
        },
        {
            "id": "fouls",
            "name": "fouls drawn",
            "func": get_foul_drawn_gravity_query,
            "stat_key": "totalFoulsDrawn",
            "stat_label": "fouls",
        },
        {
            "id": "second_chance",
            "name": "second-chance points",
            "func": get_second_chance_points_query,
            "stat_key": "totalSecondChancePoints",
            "stat_label": "points",
        },
        {
            "id": "fast_break",
            "name": "fast-break points",
            "func": get_fast_break_specialists_query,
            "stat_key": "fastBreakPoints",
            "stat_label": "points",
        },
    ]

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]

    top_5_results = []
    question_context = ""
    selected_category = None

    for _ in range(30):
        selected_category = random.choice(categories)
        random_season_code, season_text = random.choice(seasons)

        game_code = None
        target_quarter = None

        # Easy covers a season; medium a game; hard one quarter.
        if difficulty == "easy":
            question_context = f"in the {season_text} season"
        elif difficulty == "medium" or difficulty == "hard":
            games_query = get_games_list_query(random_season_code)
            games_data = query_sparql_requests(games_query)
            games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []
            if not games_bindings:
                continue

            random_game_row = random.choice(games_bindings)
            game_code = random_game_row.get("gameCode", {}).get("value", "")
            home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
            away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

            if difficulty == "medium":
                question_context = f"in {home_team} vs {away_team} ({season_text})"
            else:
                target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
                question_context = (
                    f"in the {target_quarter} quarter of {home_team} vs {away_team} ({season_text})"
                )

        stat_query = selected_category["func"](
            game_code=game_code, season_code=random_season_code, quarter=target_quarter
        )

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        if len(bindings) >= 5:
            top_5_results = []

            # Reveal only the first five ranked results.
            for b in bindings[:5]:
                stat_val = int(b.get(selected_category["stat_key"], {}).get("value", 0))

                if selected_category["id"] == "assist_duos":
                    scorer_pid = b.get("scorer", {}).get("value", "").split("/")[-1]
                    passer_pid = b.get("passer", {}).get("value", "").split("/")[-1]
                    name_str = f"{quiz_player_name(passer_pid)} & {quiz_player_name(scorer_pid)}"
                else:
                    pid = b.get("player", {}).get("value", "").split("/")[-1]
                    name_str = quiz_player_name(pid)

                top_5_results.append(
                    {"name": name_str, "stat": f"{stat_val} {selected_category['stat_label']}"}
                )
            break

    if len(top_5_results) < 5:
        raise HTTPException(
            status_code=404,
            detail="Five results could not be found for these criteria. Please try again.",
        )

    if selected_category["id"] == "assist_duos":
        question_text = f"Which five passing pairs (passer and scorer) led {question_context}?"
    else:
        question_text = (
            f"Who were the top five players for {selected_category['name']} {question_context}?"
        )

    return {
        "question_text": question_text,
        "answers": top_5_results,
        "category_name": selected_category["name"],
        "difficulty": difficulty,
    }


@app.get("/api/quiz/fifty-fifty")
async def generate_fifty_fifty(difficulty: str = Query("medium")):
    require_quiz_provider()

    categories = [
        {
            "id": "blocks",
            "name": "blocked shots",
            "func": get_defensive_anchors_query,
            "stat_key": "totalBlocks",
        },
        {
            "id": "fouls",
            "name": "fouls drawn",
            "func": get_foul_drawn_gravity_query,
            "stat_key": "totalFoulsDrawn",
        },
        {
            "id": "second_chance",
            "name": "second-chance points",
            "func": get_second_chance_points_query,
            "stat_key": "totalSecondChancePoints",
        },
        {
            "id": "assist_duos",
            "name": "assists between a passer and scorer",
            "func": get_top_assist_duos_query,
            "stat_key": "totalAssists",
        },
        {
            "id": "top_lineups",
            "name": "points scored by a five-player lineup",
            "func": get_top_lineups_query,
            "stat_key": "totalPoints",
        },
    ]

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]

    for _ in range(30):
        selected_category = random.choice(categories)
        random_season_code, season_text = random.choice(seasons)

        games_query = get_games_list_query(random_season_code)
        games_data = query_sparql_requests(games_query)
        games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []
        if not games_bindings:
            continue

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

        target_quarter = None
        filter_type = None
        filter_id = None
        context_text = f"in {home_team} vs {away_team}"

        if difficulty in ["medium", "hard"]:
            target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
            context_text += f", in the {target_quarter} quarter"

        # Individual on-court filters do not apply to pair or lineup questions.
        if difficulty == "hard" and selected_category["id"] not in ["assist_duos", "top_lineups"]:
            roster_query = get_game_roster_query(game_code, random_season_code)
            roster_data = query_sparql_requests(roster_query)
            r_bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
            p_ids = set()
            for r in r_bindings:
                for uri in [
                    r.get("homeLineup", {}).get("value", ""),
                    r.get("roadLineup", {}).get("value", ""),
                ]:
                    if "#Lineup_" in uri:
                        for pid in uri.split("#Lineup_")[1].split("_"):
                            if pid:
                                p_ids.add(pid)
            if p_ids:
                filter_id = random.choice(list(p_ids))
                filter_type = "on_court"
                res = query_sparql_requests(get_player_name_query(filter_id))
                on_court_name = filter_id
                if res and res.get("results", {}).get("bindings"):
                    on_court_name = (
                        res["results"]["bindings"][0].get("name", {}).get("value", filter_id)
                    )
                context_text += f", while {on_court_name} was on court"

        stat_query = selected_category["func"](
            game_code=game_code,
            season_code=random_season_code,
            quarter=target_quarter,
            filter_type=filter_type,
            filter_id=filter_id,
        )

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        valid_bindings = [
            b for b in bindings if int(b.get(selected_category["stat_key"], {}).get("value", 0)) > 0
        ]
        if not valid_bindings:
            continue

        selected_stat_row = random.choice(valid_bindings)
        stat_val = int(selected_stat_row.get(selected_category["stat_key"], {}).get("value", 0))

        # Describe the entity being ranked: one player, a passing pair, or a lineup.
        player_name = ""
        if selected_category["id"] == "assist_duos":
            scorer_pid = selected_stat_row.get("scorer", {}).get("value", "").split("/")[-1]
            passer_pid = selected_stat_row.get("passer", {}).get("value", "").split("/")[-1]
            player_name = f"the pair {quiz_player_name(passer_pid)} (passer) and {quiz_player_name(scorer_pid)} (scorer)"
        elif selected_category["id"] == "top_lineups":
            lineup_uri = selected_stat_row.get("lineup", {}).get("value", "")
            if "#Lineup_" in lineup_uri:
                pids = [p for p in lineup_uri.split("#Lineup_")[1].split("_") if p]
                names = [quiz_player_name(p) for p in pids]
                player_name = f"the five-player lineup ({', '.join(names)})"
            else:
                player_name = "the selected five-player lineup"
        else:
            pid = selected_stat_row.get("player", {}).get("value", "").split("/")[-1]
            player_name = f"the player {quiz_player_name(pid)}"

        correct_val = stat_val
        # Keep the incorrect option close to the true total and non-negative.
        offset = 1 if correct_val <= 5 else random.choice([1, 2])
        wrong_val = correct_val + offset if random.choice([True, False]) else correct_val - offset
        if wrong_val < 0:
            wrong_val = correct_val + offset

        options = [correct_val, wrong_val]
        random.shuffle(options)
        correct_index = options.index(correct_val)

        prompt = f"""
        Write exclusively in English. Write one short, direct question for '50/50'.
        Subject: {player_name}. Category: {selected_category["name"]}.
        Context: {context_text}. Ask for the numeric statistic without revealing it.
        Use only the supplied facts. Return only valid JSON, without Markdown:
        {{"question_text": "One short question in English"}}
        """
        try:
            result_data = await generate_quiz_text(prompt)

            result_data["game_code"] = game_code
            result_data["options"] = options
            result_data["correct_index"] = correct_index
            result_data["matchup"] = f"{home_team} - {away_team}"
            result_data["season"] = f"Euroleague Season {season_text}"
            return result_data
        except Exception as error:
            raise quiz_generation_error(error) from error

    raise HTTPException(
        status_code=404, detail="No suitable question data was found. Please try again."
    )


if __name__ == "__main__":
    uvicorn.run("src.backend.app:app", host="127.0.0.1", port=8000, reload=True)
