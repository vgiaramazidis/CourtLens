# src/backend/app.py
import asyncio
import csv
import json
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
from sparql_queries import (
    get_filtered_player_query, get_game_lineups_query, get_games_list_query,
    get_match_playbyplay_query, get_play_context_query, query_sparql_requests,
    get_filtered_shots_query, get_player_name_query, get_top_assist_duos_query,
    get_second_chance_points_query, get_top_lineups_query, get_clutch_time_performers_query,
    get_points_off_turnovers_query, get_fast_break_specialists_query,
    get_foul_drawn_gravity_query, get_defensive_anchors_query, get_simulator_crunch_time_query,get_game_roster_query
    ,get_timeouts_query, get_team_roster_query, get_simulator_crunch_time_query
)
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
VIDEO_CATALOG_PATH = REPO_ROOT / "src" / "data_pipeline" / "video_games.json"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
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
    path = Path(path_string)
    timeline = []
    try:
        with path.open(mode="r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                timeline.append({
                    "video_sec": float(row["video_time_sec"]),
                    "clock": row["game_clock"].strip(),
                    "quarter": row["quarter"].strip(),
                })
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

app = FastAPI(title="Euroleague API")

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
        games.append({
            "season_code": catalog_season,
            "game_code": catalog_game,
            "youtube_id": game_config.get("youtube_id"),
            "ocr_profile": game_config.get("ocr_profile"),
        })

    games.sort(key=lambda game: (game["season_code"], int(game["game_code"])))
    return {
        "seasons": sorted({game["season_code"] for game in games}),
        "games": games,
    }

# Βοηθητική συνάρτηση για τα δευτερόλεπτα
def time_to_seconds(t_str):
    if not t_str: return None
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
    is_opening_jump_ball = (
        action_name == "JumpBall" and 0 <= elapsed_seconds <= 1
    )
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
        shot_quarter = normalize_quarter(
            row.get("relatedShotQuarter", {}).get("value", "")
        )
        if time_to_seconds(shot_clock) is not None and shot_quarter:
            return shot_clock, shot_quarter
    return play_time, quarter


def playback_lead_for_action(game_config, action_type):
    """Return a contextual lead without changing the synchronized timestamp."""
    base_lead = max(
        0, min(15, float((game_config or {}).get("playback_lead_seconds", 5)))
    )
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

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/api/player/{player_id}")
async def get_player_name(player_id: str):
    # Εάν μας έρθει ολόκληρο όνομα (έχει κενό) αντί για ID,
    # δεν ρωτάμε τη βάση γιατί το SPARQL θα σκάσει. Επιστρέφουμε κατευθείαν το όνομα!
    if " " in player_id:
        return {"id": player_id, "name": player_id}

    query = get_player_name_query(player_id)
    data = await query_sparql(query)

    name = player_id

    # Ασφαλής προσπέλαση ΜΟΝΟ αν το data δεν είναι None (ώστε να μην κρασάρει ο server)
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
    min_end: str = Query(None)
):
    # Κλήση στο SPARQL (Προσάρμοσε τις παραμέτρους αν η συνάρτησή σου δέχεται διαφορετικές)
    # ΔΙΟΡΘΩΣΗ: Περνάμε τα arguments με το ΟΝΟΜΑ τους
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
        lineup_uri=lineup_uri
    )
    data = await query_sparql(sparql_query)

    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "shots": []}

    shots = []
    bindings = data.get("results", {}).get("bindings", [])

    for result in bindings:
        raw_coords = result.get("coords", {}).get("value", "0,0")
        x, y = raw_coords.split(",")
        action_type_full = result.get("action_type", {}).get("value", "")
        action_type = action_type_full.split("#")[-1]

        home_lineup = result.get("home_lineup", {}).get("value", "Άγνωστη πεντάδα")
        road_lineup = result.get("road_lineup", {}).get("value", "Άγνωστη πεντάδα")

        play_time = result.get("clockTime", {}).get("value", "")
        quarter_val = normalize_quarter(result.get("quarter", {}).get("value", ""))
        player_name = result.get("playerName", {}).get("value", "Άγνωστος Παίκτης")
        fast_break = get_bool(result, "isFastBreak")
        second_chance = get_bool(result, "isSecondChance")
        from_turnover = get_bool(result, "isFromTurnover")
        home_score = result.get("homeScore", {}).get("value", "0")
        road_score = result.get("roadScore", {}).get("value", "0")
        video_seconds = find_video_seconds(play_time, quarter_val, season_code, game_code)

        shots.append({
            "action_uri": result.get("action", {}).get("value", ""),
            "action_type":action_type,
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
            "teamType": result.get("teamType", {}).get("value", "")
        })

    return {"shots": shots}

@app.get("/api/player")
async def get_player(player: str = Query(None)):
    sparql_query = get_filtered_player_query(player)
    data = await query_sparql(sparql_query)

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
    data = await query_sparql(sparql_query)

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

        actions.append({
            "uri": row.get("action", {}).get("value", ""),
            "action_type": action_type_name,
            "playTime": play_time,
            "quarter": quarter,
            "sequence": int(row.get("sequence", {}).get("value", "0") or 0),
            "teamType": row.get("teamType", {}).get("value", "neutral"),
            "homeScore": int(home_score) if home_score.isdigit() else 0,
            "roadScore": int(road_score) if road_score.isdigit() else 0,
            "playerName": row.get("playerLabel", {}).get("value", ""),
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
            "playbackLeadSeconds": playback_lead_for_action(
                game_config, action_type_name
            ),
        })

    return {"actions": actions}

@app.get("/api/play/context")
async def get_play_context(action_uri: str = Query(...)):
    sparql_query = get_play_context_query(action_uri)
    data = await query_sparql(sparql_query)

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
        "playersOnCourt": players
    }

@app.get("/api/games")
async def get_games(season_code: str = Query(...)):
    sparql_query = get_games_list_query(season_code)
    data = await query_sparql(sparql_query)

    if not data:
        return {"games": []}

    games = []
    for row in data.get("results", {}).get("bindings", []):
        home_label = row.get("homeLabel", {}).get("value", "")
        away_label = row.get("awayLabel", {}).get("value", "")
        games.append({
            "gameCode": row.get("gameCode", {}).get("value", ""),
            "matchup": f"{home_label} vs {away_label}"
        })

    return {"games": games}

@app.get("/api/game/lineups")
async def get_game_lineups(game_code: str = Query(...), season_code: str = Query(...)):
    sparql_query = get_game_lineups_query(game_code, season_code)
    data = await query_sparql(sparql_query)

    if not data:
        return {"error": "Failed to fetch lineups", "lineups": []}

    lineups = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        lineup_uri = row.get("lineup", {}).get("value", "")
        team_type = row.get("teamType", {}).get("value", "")
        players_str = row.get("players", {}).get("value", "")
        homeScore = row.get("homeScore", {}).get("value", "")
        roadScore = row.get("roadScore", {}).get("value", "")
        lineups.append({
            "uri": lineup_uri,
            "teamType": team_type,
            "players": players_str
        })

    return {"homeScore": homeScore,"roadScore": roadScore,"lineups": lineups}

# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================

@app.get("/api/analytics/assist-duos")
async def get_assist_duos(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None)
):
    query = get_top_assist_duos_query(filter_type, filter_id, quarter, min_start, min_end, game_code, season_code)
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        scorer_id = row.get("scorer", {}).get("value", "").split("/")[-1]
        passer_id = row.get("passer", {}).get("value", "").split("/")[-1]

        results.append({
            "scorer_id": scorer_id,
            "passer_id": passer_id,
            "total_assists": int(row.get("totalAssists", {}).get("value", 0))
        })

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
    player_id: str = Query(None)
):
    query = get_second_chance_points_query(filter_type, filter_id, quarter, min_start, min_end, game_code, season_code, player_id)
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append({
            "player_id": player_id,
            "total_points": int(row.get("totalSecondChancePoints", {}).get("value", 0))
        })

    return {"second_chance_points": results}

