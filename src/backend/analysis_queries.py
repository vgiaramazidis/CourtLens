"""Validated, shared filters for the manual statistics browser."""
import json
import re

PREFIXES = '''PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
'''
PLAYER_BASE = 'https://www.euroleaguebasketball.net/euroleague/players/-/'

class AnalysisFilterError(ValueError):
    pass


def literal(value):
    return json.dumps(str(value), ensure_ascii=False)


def player_filter(variable, value):
    if not value:
        return ''
    tokens = re.findall(r"[\w'-]+", str(value), re.UNICODE)
    if not tokens or len(str(value)) > 150:
        raise AnalysisFilterError('Enter a player name or player ID.')
    conditions = ' && '.join(f'CONTAINS(LCASE(STR(?filterName)), LCASE({literal(token)}))' for token in tokens)
    return f'''FILTER(STR({variable}) = {literal(PLAYER_BASE + str(value))} || EXISTS {{
        {variable} rdfs:label ?filterName . FILTER({conditions}) }})'''


def filters(action='?action', game_code=None, season_code=None, filter_type=None, filter_id=None,
            quarter=None, min_start=None, min_end=None):
    parts = []
    for value, variable, relation in [(season_code, '?seasonCode', '?game bball:hasSeason/bball:hasCode ?seasonCode .'),
                                      (game_code, '?gameCode', '?game bball:hasCode ?gameCode .')]:
        if value and value != 'ALL':
            codes = [code.strip() for code in value.split(',')]
            if not all(re.fullmatch(r'[A-Za-z0-9_-]+', code) for code in codes):
                raise AnalysisFilterError('Choose a valid season or game.')
            parts.append(relation + f' FILTER({variable} IN ({", ".join(map(literal, codes))}))')
    if game_code and (not season_code or season_code == 'ALL' or ',' in season_code):
        raise AnalysisFilterError('Choose one season before selecting a game.')
    if quarter:
        if quarter not in ('1st', '2nd', '3rd', '4th', 'OT'):
            raise AnalysisFilterError('Choose a valid period.')
        parts.append(f'{action} bball:quarter ?filterQuarter .')
        parts.append('FILTER(REGEX(STR(?filterQuarter), "OT|Overtime", "i"))' if quarter == 'OT'
                     else f'FILTER(STR(?filterQuarter) = {literal(quarter)})')
    if min_start not in (None, '') or min_end not in (None, ''):
        try:
            start, end = int(min_start), int(min_end)
        except (ValueError, TypeError):
            raise AnalysisFilterError('Enter both clock limits as whole minutes.')
        if not 0 <= end <= start <= (5 if quarter == 'OT' else 10):
            raise AnalysisFilterError('Clock limits must descend from 10 to 0 minutes (5 to 0 in overtime).')
        parts.append(f'{action} bball:quarterSecondsRemaining ?seconds . FILTER(xsd:integer(?seconds) <= {start*60} && xsd:integer(?seconds) >= {end*60})')
    if filter_type:
        if filter_type not in ('on_court', 'referee') or not filter_id:
            raise AnalysisFilterError('Choose a player or referee for the context filter.')
        if filter_type == 'on_court':
            parts.append(f'''FILTER EXISTS {{
                {{ {action} bball:runningHomeTeamLineup ?filterLineup . }} UNION
                {{ {action} bball:runningRoadTeamLineup ?filterLineup . }}
                ?filterLineup bball:includesPlayer ?filterPlayer .
                {player_filter('?filterPlayer', filter_id)} }}''')
        else:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', filter_id):
                raise AnalysisFilterError('Enter the referee ID from the data source.')
            parts.append(f'?game bball:hasReferee <http://www.ics.forth.gr/isl/Basketball/entities/{filter_id}> .')
    return '\n'.join(parts)


