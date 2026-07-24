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

def get_filtered_shots_query(game_code="333", season_code="E2023", player_id=None, assist_by_id=None):
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?coords ?action_type ?playerName ?assistName ?playTime
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
              
        ?season bball:hasCode '{season_code}' .
        
       ?action rdf:type ?action_type ;
                bball:shotCoords ?coords ;
                bball:actionPlayer ?playerURI .
                
        # 1. Όνομα παίκτη για το Tooltip
        ?playerURI rdfs:label ?playerName .
        
        # 2. Χρόνος της φάσης για το Video Jump (Αν υπάρχει στην οντολογία σου, π.χ. hasTime)
        OPTIONAL {{ ?action bball:hasTime ?playTime . }}
        
        # 3. Όνομα του παίκτη που έδωσε την Ασίστ (Αν υπάρχει)
        OPTIONAL {{ 
            ?action bball:hasAssist ?assist_action .
            ?assist_action bball:actionPlayer ?assistURI .
            ?assistURI rdfs:label ?assistName .
        }}
        
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
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

def get_filtered_player_query(player_id=None):
    """
    Δημιουργεί το SPARQL query για να αντλήσει συγκεκριμένες πληροφορίες ενός παίκτη.
    """
    if not player_id:
        return ""
        
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    
    SELECT ?name ?height ?weight ?position ?birthDate ?country (SAMPLE(?biography) AS ?bio) (SAMPLE(?achievements) AS ?achievements_text) (SAMPLE(?image) AS ?img)
    WHERE {{
        BIND(<https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> AS ?player)

        OPTIONAL {{ ?player rdfs:label ?name . }}
        OPTIONAL {{ ?player bball:hasHeight ?height . }}
        OPTIONAL {{ ?player bball:hasWeight ?weight . }}
        OPTIONAL {{ ?player bball:hasPosition ?position . }}
        OPTIONAL {{ ?player bball:hasBirthDate ?birthDate . }}
        OPTIONAL {{ ?player bball:hasCountry ?country . }}
        OPTIONAL {{ ?player bball:hasBiography ?biography . }}
        OPTIONAL {{ ?player bball:hasAchievements ?achievements . }}
        OPTIONAL {{ ?player foaf:depiction ?image . }}
    }} 
    GROUP BY ?name ?height ?weight ?position ?birthDate ?country
    LIMIT 1
    """

    
    return query

def get_match_playbyplay_query(game_code="170", season_code="E2023"):
    """
    Διορθωμένη ταξινόμηση: Αγνοεί τα κενά (FILTER BOUND) ώστε να φέρει τις πραγματικές φάσεις με τη σωστή χρονική σειρά.
    """
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?actionType ?time ?description ?videoUrl ?playerLabel
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
              
        ?season bball:hasCode '{season_code}' .
        
        ?action rdf:type ?actionType .
        
        # ΠΡΟΣΟΧΗ: Αν αυτά τα 3 properties ονομάζονται αλλιώς στην οντολογία σου, πρέπει να τα αλλάξουμε
        OPTIONAL {{ ?action bball:hasTime ?time . }}
        OPTIONAL {{ ?action bball:hasDescription ?description . }}
        OPTIONAL {{ ?action bball:hasVideoUrl ?videoUrl . }}
        OPTIONAL {{ 
            ?action bball:actionPlayer ?player .
            ?player rdfs:label ?playerLabel .
        }}
        
        # Εξαναγκάζουμε να φέρει ΜΟΝΟ φάσεις που έχουν χρόνο, για να δουλέψει σωστά το ORDER BY
        FILTER(BOUND(?time))
    }}
    ORDER BY ?time
    LIMIT 500
    """

def get_play_context_query(action_uri):
    """
    Φέρνει πληροφορίες για μια συγκεκριμένη φάση: ποιοι παίκτες ήταν στο παρκέ 
    και υπολογίζει το μέσο ύψος τους.
    """
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    
    SELECT (AVG(?height) AS ?avgHeight) (GROUP_CONCAT(?playerLabel; separator=", ") AS ?playersOnCourt)
    WHERE {{
        <{action_uri}> bball:runningHomeTeamLineup ?lineup .
        ?lineup bball:hasPlayer ?player .
        ?player rdfs:label ?playerLabel ;
                bball:hasHeight ?height .
    }}
    """

def get_games_list_query(season_code="E2023"):
    """
    Bulletproof έκδοση: Παίρνει τις ομάδες και τις ενώνει (π.χ. "Panathinaikos vs Real Madrid") 
    χωρίς να ελέγχει booleans που μπορεί να σπάσουν το query.
    """
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?gameCode (GROUP_CONCAT(?teamLabel; separator=" vs ") AS ?matchup)
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode ?gameCode ;
              bball:hasSeason ?season ;
              bball:hasTeamBoxscore ?boxscore .
              
        ?season bball:hasCode '{season_code}' .
        
        ?boxscore bball:overTeam ?team .
        ?team rdfs:label ?teamLabel .
    }}
    GROUP BY ?gameCode
    LIMIT 100
    """