@app.get("/api/analytics/lineups")
async def get_top_lineups(
    filter_type: str = Query(None),
    filter_id: str = Query(None),
    quarter: str = Query(None),
    min_start: str = Query(None),
    min_end: str = Query(None),
    game_code: str = Query(None),
    season_code: str = Query(None) # ΠΡΟΣΘΗΚΗ
):
    query = get_top_lineups_query(filter_type, filter_id, quarter, min_start, min_end, game_code, season_code)
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        lineup_url = row.get("lineup", {}).get("value", "")
        if "#Lineup_" in lineup_url:
            lineup_ids = lineup_url.split("#Lineup_")[1].split("_")
        else:
            lineup_ids = []

        results.append({
            "lineup_url": lineup_url,
            "players": lineup_ids,
            "total_points": int(row.get("totalPoints", {}).get("value", 0))
        })

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
    season_code: str = Query(None)
):
    query = get_foul_drawn_gravity_query(filter_type, filter_id, quarter, min_start, min_end, fouled_id, fouling_id, game_code,season_code)
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]
        results.append({
            "player_id": player_id,
            "total_fouls_drawn": int(row.get("totalFoulsDrawn", {}).get("value", 0))
        })

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
    season_code: str = Query(None)
):
    query = get_defensive_anchors_query(filter_type, filter_id, quarter, min_start, min_end, shooter_id, blocker_id, game_code,season_code)
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]
        results.append({
            "player_id": player_id,
            "total_blocks": int(row.get("totalBlocks", {}).get("value", 0))
        })

    return {"defensive_anchors": results}

@app.get("/api/analytics/clutch-performers")
async def get_clutch_performers():
    query = get_clutch_time_performers_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append({
            "player_id": player_id,
            "clutch_points": int(row.get("clutchPoints", {}).get("value", 0)),
            "clutch_actions": int(row.get("clutchActions", {}).get("value", 0))
        })

    return {"clutch_performers": results}

@app.get("/api/analytics/points-off-turnovers")
async def get_points_off_turnovers():
    query = get_points_off_turnovers_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        team_url = row.get("team", {}).get("value", "")
        team_code = team_url.split("/")[-1] if team_url else "Άγνωστη"

        results.append({
            "team": team_code,
            "points_off_turnovers": int(row.get("pointsOffTurnovers", {}).get("value", 0))
        })

    return {"points_off_turnovers": results}

@app.get("/api/analytics/fast-break")
async def get_fast_break_specialists():
    query = get_fast_break_specialists_query()
    data = await query_sparql(query)

    results = []
    bindings = data.get("results", {}).get("bindings", [])

    for row in bindings:
        player_id = row.get("player", {}).get("value", "").split("/")[-1]

        results.append({
            "player_id": player_id,
            "fast_break_points": int(row.get("fastBreakPoints", {}).get("value", 0)),
            "total_attempts": int(row.get("totalAttempts", {}).get("value", 0))
        })

    return {"fast_break_specialists": results}

@app.get("/api/simulator/crunch-time")
async def run_simulator(
    p1: str = Query(...),
    p2: str = Query(...),
    p3: str = Query(...),
    p4: str = Query(...),
    p5: str = Query(...),
    game_code: str = Query(None),
    quarter: str = Query(None)
):
    query = get_simulator_crunch_time_query(game_code, quarter, [p1, p2, p3, p4, p5])
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

        # Αν η ομάδα που σκόραρε είναι η ομάδα της πεντάδας μας, είναι Υπέρ. Αλλιώς, Κατά.
        if action_team == lineup_team:
            points_for += points
        else:
            points_against += points

    plus_minus = points_for - points_against

    return {
        "points_for": points_for,
        "points_against": points_against,
        "plus_minus": plus_minus
    }

@app.get("/api/game/roster")
async def get_game_roster(game_code: str = Query(...)):
    query = get_game_roster_query(game_code)
    data = await query_sparql(query)

    # Προσθήκη ελέγχου για αποφυγή σφαλμάτων (timeout)
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

    roster = [{"id": pid, "name": "Φόρτωση..."} for pid in player_ids]
    return {"roster": roster}

