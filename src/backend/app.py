# src/backend/app.py
import uvicorn # <-- ΠΡΟΣΘΗΚΗ: Κάνουμε import τον server
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sparql_queries import query_sparql_requests, get_filtered_shots_query
from sparql_queries import query_sparql_requests, get_filtered_shots_query, get_player_name_query

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

# --- ΠΡΟΣΘΗΚΗ: Το παρακάτω block τρέχει όταν πατάς το βελάκι στο VS Code ---
if __name__ == "__main__":
    # Τρέχει το αρχείο 'app' και την εφαρμογή 'app'
    # Το reload=True σημαίνει ότι αν κάνεις save μια αλλαγή, ο server κάνει restart μόνος του!
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)