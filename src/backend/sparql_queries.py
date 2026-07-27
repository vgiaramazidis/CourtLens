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

def get_filtered_shots_query(game_code=None, season_code="E2023", player_id=None, assist_by_id=None, filter_type=None, filter_id=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?action ?coords ?action_type ?home_lineup ?road_lineup
    WHERE {
        ?game a bball:Game ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
              
        ?action rdf:type ?action_type .
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
        
        ?action bball:shotCoords ?coords .
        
        OPTIONAL { ?action bball:runningHomeTeamLineup ?home_lineup . }
        OPTIONAL { ?action bball:runningRoadTeamLineup ?road_lineup . }
    """
    
    # 1. Φίλτρο Σεζόν
    if season_code:
        query += f"\n        ?season bball:hasCode '{season_code}' ."
        
    # 2. Φίλτρο Παιχνιδιού
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."
        
    # 3. Φίλτρο Παίκτη (Σουτέρ)
    if player_id:
        query += f"\n        ?action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ."
        
    # 4. Φίλτρο Ασίστ
    if assist_by_id:
        query += f"""
        ?action bball:hasAssist ?assist_action .
        ?assist_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{assist_by_id}> .
        """
        
    # 5. ΤΑ ΝΕΑ ΦΙΛΤΡΑ
    if filter_type == "referee" and filter_id:
        # Ψάχνει παιχνίδια που διαιτήτευσε αυτός ο διαιτητής (π.χ. το ID 'OJLL')
        query += f"\n        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> ."
        
    elif filter_type == "on_court" and filter_id:
        # Ψάχνει αν ο παίκτης ήταν σε ένα από τα δύο Lineups τη στιγμή του σουτ
        query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        
    query += "\n    } LIMIT 500"
    return query

def get_player_name_query(player_id):
    """
    Γενικό ερώτημα που βρίσκει το όνομα της φανέλας οποιουδήποτε παίκτη βάσει του ID του.
    """
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    
    SELECT ?name
    WHERE {{
        ?participation bball:overPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ;
                       bball:hasJerseyName ?name .
    }} LIMIT 1
    """

def get_top_assist_duos_query(filter_type=None, filter_id=None):
    """
    Επιστρέφει τα καλύτερα δίδυμα (Scorer - Passer).
    Αν δοθεί filter_type (referee ή on_court) και filter_id, φιλτράρει αντίστοιχα!
    """
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>

    SELECT ?scorer ?passer (COUNT(?action) AS ?totalAssists)
    WHERE {
        ?action bball:actionPlayer ?scorer ;
                bball:hasAssist ?assistAction .
        ?assistAction bball:actionPlayer ?passer .
    """

    # ΦΙΛΤΡΟ ΔΙΑΙΤΗΤΗ (π.χ. OJLL)
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
        
    # ΦΙΛΤΡΟ ΠΑΙΚΤΗ ΣΤΟ ΠΑΡΚΕ (π.χ. 012774)
    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    query += """
    }
    GROUP BY ?scorer ?passer
    ORDER BY DESC(?totalAssists)
    LIMIT 10
    """
    return query

def get_second_chance_points_query(filter_type=None, filter_id=None):
    """
    Επιστρέφει τους κορυφαίους παίκτες σε πόντους από δεύτερη ευκαιρία (επιθετικό ριμπάουντ).
    """
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (SUM(xsd:integer(?points)) AS ?totalSecondChancePoints)
    WHERE {
        ?action bball:isSecondChance "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
    """

    # ΦΙΛΤΡΟ 1: Διαιτητής
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
        
    # ΦΙΛΤΡΟ 2: Παίκτης στο παρκέ (teammate/opponent)
    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalSecondChancePoints)
    LIMIT 10
    """
    return query

def get_top_lineups_query(filter_type=None, filter_id=None):
    """
    Επιστρέφει τις πιο παραγωγικές πεντάδες (βάσει συνολικών πόντων που σκοράρουν).
    """
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
    WHERE {
        ?action bball:pointsAwarded ?points ;
                bball:runningHomeTeamLineup ?lineup .
    """

    # ΦΙΛΤΡΟ 1: Αν έχει μπει συγκεκριμένος διαιτητής (π.χ. OJLL)
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
        
    # ΦΙΛΤΡΟ 2: Αν ψάχνουμε πεντάδες που παίζει συγκεκριμένος παίκτης (π.χ. 012774)
    elif filter_type == "on_court" and filter_id:
        query += f"""
        FILTER (
            EXISTS {{ ?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    query += """
    }
    GROUP BY ?lineup
    ORDER BY DESC(?totalPoints)
    LIMIT 10
    """
    return query

def get_clutch_time_performers_query():
    """
    Επιστρέφει τους παίκτες που σκοράρουν τους περισσότερους πόντους 
    στο 4ο δεκάλεπτο όταν η διαφορά στο σκορ είναι 5 πόντοι ή μικρότερη.
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (SUM(xsd:integer(?points)) AS ?clutchPoints) (COUNT(?action) AS ?clutchActions)
    WHERE {
        # Ψάχνουμε ενέργειες στο 4ο δεκάλεπτο που έδωσαν πόντους
        ?action bball:quarter 4 ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points ;
                bball:runningHomeTeamScore ?homeScore ;
                bball:runningRoadTeamScore ?roadScore .
                
        # ΦΙΛΤΡΟ: Η απόλυτη διαφορά του σκορ (Home - Road) να είναι <= 5
        FILTER(ABS(xsd:integer(?homeScore) - xsd:integer(?roadScore)) <= 5)
    }
    GROUP BY ?player
    ORDER BY DESC(?clutchPoints)
    LIMIT 10
    """

def get_points_off_turnovers_query():
    """
    Επιστρέφει τις ομάδες που πετυχαίνουν τους περισσότερους πόντους 
    αμέσως μετά από λάθος (turnover) του αντιπάλου.
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?team (SUM(xsd:integer(?points)) AS ?pointsOffTurnovers)
    WHERE {
        # Βρίσκουμε τα σουτ που προήλθαν από turnover
        ?action bball:isFromTurnover "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
                
        # Βρίσκουμε την ομάδα του παίκτη μέσω της συμμετοχής
        ?participation bball:overPlayer ?player ;
                       bball:hasTeam ?team .
                       
        ?game bball:hasPlayByPlayAction ?action .
    }
    GROUP BY ?team
    ORDER BY DESC(?pointsOffTurnovers)
    LIMIT 10
    """

def get_fast_break_specialists_query():
    """
    Επιστρέφει τους κορυφαίους παίκτες στον αιφνιδιασμό (Fast Break) 
    βάσει πόντων και συνολικών προσπαθειών.
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (SUM(xsd:integer(?points)) AS ?fastBreakPoints) (COUNT(?action) AS ?totalAttempts)
    WHERE {
        # Βρίσκουμε τα σουτ που έγιναν στον αιφνιδιασμό
        ?action bball:isFastBreak "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
    }
    GROUP BY ?player
    ORDER BY DESC(?fastBreakPoints)
    LIMIT 10
    """

def get_foul_drawn_gravity_query():
    """
    Επιστρέφει τους παίκτες που κερδίζουν τα περισσότερα φάουλ 
    (ιδιαίτερα κατά τη διάρκεια προσπαθειών για σουτ).
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?player (COUNT(?action) AS ?totalFoulsDrawn)
    WHERE {
        # Εντοπίζουμε τις ενέργειες τύπου FoulDrawn
        ?action rdf:type bball:FoulDrawn ;
                bball:actionPlayer ?player .
    }
    GROUP BY ?player
    ORDER BY DESC(?totalFoulsDrawn)
    LIMIT 10
    """

def get_defensive_anchors_query():
    """
    Επιστρέφει τους κορυφαίους αμυντικούς πυλώνες (Defensive Anchors) 
    βάσει των μπλοκ (blocks) που μοιράζουν στα αντίπαλα σουτ.
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>

    SELECT ?player (COUNT(?action) AS ?totalBlocks)
    WHERE {
        # Εντοπίζουμε τα σουτ που έχουν μπλοκαριστεί και ποιος παίκτης έκανε το μπλοκ
        ?action bball:blockedBy ?player .
    }
    GROUP BY ?player
    ORDER BY DESC(?totalBlocks)
    LIMIT 10
    """