@app.get("/api/simulator/scenario")
async def get_simulator_scenario(season_code: str = Query(...)):
    # 1. Φέρνουμε όλα τα Timeouts του 4ου δεκαλέπτου
    query = get_timeouts_query(season_code)
    data = await query_sparql(query)

    bindings = data.get("results", {}).get("bindings", []) if data else []
    if not bindings:
        return {"error": "No scenarios found"}

    # 2. Διαλέγουμε ένα στην ΤΥΧΗ!
    random_timeout = random.choice(bindings)

    game_uri = random_timeout.get("game", {}).get("value", "")
    game_code = game_uri.split("/")[-1]
    game_season_name = game_uri.split("/")[-4] if len(game_uri.split("/")) > 4 else "Άγνωστη Σεζόν"
    clock = random_timeout.get("clock", {}).get("value", "00:00")
    home_score = random_timeout.get("homeScore", {}).get("value", "0")
    road_score = random_timeout.get("roadScore", {}).get("value", "0")

    home_lineup = random_timeout.get("homeLineup", {}).get("value", "")
    road_lineup = random_timeout.get("roadLineup", {}).get("value", "")

    home_team = home_lineup.split("teams/-/")[1].split("#")[0] if "teams/-/" in home_lineup else "Home"
    road_team = road_lineup.split("teams/-/")[1].split("#")[0] if "teams/-/" in road_lineup else "Road"

    # 3. Σε κάνουμε προπονητή ΜΟΝΟ της ομάδας που ΧΑΝΕΙ (ή στην τύχη αν έχουμε ισοπαλία)!
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

    # 4. Φέρνουμε ΜΟΝΟ τους δικούς σου παίκτες (όσους έπαιξαν σε αυτό το ματς)
    roster_query = get_team_roster_query(game_code, user_team)
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
        "user_score": user_score,
        "opp_score": opp_score,
        "clock": clock,
        "roster": roster
    }

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_SEARCH_PROVIDER = os.getenv("AI_SEARCH_PROVIDER", "gemini").strip().lower()
AI_SEARCH_PROMPT_VARIANT = os.getenv(
    "AI_SEARCH_PROMPT_VARIANT", "ontology"
).strip().lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
OPENAI_MODEL = "gpt-5-mini"
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")
OPENAI_TIMEOUT_SECONDS = max(1, int(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")))
OPENAI_MAX_OUTPUT_TOKENS = max(
    1000, int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4000"))
)

# The backend can still start without Gemini configured; /api/chat reports a clear 503 instead.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Production AI Search prompts
euroleague_system_prompt = """
You are an expert SPARQL developer specializing in semantic sports data and the FORTH Basketball Ontology.
Translate each English user question into exactly one valid SPARQL query.
Return only the query. Do not return Markdown fences, HTML, explanations, comments, or any other text.
Only read-only SELECT and ASK queries are allowed. UPDATE operations and SERVICE clauses are forbidden.

Always include these namespaces:
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

CORE CLASSES (rdf:type):
- Shots: bball:ThreePointShotMade, bball:ThreePointShotMissed, bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:FreeThrowMade, bball:FreeThrowMissed
- Creation and possession: bball:Assist, bball:OffensiveRebound, bball:DefensiveRebound, bball:Turnover, bball:Steal
- Fouls and defense: bball:FoulDrawn, bball:DefensiveFoul, bball:OffensiveFoul, bball:BenchFoul, bball:UnsportsmanlikeFoul, bball:TechnicalFoul, bball:CoachFoul, bball:Block
- Game flow: bball:PeriodStart, bball:JumpBall, bball:PlayerIn, bball:PlayerOut

STRICT VOCABULARY AND QUERY RULES — NEVER INVENT PROPERTIES:
1. Game and season structure:
   ?game a bball:Game ; bball:hasSeason ?season ; bball:hasCode ?gameCode .
   ?season bball:hasCode ?seasonCode .
   ?game bball:homeTeam ?homeTeam ; bball:roadTeam ?roadTeam .
   Always use the exact game and season codes supplied in the Required request context.
   If a season or game context contains comma-separated codes, never search for the combined string. Split the codes and use FILTER IN.
   Correct example: FILTER(?seasonCode IN ("SEASON_CODE_1", "SEASON_CODE_2"))
2. Action connection:
   ?game bball:hasPlayByPlayAction ?action .
   ?action bball:hasPlayByPlaySequence ?order .
3. Action statistics:
   - Points: bball:pointsAwarded ?points . Always aggregate points with SUM(xsd:integer(?points)).
   - Acting player: bball:actionPlayer ?player .
   - Acting team: bball:actionTeam ?team .
   - Assist relation: ?shot bball:hasAssist ?assist . ?assist bball:actionPlayer ?assistingPlayer .
   - Running score: bball:runningHomeTeamScore ?homeScore and bball:runningRoadTeamScore ?roadScore.
     These properties belong to ?action, never to ?game. bball:homeScore and bball:roadScore do not exist.
   - Shot zone: bball:shotZone ?shotZone. Stored values are codes "A" through "J" or an empty string, never words such as "paint" or "left corner".
     A/B/C = close range and paint; D/E/F/G = two-point range outside the paint;
     H = left three-point perimeter; I = right three-point perimeter; J = very long three-pointer.
   - Exact shot position: bball:shotCoords ?coords, stored as an "x,y" string in centimeters relative to the basket center.
     x is the horizontal axis (negative means left) and y is the distance toward the court interior.
     Parse geometric coordinates with:
     BIND(xsd:decimal(STRBEFORE(str(?coords), ",")) AS ?shotX)
     BIND(xsd:decimal(STRAFTER(str(?coords), ",")) AS ?shotY)
     For "paint", use FILTER(?shotZone IN ("A", "B", "C")). For the exact left three-point corner, use
     FILTER(str(?shotZone) = "H" && ?shotX <= -600 && ?shotY <= 175).
   - Action time: ?action bball:quarter ?quarter ; bball:clock ?clock .
     ?quarter is a string: "1st", "2nd", "3rd", "4th", "1OT", "2OT", and so on; it is never numeric.
     For the fourth quarter, use FILTER(str(?quarter) = "4th").
     ?clock is an "MM:SS" string. Convert it to remaining seconds with:
     BIND((xsd:integer(STRBEFORE(str(?clock), ":")) * 60 + xsd:integer(STRAFTER(str(?clock), ":"))) AS ?secondsRemaining)
     Never use the nonexistent properties bball:period, bball:gameClock, or bball:hasQuarter.
4. On-court lineups:
   bball:runningHomeTeamLineup and bball:runningRoadTeamLineup always belong to ?action, never to ?game or a possession:
   ?action bball:runningHomeTeamLineup ?homeLineup ; bball:runningRoadTeamLineup ?roadLineup .
   ?lineup bball:includesPlayer ?player .
   To test whether a player was on court, connect the lineup of the same scoring or shot ?action to the player through bball:includesPlayer.
   For a starting lineup, take the lineup on the first bball:PeriodStart in the "1st" quarter. Keep only actions whose
   runningHomeTeamLineup or runningRoadTeamLineup is exactly the same URI. Never invent Lineup properties such as
   bball:hasPlayByPlaySequence, and never attach a running lineup directly to ?game.
   Never assume that a named team is home or road. Resolve ?targetTeam by rdfs:label and use two explicit UNION branches.
   Never join the player members of both lineups simultaneously.

   CANONICAL PATTERN — actions while a named team's starting lineup was on court:
   ?targetTeam rdfs:label ?targetTeamName .
   FILTER(regex(str(?targetTeamName), '(^|[^A-Za-z0-9])TEAM_NAME([^A-Za-z0-9]|$)', 'i'))
   ?game bball:hasPlayByPlayAction ?periodStart, ?action .
   ?periodStart rdf:type bball:PeriodStart ; bball:quarter "1st" .
   VALUES ?actionType { bball:TwoPointShotMade bball:TwoPointShotMissed bball:ThreePointShotMade bball:ThreePointShotMissed bball:FreeThrowMade bball:FreeThrowMissed }
   ?action rdf:type ?actionType .
   {
     ?game bball:homeTeam ?targetTeam .
     ?periodStart bball:runningHomeTeamLineup ?startingLineup .
     ?action bball:runningHomeTeamLineup ?startingLineup .
   } UNION {
     ?game bball:roadTeam ?targetTeam .
     ?periodStart bball:runningRoadTeamLineup ?startingLineup .
     ?action bball:runningRoadTeamLineup ?startingLineup .
   }
   If the question asks for actions while the lineup was on court, do not constrain bball:actionTeam: the actions may belong
   to either team. Constrain bball:actionTeam to ?targetTeam only when the user explicitly requests that team's actions.

   CANONICAL PATTERN — points scored by a named team while a named player was on court:
   ?targetTeam rdfs:label ?targetTeamName .
   ?player rdfs:label ?playerName .
   ?action bball:actionTeam ?targetTeam ; bball:pointsAwarded ?points .
   FILTER(xsd:integer(?points) > 0)
   {
     ?game bball:homeTeam ?targetTeam .
     ?action bball:runningHomeTeamLineup ?lineup .
   } UNION {
     ?game bball:roadTeam ?targetTeam .
     ?action bball:runningRoadTeamLineup ?lineup .
   }
   ?lineup bball:includesPlayer ?player .
   A regex filter is mandatory for both ?targetTeamName and ?playerName. A player's presence in a lineup does not replace
   the explicit filter for the team named by the user.
   For total points, repeat exactly the same team/home-road/lineup logic inside the aggregate subquery. Use the same
   variable names ?targetTeam and ?player consistently in SELECT, WHERE, and GROUP BY:
   {
     SELECT ?game ?targetTeam ?player (SUM(xsd:integer(?subPoints)) AS ?totalPoints) WHERE {
       ?game bball:hasSeason ?subSeason ; bball:hasCode ?subGameCode ; bball:hasPlayByPlayAction ?subAction .
       ?subSeason bball:hasCode ?subSeasonCode .
       FILTER(str(?subSeasonCode) = "SEASON_CODE")
       FILTER(str(?subGameCode) = "GAME_CODE")
       ?targetTeam rdfs:label ?subTargetTeamName .
       FILTER(regex(str(?subTargetTeamName), '(^|[^A-Za-z0-9])TEAM_NAME([^A-Za-z0-9]|$)', 'i'))
       ?player rdfs:label ?subPlayerName .
       FILTER(regex(str(?subPlayerName), '(^|[^A-Za-z0-9])PLAYER_NAME([^A-Za-z0-9]|$)', 'i'))
       ?subAction bball:actionTeam ?targetTeam ; bball:pointsAwarded ?subPoints .
       FILTER(xsd:integer(?subPoints) > 0)
       {
         ?game bball:homeTeam ?targetTeam .
         ?subAction bball:runningHomeTeamLineup ?subLineup .
       } UNION {
         ?game bball:roadTeam ?targetTeam .
         ?subAction bball:runningRoadTeamLineup ?subLineup .
       }
       ?subLineup bball:includesPlayer ?player .
     } GROUP BY ?game ?targetTeam ?player
   }
   "SEASON_CODE", "GAME_CODE", TEAM_NAME, and PLAYER_NAME are placeholders and must be replaced from the request context.
   Never SELECT or GROUP BY a variable different from the one actually bound inside the subquery.
   In this pattern, never introduce ?subTargetTeam or ?subPlayer for labels and then use ?targetTeam or ?player elsewhere.
   That creates a Cartesian product and may time out. Use exactly ?targetTeam and ?player throughout the subquery.
   The expression ?actionTeam = ?game/bball:homeTeam is forbidden: a property path is not a value expression inside FILTER.
   First bind ?game bball:homeTeam ?targetTeam or ?game bball:roadTeam ?targetTeam.
   Dummy triples such as ?team ?predicate ?value are forbidden.
5. Player information:
   - Height: bball:hasHeight ?height . Use AVG(xsd:float(?height)) for an average.
   - Birth date: bball:hasBirthDate ?date .
6. Possessions:
   ?game bball:hasPossession ?possession .
   ?possession bball:hasPossessionSequence ?seq .
   ?possession bball:possessionTeam ?team ;
               bball:startsAfterAction ?startAction ;
               bball:endsWithAction ?endAction ;
               bball:containsAction ?containedAction .
   ?seq is a literal sequence value, not a resource with bball:hasPlayByPlayAction.
7. Direct relations and flags:
   - Missed shot followed by a rebound:
     ?action bball:leadsToRebound ?reboundAction .
     ?reboundAction rdf:type bball:OffensiveRebound .
   - Fast-break score: ?scoreAction bball:isFastBreak "true"^^xsd:boolean ; bball:pointsAwarded ?points .
   - Points after a turnover: ?scoreAction bball:isFromTurnover "true"^^xsd:boolean .
   - Turnover that starts a possession containing fast-break points:
     ?action rdf:type bball:Turnover .
     ?possession bball:startsAfterAction ?action ; bball:containsAction ?scoreAction .
     ?scoreAction bball:isFastBreak "true"^^xsd:boolean ; bball:pointsAwarded ?points .

PLAY-BY-PLAY CONNECTION:
- When a question requests concrete plays or a player's actions, SELECT must include DISTINCT ?action.
- ?action must be the exact action URI connected through ?game bball:hasPlayByPlayAction ?action.
- ASSISTS: ?action must be the bball:Assist action itself, not the shot. Use:
  ?game bball:hasPlayByPlayAction ?action .
  ?action rdf:type bball:Assist ; bball:actionPlayer ?assistingPlayer .
  VALUES ?madeShotType { bball:TwoPointShotMade bball:ThreePointShotMade bball:FreeThrowMade }
  ?shot rdf:type ?madeShotType ; bball:hasAssist ?action ; bball:actionPlayer ?receivingPlayer .
  bball:FreeThrowMade may have an assist when the pass led to a shooting foul and at least one resulting free throw was made.
  Therefore, a request for PLAYER_A's assists to PLAYER_B must return Assist cards in Play-by-Play, not Shot cards.
- Points: use bball:pointsAwarded ?points and FILTER(xsd:integer(?points) > 0).
- Rebounds: use VALUES ?actionType { bball:OffensiveRebound bball:DefensiveRebound } and ?action rdf:type ?actionType.
- Turnovers: use ?action rdf:type bball:Turnover.
- Fouls drawn: use ?action rdf:type bball:FoulDrawn. Do not confuse this with a foul committed by another player.
- Fouls committed by a team: use VALUES ?foulType { bball:DefensiveFoul bball:OffensiveFoul bball:BenchFoul bball:UnsportsmanlikeFoul bball:TechnicalFoul bball:CoachFoul },
  then ?action rdf:type ?foulType ; bball:actionTeam ?team and connect ?team to the game's homeTeam or roadTeam. Do not include FoulDrawn or Block.
- Substitutions: use VALUES ?actionType { bball:PlayerIn bball:PlayerOut } and
  ?action rdf:type ?actionType ; bball:actionPlayer ?player. The properties/classes bball:Substitution,
  bball:SubstitutionIn, bball:SubstitutionOut, bball:playerIn, and bball:playerOut do not exist.
- For each action list, include when available: ?playerName, ?points, ?quarter, ?clock, ?homeScore, ?roadScore, and ?order.
  Use OPTIONAL for fields that may be absent. Scores must be read only with:
  OPTIONAL { ?action bball:runningHomeTeamScore ?homeScore ; bball:runningRoadTeamScore ?roadScore . }
- For total points, total made shots, or total missed shots, return both the aggregate and DISTINCT ?action through an
  aggregate subquery so the matching plays can filter the Play-by-Play overlay.
- For "how many points" or "total points", the outer SELECT must contain DISTINCT ?action and ?totalPoints.
  Calculate ?totalPoints in an inner aggregate subquery grouped by ?game and ?player, then join it to the individual scoring
  ?action values for that same game and player. The final result must contain one row per scoring action and repeat the same
  ?totalPoints value on every row.
- For "how many rebounds" or another action count connected to Play-by-Play, return DISTINCT ?action and the aggregate,
  such as ?totalRebounds. Inside the aggregate subquery, repeat the same action-type VALUES and the player, season, and game
  filters. Variables and VALUES from the outer query are not automatically available inside a subquery.
- For a pure ranking such as "which player had the most...", return only the player and COUNT/SUM with GROUP BY,
  ORDER BY DESC, and LIMIT. Do not add an outer ?action just to activate the overlay because that would select an unrelated play.
- Every comparison must appear inside FILTER(...). Wrong: ?points != 0. Correct: FILTER(xsd:integer(?points) > 0).
- Only aggregates that do not logically map to a play list, such as percentage or average, should omit ?action.
- For total points, use (SUM(xsd:integer(?points)) AS ?totalPoints), never COUNT actions.
- For a shooting percentage, always return all three fields: ?made, ?attempts, and ?percentage.
  Two-point example:
  VALUES ?actionType { bball:TwoPointShotMade bball:TwoPointShotMissed }
  ?action rdf:type ?actionType .
  BIND(IF(?actionType = bball:TwoPointShotMade, 1, 0) AS ?madeValue)
  SELECT must contain (SUM(?madeValue) AS ?made), (COUNT(?action) AS ?attempts), and
  (100.0 * SUM(?madeValue) / COUNT(?action) AS ?percentage).
  For three-pointers, use ThreePointShotMade/Missed; for free throws, use FreeThrowMade/Missed.
  Do not return an action list when the user requests a percentage; return the aggregate only.
- For a yes/no question, use ASK and keep exactly the same game, season, and player filters.

NAME LOOKUP — ALWAYS USE REGEX:
?player rdfs:label ?playerName .
FILTER(regex(str(?playerName), '(^|[^A-Za-z0-9])PLAYER_NAME([^A-Za-z0-9]|$)', 'i'))
Do not use word-boundary escapes. The SPARQL string parser may convert them into control characters before evaluating regex.
The application accepts English questions, player names, and team names. Do not transliterate Greek or Greeklish input.

FINAL CHECK BEFORE RETURNING THE QUERY:
- After PREFIX declarations, the query begins with SELECT or ASK. Every SELECT query contains LIMIT.
- No bare variable comparison exists outside FILTER.
- After a semicolon, write only the next predicate/object, never the subject again.
  Correct: ?x rdf:type bball:PeriodStart ; bball:quarter "1st" .
- VALUES binds the exact variable used by the triple pattern: VALUES ?actionType { ... } followed by ?action rdf:type ?actionType.
  Never use FILTER(?actionType IN (?differentVariable)).
- The query contains exactly the season/game filters supplied by the Required request context.
- When concrete or countable plays are requested, the outer SELECT includes DISTINCT ?action for the Play-by-Play overlay.
- Only percentages, averages, and pure summary rankings may omit ?action.

EXAMPLE:
Question: "Who assisted the first made three-pointer?"
Answer:
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?assistingPlayerName WHERE {
  ?game a bball:Game ; bball:hasPlayByPlayAction ?action .
  ?action rdf:type bball:ThreePointShotMade ; bball:hasPlayByPlaySequence ?order ; bball:hasAssist ?assist .
  ?assist bball:actionPlayer ?assistingPlayer .
  ?assistingPlayer rdfs:label ?assistingPlayerName .
} ORDER BY ASC(xsd:integer(?order)) LIMIT 1
"""

simple_sparql_system_prompt = """
Translate the English user question into exactly one valid, read-only SPARQL SELECT or ASK query for the FORTH Basketball Ontology.
This baseline prompt provides only a flat vocabulary. It intentionally does not explain how the properties and classes connect and does not include query templates.
Return only the SPARQL query, without Markdown, comments, or explanation.
Use these prefixes:
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

AVAILABLE PROPERTIES:
- rdf:type, rdfs:label, rdfs:comment, skos:altLabel, foaf:depiction
- bball:hasBio, bball:hasWebsite, bball:teamVenue, bball:hasLeague
- bball:eventEnded, bball:eventStarted, bball:hasExtraTime, bball:hasHeadCoach
- bball:dnp, bball:hasCapacity, bball:hasCode, bball:gameVenue
- bball:hasAchievements, bball:hasAddress, bball:hasAudience, bball:hasBiography
- bball:wasBornIn, bball:hasBirthDate, bball:hasCountry, bball:hasDate
- bball:hasHeight, bball:hasHomeTeamScore, bball:hasJerseyName, bball:hasJerseyNumber
- bball:hasPhase, bball:hasPhaseGroup, bball:hasPlayerParticipation
- bball:hasPlayerStatline, bball:hasPosition, bball:hasReferee
- bball:hasRoadTeamScore, bball:hasRound, bball:hasScore, bball:hasSeason
- bball:hasTeamBoxscore, bball:hasTeamStatline, bball:hasWeight
- bball:homeTeam, bball:losingTeam, bball:overPlayer, bball:overTeam
- bball:roadTeam, bball:startYear, bball:startingFive, bball:teamCountry
- bball:winningTeam, bball:endYear, bball:lineupTeam, bball:includesPlayer
- bball:PIR, bball:assists, bball:blocks, bball:blocksAgainst
- bball:defensiveRebounds, bball:offensiveRebounds, bball:totalRebounds
- bball:fieldGoalsAttempted2, bball:fieldGoalsAttempted3, bball:fieldGoalsAttemptedTotal
- bball:fieldGoalsMade2, bball:fieldGoalsMade3, bball:fieldGoalsMadeTotal
- bball:fieldGoalsPer, bball:fieldGoalsPer2, bball:fieldGoalsPer3
- bball:foulsCommitted, bball:foulsReceived
- bball:freeThrowsAttempted, bball:freeThrowsMade, bball:freeThrowsPer
- bball:plusMinus, bball:points, bball:timePlayed, bball:turnovers, bball:steals
- bball:quarter1points, bball:quarter2points, bball:quarter3points, bball:quarter4points
- bball:endOfQuarter1points, bball:endOfQuarter2points, bball:endOfQuarter3points, bball:endOfQuarter4points
- bball:belongsToPossession, bball:actionCoach, bball:actionPlayer, bball:actionTeam
- bball:blockedBy, bball:causedByFoul, bball:causedBySteal, bball:occuredByFoul
- bball:clock, bball:hasAssist, bball:hasPlayByPlayAction, bball:hasPlayByPlaySequence
- bball:isFastBreak, bball:isFromTurnover, bball:isSecondChance
- bball:leadsToRebound, bball:pointsAwarded, bball:quarter, bball:quarterSecondsRemaining
- bball:runningHomeTeamLineup, bball:runningHomeTeamScore
- bball:runningRoadTeamLineup, bball:runningRoadTeamScore
- bball:shotCoords, bball:shotZone
- bball:hasPossession, bball:containsAction, bball:endsWithAction
- bball:possessionTeam, bball:startsAfterAction, bball:hasPossessionSequence
- bball:correspondsToOCRObservation, bball:hasBroadcastVideo, bball:hasOCRObservation
- bball:isVideoEnabled, bball:ocrClock, bball:ocrProfile, bball:ocrQuarter
- bball:ocrSequence, bball:playbackLeadSeconds, bball:videoTimeSeconds, bball:youtubeURL

AVAILABLE CLASSES:
- bball:Coach, bball:League, bball:Game, bball:Country, bball:Player
- bball:PlayerParticipation, bball:Referee, bball:Season, bball:Statline
- bball:Team, bball:TeamBoxscore, bball:Venue, bball:Lineup, bball:Possession
- bball:PeriodStart, bball:PeriodEnd, bball:GameEnd, bball:JumpBall
- bball:TwoPointShotMade, bball:TwoPointShotMissed
- bball:ThreePointShotMade, bball:ThreePointShotMissed
- bball:FreeThrowMade, bball:FreeThrowMissed
- bball:OffensiveRebound, bball:DefensiveRebound, bball:Assist
- bball:Turnover, bball:Steal, bball:Block, bball:FoulDrawn
- bball:DefensiveFoul, bball:OffensiveFoul, bball:CoachFoul, bball:BenchFoul
- bball:TechnicalFoul, bball:UnsportsmanlikeFoul
- bball:PlayerIn, bball:PlayerOut, bball:Timeout, bball:TimeoutTV, bball:Challenge
- bball:BroadcastVideo, bball:OCRObservation

BASELINE GUIDELINES:
- Never use a class as a property.
- Team, player, coach, referee, and country names are English rdfs:label values.
- Use SELECT DISTINCT when returning resources. Use COUNT(DISTINCT ?game) when counting games.
- Cast a denominator to xsd:double when performing division.
- Honor the Required request context exactly.
- Do not use UPDATE operations or SERVICE clauses.
""".strip()

AI_SEARCH_PROMPTS = {
    "simple": simple_sparql_system_prompt,
    "ontology": euroleague_system_prompt,
}
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
            "Το OpenAI Responses API δεν επέστρεψε κείμενο "
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
        "total_tokens": _non_negative_int(
            usage.get("total_tokens", input_tokens + output_tokens)
        ),
    }


def extract_gemini_usage(response) -> dict[str, int]:
    """Normalize Gemini usage; output includes visible candidates and thoughts."""
    usage = getattr(response, "usage_metadata", None)
    input_tokens = _non_negative_int(getattr(usage, "prompt_token_count", 0))
    cached_input_tokens = min(
        input_tokens,
        _non_negative_int(getattr(usage, "cached_content_token_count", 0)),
    )
    visible_output_tokens = _non_negative_int(
        getattr(usage, "candidates_token_count", 0)
    )
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


def request_openai_text(
    message: str, system_prompt: str, model: str
) -> tuple[str, dict[str, int]]:
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
    prompt_variant = (
        requested_prompt_variant or AI_SEARCH_PROMPT_VARIANT
    ).strip().lower()
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
                detail="Το Gemini AI Search δεν έχει ρυθμιστεί. Ορίστε το GEMINI_API_KEY.",
            )
        return provider, prompt_variant, GEMINI_MODEL

    model = requested_openai_model or OPENAI_MODEL
    if model != OPENAI_MODEL:
        raise ValueError("openai_model must be 'gpt-5-mini'.")
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Το OpenAI AI Search δεν έχει ρυθμιστεί. Ορίστε το OPENAI_API_KEY.",
        )
    return provider, prompt_variant, model


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
    return await asyncio.to_thread(
        request_openai_text, message, system_prompt, model
    )

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    game_code: str | None = Field(default=None, max_length=50, pattern=r"^[A-Za-z0-9_,\-]+$")
    season_code: str | None = Field(default=None, max_length=50, pattern=r"^[A-Za-z0-9_,\-]+$")
    provider: Literal["gemini", "openai"] | None = None
    prompt_variant: Literal["simple", "ontology"] | None = None
    openai_model: Literal["gpt-5-mini"] | None = None
    include_query: bool = False


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
        values = [
            value.strip()
            for value in str(raw_value or "").split(",")
            if value.strip()
        ]
        if not values:
            continue
        if len(values) == 1:
            context.append(
                f'Restrict the query to the selected {label} using '
                f'bball:hasCode "{values[0]}".'
            )
            continue
        quoted_values = ", ".join(f'"{value}"' for value in values)
        context.append(
            f'Restrict the query to the selected {label} codes using '
            f'FILTER(?{variable} IN ({quoted_values})).'
        )
    return context


