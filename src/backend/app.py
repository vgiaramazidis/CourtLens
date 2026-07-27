# src/backend/app.py
import uvicorn # <-- ΠΡΟΣΘΗΚΗ: Κάνουμε import τον server
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sparql_queries import query_sparql_requests, get_filtered_shots_query, get_player_name_query, get_top_assist_duos_query, get_second_chance_points_query, get_top_lineups_query, get_clutch_time_performers_query, get_points_off_turnovers_query, get_fast_break_specialists_query, get_foul_drawn_gravity_query, get_defensive_anchors_query

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
    game_code: str = Query(None), 
    season_code: str = Query("E2023"),
    player: str = Query(None), 
    assist_by: str = Query(None),
    filter_type: str = Query(None), # "on_court" ή "referee"
    filter_id: str = Query(None)    # Το ID
):
    sparql_query = get_filtered_shots_query(game_code, season_code, player, assist_by, filter_type, filter_id)
    data = query_sparql_requests(sparql_query)

    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "shots": []}
        
    shots = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for result in bindings:
        raw_coords = result.get("coords", {}).get("value", "0,0")
        x, y = raw_coords.split(",")
        action_type = result.get("action_type", {}).get("value", "")
        
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

@app.get("/api/analytics/assist-duos")
async def get_assist_duos(
    filter_type: str = Query(None),
    filter_id: str = Query(None)
):
    # Περνάμε τα φίλτρα στο query
    query = get_top_assist_duos_query(filter_type, filter_id)
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
    filter_id: str = Query(None)
):
    query = get_second_chance_points_query(filter_type, filter_id)
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
    filter_id: str = Query(None)
):
    query = get_top_lineups_query(filter_type, filter_id)
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