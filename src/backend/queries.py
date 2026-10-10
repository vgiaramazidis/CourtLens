"""SPARQL query builders and shared validation for CourtLens."""

import json
import re

PREFIXES = """PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
PLAYER_BASE = "https://www.euroleaguebasketball.net/euroleague/players/-/"


class AnalysisFilterError(ValueError):
    pass


def literal(value):
    return json.dumps(str(value), ensure_ascii=False)


def player_filter(variable, value):
    if not value:
        return ""
    tokens = re.findall(r"[\w'-]+", str(value), re.UNICODE)
    if not tokens or len(str(value)) > 150:
        raise AnalysisFilterError("Enter a player name or player ID.")
    conditions = " && ".join(
        f"CONTAINS(LCASE(STR(?filterName)), LCASE({literal(token)}))" for token in tokens
    )
    return f"""FILTER(STR({variable}) = {literal(PLAYER_BASE + str(value))} || EXISTS {{
        {variable} rdfs:label ?filterName . FILTER({conditions}) }})"""


def filters(
    action="?action",
    game_code=None,
    season_code=None,
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
):
    parts = []
    for value, variable, relation in [
        (season_code, "?seasonCode", "?game bball:hasSeason/bball:hasCode ?seasonCode ."),
        (game_code, "?gameCode", "?game bball:hasCode ?gameCode ."),
    ]:
        if value and value != "ALL":
            codes = [code.strip() for code in value.split(",")]
            if not all(re.fullmatch(r"[A-Za-z0-9_-]+", code) for code in codes):
                raise AnalysisFilterError("Choose a valid season or game.")
            parts.append(relation + f" FILTER({variable} IN ({', '.join(map(literal, codes))}))")
    if game_code and (not season_code or season_code == "ALL" or "," in season_code):
        raise AnalysisFilterError("Choose one season before selecting a game.")
    if quarter:
        if quarter not in ("1st", "2nd", "3rd", "4th", "OT"):
            raise AnalysisFilterError("Choose a valid period.")
        parts.append(f"{action} bball:quarter ?filterQuarter .")
        parts.append(
            'FILTER(REGEX(STR(?filterQuarter), "OT|Overtime", "i"))'
            if quarter == "OT"
            else f"FILTER(STR(?filterQuarter) = {literal(quarter)})"
        )
    if min_start not in (None, "") or min_end not in (None, ""):
        try:
            start, end = int(min_start), int(min_end)
        except (ValueError, TypeError):
            raise AnalysisFilterError("Enter both clock limits as whole minutes.")
        if not 0 <= end <= start <= (5 if quarter == "OT" else 10):
            raise AnalysisFilterError(
                "Clock limits must descend from 10 to 0 minutes (5 to 0 in overtime)."
            )
        parts.append(
            f"{action} bball:quarterSecondsRemaining ?seconds . FILTER(xsd:integer(?seconds) <= {start * 60} && xsd:integer(?seconds) >= {end * 60})"
        )
    if filter_type:
        if filter_type not in ("on_court", "referee") or not filter_id:
            raise AnalysisFilterError("Choose a player or referee for the context filter.")
        if filter_type == "on_court":
            parts.append(f"""FILTER EXISTS {{
                {{ {action} bball:runningHomeTeamLineup ?filterLineup . }} UNION
                {{ {action} bball:runningRoadTeamLineup ?filterLineup . }}
                ?filterLineup bball:includesPlayer ?filterPlayer .
                {player_filter("?filterPlayer", filter_id)} }}""")
        else:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", filter_id):
                raise AnalysisFilterError("Enter the referee ID from the data source.")
            parts.append(
                f"?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> ."
            )
    return "\n".join(parts)


def get_filtered_shots_query(
    game_code=None,
    season_code=None,
    player_id=None,
    assist_by_id=None,
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    lineup_uri=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    extra = player_filter("?playerNode", player_id)
    if assist_by_id:
        extra += "?action bball:hasAssist/bball:actionPlayer ?assistPlayer . " + player_filter(
            "?assistPlayer", assist_by_id
        )
    if lineup_uri:
        if not re.fullmatch(
            r"https://www\.euroleaguebasketball\.net/euroleague/teams/[-/A-Za-z0-9]+#Lineup_[A-Za-z0-9_]+",
            lineup_uri,
        ):
            raise AnalysisFilterError("Choose a lineup from the results to inspect its shots.")
        extra += f"FILTER(?home_lineup = <{lineup_uri}> || ?road_lineup = <{lineup_uri}>)"
    # Group by the event URI so aliases and historical photos cannot consume the limit.
    limit = "" if game_code else "LIMIT 500"
    # Bound unique action IDs before loading photos/labels for cross-game browsing.
    # Full games remain complete, including long overtime games.
    candidates = ""
    if not game_code:
        candidates = f"""{{ SELECT DISTINCT ?action WHERE {{
            ?game a bball:Game ; bball:hasPlayByPlayAction ?action .
            {scope}
            VALUES ?action_type {{ bball:TwoPointShotMade bball:TwoPointShotMissed bball:ThreePointShotMade bball:ThreePointShotMissed }}
            ?action rdf:type ?action_type ; bball:actionPlayer ?playerNode .
            OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
            OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
            {extra}
        }} ORDER BY ?action LIMIT 500 }}"""
    return (
        PREFIXES
        + f"""SELECT ?action (?coordsValue AS ?coords)
           (?action_typeValue AS ?action_type)
           (?home_lineupValue AS ?home_lineup)
           (?road_lineupValue AS ?road_lineup)
           (?clockTimeValue AS ?clockTime)
           (?quarterValue AS ?quarter)
           (?playerNameValue AS ?playerName)
           (?playerImgValue AS ?playerImg)
           (?teamTypeValue AS ?teamType)
           (?isFastBreakValue AS ?isFastBreak)
           (?isSecondChanceValue AS ?isSecondChance)
           (?isFromTurnoverValue AS ?isFromTurnover)
           (?homeScoreValue AS ?homeScore)
           (?roadScoreValue AS ?roadScore)
           (?playerNodeValue AS ?playerNode)
           (?sequenceValue AS ?sequence)
    WHERE {{ {{
    SELECT ?action (MIN(?coords) AS ?coordsValue)
           (MIN(?action_type) AS ?action_typeValue)
           (MIN(?home_lineup) AS ?home_lineupValue)
           (MIN(?road_lineup) AS ?road_lineupValue)
           (MIN(?clockTime) AS ?clockTimeValue)
           (MIN(?quarter) AS ?quarterValue)
           (MIN(STR(?playerName)) AS ?playerNameValue)
           (MIN(STR(?playerImg)) AS ?playerImgValue)
           (MIN(?teamType) AS ?teamTypeValue)
           (MIN(?isFastBreak) AS ?isFastBreakValue)
           (MIN(?isSecondChance) AS ?isSecondChanceValue)
           (MIN(?isFromTurnover) AS ?isFromTurnoverValue)
           (MIN(?homeScore) AS ?homeScoreValue)
           (MIN(?roadScore) AS ?roadScoreValue)
           (MIN(?playerNode) AS ?playerNodeValue)
           (MIN(?sequence) AS ?sequenceValue) WHERE {{
        {candidates}
        ?game a bball:Game ; bball:hasPlayByPlayAction ?action ; bball:homeTeam ?homeTeam ; bball:roadTeam ?roadTeam .
        {scope}
        VALUES ?action_type {{ bball:TwoPointShotMade bball:TwoPointShotMissed bball:ThreePointShotMade bball:ThreePointShotMissed }}
        ?action rdf:type ?action_type ; bball:actionTeam ?actionTeam ; bball:quarter ?quarter ; bball:actionPlayer ?playerNode .
        OPTIONAL {{ ?playerNode rdfs:label ?playerName . }}
        OPTIONAL {{ ?action bball:hasPlayByPlaySequence ?sequence . }}
        OPTIONAL {{ ?playerNode foaf:depiction ?playerImg . }}
        BIND(IF(?actionTeam = ?homeTeam, "home", "road") AS ?teamType)
        OPTIONAL {{ ?action bball:shotCoords ?coords . }}
        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?home_lineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?road_lineup . }}
        OPTIONAL {{ ?action bball:clock ?clockTime . }}
        OPTIONAL {{ ?action bball:isFastBreak ?isFastBreak . }}
        OPTIONAL {{ ?action bball:isSecondChance ?isSecondChance . }}
        OPTIONAL {{ ?action bball:isFromTurnover ?isFromTurnover . }}
        OPTIONAL {{ ?action bball:runningHomeTeamScore ?homeScore . }}
        OPTIONAL {{ ?action bball:runningRoadTeamScore ?roadScore . }}
        {extra}
    }} GROUP BY ?action }} }} ORDER BY xsd:integer(?sequence) ?action {limit}"""
    )


def aggregate(select, body, group, metric, scope):
    # Subqueries deduplicate events before aggregation when the RDF has repeated labels/relations.
    return (
        PREFIXES
        + f"""SELECT {select} WHERE {{
        {{ SELECT DISTINCT {group} ?action ?points WHERE {{
            ?game a bball:Game ; bball:hasPlayByPlayAction ?action .
            {scope} {body}
        }} }}
    }} GROUP BY {group} ORDER BY DESC(?{metric}) {group} LIMIT 10"""
    )


def get_top_assist_duos_query(
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    game_code=None,
    season_code=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    return aggregate(
        "?scorer ?passer (COUNT(DISTINCT ?action) AS ?totalAssists)",
        "?action bball:actionPlayer ?scorer ; bball:hasAssist/bball:actionPlayer ?passer .",
        "?scorer ?passer",
        "totalAssists",
        scope,
    )


def get_second_chance_points_query(
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    game_code=None,
    season_code=None,
    player_id=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    return aggregate(
        "?player (SUM(xsd:integer(?points)) AS ?totalSecondChancePoints)",
        "?action bball:isSecondChance true ; bball:actionPlayer ?player ; bball:pointsAwarded ?points . "
        + player_filter("?player", player_id),
        "?player",
        "totalSecondChancePoints",
        scope,
    )


def get_top_lineups_query(
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    game_code=None,
    season_code=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    return aggregate(
        "?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)",
        """
        ?action bball:pointsAwarded ?points ; bball:actionTeam ?team .
        ?lineup bball:lineupTeam ?team .
        { ?action bball:runningHomeTeamLineup ?lineup . } UNION { ?action bball:runningRoadTeamLineup ?lineup . }
        """,
        "?lineup",
        "totalPoints",
        scope,
    )


def get_foul_drawn_gravity_query(
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    fouled_id=None,
    fouling_id=None,
    game_code=None,
    season_code=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    body = "?action a bball:FoulDrawn ; bball:actionPlayer ?player . " + player_filter(
        "?player", fouled_id
    )
    if fouling_id:
        body += "?action bball:occuredByFoul/bball:actionPlayer ?foulingPlayer . " + player_filter(
            "?foulingPlayer", fouling_id
        )
    return aggregate(
        "?player (COUNT(DISTINCT ?action) AS ?totalFoulsDrawn)",
        body,
        "?player",
        "totalFoulsDrawn",
        scope,
    )


def get_defensive_anchors_query(
    filter_type=None,
    filter_id=None,
    quarter=None,
    min_start=None,
    min_end=None,
    shooter_id=None,
    blocker_id=None,
    game_code=None,
    season_code=None,
):
    scope = filters(
        "?action", game_code, season_code, filter_type, filter_id, quarter, min_start, min_end
    )
    body = "?action a bball:Block ; bball:actionPlayer ?player . " + player_filter(
        "?player", blocker_id
    )
    if shooter_id:
        body += "?shot bball:blockedBy ?action ; bball:actionPlayer ?shooter . " + player_filter(
            "?shooter", shooter_id
        )
    return aggregate(
        "?player (COUNT(DISTINCT ?action) AS ?totalBlocks)", body, "?player", "totalBlocks", scope
    )


def get_fast_break_specialists_query(game_code=None, season_code=None, quarter=None):
    scope = filters(game_code=game_code, season_code=season_code, quarter=quarter)
    return aggregate(
        "?player (SUM(xsd:integer(?points)) AS ?fastBreakPoints) (COUNT(DISTINCT ?action) AS ?totalAttempts)",
        "?action bball:isFastBreak true ; bball:actionPlayer ?player ; bball:pointsAwarded ?points .",
        "?player",
        "fastBreakPoints",
        scope,
    )


def get_match_playbyplay_query(game_code, season_code):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?action (?actionTypeValue AS ?actionType)
           (?clockValue AS ?clock)
           (?quarterValue AS ?quarter)
           (?sequenceValue AS ?sequence)
           (?teamTypeValue AS ?teamType)
           (?homeScoreValue AS ?homeScore)
           (?roadScoreValue AS ?roadScore)
           (?playerLabelValue AS ?playerLabel)
           (?isFastBreakValue AS ?isFastBreak)
           (?isSecondChanceValue AS ?isSecondChance)
           (?isFromTurnoverValue AS ?isFromTurnover)
           (?relatedShotClockValue AS ?relatedShotClock)
           (?relatedShotQuarterValue AS ?relatedShotQuarter)
           (?homeLineupValue AS ?homeLineup)
           (?roadLineupValue AS ?roadLineup)
           (?playerValue AS ?player)
    WHERE {{ {{
    SELECT ?action (MIN(?actionType) AS ?actionTypeValue)
           (MIN(?clock) AS ?clockValue)
           (MIN(?quarter) AS ?quarterValue)
           (MIN(?sequence) AS ?sequenceValue)
           (MIN(?teamType) AS ?teamTypeValue)
           (MIN(?homeScore) AS ?homeScoreValue)
           (MIN(?roadScore) AS ?roadScoreValue)
           (MIN(STR(?playerLabel)) AS ?playerLabelValue)
           (MIN(?isFastBreak) AS ?isFastBreakValue)
           (MIN(?isSecondChance) AS ?isSecondChanceValue)
           (MIN(?isFromTurnover) AS ?isFromTurnoverValue)
           (MIN(?relatedShotClock) AS ?relatedShotClockValue)
           (MIN(?relatedShotQuarter) AS ?relatedShotQuarterValue)
           (MIN(?homeLineup) AS ?homeLineupValue)
           (MIN(?roadLineup) AS ?roadLineupValue)
           (MIN(?player) AS ?playerValue)
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

        OPTIONAL {{ ?action bball:runningHomeTeamLineup ?homeLineup . }}
        OPTIONAL {{ ?action bball:runningRoadTeamLineup ?roadLineup . }}
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
    GROUP BY ?action }} }}
    ORDER BY xsd:integer(COALESCE(?sequence, "9999")) ?action
    """


