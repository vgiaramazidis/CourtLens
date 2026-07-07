from itertools import count
import json
from collections import defaultdict
import os

QUARTERS = [
    "FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter", 
    "ExtraTime1", "ExtraTime2", "ExtraTime3"
]

# The shared Game URL Base
GAME_URL_BASE = "https://www.euroleaguebasketball.net/euroleague/game-center/2023-24/-/E2023/200"

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def clock_to_seconds(clock_str):
    if not clock_str: return 0
    m, s = map(int, clock_str.split(":"))
    return m * 60 + s

def generate_lineup_uri(team_code, players_set):
    if not players_set: return ""
    clean_ids = sorted([pid.replace('P', '').strip() for pid in players_set])
    lineup_str = "_".join(clean_ids)
    return f"https://www.euroleaguebasketball.net/euroleague/teams/-/{team_code}#Lineup_{lineup_str}"

def period_length(period_name):
    return 300 if "ExtraTime" in period_name else 600

def generate_player_uri(player_id):
    if not player_id: return None
    return f"https://www.euroleaguebasketball.net/euroleague/players/-/{player_id.strip()}"

def lineup_key(players):
    return tuple(sorted(players))

# --------------------------------------------------
# MAIN CLASS
# --------------------------------------------------

class GameProcessor:
    def __init__(self, pbp_data, boxscore_data, points_data):
        self.data = pbp_data
        
        self.team_a = pbp_data["CodeTeamA"].strip()
        self.team_b = pbp_data["CodeTeamB"].strip()
        self.current_score_a = 0
        self.current_score_b = 0

        # Dynamic Starters integration (from feature_teo)
        self.current_lineups = self._extract_starters(boxscore_data)
        
        # Map shot data from Points.json for easy lookup
        self.shots_extra_data = self._map_points_data(points_data)

        self.all_actions = []

    def _extract_starters(self, boxscore_data):
        starters = {self.team_a: set(), self.team_b: set()}
        for team_stat in boxscore_data["Stats"]:
            team_code = team_stat["Team"].strip()
            matched_code = self.team_a if team_code.startswith(self.team_a[:3]) else self.team_b
            
            for player in team_stat["PlayersStats"]:
                if player.get("IsStarter") == 1:
                    starters[matched_code].add(player["Player_ID"].strip())
        return starters

    def _map_points_data(self, points_data):
        shot_map = {}
        for row in points_data.get("Rows", []):
            key = (row["ID_PLAYER"].strip(), row["MINUTE"], row["CONSOLE"])
            shot_map[key] = {
                "coord_x": row.get("COORD_X"),
                "coord_y": row.get("COORD_Y"),
                "zone": row.get("ZONE"),
                "pointsAwarded": int(row.get("POINTS", 0)),
                "isFastBreak": bool(int(row.get("FASTBREAK", "0"))),
                "isSecondChance": bool(int(row.get("SECOND_CHANCE", "0"))),
                "isFromTurnover": bool(int(row.get("POINTS_OFF_TURNOVER", "0")))
            }
        return shot_map

    def extract_action_data(self, event, period_name):
        play_type = event.get("PLAYTYPE", "")
        player_id = event.get("PLAYER_ID", "").strip() if event.get("PLAYER_ID") else None
        
        # Proper empty time handling (from develop)
        markertime = event.get("MARKERTIME") or ("10:00" if play_type == "BP" else "00:00" if play_type in ("EP", "EG") else "")
        
        if event.get("POINTS_A") is not None: self.current_score_a = event["POINTS_A"]
        if event.get("POINTS_B") is not None: self.current_score_b = event["POINTS_B"]

        action_data = {
            "hasPlayByPlaySequence": event.get("NUMBEROFPLAY"),
            "quarter": period_name,
            "actionTeam": event.get("CODETEAM", "").strip() if event.get("CODETEAM") else "",
            "clock": markertime,
            "quarterSecondsRemaining": clock_to_seconds(markertime),
            "runningHomeTeamScore": self.current_score_a,
            "runningRoadTeamScore": self.current_score_b,
            "hasHomeTeamLineupSnapshot": generate_lineup_uri(self.team_a, self.current_lineups[self.team_a]),
            "hasRoadTeamLineupSnapshot": generate_lineup_uri(self.team_b, self.current_lineups[self.team_b]),
            "hasActionInfo": play_type,
        }

        # Merging Assists
        if play_type == "AS":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") in ("2FGM", "3FGM") and prev_action["actionTeam"] == action_data["actionTeam"]:
                    if prev_action["quarter"] == action_data["quarter"]:
                        prev_action["hasAssist"] = f"{GAME_URL_BASE}#PlayByPlay_{event.get('NUMBEROFPLAY')}"
                    break

        # Merging Blocks
        elif play_type == "FV":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") in ("2FGA", "3FGA") and prev_action["clock"] == action_data["clock"]:
                    prev_action["wasBlockedBy"] = f"{GAME_URL_BASE}#PlayByPlay_{event.get('NUMBEROFPLAY')}"
                    break
        # Merging Steals (ST) back to the Turnover 
        elif play_type == "ST":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") == "TO" and prev_action["quarter"] == action_data["quarter"]:
                    # Make sure the Steal is from the opposing team
                    if prev_action["actionTeam"] != action_data["actionTeam"]:
                        prev_action["causedBySteal"] = f"{GAME_URL_BASE}#PlayByPlay_{event.get('NUMBEROFPLAY')}"
                        break
                        
        # Merging Turnovers (TO) to Fouls and parsing Violations
        elif play_type == "TO":
            # 1. Look backward for an Offensive Foul (OF) at the exact same game clock
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") == "OF" and prev_action["clock"] == action_data["clock"]:
                    action_data["causedByFoul"] = f"{GAME_URL_BASE}#PlayByPlay_{prev_action['hasPlayByPlaySequence']}"
                    break
            
            # 2. Check if the descriptive PlayInfo text indicates a Violation
            play_info = event.get("PLAYINFO", "").lower()
            violation_keywords = ["travel", "second", "out of bound", "step", "violation", "carry", "goaltend"]
            
            if any(kw in play_info for kw in violation_keywords):
                action_data["isViolation"] = True            
        # Merging Rebounds
        elif play_type in ("O", "D"):
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") in ("2FGA", "3FGA", "FTA"):
                    prev_action["leadsToRebound"] = f"{GAME_URL_BASE}#PlayByPlay_{event.get('NUMBEROFPLAY')}"
                    break

        # Merging Substitutions
        if play_type in ("IN", "OUT"):
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") == "Substitution" and prev_action["clock"] == action_data["clock"] and prev_action["actionTeam"] == action_data["actionTeam"]:
                    if play_type == "IN" and prev_action.get("playerIn") is None:
                        prev_action["playerIn"] = generate_player_uri(player_id)
                        # Append lineup snapshots (from develop)
                        prev_action["hasHomeTeamLineupSnapshot"] = action_data["hasHomeTeamLineupSnapshot"]
                        prev_action["hasRoadTeamLineupSnapshot"] = action_data["hasRoadTeamLineupSnapshot"]
                        return
                    elif play_type == "OUT" and prev_action.get("playerOut") is None:
                        prev_action["playerOut"] = generate_player_uri(player_id)
                        # Append lineup snapshots (from develop)
                        prev_action["hasHomeTeamLineupSnapshot"] = action_data["hasHomeTeamLineupSnapshot"]
                        prev_action["hasRoadTeamLineupSnapshot"] = action_data["hasRoadTeamLineupSnapshot"]
                        return

            action_data["hasActionInfo"] = "Substitution"
            action_data["playerIn"] = generate_player_uri(player_id) if play_type == "IN" else None
            action_data["playerOut"] = generate_player_uri(player_id) if play_type == "OUT" else None
            self.all_actions.append(action_data)
            return
                
        else:
            action_data["actionPlayer"] = generate_player_uri(player_id)

            # Look up extra coordinates and states for shots
            if play_type in ("2FGM", "2FGA", "3FGM", "3FGA", "FTM", "FTA") and player_id:
                shot_key = (player_id, event.get("MINUTE"), event.get("MARKERTIME"))
                if shot_key in self.shots_extra_data:
                    extra = self.shots_extra_data[shot_key]
                    
                    action_data["coord_x"] = extra["coord_x"]
                    action_data["coord_y"] = extra["coord_y"]
                    
                    if extra['coord_x'] is not None and extra['coord_y'] is not None:
                        action_data["hasShotCoords"] = f"{extra['coord_x']},{extra['coord_y']}"
                        
                    action_data["hasShotZone"] = extra["zone"]
                    
                    # Force points to 0 if the shot was missed
                    if play_type in ("2FGA", "3FGA", "FTA"):
                        action_data["pointsAwarded"] = 0
                    else:
                        action_data["pointsAwarded"] = extra["pointsAwarded"]
                        
                    action_data["isFastBreak"] = extra["isFastBreak"]
                    action_data["isSecondChance"] = extra["isSecondChance"]
                    action_data["isFromTurnover"] = extra["isFromTurnover"]

            self.all_actions.append(action_data)

    def process_substitution(self, event):
        team = event["CODETEAM"].strip()
        if team not in (self.team_a, self.team_b):
            return

        player_id = event["PLAYER_ID"].strip()
        if not player_id:
            return
        if team not in (self.team_a, self.team_b): return
        player_id = event["PLAYER_ID"].strip()
        if not player_id: return

        if event["PLAYTYPE"] == "IN":
            self.current_lineups[team].add(player_id)
        elif event["PLAYTYPE"] == "OUT":
            self.current_lineups[team].discard(player_id)

    def process_period(self, period_name):
        if period_name not in self.data:
            return
        plays = self.data[period_name]
        if not plays:
            return
        if period_name not in self.data: return
        plays = self.data[period_name]
        if not plays: return

        for event in plays:
            if event["PLAYTYPE"] in ("IN", "OUT"):
                self.process_substitution(event)
            self.extract_action_data(event, period_name)

    def run(self):
        for q in QUARTERS:
            self.process_period(q)

    # --------------------------------------------------
    # GENERATE RDF TRIPLETS (MERGED SCHEMA)
    # --------------------------------------------------
    def generate_triplets(self):
        triplets = []
        NS = "http://www.ics.forth.gr/isl/Basketball#"
        RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        RDFS = "http://www.w3.org/2000/01/rdf-schema#label"
        XSD = "http://www.w3.org/2001/XMLSchema#"
        subj = f"<https://www.euroleaguebasketball.net/euroleague/game-center/2023-24/-/E2023/200" #Prepei na allaxtei apo hard coded to 2023-24,E kai to 200
        for plays in self.all_actions:
            triplets.append(f"{subj}> <{NS}hasPlayByPlayAction> {subj}#PlayByPlay_{plays['hasPlayByPlaySequence']}> .")

        triplets.append("\n")
        for action in self.all_actions:
            begin=f"{subj}#PlayByPlay_{action['hasPlayByPlaySequence']}>"
            triplets.append(f"{begin} <{NS}hasPlayByPlaySequence> \"{action['hasPlayByPlaySequence']}\" .")
            triplets.append(f"{begin} <{RDF}> <{NS}{action['hasActionInfo']}> .")
            # Game info
            triplets.append(f"{begin} <{NS}quarter> \"{action['quarter']}\"^^<{XSD}string> .")
            triplets.append(f"{begin} <{NS}clock> \"{action['clock']}\"^^<{XSD}string> .")
            triplets.append(f"{begin} <{NS}quarterSecondsRemaining> \"{action['quarterSecondsRemaining']}\"^^<{XSD}integer> .")
            
            # Scores
            triplets.append(f"{begin} <{NS}runningHomeTeamScore> \"{action['runningHomeTeamScore']}\"^^<{XSD}integer> .")
            triplets.append(f"{begin} <{NS}runningRoadTeamScore> \"{action['runningRoadTeamScore']}\"^^<{XSD}integer> .")
            
            # Lineups
            triplets.append(f"{begin} <{NS}hasHomeTeamLineup> \"{action['hasHomeTeamLineupSnapshot']}\" .")
            triplets.append(f"{begin} <{NS}hasRoadTeamLineup> \"{action['hasRoadTeamLineupSnapshot']}\" .")
            # Entities
            if action['hasActionInfo'] in ("2FGM", "3FGM","FTM"):
                triplets.append(f"{begin} <{NS}actionTeam> <https://www.euroleaguebasketball.net/euroleague/teams/-/{action['actionTeam']}> .")
                triplets.append(f"{begin} <{NS}actionPlayer> <{action['actionPlayer']}> .")
                #triplets.append(f"{begin} <{NS}pointsAwarded> \"{action['pointsAwarded']}\"^^<{XSD}integer> .")
                #triplets.append(f"{begin} <{NS}hasAssist> <{action['hasAssist']}> .")
                #triplets.append(f"{begin} <{NS}coordX> \"{action['coord_x']}\"^^<{XSD}integer> .")
                #triplets.append(f"{begin} <{NS}coordY> \"{action['coord_y']}\"^^<{XSD}integer> .")
                #triplets.append(f"{begin} <{NS}hasShotZone> \"{action['zone']}\"^^<{XSD}string> .")
                #triplets.append(f"{begin} <{NS}isFastBreak> \"{action['isFastBreak']}\"^^<{XSD}boolean> .")
                #triplets.append(f"{begin} <{NS}isSecondChance> \"{action['isSecondChance']}\"^^<{XSD}boolean> .")
                #triplets.append(f"{begin} <{NS}isFromTurnover> \"{action['isFromTurnover']}\"^^<{XSD}boolean> .")
            elif action['hasActionInfo'] in ("2FGA", "3FGA","FTA"):
                triplets.append(f"{begin} <{NS}actionTeam> <https://www.euroleaguebasketball.net/euroleague/teams/-/{action['actionTeam']}> .")
                triplets.append(f"{begin} <{NS}actionPlayer> <{action['actionPlayer']}> .")
                #triplets.append(f"{begin} <{NS}coordX> \"{action['coord_x']}\"^^<{XSD}integer> .")
                #triplets.append(f"{begin} <{NS}coordY> \"{action['coord_y']}\"^^<{XSD}integer> .")
                #triplets.append(f"{begin} <{NS}hasShotZone> \"{action['zone']}\"^^<{XSD}string> .")
                #triplets.append(f"{begin} <{NS}isFastBreak> \"{action['isFastBreak']}\"^^<{XSD}boolean> .")
                #triplets.append(f"{begin} <{NS}isSecondChance> \"{action['isSecondChance']}\"^^<{XSD}boolean> .")
                #triplets.append(f"{begin} <{NS}isFromTurnover> \"{action['isFromTurnover']}\"^^<{XSD}boolean> .")
                #triplets.append(f"{begin} <{NS}leadsToRebound> <{action['leadsToRebound']}> .")
                #triplets.append(f"{begin} <{NS}wasBlockedBy> <{action['wasBlockedBy']}> .")
            elif action['hasActionInfo'] in ("Block", "AS", "FV", "AG"):
                triplets.append(f"{begin} <{NS}actionTeam> <https://www.euroleaguebasketball.net/euroleague/teams/-/{action['actionTeam']}> .")
                triplets.append(f"{begin} <{NS}actionPlayer> <{action['actionPlayer']}> .")
                #triplets.append(f"{begin} <{NS}associatedAction> <{action['associatedAction']}> .")
            triplets.append("\n")
        return triplets

