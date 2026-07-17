from itertools import count
import json
from collections import defaultdict
import os
import time
import random
import requests 

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def clock_to_seconds(clock_str):
    if not clock_str: return 0
    m, s = map(int, clock_str.split(":"))
    return m * 60 + s

def period_length(period_name):
    return 300 if "ExtraTime" in period_name else 600

def generate_uri(entity_type, value, game_url_base=None, players_set=None):
    if not value and entity_type != "lineup": 
        return None

    if entity_type == "team":
        clean_code = value.strip()
        return f"https://www.euroleaguebasketball.net/euroleague/teams/-/{clean_code}"
        
    elif entity_type == "player":
        pid = value.replace('P', '').strip()
        return f"https://www.euroleaguebasketball.net/euroleague/players/-/{pid}"
        
    elif entity_type == "coach":
        clean_name = value.strip().replace(", ", "-").replace(" ", "-").lower()
        return f"https://www.euroleaguebasketball.net/euroleague/coaches/-/{clean_name}"
        
    elif entity_type == "action":
        return f"{game_url_base}#PlayByPlay_J{value}"
        
    elif entity_type == "lineup":
        if not players_set: return ""
        clean_ids = sorted([pid.replace('P', '').strip() for pid in players_set])
        lineup_str = "_".join(clean_ids)
        return f"https://www.euroleaguebasketball.net/euroleague/teams/-/{value}#Lineup_{lineup_str}"
        
    return None

def generate_coach_uri(coach_name):
    if not coach_name: return None
    clean_name = coach_name.strip().replace(", ", "_").replace(" ", "_")
    return f"https://www.euroleaguebasketball.net/euroleague/coaches/-/{clean_name}"

def lineup_key(players):
    return tuple(sorted(players))

def convert_action_info(action_info):
    mapping = {
        "JB": "JumpBall",
        "BP": "PeriodStart",
        "EP": "PeriodEnd",
        "EG": "GameEnd",
        "TOUT_TV": "TimeoutTV",
        "TOUT": "Timeout",
        "2FGM": "TwoPointShotMade",
        "2FGA": "TwoPointShotMissed",
        "3FGM": "ThreePointShotMade",
        "3FGA": "ThreePointShotMissed",
        "FTM": "FreeThrowMade",
        "FTA": "FreeThrowMissed",
        "AS": "Assist",
        "FV": "Block",
        "OF": "OffensiveFoul",
        "CM": "DefensiveFoul",
        "B": "BenchFoul",
        "CMU": "UnsportsmanlikeFoul",
        "CMT": "TechnicalFoul",
        "C": "CoachFoul",
        "RV": "FoulDrawn",
        "TO": "Turnover",
        "O": "OffensiveRebound",
        "D": "DefensiveRebound",
        "ST": "Steal",
        "IN": "PlayerIn",
        "OUT": "PlayerOut",
        "CCH": "Challenge"
    }
    return mapping.get(action_info, action_info)

# --------------------------------------------------
# MAIN CLASS
# --------------------------------------------------