def get_filtered_player_query(player_id=None):
    if not player_id:
        return ""

    query = f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    
    SELECT (MIN(STR(?nameValue)) AS ?name) ?height ?weight (GROUP_CONCAT(DISTINCT ?positionValue; separator=" / ") AS ?position) ?birthDate ?country (SAMPLE(?biography) AS ?bio)
           (SAMPLE(?achievements) AS ?achievements_text)
           (MIN(STR(?image)) AS ?img)
    WHERE {{
        BIND(<https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}> AS ?player)

        OPTIONAL {{ ?player rdfs:label ?nameValue . }}
        OPTIONAL {{ ?player bball:hasHeight ?height . }}
        OPTIONAL {{ ?player bball:hasWeight ?weight . }}
        OPTIONAL {{ ?player bball:hasPosition ?positionValue . }}
        OPTIONAL {{ ?player bball:hasBirthDate ?birthDate . }}
        OPTIONAL {{ ?player bball:hasCountry ?country . }}
        OPTIONAL {{ ?player bball:hasBiography ?biography . }}
        OPTIONAL {{ ?player bball:hasAchievements ?achievements . }}
        OPTIONAL {{ ?player foaf:depiction ?image . }}
    }} 
    GROUP BY ?height ?weight ?birthDate ?country
    LIMIT 1
    """
    return query


def get_play_context_query(action_uri):
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT DISTINCT ?player ?playerLabel ?height
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
      {{ SELECT ?teamType ?homeScore ?roadScore ?playerNode
          (MIN(STR(?nameValue)) AS ?playerName)
          (MIN(STR(?imageValue)) AS ?img)
          (GROUP_CONCAT(DISTINCT ?positionValue; separator=" / ") AS ?position)
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
        
        # Match each box score to its home or road team.
        {{ 
             ?game bball:homeTeam ?team . 
             BIND("home" AS ?teamType)
        }}
        UNION
        {{ 
             ?game bball:roadTeam ?team . 
             BIND("road" AS ?teamType)
        }}
        
        # Include the full game roster, not just the players in one lineup.
        ?boxscore bball:overTeam ?team ;
                  bball:hasPlayerParticipation ?participation .
                  
        ?participation bball:overPlayer ?playerNode .
        ?playerNode rdfs:label ?nameValue .
        
        # Images and positions may be absent from older records.
        OPTIONAL {{ ?playerNode foaf:depiction ?imageValue . }}
        OPTIONAL {{ ?playerNode bball:hasPosition ?positionValue . }}
        
        }} GROUP BY ?teamType ?homeScore ?roadScore ?playerNode }}
        # Keep the compact roster format consumed by the frontend.
        BIND(CONCAT(REPLACE(STR(?playerNode), ".*-/", ""), "|", ?playerName, "|", COALESCE(STR(?img), "NO_IMG"), "|", COALESCE(STR(?position), "")) AS ?playerInfo)
    }}
    GROUP BY ?teamType ?homeScore ?roadScore
    """


