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
        response = requests.get(endpoint_url, params=params, timeout=30)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None

def get_filtered_shots_query(game_code=None, season_code=None, player_id=None, assist_by_id=None, filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, lineup_uri=None):    
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?coords ?action_type ?home_lineup ?road_lineup ?clockTime ?quarter ?playerName ?teamType ?isFastBreak ?isSecondChance ?isFromTurnover ?homeScore ?roadScore
    WHERE {{
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?action ;
              bball:homeTeam ?homeTeam ;
              bball:roadTeam ?roadTeam .
    """
    if season_code:
        query += f"""
        ?game bball:hasSeason ?season .
        ?season bball:hasCode '{season_code}' .
        """
        
    query += """
        ?action rdf:type ?action_type .
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
        
        ?action bball:shotCoords ?coords ;
                bball:actionTeam ?actionTeam .

        BIND(IF(?actionTeam = ?homeTeam, "home", "road") AS ?teamType)
        
        # ΠΡΟΣΘΗΚΗ: Δηλώνουμε τη μεταβλητή ?quarter για να γεμίζει ΠΑΝΤΑ στο SELECT!
        ?action bball:quarter ?quarter .
        
        OPTIONAL { ?action bball:runningHomeTeamLineup ?home_lineup . }
        OPTIONAL { ?action bball:runningRoadTeamLineup ?road_lineup . }
        OPTIONAL { ?action bball:clock ?clockTime . }
        OPTIONAL { ?action bball:isFastBreak ?isFastBreak . }
        OPTIONAL { ?action bball:isSecondChance ?isSecondChance . }
        OPTIONAL { ?action bball:isFromTurnover ?isFromTurnover . }        
        OPTIONAL { ?action bball:runningHomeTeamScore ?homeScore . }
        OPTIONAL { ?action bball:runningRoadTeamScore ?roadScore . }
        
        ?action bball:actionPlayer ?playerNode .
        ?playerNode rdfs:label ?playerName .
    """
    
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."
        
    if player_id:
        if player_id.isdigit():
            query += f"\n        ?action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ."
        else:
            query += f"""
        FILTER(regex(str(?playerName), '\\\\b{player_id}\\\\b', 'i'))
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
        FILTER(regex(str(?assist_name_label), '\\\\b{assist_by_id}\\\\b', 'i'))
        """
        
    if lineup_uri:
        query += f"""
        {{ ?action bball:runningHomeTeamLineup <{lineup_uri}> . }}
        UNION
        {{ ?action bball:runningRoadTeamLineup <{lineup_uri}> . }}
        """
        
    if filter_type == "referee" and filter_id:
        query += f"\n        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> ."
        
    elif filter_type == "on_court" and filter_id:
        query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        
    if quarter:
        # Εδώ το αλλάζουμε ελαφρώς σε FILTER για να μην "χτυπήσει" με τη δήλωση που βάλαμε παραπάνω
        query += f'\n        FILTER(str(?quarter) = "{quarter}") .'

    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """    
        
    query += "\n    } LIMIT 500"
    return query

def get_match_playbyplay_query(game_code, season_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?action ?actionType ?clock ?quarter ?sequence ?teamType
           ?homeScore ?roadScore ?playerLabel ?isFastBreak ?isSecondChance ?isFromTurnover
           ?relatedShotClock ?relatedShotQuarter
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasPlayByPlayAction ?action ;
              bball:homeTeam ?homeTeam ;
              bball:roadTeam ?roadTeam .
              
        ?season bball:hasCode '{season_code}' .
        
        ?action rdf:type ?actionType ;
                bball:clock ?clock ;
                bball:quarter ?quarter .

        OPTIONAL {{ ?action bball:hasPlayByPlaySequence ?sequence . }}
        OPTIONAL {{ ?action bball:runningHomeTeamScore ?homeScore . }}
        OPTIONAL {{ ?action bball:runningRoadTeamScore ?roadScore . }}
        OPTIONAL {{ ?action bball:isFastBreak ?isFastBreak . }}
        OPTIONAL {{ ?action bball:isSecondChance ?isSecondChance . }}
        OPTIONAL {{ ?action bball:isFromTurnover ?isFromTurnover . }}
        OPTIONAL {{ ?action bball:actionTeam ?actionTeam . }}
        OPTIONAL {{ 
            ?action bball:actionPlayer ?player .
            ?player rdfs:label ?playerLabel .
        }}
        OPTIONAL {{
            ?relatedShot bball:hasAssist ?action ;
                         rdf:type ?relatedShotType ;
                         bball:clock ?relatedShotClock ;
                         bball:quarter ?relatedShotQuarter ;
                         bball:quarterSecondsRemaining ?relatedShotSeconds .
            ?action bball:quarterSecondsRemaining ?assistSeconds .
            VALUES ?relatedShotType {{
                bball:TwoPointShotMade
                bball:ThreePointShotMade
                bball:FreeThrowMade
            }}
            FILTER(
                ?relatedShotQuarter = ?quarter &&
                ABS(xsd:decimal(?relatedShotSeconds) - xsd:decimal(?assistSeconds)) <= 5
            )
        }}

        BIND(IF(
            BOUND(?actionTeam),
            IF(?actionTeam = ?homeTeam, "home", IF(?actionTeam = ?roadTeam, "road", "neutral")),
            "neutral"
        ) AS ?teamType)
    }}
    ORDER BY xsd:integer(COALESCE(?sequence, "9999"))
    LIMIT 1000
    """

def get_filtered_player_query(player_id=None):
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

def get_play_context_query(action_uri):
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

def get_games_list_query(season_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?gameCode ?homeLabel ?awayLabel
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode ?gameCode ;
              bball:hasSeason ?season ;
              bball:homeTeam ?homeTeam ;
              bball:roadTeam ?roadTeam .
              
        ?season bball:hasCode '{season_code}' .
        
        ?homeTeam rdfs:label ?homeLabel .
        ?roadTeam rdfs:label ?awayLabel .
    }}
    ORDER BY DESC(xsd:integer(?gameCode))
    """

def get_player_name_query(player_id):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>

    SELECT ?name
    WHERE {{
        ?participation bball:overPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> ;
                       bball:hasJerseyName ?name .
    }} LIMIT 1
    """

def get_top_assist_duos_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?scorer ?passer (COUNT(?action) AS ?totalAssists)
    WHERE {
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?action .
    """
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season .\n        ?season bball:hasCode '{season_code}' ."
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."

    query += """
        ?action bball:actionPlayer ?scorer ;
                bball:hasAssist ?assistAction .
        ?assistAction bball:actionPlayer ?passer .
    """

    # --- ΕΔΩ ΕΙΝΑΙ Η ΜΑΓΕΙΑ ΓΙΑ ΤΑ ΟΝΟΜΑΤΑ ---
    if filter_type == "on_court" and filter_id:
        query += """
        OPTIONAL { ?action bball:runningHomeTeamLineup ?home_lineup . }
        OPTIONAL { ?action bball:runningRoadTeamLineup ?road_lineup . }
        """
        # Αν είναι νούμερο (ID) κάνει το κλασικό γρήγορο URL match
        if filter_id.isdigit():
            query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        # Αν είναι κείμενο (ΟΝΟΜΑ) ψάχνει στα labels των παικτών της πεντάδας!
        else:
            query += f"""
        FILTER (
            EXISTS {{
                ?home_lineup bball:includesPlayer ?hPlayer .
                ?hPlayer rdfs:label ?hName .
                FILTER(regex(str(?hName), '\\\\b{filter_id}\\\\b', 'i'))
            }} ||
            EXISTS {{
                ?road_lineup bball:includesPlayer ?rPlayer .
                ?rPlayer rdfs:label ?rName .
                FILTER(regex(str(?rName), '\\\\b{filter_id}\\\\b', 'i'))
            }}
        )
        """
    elif filter_type == "referee" and filter_id:
        query += f"\n        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> ."

    if quarter:
        query += f'\n        ?action bball:quarter "{quarter}" .'

    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """

    query += """
    }
    GROUP BY ?scorer ?passer
    ORDER BY DESC(?totalAssists)
    LIMIT 10
    """
    return query

def get_second_chance_points_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None, player_id=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (SUM(xsd:integer(?points)) AS ?totalSecondChancePoints)
    WHERE {
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?action .
    """
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season .\n        ?season bball:hasCode '{season_code}' ."
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."

    query += """
        ?action bball:isSecondChance "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
    """

    # --- ΝΕΟ ΦΙΛΤΡΟ ΓΙΑ ΤΟΝ ΠΑΙΚΤΗ ---
    if player_id:
        if player_id.isdigit():
            query += f"\n        FILTER(?player = <https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}>)"
        else:
            query += f"""
        ?player rdfs:label ?playerName .
        FILTER(regex(str(?playerName), '\\\\b{player_id}\\\\b', 'i'))
        """
    # ----------------------------------

    if filter_type == "on_court" and filter_id:
        query += """
        OPTIONAL { ?action bball:runningHomeTeamLineup ?home_lineup . }
        OPTIONAL { ?action bball:runningRoadTeamLineup ?road_lineup . }
        """
        if filter_id.isdigit():
            query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        else:
            query += f"""
        FILTER (
            EXISTS {{
                ?home_lineup bball:includesPlayer ?hPlayer .
                ?hPlayer rdfs:label ?hName .
                FILTER(regex(str(?hName), '\\\\b{filter_id}\\\\b', 'i'))
            }} ||
            EXISTS {{
                ?road_lineup bball:includesPlayer ?rPlayer .
                ?rPlayer rdfs:label ?rName .
                FILTER(regex(str(?rName), '\\\\b{filter_id}\\\\b', 'i'))
            }}
        )
        """
    elif filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
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

    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalSecondChancePoints)
    LIMIT 10
    """
    return query

def get_top_lineups_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None):
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
    WHERE {{
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?action .
    """
    
    if season_code:
        query += f"""
        ?game bball:hasSeason ?season .
        ?season bball:hasCode '{season_code}' .
        """

    query += """
        # 1. Βρίσκουμε τους πόντους και ΠΟΙΑ ομάδα σκόραρε
        ?action bball:pointsAwarded ?points ;
                bball:actionTeam ?team .
                
        # 2. Βρίσκουμε την πεντάδα και βεβαιωνόμαστε ότι ανήκει στην ΙΔΙΑ ομάδα
        ?lineup bball:lineupTeam ?team .
        
        # 3. Ελέγχουμε τόσο τις γηπεδούχες όσο και τις φιλοξενούμενες πεντάδες
        { ?action bball:runningHomeTeamLineup ?lineup . }
        UNION
        { ?action bball:runningRoadTeamLineup ?lineup . }
    """

    if filter_type == "on_court" and filter_id:
        if filter_id.isdigit():
            query += f"""
        FILTER (
            EXISTS {{ ?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        else:
            query += f"""
        FILTER (
            EXISTS {{
                ?lineup bball:includesPlayer ?lPlayer .
                ?lPlayer rdfs:label ?lName .
                FILTER(regex(str(?lName), '\\\\b{filter_id}\\\\b', 'i'))
            }}
        )
        """
    elif filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
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
        # Εφόσον το ?game έχει ήδη οριστεί, προσθέτουμε μόνο το φίλτρο
        query += f"\n        ?game bball:hasCode '{game_code}' ."
        
    query += """
    }
    GROUP BY ?lineup
    ORDER BY DESC(?totalPoints)
    LIMIT 10
    """
    return query

def get_foul_drawn_gravity_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, fouled_id=None, fouling_id=None, game_code=None, season_code=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (COUNT(?action) AS ?totalFoulsDrawn)
    WHERE {
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?action .
    """
    
    # --- ΠΡΟΣΘΗΚΗ: Σωστή σύνδεση Season και Game Code ---
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season .\n        ?season bball:hasCode '{season_code}' ."
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."
    # ----------------------------------------------------

    query += """
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
        query += f"\n        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> ."

    elif filter_type == "on_court" and filter_id:
        query += f"""
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        """
        if filter_id.isdigit():
            query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        else:
            query += f"""
        FILTER (
            EXISTS {{
                ?home_lineup bball:includesPlayer ?hPlayer .
                ?hPlayer rdfs:label ?hName .
                FILTER(regex(str(?hName), '\\\\b{filter_id}\\\\b', 'i'))
            }} ||
            EXISTS {{
                ?road_lineup bball:includesPlayer ?rPlayer .
                ?rPlayer rdfs:label ?rName .
                FILTER(regex(str(?rName), '\\\\b{filter_id}\\\\b', 'i'))
            }}
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

    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalFoulsDrawn)
    LIMIT 10
    """
    return query

def get_defensive_anchors_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, shooter_id=None, blocker_id=None, game_code=None, season_code=None):
    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?player (COUNT(?block_action) AS ?totalBlocks)
    WHERE {
        ?game a bball:Game ;
              bball:hasPlayByPlayAction ?block_action .
    """
    
    # 1. Βασικά φίλτρα Game & Season
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season .\n        ?season bball:hasCode '{season_code}' ."
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."

    query += """
        ?block_action rdf:type bball:Block ;
                      bball:actionPlayer ?player .
    """

    if blocker_id:
        if blocker_id.isdigit():
            query += f"\n        FILTER(?player = <https://www.euroleaguebasketball.net/euroleague/players/-/{blocker_id}>)"
        else:
            query += f"""
        ?player rdfs:label ?blocker_name .
        FILTER(regex(str(?blocker_name), '\\\\b{blocker_id}\\\\b', 'i'))
        """

    # 2. Έξυπνο φίλτρο για τον ΣΟΥΤΕΡ (Shooter)
    if shooter_id:
        query += "\n        ?shot_action bball:blockedBy ?block_action ."
        if shooter_id.isdigit():
            query += f"\n        ?shot_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{shooter_id}> ."
        else:
            query += f"""
        ?shot_action bball:actionPlayer ?shooter_player .
        ?shooter_player rdfs:label ?shooter_name .
        FILTER(regex(str(?shooter_name), '\\\\b{shooter_id}\\\\b', 'i'))
        """

    # 3. Έξυπνο Extra Filter (on_court / referee)
    if filter_type == "on_court" and filter_id:
        query += """
        OPTIONAL { ?block_action bball:runningHomeTeamLineup ?home_lineup . }
        OPTIONAL { ?block_action bball:runningRoadTeamLineup ?road_lineup . }
        """
        if filter_id.isdigit():
            query += f"""
        FILTER (
            EXISTS {{ ?home_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }} ||
            EXISTS {{ ?road_lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{filter_id}> }}
        )
        """
        else:
            # Διορθώθηκε το τυπογραφικό '{fofilter_iduled_id}' σε '{filter_id}'
            query += f"""
        FILTER (
            EXISTS {{
                ?home_lineup bball:includesPlayer ?hPlayer .
                ?hPlayer rdfs:label ?hName .
                FILTER(regex(str(?hName), '\\\\b{filter_id}\\\\b', 'i'))
            }} ||
            EXISTS {{
                ?road_lineup bball:includesPlayer ?rPlayer .
                ?rPlayer rdfs:label ?rName .
                FILTER(regex(str(?rName), '\\\\b{filter_id}\\\\b', 'i'))
            }}
        )
        """
    elif filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """

    # 4. Φίλτρα Χρόνου
    if quarter:
        query += f'\n        ?block_action bball:quarter "{quarter}" .'

    if min_start is not None and min_end is not None and min_start != "" and min_end != "":
        sec_start = int(min_start) * 60
        sec_end = int(min_end) * 60
        query += f"""
        ?block_action bball:quarterSecondsRemaining ?seconds .
        FILTER(xsd:integer(?seconds) <= {sec_start} && xsd:integer(?seconds) >= {sec_end})
        """

    # Προσοχή: Αφαιρέθηκε το διπλό 'if game_code:' που υπήρχε εδώ στο τέλος!

    query += """
    }
    GROUP BY ?player
    ORDER BY DESC(?totalBlocks)
    LIMIT 10
    """
    return query

def get_game_lineups_query(game_code, season_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    
    SELECT ?teamType ?homeScore ?roadScore (GROUP_CONCAT(DISTINCT ?playerInfo; separator="@@") AS ?players)
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasSeason ?season ;
              bball:hasTeamBoxscore ?boxscore .
              
        ?season bball:hasCode '{season_code}' .
        
        OPTIONAL {{
            ?game bball:hasHomeTeamScore ?homeScore .
            ?game bball:hasRoadTeamScore ?roadScore .
        }}
        
        # Αντιστοιχίζουμε το Boxscore στην Home ή Road ομάδα
        {{ 
             ?game bball:homeTeam ?team . 
             BIND("home" AS ?teamType)
        }}
        UNION
        {{ 
             ?game bball:roadTeam ?team . 
             BIND("road" AS ?teamType)
        }}
        
        # Διαβάζουμε ΟΛΟΥΣ τους παίκτες της αποστολής από το Boxscore
        ?boxscore bball:overTeam ?team ;
                  bball:hasPlayerParticipation ?participation .
                  
        ?participation bball:overPlayer ?playerNode .
        ?playerNode rdfs:label ?playerName .
        
        # Φέρνουμε και την εικόνα αν υπάρχει
        OPTIONAL {{ ?playerNode foaf:depiction ?img . }}
        
        # Πακετάρουμε τα δεδομένα
        BIND(CONCAT(REPLACE(STR(?playerNode), ".*-/", ""), "|", ?playerName, "|", COALESCE(STR(?img), "NO_IMG")) AS ?playerInfo)
    }}
    GROUP BY ?teamType ?homeScore ?roadScore
    """
    
