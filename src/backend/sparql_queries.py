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

def get_filtered_shots_query(game_code="333", season_code="E2023", player_id=None, assist_by_id=None, lineup_uri=None):
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?coords ?action_type ?home_lineup ?road_lineup ?clockTime ?quarter
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
              
        ?season bball:hasCode '{season_code}' .
        
        ?action rdf:type ?action_type .
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
        
        ?action bball:shotCoords ?coords .
        
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        OPTIONAL {{ ?action bball:clock ?clockTime . }}
        OPTIONAL {{ ?action bball:quarter ?quarter . }}
    """
    
    if player_id:
        # Έλεγχος: Είναι νούμερο (ID) ή κείμενο (Όνομα);
        if player_id.isdigit():
            query += f"\n        ?action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ."
        else:
            # Αν είναι όνομα, ψάχνουμε με CONTAINS αγνοώντας κεφαλαία/μικρά (LCASE)
            query += f"""
        ?action bball:actionPlayer ?action_player_node .
        ?action_player_node rdfs:label ?player_name_label .
        FILTER(CONTAINS(LCASE(STR(?player_name_label)), LCASE('{player_id}')))
        """
        
    if assist_by_id:
        if assist_by_id.isdigit():
            query += f"""
        ?action bball:hasAssist ?assist_action .
        ?assist_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{assist_by_id}> .
        """
        else:
            query += f"""
        ?action bball:hasAssist ?assist_action .
        ?assist_action bball:actionPlayer ?assist_player_node .
        ?assist_player_node rdfs:label ?assist_name_label .
        FILTER(CONTAINS(LCASE(STR(?assist_name_label)), LCASE('{assist_by_id}')))
        """
    if lineup_uri:
        query += f"""
        {{ ?action bball:runningHomeTeamLineup <{lineup_uri}> . }}
        UNION
        {{ ?action bball:runningRoadTeamLineup <{lineup_uri}> . }}
        """
    query += "\n    } LIMIT 500"
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



def get_top_assist_duos_query():
    """
    Επιστρέφει τα καλύτερα δίδυμα (Scorer - Passer) βάσει ασίστ.
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>

    SELECT ?scorer ?passer (COUNT(?action) AS ?totalAssists)
    WHERE {
        ?action bball:actionPlayer ?scorer ;
                bball:hasAssist ?assistAction .
        ?assistAction bball:actionPlayer ?passer .
    }
    GROUP BY ?scorer ?passer
    ORDER BY DESC(?totalAssists)
    LIMIT 10
    """

def get_second_chance_points_query():
    """
    Επιστρέφει τους κορυφαίους παίκτες σε πόντους από δεύτερη ευκαιρία (επιθετικό ριμπάουντ).
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (SUM(?points) AS ?totalSecondChancePoints)
    WHERE {
        ?action bball:isSecondChance "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
    }
    GROUP BY ?player
    ORDER BY DESC(?totalSecondChancePoints)
    LIMIT 10
    """

def get_top_lineups_query():
    """
    Επιστρέφει τις πιο παραγωγικές πεντάδες (βάσει συνολικών πόντων που σκοράρουν).
    """
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>

    SELECT ?lineup (SUM(?points) AS ?totalPoints)
    WHERE {
        # Βρίσκουμε τις ενέργειες που έδωσαν πόντους
        ?action bball:pointsAwarded ?points ;
                bball:runningHomeTeamLineup ?lineup .
    }
    # Ομαδοποιούμε με βάση την πεντάδα
    GROUP BY ?lineup
    # Φέρνουμε πρώτες τις πεντάδες με τους περισσότερους πόντους
    ORDER BY DESC(?totalPoints)
    LIMIT 10
    """

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

def get_game_lineups_query(game_code="333", season_code="E2023"):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?lineup ?teamType (GROUP_CONCAT(DISTINCT ?playerName; separator=", ") AS ?players)
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action .
        ?season bball:hasCode '{season_code}' .
        
        # Μαρκάρουμε αν η πεντάδα είναι γηπεδούχος ή φιλοξενούμενη δυναμικά
        {{ 
            ?action bball:runningHomeTeamLineup ?lineup . 
            BIND("home" AS ?teamType)
        }}
        UNION
        {{ 
            ?action bball:runningRoadTeamLineup ?lineup . 
            BIND("road" AS ?teamType)
        }}
        
        ?lineup bball:includesPlayer ?playerNode .
        ?playerNode rdfs:label ?playerName .
    }}
    GROUP BY ?lineup ?teamType
    """