def get_clutch_time_performers_query():
    return """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?player (SUM(xsd:integer(?points)) AS ?clutchPoints)
           (COUNT(?action) AS ?clutchActions)
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
    season_filter = (
        f"?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' ."
        if season_code
        else ""
    )
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


def get_quiz_points_query(game_code=None, season_code=None, quarter=None, **context):
    """Rank scorers by distinct scoring events, independent of profile aliases."""
    scope = filters(game_code=game_code, season_code=season_code, quarter=quarter, **context)
    return (
        PREFIXES
        + f"""
    SELECT ?player (SUM(xsd:integer(?points)) AS ?totalPoints) WHERE {{
      {{ SELECT DISTINCT ?player ?action ?points WHERE {{
        ?game bball:hasPlayByPlayAction ?action .
        ?action bball:actionPlayer ?player ; bball:pointsAwarded ?points .
        FILTER(xsd:integer(?points) > 0)
        {scope}
      }} }}
    }} GROUP BY ?player ORDER BY DESC(?totalPoints) STR(?player) LIMIT 20
    """
    )


def get_simulator_crunch_time_query(game_code, quarter, players_list, season_code=None):
    filters = ""
    for pid in players_list:
        filters += f"?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/{pid}> .\n        "

    query = """
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?actionTeam ?lineupTeam ?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)
           (COUNT(DISTINCT ?action) AS ?observedActions)
    WHERE {
      { SELECT DISTINCT ?action ?actionTeam ?lineupTeam ?lineup ?points WHERE {
        ?game a bball:Game .
        
        ?game bball:hasPlayByPlayAction ?action .
        OPTIONAL { ?action bball:pointsAwarded ?awarded . }
        BIND(COALESCE(?awarded, 0) AS ?points)
        OPTIONAL { ?action bball:actionTeam ?actionTeam . }
    """
    if game_code:
        query += f"\n        ?game bball:hasCode '{game_code}' .\n"
    if season_code:
        query += (
            f"\n        ?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' .\n"
        )
    if quarter:
        query += f"\n        ?action bball:quarter '{quarter}' .\n"

    query += f"""
        {{ ?action bball:runningHomeTeamLineup ?lineup . ?game bball:homeTeam ?lineupTeam . }}
        UNION
        {{ ?action bball:runningRoadTeamLineup ?lineup . ?game bball:roadTeam ?lineupTeam . }}

        {filters}
      }} }}
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
        ?game bball:hasSeason/bball:hasCode {literal(season_code)} .
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
                
        # Close fourth-quarter games with enough time for a plausible comeback.
        FILTER(xsd:integer(?seconds) >= 60 && xsd:integer(?seconds) <= 300
               && ABS(xsd:integer(?homeScore) - xsd:integer(?roadScore)) <= 6
               && ABS(xsd:integer(?homeScore) - xsd:integer(?roadScore)) * 30 <= xsd:integer(?seconds))
    }} LIMIT 200
    """


def get_team_roster_query(game_code, team_code, season_code=None):
    season_filter = (
        f"?game bball:hasSeason ?season . ?season bball:hasCode '{season_code}' ."
        if season_code
        else ""
    )
    return f"""
    PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
    SELECT DISTINCT ?lineup
    WHERE {{
        ?game a bball:Game ;
              bball:hasCode '{game_code}' ;
              bball:hasPlayByPlayAction ?action .

        {season_filter}

        # Scope lineups to this exact team and game.
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