def get_clutch_time_performers_query():
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?player (SUM(xsd:integer(?points)) AS ?clutchPoints) (COUNT(?action) AS ?clutchActions)
    WHERE {
        ?action bball:quarter "4th" ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points ;
                bball:runningHomeTeamScore ?homeScore ;
                bball:runningRoadTeamScore ?roadScore .
        FILTER(ABS(xsd:integer(?homeScore) - xsd:integer(?roadScore)) <= 5)
    }
    GROUP BY ?player
    ORDER BY DESC(?clutchPoints)
    LIMIT 10
    """

def get_points_off_turnovers_query():
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?team (SUM(xsd:integer(?points)) AS ?pointsOffTurnovers)
    WHERE {
        ?action bball:isFromTurnover "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
                
        ?participation bball:overPlayer ?player ;
                       bball:hasTeam ?team .
                       
        ?game bball:hasPlayByPlayAction ?action .
    }
    GROUP BY ?team
    ORDER BY DESC(?pointsOffTurnovers)
    LIMIT 10
    """

def get_fast_break_specialists_query():
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?player (SUM(xsd:integer(?points)) AS ?fastBreakPoints) (COUNT(?action) AS ?totalAttempts)
    WHERE {
        ?action bball:isFastBreak "true"^^xsd:boolean ;
                bball:actionPlayer ?player ;
                bball:pointsAwarded ?points .
    }
    GROUP BY ?player
    ORDER BY DESC(?fastBreakPoints)
    LIMIT 10
    """



def get_game_roster_query(game_code, season_code=None):
    season_filter = f"?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' ." if season_code else ""
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?homeLineup ?roadLineup
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        
        {season_filter}

        ?action bball:runningHomeTeamLineup ?homeLineup ;
                bball:runningRoadTeamLineup ?roadLineup .
    }}
    """