def clean_and_validate_sparql(raw_query: str) -> str:
    query = (raw_query or "").strip()
    query = re.sub(r"^```(?:sparql)?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s*```$", "", query).strip()

    query_body = query
    while True:
        prefix_match = re.match(
            r"^(?:PREFIX\s+[A-Za-z][\w-]*:\s*<[^>]+>|BASE\s+<[^>]+>)\s*",
            query_body,
            flags=re.IGNORECASE,
        )
        if not prefix_match:
            break
        query_body = query_body[prefix_match.end():].lstrip()

    if not re.match(r"^(SELECT|ASK)\b", query_body, flags=re.IGNORECASE):
        raise ValueError("Το AI query πρέπει να είναι read-only SELECT ή ASK.")

    forbidden = re.search(
        r"\b(LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|INSERT|DELETE|WITH|SERVICE)\b",
        query,
        flags=re.IGNORECASE,
    )
    if forbidden:
        raise ValueError(f"Μη επιτρεπτή SPARQL εντολή: {forbidden.group(1).upper()}")

    if re.match(r"^SELECT\b", query_body, flags=re.IGNORECASE) and not re.search(r"\bLIMIT\s+\d+\b", query, flags=re.IGNORECASE):
        query = f"{query}\nLIMIT 200"

    return query


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
            if normalized_key not in {"action", "actionuri", "play", "playuri", "event", "eventuri"}:
                continue
            value = binding.get("value") if isinstance(binding, dict) else None
            if value and value not in seen:
                seen.add(value)
                action_uris.append(value)
    return action_uris


