# src/backend/sparql_queries.py
import requests
from analysis_queries import (
    get_fast_break_specialists_query, get_filtered_shots_query, get_top_assist_duos_query, get_second_chance_points_query, get_top_lineups_query, get_foul_drawn_gravity_query, get_defensive_anchors_query
)

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
    
    SELECT ?name ?height ?weight (GROUP_CONCAT(DISTINCT ?positionValue; separator=" / ") AS ?position) ?birthDate ?country (SAMPLE(?biography) AS ?bio) (SAMPLE(?achievements) AS ?achievements_text) (SAMPLE(?image) AS ?img)
    WHERE {{
        BIND(<https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> AS ?player)

        OPTIONAL {{ ?player rdfs:label ?name . }}
        OPTIONAL {{ ?player bball:hasHeight ?height . }}
        OPTIONAL {{ ?player bball:hasWeight ?weight . }}
        OPTIONAL {{ ?player bball:hasPosition ?positionValue . }}
        OPTIONAL {{ ?player bball:hasBirthDate ?birthDate . }}
        OPTIONAL {{ ?player bball:hasCountry ?country . }}
        OPTIONAL {{ ?player bball:hasBiography ?biography . }}
        OPTIONAL {{ ?player bball:hasAchievements ?achievements . }}
        OPTIONAL {{ ?player foaf:depiction ?image . }}
    }} 
    GROUP BY ?name ?height ?weight ?birthDate ?country
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
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT DISTINCT ?gameCode ?homeLabel ?awayLabel ?phase ?phaseGroup ?round
    WHERE {{
        ?game a bball:Game ; bball:hasCode ?gameCode ; bball:hasSeason ?season ;
              bball:homeTeam ?homeTeam ; bball:roadTeam ?roadTeam .
        ?season bball:hasCode '{season_code}' .
        ?homeTeam rdfs:label ?homeLabel .
        ?roadTeam rdfs:label ?awayLabel .
        OPTIONAL {{ ?game bball:hasPhase ?phase . }}
        OPTIONAL {{ ?game bball:hasPhaseGroup ?phaseGroup . }}
        OPTIONAL {{ ?game bball:hasRound ?round . }}
    }}
    ORDER BY DESC(xsd:integer(?gameCode))
    """


def get_player_name_query(player_id):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?name
    WHERE {{
        BIND(<https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> AS ?player)
        OPTIONAL {{ ?player rdfs:label ?fullName . }}
        OPTIONAL {{ ?participation bball:overPlayer ?player ; bball:hasJerseyName ?jerseyName . }}
        BIND(COALESCE(?fullName, ?jerseyName) AS ?name)
        FILTER(BOUND(?name))
    }} LIMIT 1
    """

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
        OPTIONAL {{ ?playerNode bball:hasPosition ?position . }}
        
        # Πακετάρουμε τα δεδομένα
        BIND(CONCAT(REPLACE(STR(?playerNode), ".*-/", ""), "|", ?playerName, "|", COALESCE(STR(?img), "NO_IMG"), "|", COALESCE(STR(?position), "")) AS ?playerInfo)
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