def get_simulator_crunch_time_query(game_code, quarter, players_list, season_code=None):
    filters = ""
    for pid in players_list:
        filters += f"?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{pid}> .\n        "

    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?actionTeam ?lineupTeam ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
    WHERE {{
        ?game a bball:Game .
        
        ?game bball:hasPlayByPlayAction ?action .
        ?action bball:pointsAwarded ?points ;
                bball:actionTeam ?actionTeam .
    """
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' .\n"
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' .\n"
    if quarter:
        query += f"\n        ?action bball:quarter '{quarter}' .\n"

    query += f"""
        {{ ?action bball:runningHomeTeamLineup ?lineup . ?game bball:homeTeam ?lineupTeam . }}
        UNION
        {{ ?action bball:runningRoadTeamLineup ?lineup . ?game bball:roadTeam ?lineupTeam . }}

        {filters}
    }}
    GROUP BY ?actionTeam ?lineupTeam ?lineup
    """
    return query

def get_timeouts_query(season_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?game ?clock ?homeScore ?roadScore ?homeLineup ?roadLineup ?homeLabel ?awayLabel
    WHERE {{
        ?game bball:hasPlayByPlayAction ?action .
        FILTER(CONTAINS(STR(?game), "{season_code}"))
        OPTIONAL {{ ?game bball:homeTeam ?homeTeam . ?homeTeam rdfs:label ?homeLabel . }}
        OPTIONAL {{ ?game bball:roadTeam ?awayTeam . ?awayTeam rdfs:label ?awayLabel . }}

        ?action a ?actionType .
        FILTER(?actionType IN (bball:Timeout, bball:TimeoutTV))
        
        ?action bball:quarter "4th" ;
                bball:clock ?clock ;
                bball:quarterSecondsRemaining ?seconds ;
                bball:runningHomeTeamScore ?homeScore ;
                bball:runningRoadTeamScore ?roadScore ;
                bball:runningHomeTeamLineup ?homeLineup ;
                bball:runningRoadTeamLineup ?roadLineup .
                
        # Η ΜΕΓΑΛΗ ΑΛΛΑΓΗ: Κάτω από 1 λεπτό (60 δευτ.) Ή διαφορά κάτω από 6 πόντους
        FILTER(xsd:integer(?seconds) <= 60 || ABS(xsd:integer(?homeScore) - xsd:integer(?roadScore)) <= 6)
    }} LIMIT 200
    """

def get_team_roster_query(game_code, team_code, season_code=None):
    season_filter = f"?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' ." if season_code else ""
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?lineup
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .

        {season_filter}

        # Ψάχνουμε ΑΥΣΤΗΡΑ μόνο τις πεντάδες της συγκεκριμένης ομάδας στον συγκεκριμένο αγώνα
        {{ 
            ?action bball:runningHomeTeamLineup ?lineup . 
            FILTER(CONTAINS(STR(?lineup), "teams/-/{team_code}"))
        }}
        UNION
        {{ 
            ?action bball:runningRoadTeamLineup ?lineup . 
            FILTER(CONTAINS(STR(?lineup), "teams/-/{team_code}"))
        }}
    }}
    """
