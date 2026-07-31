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

def get_filtered_shots_query(game_code=None, season_code=None, player_id=None, assist_by_id=None, filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, lineup_uri=None):    
    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?action ?coords ?action_type ?home_lineup ?road_lineup ?clockTime ?quarter ?playerName
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
        ?action rdf:type ?action_type .
        FILTER(?action_type IN (bball:TwoPointShotMade, bball:TwoPointShotMissed, bball:ThreePointShotMade, bball:ThreePointShotMissed))
        
        ?action bball:shotCoords ?coords .
        
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        OPTIONAL {{ ?action bball:clock ?clockTime . }}
        OPTIONAL {{ ?action bball:quarter ?quarter . }}
        
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
        
        OPTIONAL {{ ?action bball:hasTime ?time . }}
        OPTIONAL {{ ?action bball:hasDescription ?description . }}
        OPTIONAL {{ ?action bball:hasVideoUrl ?videoUrl . }}
        OPTIONAL {{ 
            ?action bball:actionPlayer ?player .
            ?player rdfs:label ?playerLabel .
        }}
        
        FILTER(BOUND(?time))
    }}
    ORDER BY ?time
    LIMIT 500
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

def get_second_chance_points_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None):
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
    if season_code:
        query += f"\n        ?game bball:hasSeason ?season .\n        ?season bball:hasCode '{season_code}' ."
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' ."

    query += """
        ?action rdf:type bball:FoulDrawn ;
                bball:actionPlayer ?player .
    """

    # 1. Έξυπνο φίλτρο για το ποιος ΚΕΡΔΙΣΕ το φάουλ
    if fouled_id:
        if fouled_id.isdigit():
            query += f"\n        FILTER(?player = <https://www.euroleaguebasketball.net/euroleague/players/-/{fouled_id}>)"
        else:
            query += f"""
        ?player rdfs:label ?fouled_name .
        FILTER(regex(str(?fouled_name), '\\\\b{fouled_id}\\\\b', 'i'))
        """

    # 2. Έξυπνο φίλτρο για το ποιος ΕΚΑΝΕ το φάουλ
    if fouling_id:
        query += "\n        ?action bball:occuredByFoul ?foul_action ."
        if fouling_id.isdigit():
            query += f"\n        ?foul_action bball:actionPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{fouling_id}> ."
        else:
            query += f"""
        ?foul_action bball:actionPlayer ?fouling_player .
        ?fouling_player rdfs:label ?fouling_name .
        FILTER(regex(str(?fouling_name), '\\\\b{fouling_id}\\\\b', 'i'))
        """

    # 3. Έξυπνο Extra Filter (on_court)
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

    # 3. Έξυπνο Extra Filter (on_court)
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
                FILTER(regex(str(?rName), '\\\\b{fofilter_iduled_id}\\\\b', 'i'))
            }}
        )
        """
    elif filter_type == "referee" and filter_id:
        query += f"""
        ?game bball:hasPlayByPlayAction ?block_action ;
              bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .
        """

    if quarter:
        query += f'\n        ?block_action bball:quarter "{quarter}" .'

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
    return query

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

def get_games_list_query(season_code="E2023"):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?game ?homeLineup ?roadLineup
    WHERE {{
        ?game a bball:Game .
        FILTER(CONTAINS(STR(?game), "{season_code}"))
        
        ?game bball:hasPlayByPlayAction ?action .
        ?action bball:runningHomeTeamLineup ?homeLineup ;
                bball:runningRoadTeamLineup ?roadLineup .
    }} LIMIT 1000
    """

def get_game_roster_query(game_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?homeLineup ?roadLineup
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .
        
        ?action bball:runningHomeTeamLineup ?homeLineup ;
                bball:runningRoadTeamLineup ?roadLineup .
    }}
    """

def get_simulator_crunch_time_query(game_code, quarter, players_list):
    filters = ""
    for pid in players_list:
        filters += f"FILTER(CONTAINS(STR(?lineup), '{pid}'))\n        "

    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?actionTeamURI ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
    WHERE {{
        ?game a bball:Game .
        FILTER(CONTAINS(STR(?game), "/{game_code}"))
        
        ?game bball:hasPlayByPlayAction ?action .
        ?action bball:pointsAwarded ?points ;
                bball:actionTeam ?actionTeamURI .
    """
    if quarter:
        query += f"\n        ?action bball:quarter '{quarter}' .\n"

    query += f"""
        {{ ?action bball:runningHomeTeamLineup ?lineup . }}
        UNION
        {{ ?action bball:runningRoadTeamLineup ?lineup . }}

        {filters}
    }}
    GROUP BY ?actionTeamURI ?lineup
    """
    return query

def get_timeouts_query(season_code="E2023"):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT DISTINCT ?game ?clock ?homeScore ?roadScore ?homeLineup ?roadLineup
    WHERE {{
        ?game bball:hasPlayByPlayAction ?action .
        FILTER(CONTAINS(STR(?game), "{season_code}"))

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

def get_team_roster_query(game_code, team_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?lineup
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .

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