def query_mentions_assists(message: str) -> bool:
    return bool(re.search(r"\bassist(?:s|ed|ing)?\b|\basist(?:s)?\b|ασ[ίι]στ", message or "", flags=re.IGNORECASE))


def classify_playbyplay_action_kind(message: str) -> str:
    normalized = message or ""
    intent_patterns = [
        ("assists", r"\bassist(?:s|ed|ing)?\b|\basist(?:s)?\b|ασ[ίι]στ"),
        ("rebounds", r"\brebound(?:s|ed|ing)?\b|\bribaund(?:s)?\b|ριμπ[άα]ουντ"),
        ("turnovers", r"\bturnover(?:s)?\b|\blath(?:os|i)\b|λ[άα]θ(?:ος|η)"),
        ("fouls", r"\bfoul(?:s|ed)?\b|\bfaoul\b|φ[άα]ουλ"),
        ("steals", r"\bsteal(?:s)?\b|\bkleps(?:imo|imata)\b|κλ[έε]ψιμο"),
        ("blocks", r"\bblock(?:s|ed)?\b|\btap(?:a|es)\b|τ[άα]πα"),
        ("shots", r"\bshot(?:s)?\b|free[ -]?throw|three-pointer|two-pointer|tripont|dipont|τρ[ίι]ποντ|δ[ίι]ποντ|σουτ"),
        ("points", r"\bpoint(?:s)?\b|\bpont(?:os|oi|ous|a)\b|π[όο]ντ"),
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

@app.post("/api/chat")
async def ai_chat_handler(request: ChatRequest):
    try:
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
        )
        if not request.include_query:
            cached_payload = _get_cached_ai_search(cache_key)
            if cached_payload is not None:
                return ai_search_response(cached_payload, False)

        context = build_ai_scope_context(
            request.season_code,
            request.game_code,
        )
        contextual_message = request.message
        if context:
            contextual_message += (
                "\n\nRequired request context:\n- " + "\n- ".join(context)
            )

        generated_query, ai_usage = await generate_ai_search_text(
            provider,
            prompt_variant,
            model,
            contextual_message,
        )

        clean_sparql_query = clean_and_validate_sparql(generated_query)
        data = await query_sparql(clean_sparql_query, use_cache=False)

        if data is None:
            if request.include_query:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Η βάση SPARQL δεν απάντησε.",
                        "sparql_query": clean_sparql_query,
                        "ai_provider": provider,
                        "ai_model": model,
                        "prompt_variant": prompt_variant,
                        "ai_usage": ai_usage,
                    },
                )
            raise HTTPException(status_code=502, detail="Η βάση SPARQL δεν απάντησε.")

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
        if not request.include_query:
            _cache_ai_search(cache_key, payload)
        return ai_search_response(payload, request.include_query)
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
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as e:
        print(f"AI Search failed: {e}")
        error_text = str(e).upper()
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text or "RATE LIMIT" in error_text:
            raise HTTPException(
                status_code=429,
                detail="Το όριο χρήσης της επιλεγμένης AI υπηρεσίας έχει εξαντληθεί. Δοκίμασε αργότερα ή έλεγξε το API quota.",
            ) from e
        raise HTTPException(status_code=502, detail="Αποτυχία επεξεργασίας του AI Search.") from e


