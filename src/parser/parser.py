import json
from collections import defaultdict
import os

QUARTERS = [
    "FirstQuarter",
    "SecondQuarter",
    "ThirdQuarter",
    "ForthQuarter",
    "ExtraTime1",
    "ExtraTime2",
    "ExtraTime3",
]

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

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


# --------------------------------------------------
# MAIN CLASS
# --------------------------------------------------

class GameProcessor:

    def __init__(self, pbp_data, starting_lineups, points_data):
        self.data = pbp_data
        
        self.team_a = pbp_data["CodeTeamA"].strip()
        self.team_b = pbp_data["CodeTeamB"].strip()
        self.current_score_a = 0
        self.current_score_b = 0

        # Hardcoded Starters integration
        self.current_lineups = {
            self.team_a: set(starting_lineups[self.team_a]),
            self.team_b: set(starting_lineups[self.team_b]),
        }
        
        # Map shot data from Points.json for easy lookup
        self.shots_extra_data = self._map_points_data(points_data)

        self.all_actions = []

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
        
        if event.get("POINTS_A") is not None:
            self.current_score_a = event["POINTS_A"]
        if event.get("POINTS_B") is not None:
            self.current_score_b = event["POINTS_B"]

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
        if team not in (self.team_a, self.team_b):
            return

        player_id = event["PLAYER_ID"].strip()
        if not player_id:
            return

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

        for event in plays:
            if event["PLAYTYPE"] in ("IN", "OUT"):
                self.process_substitution(event)

            self.extract_action_data(event, period_name)

    def run(self):
        for q in QUARTERS:
            self.process_period(q)

    # --------------------------------------------------
    # GENERATE RDF TRIPLETS
    # --------------------------------------------------
    def generate_triplets(self):
        triplets = []
        NS = "http://www.ics.forth.gr/isl/Basketball#"
        XSD = "http://www.w3.org/2001/XMLSchema#"
        
        for action in self.all_actions:
            subj = f"<https://www.euroleaguebasketball.net/euroleague/game-center/action/{action['hasPlayByPlaySequence']}>"
            
            # Action Type
            triplets.append(f"{subj} <{NS}hasActionType> \"{action['hasActionInfo']}\" .")
            
            # Game info
            triplets.append(f"{subj} <{NS}inQuarter> \"{action['quarter']}\" .")
            triplets.append(f"{subj} <{NS}gameClock> \"{action['clock']}\" .")
            
            # Scores
            triplets.append(f"{subj} <{NS}homeScore> \"{action['runningHomeTeamScore']}\"^^<{XSD}integer> .")
            triplets.append(f"{subj} <{NS}roadScore> \"{action['runningRoadTeamScore']}\"^^<{XSD}integer> .")
            
            # Entities
            if action.get("actionPlayer"):
                triplets.append(f"{subj} <{NS}performedBy> <{action['actionPlayer']}> .")
            if action.get("hasAssist"):
                triplets.append(f"{subj} <{NS}hasAssist> <{action['hasAssist']}> .")
            if action.get("wasBlockedBy"):
                triplets.append(f"{subj} <{NS}wasBlockedBy> <{action['wasBlockedBy']}> .")
                
            # Extra Shot Data
            if action.get("coord_x") is not None:
                triplets.append(f"{subj} <{NS}coordX> \"{action['coord_x']}\"^^<{XSD}integer> .")
                triplets.append(f"{subj} <{NS}coordY> \"{action['coord_y']}\"^^<{XSD}integer> .")
                triplets.append(f"{subj} <{NS}shotZone> \"{action['zone']}\" .")

        return triplets

# ==================================================
# USAGE
# ==================================================

# Paths mapping (Adjust these according to your local setup)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

playbyplay_path = os.path.join(project_root, "data", "raw", "PlaybyPlay.json")
points_path = os.path.join(project_root, "data", "raw", "Points.json")

output_dir = os.path.join(project_root, "data", "processed")
output_json_path = os.path.join(output_dir, "AllActions.json")
output_triplets_path = os.path.join(output_dir, "Triplets.nt")

# Load JSON files
print(f"Reading files...")
with open(playbyplay_path, "r", encoding="utf8") as f:
    pbp_data = json.load(f)

with open(points_path, "r", encoding="utf8") as f:
    points_data = json.load(f)

# HARDCODED STARTERS
starting_lineups = {
    "ZAL": {"P007975", "P003210", "P011983", "P007513", "P005504"},
    "PAN": {"P011442", "P012774", "P005161", "P007866", "P003842"},
}

processor = GameProcessor(pbp_data, starting_lineups, points_data)
processor.run()

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

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