class GameProcessor:
    def __init__(self, pbp_data, boxscore_data, points_data, game_url_base):
        self.data = pbp_data
        self.game_url_base = game_url_base  
        self.team_a = pbp_data["CodeTeamA"].strip()
        self.team_b = pbp_data["CodeTeamB"].strip()
        self.current_score_a = 0
        self.current_score_b = 0
        self.play_seq = 1  # Unique counter for play sequences

        # --- ΠΡΟΣΘΗΚΗ: Set για να κρατάμε τις μοναδικές πεντάδες ---
        self.unique_lineups = set()
        # --- ΝΕΕΣ ΜΕΤΑΒΛΗΤΕΣ ΓΙΑ ΤΙΣ ΚΑΤΟΧΕΣ (POSSESSIONS) ---
        self.possessions = []
        self.pos_seq = 1 

        # Dynamic Starters integration
        self.current_lineups = self._extract_starters(boxscore_data)
        self._update_unique_lineups()
    
        # Extract Coaches dynamically
        self.current_coaches = {}
        for index, team_stat in enumerate(boxscore_data["Stats"]):
            # Το index 0 αντιστοιχεί στην Home Team (team_a) και το 1 στην Road Team (team_b)
            matched_code = self.team_a if index == 0 else self.team_b
            self.current_coaches[matched_code] = generate_coach_uri(team_stat.get("Coach", ""))
        
        # Map shot data from Points.json for easy lookup
        self.shots_extra_data = self._map_points_data(points_data)
        self.all_actions = []

    def _extract_starters(self, boxscore_data):
        starters = {self.team_a: set(), self.team_b: set()}
        for index, team_stat in enumerate(boxscore_data["Stats"]):
            # Το index 0 αντιστοιχεί στην Home Team (team_a) και το 1 στην Road Team (team_b)
            matched_code = self.team_a if index == 0 else self.team_b
            
            for player in team_stat["PlayersStats"]:
                if player.get("IsStarter") == 1:
                    starters[matched_code].add(player["Player_ID"].strip())
        return starters

    def _map_points_data(self, points_data):
        shot_map = {}
        for row in points_data.get("Rows", []):
            key = row.get("NUM_ANOT")
            shot_map[key] = {
                "coord_x": row.get("COORD_X"),
                "coord_y": row.get("COORD_Y"),
                "shotZone": row.get("ZONE"),
                "pointsAwarded": int(row.get("POINTS", 0)),
                "isFastBreak": bool(int(row.get("FASTBREAK", "0"))),
                "isSecondChance": bool(int(row.get("SECOND_CHANCE", "0"))),
                "isFromTurnover": bool(int(row.get("POINTS_OFF_TURNOVER", "0")))
            }
        return shot_map

    def _update_unique_lineups(self):
        # Add current lineups to the unique set if they have 5 players
        if len(self.current_lineups[self.team_a]) == 5:
            self.unique_lineups.add((self.team_a, tuple(sorted(self.current_lineups[self.team_a]))))
            
        if len(self.current_lineups[self.team_b]) == 5:
            self.unique_lineups.add((self.team_b, tuple(sorted(self.current_lineups[self.team_b]))))

    def extract_action_data(self, event, period_name):
        play_type = event.get("PLAYTYPE", "")
        if play_type == "AG":
            return  # Ignore "ShotRejected" actions
        
        player_id = event.get("PLAYER_ID", "").strip() if event.get("PLAYER_ID") else None

        euroleague_number_of_play = event.get("NUMBEROFPLAY")

        # --- ΝΕΟ ΚΟΜΜΑΤΙ: Μετατροπή του Quarter ---
        quarter_mapping = {
            "FirstQuarter": "1st",
            "SecondQuarter": "2nd",
            "ThirdQuarter": "3rd",
            "ForthQuarter": "4th",
            "ExtraTime1": "OT",
            "ExtraTime2": "2OT",
            "ExtraTime3": "3OT",
            "ExtraTime4": "4OT"
        }
        mapped_quarter = quarter_mapping.get(period_name, period_name)

        # Proper empty time handling
        markertime = event.get("MARKERTIME") or ("10:00" if play_type == "BP" else "00:00" if play_type in ("EP", "EG") else "")
        
        if event.get("POINTS_A") is not None: self.current_score_a = event["POINTS_A"]
        if event.get("POINTS_B") is not None: self.current_score_b = event["POINTS_B"]

        # Initialize ALL fields to None to safely avoid KeyErrors in generate_triplets
        action_data = {
            "hasPlayByPlaySequence": self.play_seq,
            "originalEventId": euroleague_number_of_play,
            "quarter": mapped_quarter,
            "actionTeam": generate_uri("team", event.get('CODETEAM', '').strip()),
            "clock": markertime,
            "quarterSecondsRemaining": clock_to_seconds(markertime),
            "runningHomeTeamScore": self.current_score_a,
            "runningRoadTeamScore": self.current_score_b,
            "runningHomeTeamLineup": generate_uri("lineup", self.team_a, players_set=self.current_lineups[self.team_a]),
            "runningRoadTeamLineup": generate_uri("lineup", self.team_b, players_set=self.current_lineups[self.team_b]),
            "actionInfo": play_type,
        }
        self.play_seq += 1

        # Merging Logic (Assists, Blocks, Rejects, Steals, TOs, Rebounds, Reviews, Challenges, Substitutions)
        if play_type == "AS":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if prev_action.get("actionInfo") in ("2FGM", "3FGM", "FTM") and prev_action["actionTeam"] == action_data["actionTeam"]:
                    prev_action["hasAssist"] = generate_uri("action", euroleague_number_of_play, self.game_url_base)
                    break

        elif play_type == "FV":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if prev_action.get("actionInfo") in ("2FGA", "3FGA") and prev_action["actionTeam"] != action_data["actionTeam"]:
                    prev_action["blockedBy"] = generate_uri("action", euroleague_number_of_play,self.game_url_base)
                    break

        elif play_type == "ST":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if abs(prev_action["quarterSecondsRemaining"] - action_data["quarterSecondsRemaining"]) > 3:
                    break
                if prev_action.get("actionInfo") == "TO" and prev_action["actionTeam"] != action_data["actionTeam"]:
                    prev_action["causedBySteal"] = generate_uri("action", euroleague_number_of_play, self.game_url_base)
                    break
                        
        elif play_type == "TO":
            action_data["causedByFoul"] = None
            action_data["causedByViolation"] = None
            action_data["causedBySteal"] = None
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if abs(prev_action["quarterSecondsRemaining"] - action_data["quarterSecondsRemaining"]) > 3:
                    break
                if prev_action.get("actionInfo") == "OF":
                    action_data["causedByFoul"] = generate_uri("action", prev_action['originalEventId'], self.game_url_base)
                    break
            
            play_info = event.get("PLAYINFO", "").lower()
            violation_keywords = ["travel", "second", "out of bound", "step", "violation", "carry", "goaltend"]
            if any(kw in play_info for kw in violation_keywords):
                action_data["causedByViolation"] = True       

        elif play_type in ("O", "D"):
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") in ("2FGA", "3FGA", "FTA"):
                    prev_action["leadsToRebound"] = generate_uri("action", euroleague_number_of_play, self.game_url_base)
                    break
        
        elif play_type in ("CM", "OF", "CMU"):
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if abs(prev_action["quarterSecondsRemaining"] - action_data["quarterSecondsRemaining"]) > 3:
                    break
                if prev_action.get("actionInfo") == "RV" and not prev_action.get("occuredByFoul"):
                    prev_action["occuredByFoul"] = generate_uri("action", action_data['originalEventId'], self.game_url_base)
                    break

        elif play_type == "CCH":
            action_data["actionInfo"] = "CCH"
            action_data["actionCoach"] = self.current_coaches.get(event.get("CODETEAM", "").strip())

        elif play_type == "C":
            action_data["actionInfo"] = "C"
            action_data["actionCoach"] = self.current_coaches.get(event.get("CODETEAM", "").strip())
        
        # Merging Substitutions (Τώρα τα κρατάμε ξεχωριστά!)
        if play_type in ("IN", "OUT"):
            # Δεν κάνουμε merge. Απλά ορίζουμε ποιος παίκτης μπαίνει ή βγαίνει
            if play_type == "IN":
                action_data["actionPlayer"] = generate_uri("player", player_id)
            else:
                action_data["actionPlayer"] = generate_uri("player", player_id)
                
            self.all_actions.append(action_data)
            
            # --- ΔΙΟΡΘΩΣΗ LINEUP ΓΙΑ ΠΟΛΛΑΠΛΕΣ ΑΛΛΑΓΕΣ ---
            # Υπολογίζουμε την ΠΡΑΓΜΑΤΙΚΗ πεντάδα όπως διαμορφώθηκε μετά την αλλαγή
            final_home = generate_uri("lineup", self.team_a, players_set=self.current_lineups[self.team_a])
            final_road = generate_uri("lineup", self.team_b, players_set=self.current_lineups[self.team_b])
            
            # Γυρνάμε στα Actions του ίδιου δευτερολέπτου και διορθώνουμε τις 5άδες σε όλα τα "IN" και "OUT"
            for prev_action in reversed(self.all_actions):
                if prev_action["clock"] != action_data["clock"]:
                    break  # Αν πάμε σε προηγούμενο χρόνο αγώνα, σταματάμε το ψάξιμο
                
                if prev_action.get("actionInfo") in ("IN", "OUT"):
                    prev_action["runningHomeTeamLineup"] = final_home
                    prev_action["runningRoadTeamLineup"] = final_road

            self._update_unique_lineups()      
            return     
        else:
            action_data["actionPlayer"] = generate_player_uri(player_id)
            action_data["actionPlayer"] = generate_uri("player", player_id)

            if play_type in ("2FGM", "2FGA", "3FGM", "3FGA", "FTM") and player_id:
                shot_key = euroleague_number_of_play
                if shot_key in self.shots_extra_data:
                    extra = self.shots_extra_data[shot_key]
                    
                    action_data["coord_x"] = extra["coord_x"]
                    action_data["coord_y"] = extra["coord_y"]
                    action_data["shotZone"] = extra["shotZone"]
                    
                    if extra['coord_x'] is not None and extra['coord_y'] is not None:
                        action_data["shotCoords"] = f"{extra['coord_x']},{extra['coord_y']}"
                        
                    if play_type in ("2FGA", "3FGA", "FTA"):
                        action_data["blockedBy"] = None
                        action_data["leadsToRebound"] = None
                        action_data["pointsAwarded"] = None
                    else:
                        action_data["pointsAwarded"] = extra["pointsAwarded"]
                        action_data["hasAssist"] = None
                        
                    action_data["isFastBreak"] = extra["isFastBreak"]
                    action_data["isSecondChance"] = extra["isSecondChance"]
                    action_data["isFromTurnover"] = extra["isFromTurnover"]
            elif play_type in ("FTA"):
                action_data["isFastBreak"] = False
                action_data["isSecondChance"] = False
                action_data["isFromTurnover"] = False
                action_data["coord_x"] = -1
                action_data["coord_y"] = -1
                action_data["shotZone"] = " "
                action_data["shotCoords"] = f"{action_data['coord_x']},{action_data['coord_y']}"
                action_data["blockedBy"] = None
                action_data["leadsToRebound"] = None
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

    # --------------------------------------------------
    # --- ΝΕΑ ΜΕΘΟΔΟΣ: STATE MACHINE ΓΙΑ POSSESSIONS ---
    # --------------------------------------------------
    def _build_possessions(self):
        self.possessions = []
        current_possession = None
        previous_action_id = None # Κρατάμε το ID του προηγούμενου play
        
        # Ενέργειες που υποδηλώνουν ότι η ομάδα έχει την κατοχή
        offensive_actions = {
            "TwoPointShotMade", "TwoPointShotMissed", 
            "ThreePointShotMade", "ThreePointShotMissed", 
            "FreeThrowMade", "FreeThrowMissed", 
            "Turnover", "OffensiveRebound", "OffensiveFoul", 
            "Assist", "FoulDrawn"
        }
        
        for action in self.all_actions:
            play_type = convert_action_info(action.get("actionInfo", ""))
            team = action.get("actionTeam")
            action_id = action["originalEventId"]
            
            # Κλείσιμο κατοχής αν τελειώσει το δεκάλεπτο
            if play_type in ("PeriodStart", "PeriodEnd", "GameEnd"):
                if current_possession:
                    if current_possession["containsAction"]:
                        current_possession["endsWithAction"] = current_possession["containsAction"][-1]
                    self.possessions.append(current_possession)
                    current_possession = None
                previous_action_id = action_id
                continue
                
            # Actions χωρίς ξεκάθαρη ομάδα (π.χ. TV Timeout) κολλάνε στην τρέχουσα κατοχή
            if not team:
                if current_possession:
                    current_possession["containsAction"].append(action_id)
                previous_action_id = action_id
                continue

            change_possession = False
            
            if not current_possession:
                if play_type in offensive_actions or play_type in ("DefensiveRebound", "Steal"):
                    change_possession = True
            else:
                current_off_team = current_possession["possessionTeam"]
                
                # Αλλαγή κατοχής βάσει ενεργειών από την ΑΛΛΗ ομάδα
                if play_type == "DefensiveRebound" and team != current_off_team:
                    change_possession = True
                elif play_type == "Steal" and team != current_off_team:
                    change_possession = True
                elif play_type in offensive_actions and team != current_off_team:
                    change_possession = True
                    
            if change_possession:
                if current_possession:
                    # Το endsWithAction είναι το τελευταίο καταγεγραμμένο action της κατοχής
                    if current_possession["containsAction"]:
                        current_possession["endsWithAction"] = current_possession["containsAction"][-1]
                    self.possessions.append(current_possession)
                
                # Αρχικοποίηση νέας Κατοχής
                current_possession = {
                    "possession_id": self.pos_seq,
                    "possessionTeam": team,  # <-- Ζητούμενο
                    "startsAfterAction": previous_action_id, # <-- Ζητούμενο
                    "endsWithAction": None, # <-- Ζητούμενο (Θα συμπληρωθεί στο τέλος)
                    "containsAction": [] # <-- Ζητούμενο
                }
                self.pos_seq += 1

            if current_possession:
                current_possession["containsAction"].append(action_id)
                
            previous_action_id = action_id
                
        # Αποθήκευση της τελευταίας κατοχής του αγώνα
        if current_possession:
            if current_possession["containsAction"]:
                current_possession["endsWithAction"] = current_possession["containsAction"][-1]
            self.possessions.append(current_possession)

    def run(self):
        standard_quarters = ["FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter"]
        for q in standard_quarters:
            self.process_period(q)

        if "ExtraTime" in self.data and self.data["ExtraTime"]:
            current_ot = 0
            current_ot_name = "OT" 
            for event in self.data["ExtraTime"]:
                if event["PLAYTYPE"] == "BP":
                    current_ot += 1
                    current_ot_name = f"{current_ot}OT"
                if event["PLAYTYPE"] in ("IN", "OUT"):
                    self.process_substitution(event)
                self.extract_action_data(event, current_ot_name)

        # Μόλις μαζευτούν όλα τα Actions, υπολογίζουμε τις Κατοχές
        self._build_possessions()

    # --------------------------------------------------
    # GENERATE RDF TRIPLETS
    # --------------------------------------------------
    def generate_triplets(self):
        triplets = []
        NS = "http://www.ics.forth.gr/isl/Basketball#"
        RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        XSD = "http://www.w3.org/2001/XMLSchema#"
        subj = f"<{self.game_url_base}"

        # 1. Base Game to Play links
        for plays in self.all_actions:
            triplets.append(f"{subj}> <{NS}hasPlayByPlayAction> {subj}#PlayByPlay_J{plays['originalEventId']}> .")

        triplets.append("\n")

        PROPERTY_MAPPING = {
            "quarter": ("quarter", "string"),
            "clock": ("clock", "string"),
            "quarterSecondsRemaining": ("quarterSecondsRemaining", "integer"),
            "runningHomeTeamScore": ("runningHomeTeamScore", "integer"),
            "runningRoadTeamScore": ("runningRoadTeamScore", "integer"),
            "runningHomeTeamLineup": ("runningHomeTeamLineup", "uri"),
            "runningRoadTeamLineup": ("runningRoadTeamLineup", "uri"),
            "actionTeam": ("actionTeam", "uri"),
            "actionPlayer": ("actionPlayer", "uri"),
            "actionCoach": ("actionCoach", "uri"),
            "pointsAwarded": ("pointsAwarded", "integer"),
            "hasAssist": ("hasAssist", "uri"),
            "shotCoords": ("shotCoords", "string"),
            "shotZone": ("shotZone", "string"),
            "isFastBreak": ("isFastBreak", "boolean"),
            "isSecondChance": ("isSecondChance", "boolean"),
            "isFromTurnover": ("isFromTurnover", "boolean"),
            "leadsToRebound": ("leadsToRebound", "uri"),
            "blockedBy": ("blockedBy", "uri"),
            "occuredByFoul": ("occuredByFoul", "uri"),
            "causedByFoul": ("causedByFoul", "uri"),
            "causedByViolation": ("causedByViolation", "boolean"),
            "causedBySteal": ("causedBySteal", "uri"),
        }

        # 2. Triplets for Play-by-Play Actions
        for action in self.all_actions:
            action_type = convert_action_info(action.get('actionInfo', ''))
            begin = f"{subj}#PlayByPlay_J{action['originalEventId']}>"
            
            if action.get('hasPlayByPlaySequence'):
                triplets.append(f"{begin} <{NS}hasPlayByPlaySequence> \"{action['hasPlayByPlaySequence']}\" .")
                
            triplets.append(f"{begin} <{RDF}> <{NS}{action_type}> .")

            for key, (predicate, data_type) in PROPERTY_MAPPING.items():
                value = action.get(key)
                if value is None: continue
                    
                if data_type == "uri":
                    triplets.append(f"{begin} <{NS}{predicate}> <{value}> .")
                elif data_type == "string":
                    triplets.append(f"{begin} <{NS}{predicate}> \"{value}\" .")
                elif data_type == "integer":
                    triplets.append(f"{begin} <{NS}{predicate}> \"{int(value)}\"^^<{XSD}integer> .")
                elif data_type == "boolean":
                    triplets.append(f"{begin} <{NS}{predicate}> \"{str(value).lower()}\"^^<{XSD}boolean> .")

            triplets.append("\n")

        # --------------------------------------------------
        # 3. Triplets for POSSESSIONS
        # --------------------------------------------------
        for pos in self.possessions:
            pos_uri = f"{subj}#Possession_{pos['possession_id']}>"
            
            # Ορισμός Entity
            triplets.append(f"{pos_uri} <{RDF}> <{NS}Possession> .")
            
            # Ιδιότητα: possessionTeam
            if pos.get('possessionTeam'):
                triplets.append(f"{pos_uri} <{NS}possessionTeam> <{pos['possessionTeam']}> .")
            
            # Ιδιότητα: startsAfterAction
            if pos.get('startsAfterAction'):
                start_act_uri = f"{subj}#PlayByPlay_J{pos['startsAfterAction']}>"
                triplets.append(f"{pos_uri} <{NS}startsAfterAction> {start_act_uri} .")
                
            # Ιδιότητα: endsWithAction (ΕΔΩ ΕΙΝΑΙ Η ΠΡΟΣΘΗΚΗ ΠΟΥ ΕΛΕΙΠΕ)
            if pos.get('endsWithAction'):
                end_act_uri = f"{subj}#PlayByPlay_J{pos['endsWithAction']}>"
                triplets.append(f"{pos_uri} <{NS}endsWithAction> {end_act_uri} .")
            
            # Ιδιότητα: containsAction (ΔΙΟΡΘΩΣΗ ΑΠΟ includesAction ΣΕ containsAction)
            if 'containsAction' in pos:
                for act_id in pos['containsAction']:
                    act_uri = f"{subj}#PlayByPlay_J{act_id}>"
                    triplets.append(f"{pos_uri} <{NS}containsAction> {act_uri} .")
                
            triplets.append("\n")
        
        # --------------------------------------------------
        # 4. Triplets for LINEUPS
        # --------------------------------------------------
        for team_code, players in self.unique_lineups:
            if not players: 
                continue
                
            # Χρησιμοποιούμε τη Helper συνάρτηση για να πάρουμε τα καθαρά URLs!
            lineup_url = generate_uri("lineup", team_code, players_set=players)
            team_url = generate_uri("team", team_code)
            
            lineup_uri = f"<{lineup_url}>"
            team_uri = f"<{team_url}>"
            
            triplets.append(f"{lineup_uri} <{RDF}> <{NS}Lineup> .")
            triplets.append(f"{lineup_uri} <{NS}lineupTeam> {team_uri} .")
            
            # Επαναληπτική κλήση της generate_uri για κάθε παίκτη της πεντάδας
            for pid in players:
                player_url = generate_uri("player", pid)
                player_uri = f"<{player_url}>"
                triplets.append(f"{lineup_uri} <{NS}includesPlayer> {player_uri} .")
            
            triplets.append("\n")

        return triplets
    
