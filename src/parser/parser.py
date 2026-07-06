import json
from collections import defaultdict
import os

QUARTERS = ["FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter", "ExtraTime1", "ExtraTime2", "ExtraTime3"]

def clock_to_seconds(clock_str):
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

class GameProcessor:
    def __init__(self, pbp_data, boxscore_data, points_data):
        self.data = pbp_data
        self.team_a = pbp_data["CodeTeamA"].strip()
        self.team_b = pbp_data["CodeTeamB"].strip()
        self.current_score_a = 0
        self.current_score_b = 0

        # 1. FIX: Dynamically extract starting lineups from Boxscore.json
        self.current_lineups = self._extract_starters(boxscore_data)
        
        # 2. FIX: Map shot data from Points.json for easy lookup
        self.shots_extra_data = self._map_points_data(points_data)

        self.all_actions = []

    def _extract_starters(self, boxscore_data):
        starters = {self.team_a: set(), self.team_b: set()}
        for team_stat in boxscore_data["Stats"]:
            team_code = team_stat["Team"].strip()
            # Map full team names to codes if necessary, assuming Boxscore uses TeamA/B codes or similar logic
            # For safety, we will just match by the first 3 letters matching the code
            matched_code = self.team_a if team_code.startswith(self.team_a[:3]) else self.team_b
            
            for player in team_stat["PlayersStats"]:
                if player.get("IsStarter") == 1:
                    starters[matched_code].add(player["Player_ID"].strip())
        return starters

    def _map_points_data(self, points_data):
        shot_map = {}
        for row in points_data.get("Rows", []):
            # Key based on Player ID, Minute, and Clock time to match with PBP
            key = (row["ID_PLAYER"].strip(), row["MINUTE"], row["CONSOLE"])
            shot_map[key] = {
                "coord_x": row.get("COORD_X"),
                "coord_y": row.get("COORD_Y"),
                "zone": row.get("ZONE")
            }
        return shot_map

    def extract_action_data(self, event, period_name):
        if not event.get("MARKERTIME"):
            return

        play_type = event.get("PLAYTYPE", "")
        player_id = event.get("PLAYER_ID", "").strip() if event.get("PLAYER_ID") else None
        
        if event.get("POINTS_A") is not None: self.current_score_a = event["POINTS_A"]
        if event.get("POINTS_B") is not None: self.current_score_b = event["POINTS_B"]

        action_data = {
            "hasPlayByPlaySequence": event.get("NUMBEROFPLAY"),
            "quarter": period_name,
            "actionTeam": event.get("CODETEAM", "").strip() if event.get("CODETEAM") else "",
            "clock": event["MARKERTIME"],
            "quarterSecondsRemaining": clock_to_seconds(event["MARKERTIME"]),
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
                    prev_action["hasAssist"] = generate_player_uri(player_id)
                    break
                    
        # Merging Blocks
        elif play_type == "FV":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") in ("2FGA", "3FGA") and prev_action["clock"] == action_data["clock"]:
                    prev_action["wasBlockedBy"] = generate_player_uri(player_id)
                    break

        # Merging Substitutions
        if play_type in ("IN", "OUT"):
            for prev_action in reversed(self.all_actions):
                if prev_action.get("hasActionInfo") == "Substitution" and prev_action["clock"] == action_data["clock"] and prev_action["actionTeam"] == action_data["actionTeam"]:
                    if play_type == "IN" and prev_action.get("playerIn") is None:
                        prev_action["playerIn"] = generate_player_uri(player_id)
                        return
                    elif play_type == "OUT" and prev_action.get("playerOut") is None:
                        prev_action["playerOut"] = generate_player_uri(player_id)
                        return

            action_data["hasActionInfo"] = "Substitution"
            action_data["playerIn"] = generate_player_uri(player_id) if play_type == "IN" else None
            action_data["playerOut"] = generate_player_uri(player_id) if play_type == "OUT" else None
            self.all_actions.append(action_data)
            return
                
        else:
            action_data["actionPlayer"] = generate_player_uri(player_id)

            # Look up extra coordinates from Points.json
            if play_type in ("2FGM", "2FGA", "3FGM", "3FGA") and player_id:
                shot_key = (player_id, event.get("MINUTE"), event.get("MARKERTIME"))
                if shot_key in self.shots_extra_data:
                    extra = self.shots_extra_data[shot_key]
                    action_data["coord_x"] = extra["coord_x"]
                    action_data["coord_y"] = extra["coord_y"]
                    action_data["zone"] = extra["zone"]

            self.all_actions.append(action_data)

    def process_substitution(self, event):
        team = event["CODETEAM"].strip()
        if team not in (self.team_a, self.team_b): return
        player_id = event["PLAYER_ID"].strip()
        if not player_id: return

        if event["PLAYTYPE"] == "IN":
            self.current_lineups[team].add(player_id)
        elif event["PLAYTYPE"] == "OUT":
            self.current_lineups[team].discard(player_id)

    def process_period(self, period_name):
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

    # 3. NEW FEATURE: Generate Triplets
    def generate_triplets(self):
        triplets = []
        # Ορισμός του υποχρεωτικού prefix για τα schema elements
        bball_prefix = "http://www.ics.forth.gr/isl/Basketball#"
        
        for action in self.all_actions:
            # Create a unique subject URI for this specific event
            subj = f"<http://euroleague.net/action/{action['hasPlayByPlaySequence']}>"
            
            # Map standard properties (Προσθήκη του bball_prefix σε όλα τα predicates)
            triplets.append(f"{subj} <{bball_prefix}hasActionType> \"{action['hasActionInfo']}\" .")
            triplets.append(f"{subj} <{bball_prefix}inQuarter> \"{action['quarter']}\" .")
            triplets.append(f"{subj} <{bball_prefix}gameClock> \"{action['clock']}\" .")
            triplets.append(f"{subj} <{bball_prefix}homeScore> \"{action['runningHomeTeamScore']}\" .")
            triplets.append(f"{subj} <{bball_prefix}roadScore> \"{action['runningRoadTeamScore']}\" .")
            
            # Map Object/Relational properties
            if action.get("actionPlayer"):
                triplets.append(f"{subj} <{bball_prefix}performedBy> <{action['actionPlayer']}> .")
            if action.get("hasAssist"):
                triplets.append(f"{subj} <{bball_prefix}hasAssist> <{action['hasAssist']}> .")
            if action.get("wasBlockedBy"):
                triplets.append(f"{subj} <{bball_prefix}wasBlockedBy> <{action['wasBlockedBy']}> .")
            if action.get("playerIn"):
                triplets.append(f"{subj} <{bball_prefix}playerIn> <{action['playerIn']}> .")
            if action.get("playerOut"):
                triplets.append(f"{subj} <{bball_prefix}playerOut> <{action['playerOut']}> .")
                
            # Map Extra Shot Information
            if action.get("coord_x") is not None:
                triplets.append(f"{subj} <{bball_prefix}coordX> \"{action['coord_x']}\" .")
                triplets.append(f"{subj} <{bball_prefix}coordY> \"{action['coord_y']}\" .")
                triplets.append(f"{subj} <{bball_prefix}shotZone> \"{action['zone']}\" .")

        return triplets

# ==================================================
# USAGE
# ==================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

# File Paths
playbyplay_path = os.path.join(project_root, "data", "raw", "PlaybyPlay.json")
boxscore_path = os.path.join(project_root, "data", "raw", "Boxscore.json")
points_path = os.path.join(project_root, "data", "raw", "Points.json")

output_dir = os.path.join(project_root, "data", "processed")
output_json_path = os.path.join(output_dir, "AllActions.json")
output_triplets_path = os.path.join(output_dir, "Triplets.nt")

# Load all 3 JSON files
with open(playbyplay_path, "r", encoding="utf8") as f: pbp_data = json.load(f)
with open(boxscore_path, "r", encoding="utf8") as f: boxscore_data = json.load(f)
with open(points_path, "r", encoding="utf8") as f: points_data = json.load(f)

processor = GameProcessor(pbp_data, boxscore_data, points_data)
processor.run()

os.makedirs(output_dir, exist_ok=True)

# Print the extracted starters to verify
print("=== STARTERS EXTRACTED ===")
for team, players in processor.current_lineups.items():
    print(f"{team}: {players}")
print("==========================")

# Save standard JSON
with open(output_json_path, "w", encoding="utf8") as out_file:
    json.dump(processor.all_actions, out_file, ensure_ascii=False, indent=4)

# Save Triplets (N-Triples format)
triplets = processor.generate_triplets()
with open(output_triplets_path, "w", encoding="utf8") as out_file:
    for triple in triplets:
        out_file.write(triple + "\n")

print("Processing complete! Both JSON and Triplets have been generated.")