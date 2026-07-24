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

def get_filtered_shots_query(game_code=None, season_code="E2023", player_id=None, assist_by_id=None, filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None):    
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?coords ?action_type ?home_lineup ?road_lineup ?clockTime ?quarter
    WHERE {{
        ?game a bball:Game ;
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
        
        ?action bball:shotCoords ?coords .
        
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        OPTIONAL {{ ?action bball:clock ?clockTime . }}
        OPTIONAL {{ ?action bball:quarter ?quarter . }}
    """
    
    # 1. Φίλτρο Σεζόν
    if season_code:
        query += f"\n        ?season bball:hasCode '{season_code}' ."
        
    # 2. Φίλτρο Παιχνιδιού
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."
        
    # 3. Φίλτρο Παίκτη (Σουτέρ)
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
        
    # 4. Φίλτρο Ασίστ
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
    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
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
    SELECT ?name
    WHERE {{
        ?participation bball:overPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ;
                       bball:hasJerseyName ?name .
    }} LIMIT 1
    """

def get_top_assist_duos_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None):
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
def get_top_assist_duos_query(filter_type=None, filter_id=None):
    """
    Επιστρέφει τα καλύτερα δίδυμα (Scorer - Passer).
    Αν δοθεί filter_type (referee ή on_court) και filter_id, φιλτράρει αντίστοιχα!
    """
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?scorer ?passer (COUNT(?action) AS ?totalAssists)
    WHERE {
        ?action bball:actionPlayer ?scorer ;
                bball:hasAssist ?assistAction .
        ?assistAction bball:actionPlayer ?passer .
    """

    # ... (Εδώ παραμένουν τα προηγούμενα φίλτρα για filter_type / filter_id) ...

    # ΦΙΛΤΡΟ ΔΕΚΑΛΕΠΤΟΥ (π.χ. "3rd")
    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    # ΦΙΛΤΡΟ ΧΡΟΝΟΥ (Μετατροπή λεπτών σε δευτερόλεπτα)
    if min_start is not None and min_end is not None:
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        # Το χρονόμετρο μετράει αντίστροφα, άρα ?seconds <= sec_start ΚΑΙ ?seconds >= sec_end
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """
    if game_code:
        query += f"""
        ?game bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        """
        
    query += """
    }
    GROUP BY ?scorer ?passer
    ORDER BY DESC(?totalAssists)
    LIMIT 10
    """
    return query

def get_second_chance_points_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None):
    """
    Επιστρέφει τους κορυφαίους παίκτες σε πόντους από δεύτερη ευκαιρία.
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

    # ΦΙΛΤΡΑ: Διαιτητής ή Παίκτης στο παρκέ
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    # ΦΙΛΤΡΟ: Δεκάλεπτο
    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    # ΦΙΛΤΡΟ: Χρόνος (Μετατροπή λεπτών σε δευτερόλεπτα)
    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """
    if game_code:
        query += f"""
        ?game bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        """

    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalSecondChancePoints)
    LIMIT 10
    """
    return query

def get_top_lineups_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None):
    """
    Επιστρέφει τις πιο παραγωγικές πεντάδες βάσει συνολικών πόντων, με υποστήριξη φίλτρων.
    """
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
    WHERE {
        ?action bball:pointsAwarded ?points ;
                bball:runningHomeTeamLineup ?lineup .
    """

    # ΦΙΛΤΡΟ: Διαιτητής
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
    # ΦΙΛΤΡΟ: Παίκτης στην πεντάδα
    elif filter_type == "on_court" and filter_id:
        query += f"""
        FILTER (
            EXISTS {{ ?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    # ΦΙΛΤΡΟ: Δεκάλεπτο
    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    # ΦΙΛΤΡΟ: Χρόνος (Δευτερόλεπτα)
    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """
    if game_code:
        query += f"""
        ?game bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        """
        
    query += """
    }
    GROUP BY ?lineup
    ORDER BY DESC(?totalPoints)
    LIMIT 10
    """
    return query

def get_foul_drawn_gravity_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, fouled_id=None, fouling_id=None, game_code=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (COUNT(?action) AS ?totalFoulsDrawn)
    WHERE {
        ?action rdf:type bball:FoulDrawn ;
                bball:actionPlayer ?player .
    """
    
    if fouled_id:
        query += f"\n        FILTER(?player = <https://www.euroleaguebasketball.net/euroleague/players/-/{fouled_id}>)"

    if fouling_id:
        query += f"""
        ?action bball:occuredByFoul ?foul_action .
        ?foul_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{fouling_id}> .
        """

    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """
    if game_code:
        query += f"""
        ?game bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        """
    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalFoulsDrawn)
    LIMIT 10
    """
    return query

def get_defensive_anchors_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, shooter_id=None, blocker_id=None, game_code=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (COUNT(?block_action) AS ?totalBlocks)
    WHERE {
        ?block_action rdf:type bball:Block ;
                      bball:actionPlayer ?player .
    """

    # ΝΕΟ: Αν θέλουμε συγκεκριμένο αμυντικό
    if blocker_id:
        query += f"\n        FILTER(?player = <https://www.euroleaguebasketball.net/euroleague/players/-/{blocker_id}>)"

    if shooter_id:
        query += f"""
        ?shot_action bball:blockedBy ?block_action ;
                     bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{shooter_id}> .
        """
    # ΝΕΟ: Αν θέλουμε να δούμε ποιον έκοψε (π.χ. τον Φουρνιέ)
    if shooter_id:
        query += f"""
        # Συνδέουμε την τάπα με το άστοχο σουτ, και φιλτράρουμε τον σουτέρ
        ?shot_action bball:blockedBy ?block_action ;
                     bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{shooter_id}> .
        """

    # Φίλτρα διαιτητή ή αν ήταν κάποιος άλλος παίκτης στο παρκέ (όπως τα είχαμε)
    if filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?block_action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """
    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?block_action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?block_action bball:runningRoadTeamLineup ?road_lineup . }}
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """

    # Φίλτρο δεκαλέπτου
    if quarter:
        query += f'\n        ?block_action bball:quarter "{quarter}" .'

    # Φίλτρο λεπτών
    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?block_action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """
    if game_code:
        query += f"""
        ?game bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?block_action .
        """

    query += """
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
