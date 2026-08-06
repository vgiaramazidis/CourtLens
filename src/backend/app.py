# src/backend/app.py
import asyncio
import csv
import json
import os
import random
import re
from functools import lru_cache
from pathlib import Path

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

app = FastAPI(title="Euroleague API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
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

def find_video_seconds(play_time, quarter, season_code="E2023", game_code="333"):
    target_sec = time_to_seconds(play_time)
    if target_sec is None or not quarter:
        return 0

    game_config = get_video_game_config(season_code, game_code)
    if not game_config:
        return 0
    timeline = load_video_timeline(str(game_config.get("timeline_file", "")))

    closest_diff = float("inf")
    matched_video_seconds = 0
    for entry in timeline:
        if entry["quarter"] != quarter:
            continue
        ocr_sec = time_to_seconds(entry["clock"])
        if ocr_sec is None:
            continue
        diff = abs(target_sec - ocr_sec)
        if diff <= 4 and diff < closest_diff:
            closest_diff = diff
            matched_video_seconds = entry["video_sec"]
            if diff == 0:
                break
    return matched_video_seconds

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
    data = query_sparql_requests(query)
    
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
    season_code: str = Query("E2023"),
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
    data = query_sparql_requests(sparql_query)

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
        quarter_val = result.get("quarter", {}).get("value", "")
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
    data = query_sparql_requests(sparql_query)
    
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
async def get_match_pbp(game_code: str = Query("170"), season_code: str = Query("E2023")):
    sparql_query = get_match_playbyplay_query(game_code, season_code)
    data = query_sparql_requests(sparql_query)
    
    if not data:
        return {"error": "Failed to fetch play-by-play", "actions": []}
        
    actions = []
    for row in data.get("results", {}).get("bindings", []):
        action_type_uri = row.get("actionType", {}).get("value", "")
        action_type_name = action_type_uri.split("#")[-1] 
        play_time = row.get("clock", {}).get("value", "")
        quarter = row.get("quarter", {}).get("value", "")
        home_score = row.get("homeScore", {}).get("value", "0")
        road_score = row.get("roadScore", {}).get("value", "0")
        
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
            "videoSeconds": find_video_seconds(play_time, quarter, season_code, game_code)
        })
        
    return {"actions": actions}