def get_filtered_shots_query(game_code=None, season_code=None, player_id=None, assist_by_id=None,
                             filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, lineup_uri=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    extra = player_filter('?playerNode', player_id)
    if assist_by_id:
        extra += '?action bball:hasAssist/bball:actionPlayer ?assistPlayer . ' + player_filter('?assistPlayer', assist_by_id)
    if lineup_uri:
        if not re.fullmatch(r'https://www\.euroleaguebasketball\.net/euroleague/teams/[-/A-Za-z0-9]+#Lineup_[A-Za-z0-9_]+', lineup_uri):
            raise AnalysisFilterError('Choose a lineup from the results to inspect its shots.')
        extra += f'FILTER(?home_lineup = <{lineup_uri}> || ?road_lineup = <{lineup_uri}>)'
    return PREFIXES + f'''SELECT DISTINCT ?action ?coords ?action_type ?home_lineup ?road_lineup ?clockTime ?quarter ?playerName ?teamType ?isFastBreak ?isSecondChance ?isFromTurnover ?homeScore ?roadScore WHERE {{
        ?game a bball:Game ; bball:hasPlayByPlayAction ?action ; bball:homeTeam ?homeTeam ; bball:roadTeam ?roadTeam .
        {scope}
        VALUES ?action_type {{ bball:TwoPointShotMade bball:TwoPointShotMissed bball:ThreePointShotMade bball:ThreePointShotMissed }}
        ?action rdf:type ?action_type ; bball:actionTeam ?actionTeam ; bball:quarter ?quarter ; bball:actionPlayer ?playerNode .
        ?playerNode rdfs:label ?playerName .
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
    }} ORDER BY ?action LIMIT 500'''


def aggregate(select, body, group, metric, scope):
    # Subqueries deduplicate events before aggregation when the RDF has repeated labels/relations.
    return PREFIXES + f'''SELECT {select} WHERE {{
        {{ SELECT DISTINCT {group} ?action ?points WHERE {{
            ?game a bball:Game ; bball:hasPlayByPlayAction ?action .
            {scope} {body}
        }} }}
    }} GROUP BY {group} ORDER BY DESC(?{metric}) {group} LIMIT 10'''


def get_top_assist_duos_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    return aggregate('?scorer ?passer (COUNT(DISTINCT ?action) AS ?totalAssists)',
        '?action bball:actionPlayer ?scorer ; bball:hasAssist/bball:actionPlayer ?passer .', '?scorer ?passer', 'totalAssists', scope)


def get_second_chance_points_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None, player_id=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    return aggregate('?player (SUM(xsd:integer(?points)) AS ?totalSecondChancePoints)',
        '?action bball:isSecondChance true ; bball:actionPlayer ?player ; bball:pointsAwarded ?points . ' + player_filter('?player', player_id), '?player', 'totalSecondChancePoints', scope)


def get_top_lineups_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, game_code=None, season_code=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    return aggregate('?lineup (SUM(xsd:integer(?points)) AS ?totalPoints)', '''
        ?action bball:pointsAwarded ?points ; bball:actionTeam ?team .
        ?lineup bball:lineupTeam ?team .
        { ?action bball:runningHomeTeamLineup ?lineup . } UNION { ?action bball:runningRoadTeamLineup ?lineup . }
        ''', '?lineup', 'totalPoints', scope)


def get_foul_drawn_gravity_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, fouled_id=None, fouling_id=None, game_code=None, season_code=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    body = '?action a bball:FoulDrawn ; bball:actionPlayer ?player . ' + player_filter('?player', fouled_id)
    if fouling_id:
        body += '?action bball:occuredByFoul/bball:actionPlayer ?foulingPlayer . ' + player_filter('?foulingPlayer', fouling_id)
    return aggregate('?player (COUNT(DISTINCT ?action) AS ?totalFoulsDrawn)', body, '?player', 'totalFoulsDrawn', scope)


def get_defensive_anchors_query(filter_type=None, filter_id=None, quarter=None, min_start=None, min_end=None, shooter_id=None, blocker_id=None, game_code=None, season_code=None):
    scope = filters('?action', game_code, season_code, filter_type, filter_id, quarter, min_start, min_end)
    body = '?action a bball:Block ; bball:actionPlayer ?player . ' + player_filter('?player', blocker_id)
    if shooter_id:
        body += '?shot bball:blockedBy ?action ; bball:actionPlayer ?shooter . ' + player_filter('?shooter', shooter_id)
    return aggregate('?player (COUNT(DISTINCT ?action) AS ?totalBlocks)', body, '?player', 'totalBlocks', scope)


def get_fast_break_specialists_query(game_code=None, season_code=None, quarter=None):
    scope = filters(game_code=game_code, season_code=season_code, quarter=quarter)
    return aggregate('?player (SUM(xsd:integer(?points)) AS ?fastBreakPoints) (COUNT(DISTINCT ?action) AS ?totalAttempts)',
        '?action bball:isFastBreak true ; bball:actionPlayer ?player ; bball:pointsAwarded ?points .',
        '?player', 'fastBreakPoints', scope)