# ==================================================
# USAGE
# ==================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

playbyplay_path = os.path.join(project_root, "data", "raw", "PlaybyPlay.json")
boxscore_path = os.path.join(project_root, "data", "raw", "Boxscore.json")
points_path = os.path.join(project_root, "data", "raw", "Points.json")

output_dir = os.path.join(project_root, "data", "processed")
output_json_path = os.path.join(output_dir, "AllActions.json")
output_triplets_path = os.path.join(output_dir, "Triplets.nt")

# Load JSON files
print(f"Reading files...")
with open(playbyplay_path, "r", encoding="utf8") as f:
    pbp_data = json.load(f)

# Note: Using boxscore dynamically so you don't have to hardcode starters anymore
with open(boxscore_path, "r", encoding="utf8") as f:
    boxscore_data = json.load(f)

with open(points_path, "r", encoding="utf8") as f:
    points_data = json.load(f)

processor = GameProcessor(pbp_data, boxscore_data, points_data)
processor.run()

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Print the dynamically extracted starters to verify
print("=== STARTERS EXTRACTED ===")
for team, players in processor.current_lineups.items():
    print(f"{team}: {players}")
print("==========================")

# Save standard JSON with all the merged data
print(f"Saving merged JSON to: {output_json_path}")
with open(output_json_path, "w", encoding="utf8") as out_file:
    json.dump(processor.all_actions, out_file, ensure_ascii=False, indent=4)

# Save Triplets (N-Triples format)
print(f"Saving Triplets to: {output_triplets_path}")
triplets = processor.generate_triplets()
with open(output_triplets_path, "w", encoding="utf8") as out_file:
    for triple in triplets:
        out_file.write(triple + "\n")

print("Processing complete!")