@app.get("/api/play/context")
async def get_play_context(action_uri: str = Query(...)):
    sparql_query = get_play_context_query(action_uri)
    data = query_sparql_requests(sparql_query)
    
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
async def get_games(season_code: str = Query("E2023")):
    sparql_query = get_games_list_query(season_code)
    data = query_sparql_requests(sparql_query)
    
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
async def get_game_lineups(game_code: str = Query("333"), season_code: str = Query("E2023")):
    sparql_query = get_game_lineups_query(game_code, season_code)
    data = query_sparql_requests(sparql_query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
    data = query_sparql_requests(query)
    
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
async def get_simulator_scenario(season_code: str = Query("E2023")):
    # 1. Φέρνουμε όλα τα Timeouts του 4ου δεκαλέπτου
    query = get_timeouts_query(season_code)
    data = query_sparql_requests(query)
    
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
    
    # 3. Σε κάνουμε τυχαία προπονητή είτε των Γηπεδούχων είτε των Φιλοξενούμενων!
    is_home = random.choice([True, False])
    user_team = home_team if is_home else road_team
    opponent = road_team if is_home else home_team
    user_score = home_score if is_home else road_score
    opp_score = road_score if is_home else home_score
    
    # 4. Φέρνουμε ΜΟΝΟ τους δικούς σου παίκτες (όσους έπαιξαν σε αυτό το ματς)
    roster_query = get_team_roster_query(game_code, user_team)
    roster_data = query_sparql_requests(roster_query)
    
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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# The backend can still start without Gemini configured; /api/chat reports a clear 503 instead.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# 2. Το System Prompt παραμένει το ίδιο
euroleague_system_prompt = """
Είσαι ένας έμπειρος προγραμματιστής SPARQL και ειδικός σε σημασιολογικά μοντέλα δεδομένων για αθλητικά γεγονότα, χρησιμοποιώντας το FORTH Basketball Ontology.
Στόχος σου είναι να μεταφράζεις τις ερωτήσεις του χρήστη ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ σε έγκυρο κώδικα SPARQL.
Απαγορεύεται να επιστρέψεις markdown blocks (π.χ. ```sparql), HTML, ή οποιοδήποτε άλλο κείμενο.
Να επιστρέφεις μόνο read-only SELECT ή ASK queries. Απαγορεύονται UPDATE operations και SERVICE clauses.

Να χρησιμοποιείς ΠΑΝΤΑ αυτά τα Namespaces:
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

ΒΑΣΙΚΕΣ ΚΛΑΣΕΙΣ (rdf:type):
- bball:PeriodStart, bball:JumpBall, bball:ThreePointShotMade, bball:ThreePointShotMissed, bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:FreeThrowMade, bball:FreeThrowMissed, bball:Assist, bball:OffensiveRebound, bball:Steal

ΑΥΣΤΗΡΟ ΛΕΞΙΛΟΓΙΟ ΚΑΙ ΚΑΝΟΝΕΣ (ΜΗΝ ΕΦΕΥΡΙΣΚΕΙΣ ΙΔΙΟΤΗΤΕΣ):
1. Δομή Αγώνα & Σεζόν:
   ?game a bball:Game ; bball:hasSeason ?season ; bball:hasCode "333" .
   ?season bball:hasCode "E2023" .
2. Σύνδεση Ενεργειών:
   ?game bball:hasPlayByPlayAction ?action .
   ?action bball:hasPlayByPlaySequence ?order .
3. Στατιστικά Ενέργειας:
   - Πόντοι: bball:pointsAwarded ?points . (Για άθροισμα ΠΑΝΤΑ: SUM(xsd:integer(?points)))
   - Παίκτης (Δράστης): bball:actionPlayer ?player .
   - Ομάδα (Δράστης): bball:actionTeam ?team .
   - Ασίστ: ?action bball:hasAssist ?assist . ?assist bball:actionPlayer ?pl .
   - Ζώνη Σουτ: bball:shotZone "I" .
4. Πεντάδες στο παρκέ:
   Χρησιμοποίησε τα bball:runningHomeTeamLineup ή bball:runningRoadTeamLineup.
   ?lineup bball:includesPlayer ?player .
5. Πληροφορίες Παικτών:
   - Ύψος: bball:hasHeight ?height . (Για μέσο όρο: AVG(xsd:float(?height)))
   - Ηλικία/Γέννηση: bball:hasBirthDate ?date .
6. Κατοχές (Possessions):
   ?game bball:hasPossession ?possession .
   ?possession bball:hasPossessionSequence ?seq .
   ?possession bball:startsAfterAction ?action .

ΣΥΝΔΕΣΗ ΜΕ PLAY-BY-PLAY:
- Όταν η ερώτηση ζητά συγκεκριμένες φάσεις ή ενέργειες (π.χ. "δείξε όλους τους πόντους/σουτ/ασίστ του Sloukas"), το SELECT ΠΡΕΠΕΙ να περιλαμβάνει DISTINCT ?action.
- Το ?action πρέπει να είναι ακριβώς το URI της ενέργειας που συνδέεται με ?game bball:hasPlayByPlayAction ?action.
- Για πόντους χρησιμοποίησε bball:pointsAwarded ?points και FILTER(xsd:integer(?points) > 0).
- Πρόσθεσε χρήσιμα πεδία όπως ?playerName, ?points, ?quarter και ?clock όταν είναι διαθέσιμα.
- Μόνο όταν ο χρήστης ζητά αποκλειστικά αριθμητικό σύνολο (π.χ. "πόσους πόντους συνολικά") μπορείς να επιστρέψεις aggregate χωρίς ?action.


ΑΝΑΖΗΤΗΣΗ ΟΝΟΜΑΤΩΝ (ΠΑΝΤΑ ΜΕ REGEX):
?player rdfs:label ?playerName .
FILTER(regex(str(?playerName), '\\bΟΝΟΜΑ\\b', 'i'))
ΣΗΜΑΝΤΙΚΟ: Αν ο χρήστης ρωτάει στα Ελληνικά, ΠΡΕΠΕΙ ΠΑΝΤΑ να μεταγράφεις το όνομα του παίκτη σε λατινικούς χαρακτήρες (Αγγλικά) μέσα στο regex (π.χ. "σλουκας" -> "sloukas", "χεζονια" -> "hezonja").

ΠΑΡΑΔΕΙΓΜΑ:
Ερώτηση: "Βρες ποιος παίκτης έδωσε ασίστ στο πρώτο εύστοχο τρίποντο"
Απάντηση:
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

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    game_code: str | None = Field(default=None, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    season_code: str | None = Field(default=None, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


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
    return bool(select_match and re.search(r"\?action\b", select_match.group(1), flags=re.IGNORECASE))


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

@app.post("/api/chat")
async def ai_chat_handler(request: ChatRequest):
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Το AI Search δεν έχει ρυθμιστεί. Ορίστε το GEMINI_API_KEY στο backend environment.",
        )

    try:
        context = []
        if request.season_code:
            context.append(f'Περιορίσε το query στη σεζόν με bball:hasCode "{request.season_code}".')
        if request.game_code:
            context.append(f'Περιορίσε το query στον αγώνα με bball:hasCode "{request.game_code}".')

        contextual_message = request.message
        if context:
            contextual_message += "\n\nΥποχρεωτικό context:\n- " + "\n- ".join(context)

        response = await client.aio.models.generate_content(
            model='gemini-3.5-flash',
            contents=contextual_message,
            config=types.GenerateContentConfig(
                system_instruction=euroleague_system_prompt,
            )
        )

        clean_sparql_query = clean_and_validate_sparql(response.text)
        data = await asyncio.to_thread(query_sparql_requests, clean_sparql_query)

        if data is None:
            raise HTTPException(status_code=502, detail="Η βάση SPARQL δεν απάντησε.")

        results = data.get("results", {}).get("bindings", [])
        playbyplay_filter = query_selects_playbyplay_actions(clean_sparql_query)

        return {
            "generated_query": clean_sparql_query,
            "results": results,
            "boolean": data.get("boolean"),
            "playbyplay_filter": playbyplay_filter,
            "action_uris": extract_playbyplay_action_uris(results) if playbyplay_filter else []
        }
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as e:
        print(f"AI Search failed: {e}")
        raise HTTPException(status_code=502, detail="Αποτυχία επεξεργασίας του AI Search.") from e

# --- Block εκτέλεσης ---
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
