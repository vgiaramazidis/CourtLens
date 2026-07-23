# src/backend/app.py
import uvicorn # <-- ΠΡΟΣΘΗΚΗ: Κάνουμε import τον server
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sparql_queries import query_sparql_requests, get_filtered_shots_query

app = FastAPI(title="Euroleague API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/shots")
async def get_shots(
    game_code: str = Query("170"), 
    season_code: str = Query("E2023"),
    player: str = Query(None), 
    assist_by: str = Query(None)
):
    # 1. Κατασκευή του query
    sparql_query = get_filtered_shots_query(game_code, season_code, player, assist_by)
    
    # 2. Αποστολή στο endpoint
    data = query_sparql_requests(sparql_query)
    
    if not data:
        return {"error": "Failed to fetch data from SPARQL endpoint", "shots": []}
        
    # 3. Μορφοποίηση δεδομένων για το frontend
    shots = []
    bindings = data.get("results", {}).get("bindings", [])
    
    for result in bindings:
        raw_coords = result.get("coords", {}).get("value", "0,0")
        x, y = raw_coords.split(",")
        action_type = result.get("action_type", {}).get("value", "")
        
        shots.append({
            "action_uri": result.get("action", {}).get("value", ""),
            "x": float(x),
            "y": float(y),
            "isMade": "Made" in action_type 
        })
        
    return {"shots": shots}

# --- ΠΡΟΣΘΗΚΗ: Το παρακάτω block τρέχει όταν πατάς το βελάκι στο VS Code ---
if __name__ == "__main__":
    # Τρέχει το αρχείο 'app' και την εφαρμογή 'app'
    # Το reload=True σημαίνει ότι αν κάνεις save μια αλλαγή, ο server κάνει restart μόνος του!
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)