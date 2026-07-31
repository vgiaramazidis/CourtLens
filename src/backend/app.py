# src/backend/app.py
import random

import uvicorn
from fastapi import FastAPI, Query
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
import csv
import os

# --- ΦΟΡΤΩΣΗ ΤΟΥ CSV ΜΕ ΤΟΥΣ ΧΡΟΝΟΥΣ ---
TIMELINE = []
csv_path = "game_clock_map.csv"
if os.path.exists(csv_path):
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            TIMELINE.append({
                "video_sec": float(row["video_time_sec"]),
                "clock": row["game_clock"].strip(),
                "quarter": row["quarter"].strip()
            })
    print(f"Success: The file found {csv_path}")
else:
    print(f"Attention: The file not found {csv_path}")

app = FastAPI(title="Euroleague API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/api/player/{player_id}")
async def get_player_name(player_id: str):
    query = get_player_name_query(player_id)
    data = query_sparql_requests(query)
    
    name = f"Παίκτης {player_id}" 
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

        video_seconds = 0
        target_sec = time_to_seconds(play_time)

        if target_sec is not None and quarter_val:
            closest_diff = float('inf') 

            for entry in TIMELINE:
                if entry["quarter"] == quarter_val:
                    ocr_sec = time_to_seconds(entry["clock"])
                    
                    if ocr_sec is not None:
                        diff = abs(target_sec - ocr_sec)
                        
                        if diff <= 4 and diff < closest_diff:
                            closest_diff = diff
                            video_seconds = entry["video_sec"]
                            if diff == 0:
                                break

        shots.append({
            "action_uri": result.get("action", {}).get("value", ""),
            "x": float(x),
            "y": float(y),
            "isMade": "Made" in action_type,
            "runningHomeTeamLineup": home_lineup,   
            "runningRoadTeamLineup": road_lineup,    
            "playTime": play_time,           
            "videoSeconds": video_seconds,
            "playerName": player_name
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
        
        actions.append({
            "uri": row.get("action", {}).get("value", ""),
            "type": action_type_name,
            "time": row.get("time", {}).get("value", ""),
            "description": row.get("description", {}).get("value", ""),
            "videoUrl": row.get("videoUrl", {}).get("value", None),
            "player": row.get("playerLabel", {}).get("value", "Unknown")
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
        
    games_dict = {}
    for row in data.get("results", {}).get("bindings", []):
        game_uri = row.get("game", {}).get("value", "")
        game_code = game_uri.split("/")[-1]
        
        if game_code not in games_dict:
            home_uri = row.get("homeLineup", {}).get("value", "")
            road_uri = row.get("roadLineup", {}).get("value", "")
            
            # Κόβουμε την ομάδα π.χ. "PAN" από το https://.../teams/-/PAN#Lineup_...
            home_team = home_uri.split("teams/-/")[1].split("#")[0] if "teams/-/" in home_uri else "Home"
            road_team = road_uri.split("teams/-/")[1].split("#")[0] if "teams/-/" in road_uri else "Road"
            
            games_dict[game_code] = f"{home_team} vs {road_team}"
            
    games = [{"gameCode": k, "matchup": v} for k, v in games_dict.items()]
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
        
        lineups.append({
            "uri": lineup_uri,
            "teamType": team_type,
            "players": players_str
        })
        
    return {"lineups": lineups}

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
    season_code: str = Query(None)
):
    query = get_second_chance_points_query(filter_type, filter_id, quarter, min_start, min_end, game_code,season_code)
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

# --- Block εκτέλεσης ---
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)