@app.get("/api/quiz/who-am-i")
async def generate_who_am_i(difficulty: str = Query("medium")):
    if client is None:
        raise HTTPException(status_code=503, detail="Το AI Search δεν έχει ρυθμιστεί. Ορίστε το GEMINI_API_KEY.")

    # 1. Βρίσκουμε ένα τυχαίο παιχνίδι (π.χ. από το 1 έως το 300) για να τραβήξουμε ένα ρόστερ
    import random
    player_ids = set()

    # Δοκιμάζουμε μέχρι 5 φορές να βρούμε ένα ματς με έγκυρο ρόστερ στη βάση
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

        # Αν βρήκαμε παίκτες, σπάμε τη λούπα και προχωράμε!
        if player_ids:
            break

    if not player_ids:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκαν παίκτες στη βάση δεδομένων αυτή τη στιγμή.")

    # 2. Επιλέγουμε τυχαίο παίκτη και τραβάμε το βιογραφικό του
    secret_player_id = random.choice(list(player_ids))
    player_bio_query = get_filtered_player_query(secret_player_id)
    player_bio = query_sparql_requests(player_bio_query)

    # 3. Prompt στο Gemini (ενσωματώνουμε τη ΔΥΣΚΟΛΙΑ!)
    prompt = f"""
    Παίζουμε το παιχνίδι 'Ποιος Είμαι;'. Ο μυστικός παίκτης μπάσκετ έχει αυτά τα στοιχεία από τη βάση:
    {player_bio}

    Ο χρήστης επέλεξε επίπεδο δυσκολίας: {difficulty.upper()}.
    Φτιάξε 3 στοιχεία (hints) για να τον μαντέψει ο χρήστης. Προσάρμοσε τα στοιχεία ανάλογα με τη δυσκολία:
    - Αν είναι EASY: Δώσε πολύ γνωστά στοιχεία (π.χ. τωρινή ομάδα, Εθνικότητα, γνωστό ρεκόρ).
    - Αν είναι MEDIUM: Μέτρια στοιχεία (π.χ. θέση, προηγούμενες ομάδες).
    - Αν είναι HARD: Πολύ ψαγμένα στατιστικά, ακριβές ύψος ή άγνωστες λεπτομέρειες.

    Επίστρεψε ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ ένα έγκυρο JSON (χωρίς markdown, χωρίς ```json), με την εξής ακριβώς δομή:
    {{
        "secret_player_name": "Ονοματεπώνυμο Παίκτη (όπως προκύπτει από τα δεδομένα)",
        "hints": ["Εδώ το πρώτο στοιχείο", "Εδώ το δεύτερο στοιχείο", "Εδώ το τρίτο στοιχείο"]
    }}
    """

    try:
        import json
        response = await client.aio.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        # Καθαρίζουμε τυχόν markdown formatting (```json ... ```)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Αποτυχία δημιουργίας κουίζ: {str(e)}")

@app.get("/api/quiz/who-is-missing")
async def generate_who_is_missing(difficulty: str = Query("medium")):
    if client is None:
        raise HTTPException(status_code=503, detail="Το AI Search δεν έχει ρυθμιστεί. Ορίστε το GEMINI_API_KEY.")

    import random
    lineup_players = []
    matchup_text = "Άγνωστος Αγώνας"
    season_text = ""

    # 1. Διαλέγουμε τυχαία σεζόν
    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]
    random_season_code, season_text = random.choice(seasons)

    # 2. Τραβάμε τα παιχνίδια της συγκεκριμένης σεζόν
    games_query = get_games_list_query(random_season_code)
    games_data = query_sparql_requests(games_query)
    games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []

    # 3. Βρίσκουμε μια πραγματική 5άδα
    for _ in range(5):
        if not games_bindings:
            break

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home Team")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road Team")

        roster_query = get_game_roster_query(game_code)
        roster_data = query_sparql_requests(roster_query)

        bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
        if not bindings:
            continue

        # Διαλέγουμε μια τυχαία φάση και παίρνουμε την πεντάδα
        random_row = random.choice(bindings)
        lineup_uri = random_row.get("homeLineup", {}).get("value", "")
        if random.choice([True, False]):  # 50% πιθανότητα να πάρουμε τους φιλοξενούμενους
            lineup_uri = random_row.get("roadLineup", {}).get("value", "")

        if "#Lineup_" in lineup_uri:
            parts = lineup_uri.split("#Lineup_")[1].split("_")
            parts = [p for p in parts if p]
            if len(parts) == 5:
                lineup_players = parts
                matchup_text = f"{home_team} - {away_team}"
                break

    if len(lineup_players) != 5:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε έγκυρη πεντάδα στη βάση.")

    # 4. Τραβάμε τα ονόματα των 5 παικτών από τη βάση
    player_names = []
    for pid in lineup_players:
        q = get_player_name_query(pid)
        res = query_sparql_requests(q)
        name = pid
        if res and res.get("results", {}).get("bindings"):
            name = res["results"]["bindings"][0].get("name", {}).get("value", pid)
        player_names.append(name)

    # 5. Κρύβουμε 1 παίκτη τυχαία
    secret_index = random.randint(0, 4)
    secret_player = player_names[secret_index]
    known_players = [name for i, name in enumerate(player_names) if i != secret_index]

    # 6. Prompt στο Gemini
    import json
    prompt = f"""
    Παίζουμε το παιχνίδι 'Ποιος Λείπει;'. Έχουμε μια πραγματική πεντάδα από αγώνα Euroleague.
    Οι 4 γνωστοί παίκτες στο παρκέ είναι οι: {', '.join(known_players)}.
    Ο 5ος παίκτης που λείπει (μυστικός) είναι ο: {secret_player}.

    Ο χρήστης επέλεξε επίπεδο δυσκολίας: {difficulty.upper()}.
    Δώσε ΜΟΝΟ ΕΝΑ στοιχείο (hint) για να τον βοηθήσεις, προσαρμοσμένο στη δυσκολία:
    - Αν είναι EASY: Πες την ομάδα του, τη θέση του ή κάτι πασίγνωστο (π.χ. 'Είναι ο βασικός Point Guard του Παναθηναϊκού').
    - Αν είναι MEDIUM: Δώσε την εθνικότητά του ή μια πρώην ομάδα του.
    - Αν είναι HARD: Κάνε το πολύ αινιγματικό (π.χ. κάποιο στατιστικό ρεκόρ ή κάτι δευτερεύον).

    Επίστρεψε ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ ένα έγκυρο JSON:
    {{
        "secret_player_name": "{secret_player}",
        "known_players": {json.dumps(known_players, ensure_ascii=False)},
        "hint": "Εδώ το κείμενο της βοήθειας (1-2 προτάσεις)"
    }}
    """

    try:
        response = await client.aio.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(clean_json)

        # Προσθέτουμε τα metadata του αγώνα στο τελικό JSON
        result_data["matchup"] = matchup_text
        result_data["season"] = f"Euroleague Season {season_text}"

        return result_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Αποτυχία: {str(e)}")

