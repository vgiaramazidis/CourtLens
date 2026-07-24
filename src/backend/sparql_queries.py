# src/backend/sparql_queries.py
import requests

def query_sparql_requests(sparql_query):
    """
    Sends a SPARQL query to the specified endpoint using standard HTTP requests.
    """
    endpoint_url = "http://93.115.20.167:8890/sparql"

    params = {
        "query": sparql_query,
        "format": "application/sparql-results+json"
    }

    try:
        response = requests.get(endpoint_url, params=params)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None

def get_filtered_shots_query(game_code="170", season_code="E2023", player_id=None, assist_by_id=None):
    """
    Δημιουργεί το SPARQL query για τα σουτ ενός συγκεκριμένου αγώνα, με προαιρετικά φίλτρα.
    """
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?action ?coords ?action_type
    WHERE {{
        # Βρίσκουμε τον αγώνα
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
              
        ?season bball:hasCode '{season_code}' .
        
        # Φιλτράρουμε μόνο τα σουτ
        ?action rdf:type ?action_type .
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
        
        # Παίρνουμε τις συντεταγμένες
        ?action bball:shotCoords ?coords .
    """
    
    if player_id:
        query += f"\n        ?action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ."
        
    if assist_by_id:
        query += f"""
        ?action bball:hasAssist ?assist_action .
        ?assist_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{assist_by_id}> .
        """
        
    query += "\n    } LIMIT 500"
    return query