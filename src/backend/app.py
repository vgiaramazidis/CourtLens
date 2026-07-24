# src/backend/app.py
import uvicorn # <-- ΠΡΟΣΘΗΚΗ: Κάνουμε import τον server
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sparql_queries import get_filtered_player_query, get_games_list_query, get_match_playbyplay_query, get_play_context_query, query_sparql_requests, get_filtered_shots_query, get_player_name_query, get_top_assist_duos_query, get_second_chance_points_query, get_top_lineups_query, get_clutch_time_performers_query, get_points_off_turnovers_query, get_fast_break_specialists_query, get_foul_drawn_gravity_query, get_defensive_anchors_query
import csv
import os

# --- ΦΟΡΤΩΣΗ ΤΟΥ CSV ΜΕ ΤΟΥΣ ΧΡΟΝΟΥΣ ---
CLOCK_MAP = {}
csv_path = "game_clock_map.csv"
if os.path.exists(csv_path):
    with open(csv_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Αποθηκεύει π.χ. CLOCK_MAP["08:24"] = 1020.5
            CLOCK_MAP[row["game_clock"]] = float(row["video_time_sec"])
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



@app.get("/api/player/{player_id}")
async def get_player_name(player_id: str):
    # 1. Φτιάχνουμε το δυναμικό ερώτημα
    query = get_player_name_query(player_id)
    
    # 2. Το στέλνουμε στη βάση
    data = query_sparql_requests(query)
    
    # 3. Βρίσκουμε το όνομα από την απάντηση (αν δεν υπάρχει βάζουμε απλά το ID)
    name = f"Παίκτης {player_id}" 
    bindings = data.get("results", {}).get("bindings", [])
    
    if bindings:
        name = bindings[0].get("name", {}).get("value", name)
        
    return {"id": player_id, "name": name}

@app.get("/api/shots")
async def get_shots(
    game_code: str = Query("333"), 
    season_code: str = Query("E2023"),
    player: str = Query(None), 
    assist_by: str = Query(None)
):
    sparql_query = get_filtered_shots_query(game_code, season_code, player, assist_by)
    data = query_sparql_requests(sparql_query)
    
    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "shots": []}
        
    shots = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for result in bindings:
        raw_coords = result.get("coords", {}).get("value", "0,0")
        x, y = raw_coords.split(",")
        action_type_full = result.get("action_type", {}).get("value", "")
        action_type = action_type_full.split("#")[-1] # Παίρνουμε μόνο το 'TwoPointShotMade'
        
        # --- ΠΡΟΣΘΗΚΗ: Τραβάμε τις πεντάδες από το SPARQL result (αν υπάρχουν) ---
        home_lineup = result.get("home_lineup", {}).get("value", "Άγνωστη πεντάδα")
        road_lineup = result.get("road_lineup", {}).get("value", "Άγνωστη πεντάδα")

        # --- ΝΕΟ: Παίρνουμε τον χρόνο της φάσης ---
        play_time = result.get("clockTime", {}).get("value", "") # π.χ. "08:24" (Βάλε το σωστό κλειδί αν λέγεται αλλιώς)
        
        # --- ΝΕΟ: Αντιστοίχιση με τα δευτερόλεπτα του YouTube ---
        video_seconds = 0
        if play_time:
            # Ελέγχουμε αν υπάρχει ως "09:42" ή "9:42" στο Dictionary
            if play_time in CLOCK_MAP:
                video_seconds = CLOCK_MAP[play_time]
            elif play_time.lstrip("0") in CLOCK_MAP:
                video_seconds = CLOCK_MAP[play_time.lstrip("0")]

        shots.append({
            "action_uri": result.get("action", {}).get("value", ""),
            "x": float(x),
            "y": float(y),
            "isMade": "Made" in action_type,
            "runningHomeTeamLineup": home_lineup,   # <-- Προσθήκη
            "runningRoadTeamLineup": road_lineup,    # <-- Προσθήκη
            "playTime": play_time,           # Το στέλνουμε για το Tooltip
            "videoSeconds": video_seconds    # Το στέλνουμε για το Video Jump!
        })
        
    return {"shots": shots}

@app.get("/api/player")
async def get_player(player: str = Query(None)):
    # 1. Κατασκευή του query
    sparql_query = get_filtered_player_query(player)
    
    # 2. Αποστολή στο endpoint
    data = query_sparql_requests(sparql_query)
    
    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "player": {}}
        
    bindings = data.get("results", {}).get("bindings", [])
    
    if not bindings:
        return {"player": {}}
        
    # Παίρνουμε την πρώτη γραμμή
    raw_player = bindings[0]
    
    # 3. Καθαρισμός: Κρατάμε ΜΟΝΟ τα 'value'
    clean_player = {}
    for key, field_data in raw_player.items():
        if isinstance(field_data, dict) and "value" in field_data:
            val = field_data["value"]
            
            # ΕΙΔΙΚΟΣ ΚΑΝΟΝΑΣ ΓΙΑ ΤΗ ΧΩΡΑ: Κρατάμε μόνο το τελευταίο κομμάτι του URL
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
        action_type_name = action_type_uri.split("#")[-1] # Παίρνουμε μόνο το όνομα (π.χ. TwoPointShotMade)
        
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
        
    games = []
    for row in data.get("results", {}).get("bindings", []):
        games.append({
            "gameCode": row.get("gameCode", {}).get("value", ""),
            "matchup": f"{row.get('homeTeamLabel', {}).get('value', '')} vs {row.get('awayTeamLabel', {}).get('value', '')}"
        })
        
    return {"games": games}

@app.get("/api/analytics/assist-duos")
async def get_assist_duos():
    query = get_top_assist_duos_query()
    data = query_sparql_requests(query)
    
    results = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for row in bindings:
        # Κόβουμε το URL για να κρατήσουμε μόνο το ID του παίκτη (π.χ. "012774")
        scorer_id = row.get("scorer", {}).get("value", "").split("/")[-1]
        passer_id = row.get("passer", {}).get("value", "").split("/")[-1]
        
        results.append({
            "scorer_id": scorer_id,
            "passer_id": passer_id,
            "total_assists": int(row.get("totalAssists", {}).get("value", 0))
        })
        
    return {"assist_duos": results}

@app.get("/api/analytics/second-chance")
async def get_second_chance():
    query = get_second_chance_points_query()
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
async def get_top_lineups():
    query = get_top_lineups_query()
    data = query_sparql_requests(query)
    
    results = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for row in bindings:
        lineup_url = row.get("lineup", {}).get("value", "")
        # Αν το URL είναι έγκυρο, εξάγουμε τα IDs της πεντάδας
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

@app.get("/api/analytics/clutch-performers")
async def get_clutch_performers():
    query = get_clutch_time_performers_query()
    data = query_sparql_requests(query)
    
    results = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for row in bindings:
        # Παίρνουμε το ID του παίκτη κόβοντας το URL
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

@app.get("/api/analytics/fouls-drawn")
async def get_fouls_drawn():
    query = get_foul_drawn_gravity_query()
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
async def get_defensive_anchors():
    query = get_defensive_anchors_query()
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


# --- ΠΡΟΣΘΗΚΗ: Το παρακάτω block τρέχει όταν πατάς το βελάκι στο VS Code ---
if __name__ == "__main__":
    # Τρέχει το αρχείο 'app' και την εφαρμογή 'app'
    # Το reload=True σημαίνει ότι αν κάνεις save μια αλλαγή, ο server κάνει restart μόνος του!
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
