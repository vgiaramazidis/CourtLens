# src/backend/app.py
import uvicorn # <-- ΠΡΟΣΘΗΚΗ: Κάνουμε import τον server
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sparql_queries import query_sparql_requests, get_filtered_shots_query
from sparql_queries import query_sparql_requests, get_filtered_shots_query, get_player_name_query

from sparql_queries import (
    query_sparql_requests, 
    get_filtered_shots_query, 
    get_filtered_player_query,
    get_match_playbyplay_query,
    get_play_context_query,
    get_games_list_query
)
app = FastAPI(title="Euroleague API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Πρόσθεσε το get_player_name_query στο import στην αρχή του αρχείου!

# ... (ο υπόλοιπος κώδικας του get_shots παραμένει ίδιος) ...

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
        
        shots.append({
            "action_uri": result.get("action", {}).get("value", ""),
            "x": float(x),
            "y": float(y),
            "isMade": "Made" in action_type,
            "runningHomeTeamLineup": home_lineup,   # <-- Προσθήκη
            "runningRoadTeamLineup": road_lineup    # <-- Προσθήκη
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

# --- ΠΡΟΣΘΗΚΗ: Το παρακάτω block τρέχει όταν πατάς το βελάκι στο VS Code ---
if __name__ == "__main__":
    # Τρέχει το αρχείο 'app' και την εφαρμογή 'app'
    # Το reload=True σημαίνει ότι αν κάνεις save μια αλλαγή, ο server κάνει restart μόνος του!
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