# ==================================================
# USAGE (DYNAMIC API FETCH)
# ==================================================

season_str = "2023-24"
season_code = "E2023"   
MAX_GAMES = 333 

# --- Δημιουργία Session για να φαίνεται σαν πραγματικός browser ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.euroleaguebasketball.net/",
    "Origin": "https://www.euroleaguebasketball.net"
})

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
output_dir = os.path.join(project_root, "data", "processed")
os.makedirs(output_dir, exist_ok=True)

def remove_nulls(obj):
    if isinstance(obj, list):
        return [remove_nulls(item) for item in obj if item is not None]
    elif isinstance(obj, dict):
        return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
    return obj

print(f"Starting batch process for Season {season_code}...")

for gc in range(73, MAX_GAMES + 1):
    game_code = str(gc)
    dynamic_game_url_base = f"https://www.euroleaguebasketball.net/euroleague/game-center/{season_str}/-/{season_code}/{game_code}"
    
    print(f"\n[{game_code}/{MAX_GAMES}] Fetching data from API...")
    
    try:
        # Χρησιμοποιούμε το 'session.get' αντί για 'requests.get'
        pbp_response = session.get(f"https://live.euroleague.net/api/PlaybyPlay?gamecode={game_code}&seasoncode={season_code}")
        
        # Αν μας μπλοκάρουν (403) ή έχουμε φτάσει στο όριο (429), περιμένουμε λίγο παραπάνω και ξαναδοκιμάζουμε
        if pbp_response.status_code in (403, 429):
            print(f"  -> Banned/Rate Limited (Status: {pbp_response.status_code})! Sleeping for 10 seconds...")
            time.sleep(10)
            pbp_response = session.get(f"https://live.euroleague.net/api/PlaybyPlay?gamecode={game_code}&seasoncode={season_code}")

        # Μικρή παύση 0.5 δευτ. ανάμεσα στα requests του ΙΔΙΟΥ παιχνιδιού
        time.sleep(0.5) 
        boxscore_response = session.get(f"https://live.euroleague.net/api/Boxscore?gamecode={game_code}&seasoncode={season_code}")
        time.sleep(0.5)
        points_response = session.get(f"https://live.euroleague.net/api/Points?gamecode={game_code}&seasoncode={season_code}")
        
        if pbp_response.status_code != 200:
            print(f"  -> Skipping... (Status: {pbp_response.status_code})")
            time.sleep(random.uniform(2.0, 3.5))
            continue
            
        pbp_data = pbp_response.json()
        boxscore_data = boxscore_response.json()
        points_data = points_response.json()
        
        if not pbp_data or not boxscore_data:
            print(f"  -> Game {game_code} has no valid JSON data. Skipping...")
            time.sleep(random.uniform(2.0, 3.5))
            continue

    except Exception as e:
        print(f"  -> Error fetching data for game {game_code}: {e}")
        time.sleep(5) # Αν "χτυπήσει" κάποιο timeout, περιμένουμε λίγο παραπάνω
        continue 

    print("  -> Data fetched successfully. Processing...")
    
    try:
        processor = GameProcessor(pbp_data, boxscore_data, points_data, dynamic_game_url_base)
        processor.run()
        
        output_json_path = os.path.join(output_dir, f"AllActions_{season_code}_{game_code}.json")
        output_triplets_path = os.path.join(output_dir, f"Triplets_{season_code}_{game_code}.nt")
        
        combined_output = {
            "Possessions": processor.possessions,
            "AllActions": processor.all_actions
        }
        cleaned_output = remove_nulls(combined_output)
        
        with open(output_json_path, "w", encoding="utf8") as out_file:
            json.dump(cleaned_output, out_file, ensure_ascii=False, indent=4)
            
        triplets = processor.generate_triplets()
        with open(output_triplets_path, "w", encoding="utf8") as out_file:
            for triple in triplets:
                out_file.write(triple + "\n")
                
        print(f"  -> Saved successfully: AllActions_{season_code}_{game_code}.json")
        
    except Exception as e:
        print(f"  -> Error processing or saving game {game_code}: {e}")

    # ΠΑΥΣΗ: Από 2.5 έως 4.5 δευτερόλεπτα (τυχαία) για να φαίνεται σαν άνθρωπος
    sleep_time = random.uniform(2.5, 4.5)
    time.sleep(sleep_time)

print("\nBatch processing complete! All games processed.")