@app.get("/api/quiz/higher-or-lower")
async def generate_higher_or_lower(difficulty: str = Query("medium")):
    if client is None:
        raise HTTPException(status_code=503, detail="Το AI Search δεν έχει ρυθμιστεί.")

    import random
    import itertools

    categories = [
        {"id": "blocks", "name": "Κοψίματα (Blocks)", "func": get_defensive_anchors_query, "stat_key": "totalBlocks"},
        {"id": "fouls", "name": "Κερδισμένα Φάουλ", "func": get_foul_drawn_gravity_query, "stat_key": "totalFoulsDrawn"},
        {"id": "second_chance", "name": "Πόντοι 2ης Ευκαιρίας", "func": get_second_chance_points_query, "stat_key": "totalSecondChancePoints"}
    ]
    selected_category = random.choice(categories)

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]

    player_a = player_b = None
    matchup_text = season_text = ""
    quarter_text = ""

    # --- ΒΕΛΤΙΩΜΕΝΗ ΛΟΓΙΚΗ ΔΙΑΦΟΡΑΣ ---
    def is_valid_gap(stat1, stat2, diff_level, is_quarter):
        gap = abs(stat1 - stat2)
        if gap == 0: return False # Ποτέ ισοπαλία!

        # Αν είναι δεκάλεπτο, τα νούμερα είναι μικρά, άρα μικραίνουμε τις απαιτήσεις
        if is_quarter:
            if diff_level == "easy": return gap >= 2
            if diff_level == "medium": return gap == 1
            if diff_level == "hard": return gap == 1
        else:
            if diff_level == "easy": return gap >= 3
            if diff_level == "medium": return gap in [1, 2]
            if diff_level == "hard": return gap == 1
        return True

    # Αυξάνουμε τις προσπάθειες σε 30
    for _ in range(30):
        random_season_code, season_text = random.choice(seasons)
        games_query = get_games_list_query(random_season_code)
        games_data = query_sparql_requests(games_query)
        games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []

        if not games_bindings: continue

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

        target_quarter = None
        quarter_text = "συνολικά στο ματς"
        is_quarter = False

        if random.random() < 0.40:
            target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
            quarter_text = f"μόνο κατά τη διάρκεια του {target_quarter} δεκαλέπτου"
            is_quarter = True

        stat_query = selected_category["func"](
            game_code=game_code,
            season_code=random_season_code,
            quarter=target_quarter
        )

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        if len(bindings) >= 2:
            valid_pairs = []
            backup_pairs = [] # Σχέδιο Β: Οποιοδήποτε ζευγάρι χωρίς ισοπαλία

            for b1, b2 in itertools.combinations(bindings, 2):
                s1 = int(b1.get(selected_category["stat_key"], {}).get("value", 0))
                s2 = int(b2.get(selected_category["stat_key"], {}).get("value", 0))

                if s1 != s2:
                    backup_pairs.append((b1, b2))
                    if is_valid_gap(s1, s2, difficulty.lower(), is_quarter):
                        valid_pairs.append((b1, b2))

            # Αν δεν βρει τέλειο ζευγάρι, παίρνει το Backup για να μην βγάλει 404!
            if valid_pairs:
                sampled = random.choice(valid_pairs)
            elif backup_pairs:
                sampled = random.choice(backup_pairs)
            else:
                continue

            def get_name(row):
                pid = row.get("player", {}).get("value", "").split("/")[-1]
                res = query_sparql_requests(get_player_name_query(pid))
                if res and res.get("results", {}).get("bindings"):
                    return res["results"]["bindings"][0].get("name", {}).get("value", pid)
                return pid

            name_a = get_name(sampled[0])
            name_b = get_name(sampled[1])
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
        raise HTTPException(status_code=404, detail="Δεν βρέθηκαν στατιστικά. Δοκίμασε ξανά!")

    import json
    prompt = f"""
    Φτιάξε μια ατμοσφαιρική περιγραφή αγώνα Euroleague σε στυλ σπορτκάστερ.
    Το στατιστικό που εξετάζουμε είναι: '{selected_category['name']}'.
    Το χρονικό πλαίσιο είναι: {quarter_text}.

    Ο παίκτης {player_a['name']} είχε {player_a['stat']} {selected_category['name']} {quarter_text}.
    Ο παίκτης {player_b['name']} είχε {player_b['stat']} {selected_category['name']} {quarter_text} (ΜΗΝ αποκαλύψεις το νούμερο του {player_b['name']}).
    Ο αγώνας ήταν {matchup_text}.

    Η δυσκολία της ερώτησης είναι {difficulty.upper()}. Δώσε έμφαση στη δράση (play-by-play αίσθηση) και ρώτα στο τέλος αν ο {player_b['name']} είχε ΠΕΡΙΣΣΟΤΕΡΑ ή ΛΙΓΟΤΕΡΑ από τον {player_a['name']} ΣΤΟ ΣΥΓΚΕΚΡΙΜΕΝΟ ΧΡΟΝΙΚΟ ΠΛΑΙΣΙΟ.

    Επίστρεψε ΑΥΣΤΗΡΑ ΕΝΑ JSON:
    {{
        "question_text": "Η περιγραφή του σπορτκάστερ (μέχρι 2-3 προτάσεις)...",
        "player_a": {{"name": "{player_a['name']}", "stat": {player_a['stat']}}},
        "player_b": {{"name": "{player_b['name']}", "stat": {player_b['stat']}}},
        "category_name": "{selected_category['name']} ({quarter_text})",
        "matchup": "{matchup_text}",
        "season": "Euroleague Season {season_text}"
    }}
    """

    try:
        response = await client.aio.models.generate_content(model='gemini-3.5-flash', contents=prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Αποτυχία: {str(e)}")

@app.get("/api/quiz/top-5")
async def generate_top_5(difficulty: str = Query("medium")):
    if client is None:
        raise HTTPException(status_code=503, detail="Το AI Search δεν έχει ρυθμιστεί.")

    import random

    categories = [
        {"id": "assist_duos", "name": "Κορυφαία Δίδυμα (Ασίστ - Σκόρερ)", "func": get_top_assist_duos_query, "stat_key": "totalAssists", "stat_label": "Ασίστ"},
        {"id": "blocks", "name": "Κοψίματα (Blocks)", "func": get_defensive_anchors_query, "stat_key": "totalBlocks", "stat_label": "Μπλοκ"},
        {"id": "fouls", "name": "Κερδισμένα Φάουλ", "func": get_foul_drawn_gravity_query, "stat_key": "totalFoulsDrawn", "stat_label": "Φάουλ"},
        {"id": "second_chance", "name": "Πόντοι 2ης Ευκαιρίας", "func": get_second_chance_points_query, "stat_key": "totalSecondChancePoints", "stat_label": "Πόντοι"},
        {"id": "fast_break", "name": "Πόντοι Αιφνιδιασμού", "func": get_fast_break_specialists_query, "stat_key": "fastBreakPoints", "stat_label": "Πόντοι"}
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

        # Λογική Δυσκολίας
        if difficulty == "easy":
            # Ολόκληρη η σεζόν
            question_context = f"στη σεζόν {season_text}"
        elif difficulty == "medium" or difficulty == "hard":
            # Πρέπει να βρούμε ένα τυχαίο ματς
            games_query = get_games_list_query(random_season_code)
            games_data = query_sparql_requests(games_query)
            games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []
            if not games_bindings: continue

            random_game_row = random.choice(games_bindings)
            game_code = random_game_row.get("gameCode", {}).get("value", "")
            home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
            away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

            if difficulty == "medium":
                question_context = f"στον αγώνα {home_team} - {away_team} ({season_text})"
            else:
                target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
                question_context = f"στο {target_quarter} δεκάλεπτο του αγώνα {home_team} - {away_team} ({season_text})"

        # Εκτέλεση του query
        if selected_category["id"] == "fast_break":
            # Επειδή το fast break δεν παίρνει game_code στις τρέχουσες παραμέτρους, το τρέχουμε γενικά αν κληρωθεί,
            # ή το αποφεύγουμε. Για σιγουριά το αντικαθιστούμε με fouls αν έχει game_code.
            if game_code: selected_category = categories[2]
            stat_query = selected_category["func"]() if not game_code else selected_category["func"](game_code=game_code, season_code=random_season_code, quarter=target_quarter)
        elif selected_category["id"] == "assist_duos":
            stat_query = selected_category["func"](game_code=game_code, season_code=random_season_code, quarter=target_quarter)
        else:
            stat_query = selected_category["func"](game_code=game_code, season_code=random_season_code, quarter=target_quarter)

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        if len(bindings) >= 5:
            top_5_results = []
            # Βοηθητική συνάρτηση για τα ονόματα
            def get_name(pid):
                if not pid: return ""
                res = query_sparql_requests(get_player_name_query(pid))
                if res and res.get("results", {}).get("bindings"):
                    return res["results"]["bindings"][0].get("name", {}).get("value", pid)
                return pid

            # Διαβάζουμε τους 5 πρώτους
            for b in bindings[:5]:
                stat_val = int(b.get(selected_category["stat_key"], {}).get("value", 0))

                if selected_category["id"] == "assist_duos":
                    scorer_pid = b.get("scorer", {}).get("value", "").split("/")[-1]
                    passer_pid = b.get("passer", {}).get("value", "").split("/")[-1]
                    name_str = f"{get_name(passer_pid)} & {get_name(scorer_pid)}"
                else:
                    pid = b.get("player", {}).get("value", "").split("/")[-1]
                    name_str = get_name(pid)

                top_5_results.append({
                    "name": name_str,
                    "stat": f"{stat_val} {selected_category['stat_label']}"
                })
            break

    if len(top_5_results) < 5:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκαν 5 αποτελέσματα με αυτά τα κριτήρια.")

    # Προετοιμασία της ερώτησης
    if selected_category["id"] == "assist_duos":
        question_text = f"Ποια είναι τα Top 5 δίδυμα (Πασέρ & Σκόρερ) {question_context};"
    else:
        question_text = f"Ποιοι είναι οι Top 5 παίκτες σε {selected_category['name']} {question_context};"

    return {
        "question_text": question_text,
        "answers": top_5_results,
        "category_name": selected_category["name"],
        "difficulty": difficulty
    }

@app.get("/api/quiz/fifty-fifty")
async def generate_fifty_fifty(difficulty: str = Query("medium")):
    if client is None:
        raise HTTPException(status_code=503, detail="Το AI Search δεν έχει ρυθμιστεί.")

    import random

    # --- ΠΡΟΣΘΗΚΗ: Top Assist Duos και Top Lineups ---
    categories = [
        {"id": "blocks", "name": "Κοψίματα (Blocks)", "func": get_defensive_anchors_query, "stat_key": "totalBlocks"},
        {"id": "fouls", "name": "Κερδισμένα Φάουλ", "func": get_foul_drawn_gravity_query, "stat_key": "totalFoulsDrawn"},
        {"id": "second_chance", "name": "Πόντοι 2ης Ευκαιρίας", "func": get_second_chance_points_query, "stat_key": "totalSecondChancePoints"},
        {"id": "assist_duos", "name": "Συνεργασίες (Ασίστ & Σκόρερ)", "func": get_top_assist_duos_query, "stat_key": "totalAssists"},
        {"id": "top_lineups", "name": "Πόντοι Πεντάδας", "func": get_top_lineups_query, "stat_key": "totalPoints"}
    ]

    seasons = [("E2023", "2023-24"), ("E2024", "2024-25"), ("E2025", "2025-26")]

    for _ in range(30):
        selected_category = random.choice(categories)
        random_season_code, season_text = random.choice(seasons)

        games_query = get_games_list_query(random_season_code)
        games_data = query_sparql_requests(games_query)
        games_bindings = games_data.get("results", {}).get("bindings", []) if games_data else []
        if not games_bindings: continue

        random_game_row = random.choice(games_bindings)
        game_code = random_game_row.get("gameCode", {}).get("value", "")
        home_team = random_game_row.get("homeLabel", {}).get("value", "Home")
        away_team = random_game_row.get("awayLabel", {}).get("value", "Road")

        target_quarter = None
        filter_type = None
        filter_id = None
        context_text = f"στον αγώνα {home_team} - {away_team}"

        if difficulty in ["medium", "hard"]:
            target_quarter = random.choice(["1st", "2nd", "3rd", "4th"])
            context_text += f", στο {target_quarter} δεκάλεπτο"

        # Το on_court filter δεν έχει νόημα όταν ψάχνουμε ολόκληρες πεντάδες ή δίδυμα
        if difficulty == "hard" and selected_category["id"] not in ["assist_duos", "top_lineups"]:
            roster_query = get_game_roster_query(game_code)
            roster_data = query_sparql_requests(roster_query)
            r_bindings = roster_data.get("results", {}).get("bindings", []) if roster_data else []
            p_ids = set()
            for r in r_bindings:
                for uri in [r.get("homeLineup", {}).get("value", ""), r.get("roadLineup", {}).get("value", "")]:
                    if "#Lineup_" in uri:
                        for pid in uri.split("#Lineup_")[1].split("_"):
                            if pid: p_ids.add(pid)
            if p_ids:
                filter_id = random.choice(list(p_ids))
                filter_type = "on_court"
                res = query_sparql_requests(get_player_name_query(filter_id))
                on_court_name = filter_id
                if res and res.get("results", {}).get("bindings"):
                    on_court_name = res["results"]["bindings"][0].get("name", {}).get("value", filter_id)
                context_text += f", όσο βρισκόταν στο παρκέ ο {on_court_name}"

        stat_query = selected_category["func"](
            game_code=game_code,
            season_code=random_season_code,
            quarter=target_quarter,
            filter_type=filter_type,
            filter_id=filter_id
        )

        stat_data = query_sparql_requests(stat_query)
        bindings = stat_data.get("results", {}).get("bindings", []) if stat_data else []

        valid_bindings = [b for b in bindings if int(b.get(selected_category["stat_key"], {}).get("value", 0)) > 0]
        if not valid_bindings:
            continue

        selected_stat_row = random.choice(valid_bindings)
        stat_val = int(selected_stat_row.get(selected_category["stat_key"], {}).get("value", 0))

        def get_name(pid):
            if not pid: return ""
            res = query_sparql_requests(get_player_name_query(pid))
            if res and res.get("results", {}).get("bindings"):
                return res["results"]["bindings"][0].get("name", {}).get("value", pid)
            return pid

        # --- ΠΡΟΣΘΗΚΗ: Έξυπνη διαχείριση Ονομάτων (Δίδυμα & Πεντάδες) ---
        player_name = ""
        if selected_category["id"] == "assist_duos":
            scorer_pid = selected_stat_row.get("scorer", {}).get("value", "").split("/")[-1]
            passer_pid = selected_stat_row.get("passer", {}).get("value", "").split("/")[-1]
            player_name = f"το δίδυμο {get_name(passer_pid)} (Πασέρ) & {get_name(scorer_pid)} (Σκόρερ)"
        elif selected_category["id"] == "top_lineups":
            lineup_uri = selected_stat_row.get("lineup", {}).get("value", "")
            if "#Lineup_" in lineup_uri:
                pids = [p for p in lineup_uri.split("#Lineup_")[1].split("_") if p]
                names = [get_name(p) for p in pids]
                player_name = f"η πεντάδα ({', '.join(names)})"
            else:
                player_name = "η συγκεκριμένη πεντάδα"
        else:
            pid = selected_stat_row.get("player", {}).get("value", "").split("/")[-1]
            player_name = f"ο παίκτης {get_name(pid)}"

        correct_val = stat_val
        # Στις πεντάδες, τα νούμερα πόντων μπορεί να είναι μεγάλα, άρα βάζουμε +/- 1 ή 2 πόντους διαφορά
        offset = 1 if correct_val <= 5 else random.choice([1, 2])
        wrong_val = correct_val + offset if random.choice([True, False]) else correct_val - offset
        if wrong_val < 0: wrong_val = correct_val + offset

        options = [correct_val, wrong_val]
        random.shuffle(options)
        correct_index = options.index(correct_val)

        import json
        prompt = f"""
        Γράψε ΜΙΑ ΜΟΝΟ σύντομη και ενθουσιώδη ερώτηση παρουσιαστή για το παιχνίδι "50/50".
        Το υποκείμενο είναι: {player_name}.
        Η στατιστική κατηγορία είναι: {selected_category['name']}.
        Το πλαίσιο του αγώνα είναι: {context_text}.

        Η ερώτηση πρέπει να είναι άμεση (π.χ. Πόσα κοψίματα έκανε ο Τάδε στον αγώνα Δείνα στο 2ο δεκάλεπτο;)
        Επίστρεψε ΑΥΣΤΗΡΑ ΕΝΑ JSON:
        {{
            "question_text": "Η ερώτηση..."
        }}
        """
        try:
            response = await client.aio.models.generate_content(model='gemini-3.5-flash', contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            result_data = json.loads(clean_json)

            result_data["options"] = options
            result_data["correct_index"] = correct_index
            result_data["matchup"] = f"{home_team} - {away_team}"
            result_data["season"] = f"Euroleague Season {season_text}"
            return result_data
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="Δεν βρέθηκαν κατάλληλα δεδομένα. Δοκίμασε ξανά!")

# --- Block εκτέλεσης ---
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
