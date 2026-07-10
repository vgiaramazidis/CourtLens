from itertools import count
import json
from collections import defaultdict
import os
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

def lineup_key(players):
    return tuple(sorted(players))

def convert_action_info(action_info):
    mapping = {
        "JB": "JumpBall",
        "BP": "PeriodStar",
        "EP": "#PeriodEnd",
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
        "AG": "ShotRejected",
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
        "IN": "SubstitutionIn",
        "OUT": "SubstitutionOut",
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

        # --- ΝΕΕΣ ΜΕΤΑΒΛΗΤΕΣ ΓΙΑ ΤΙΣ ΚΑΤΟΧΕΣ (POSSESSIONS) ---
        self.possessions = []
        self.pos_seq = 1 

        # Dynamic Starters integration
        self.current_lineups = self._extract_starters(boxscore_data)
        
        # Extract Coaches dynamically
        self.current_coaches = {}
        for team_stat in boxscore_data["Stats"]:
            team_code = team_stat["Team"].strip()
            matched_code = self.team_a if team_code.startswith(self.team_a[:3]) else self.team_b
            self.current_coaches[matched_code] = generate_uri("coach", team_stat.get("Coach", ""))
        
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

    def extract_action_data(self, event, period_name):
        play_type = event.get("PLAYTYPE", "")
        player_id = event.get("PLAYER_ID", "").strip() if event.get("PLAYER_ID") else None

        euroleague_number_of_play = event.get("NUMBEROFPLAY")

        # --- ΝΕΟ ΚΟΜΜΑΤΙ: Μετατροπή του Quarter ---
        quarter_mapping = {
            "FirstQuarter": "1st",
            "SecondQuarter": "2nd",
            "ThirdQuarter": "3rd",
            "ForthQuarter": "4th", # Πρόσεξε: Στη μέθοδο run() το είχες γράψει ForthQuarter χωρίς 'u', οπότε το αφήνουμε έτσι για να το βρει!
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
                if prev_action.get("actionInfo") in ("2FGM", "3FGM", "FTM") and prev_action["actionTeam"] == action_data["actionTeam"]:
                    if prev_action["quarter"] == action_data["quarter"]:
                        prev_action["hasAssist"] = generate_uri("action", euroleague_number_of_play, self.game_url_base)
                        action_data["associatedAction"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
                        break

        elif play_type == "FV":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") in ("2FGA", "3FGA") and prev_action["quarter"] == action_data["quarter"]:
                    if prev_action["actionTeam"] != action_data["actionTeam"]:
                        prev_action["blockedBy"] = generate_uri("action", euroleague_number_of_play,self.game_url_base)
                        action_data["associatedAction"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
                        break

        elif play_type == "AG":
                for prev_action in reversed(self.all_actions):
                    if prev_action.get("actionInfo") in ("2FGA", "3FGA") and prev_action["clock"] == action_data["clock"]:
                        if prev_action["actionTeam"] == action_data["actionTeam"]:
                            action_data["associatedAction"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
                            break

        elif play_type == "ST":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") == "TO" and prev_action["quarter"] == action_data["quarter"]:
                    if prev_action["actionTeam"] != action_data["actionTeam"]:
                        prev_action["causedBySteal"] = generate_uri("action", euroleague_number_of_play, self.game_url_base)
                        action_data["associatedAction"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
                        break
                        
        elif play_type == "TO":
            action_data["causedByFoul"] = False
            action_data["causedByViolation"] = False
            action_data["causedBySteal"] = False
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") in ("CM", "OF", "U", "T", "C", "B") and prev_action["clock"] == action_data["clock"]:
                    action_data["causedByFoul"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
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
        
        elif play_type == "RV":
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") in ("TO", "CM", "CMU") and prev_action["quarter"] == action_data["quarter"]:
                    action_data["occuredByFoul"] = generate_uri("action", prev_action['hasPlayByPlaySequence'], self.game_url_base)
                    break

        elif play_type == "CCH":
            action_data["actionInfo"] = "CCH"
            action_data["actionCoach"] = self.current_coaches.get(event.get("CODETEAM", "").strip())

        elif play_type == "C":
            action_data["actionInfo"] = "C"
            action_data["actionCoach"] = self.current_coaches.get(event.get("CODETEAM", "").strip())
        
        if play_type in ("IN", "OUT"):
            merged = False
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") == "Substitution" and prev_action["clock"] == action_data["clock"] and prev_action["actionTeam"] == action_data["actionTeam"]:
                    if play_type == "IN" and prev_action.get("playerIn") is None:
                        prev_action["playerIn"] = generate_uri("player", player_id)
                        merged = True
                        break
                    elif play_type == "OUT" and prev_action.get("playerOut") is None:
                        prev_action["playerOut"] = generate_uri("player", player_id)
                        merged = True
                        break

            # Αν δεν βρήκαμε προηγούμενο μισό-Substitution για να το ενώσουμε, φτιάχνουμε νέο
            if not merged:
                action_data["actionInfo"] = "Substitution"
                action_data["playerIn"] = generate_uri("player", player_id) if play_type == "IN" else None
                action_data["playerOut"] = generate_uri("player", player_id) if play_type == "OUT" else None
                self.all_actions.append(action_data)
            
            # --- ΔΙΟΡΘΩΣΗ LINEUP ΓΙΑ ΠΟΛΛΑΠΛΕΣ ΑΛΛΑΓΕΣ ---
            # Υπολογίζουμε την ΠΡΑΓΜΑΤΙΚΗ πεντάδα όπως διαμορφώθηκε μετά την αλλαγή
            final_home = generate_uri("lineup", self.team_a, players_set=self.current_lineups[self.team_a])
            final_road = generate_uri("lineup", self.team_b, players_set=self.current_lineups[self.team_b])
            
            # Γυρνάμε στα Actions του ίδιου δευτερολέπτου και διορθώνουμε τις 5άδες σε όλα
            for prev_action in reversed(self.all_actions):
                if prev_action["clock"] != action_data["clock"]:
                    break  # Αν πάμε σε προηγούμενο χρόνο αγώνα, σταματάμε το ψάξιμο
                
                if prev_action.get("actionInfo") == "Substitution":
                    prev_action["runningHomeTeamLineup"] = final_home
                    prev_action["runningRoadTeamLineup"] = final_road
                    
            return         
        else:
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
                action["belongsToPossession"] = current_possession["possession_id"]
                
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
            current_ot_name = "ExtraTime1" 
            for event in self.data["ExtraTime"]:
                if event["PLAYTYPE"] == "BP":
                    current_ot += 1
                    current_ot_name = f"ExtraTime{current_ot}"
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
        XSD = ""
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
            "playerIn": ("playerIn", "uri"),
            "playerOut": ("playerOut", "uri"),
            "pointsAwarded": ("pointsAwarded", "integer"),
            "hasAssist": ("hasAssist", "uri"),
            "shotCoords": ("shotCoords", "string"),
            "shotZone": ("shotZone", "string"),
            "isFastBreak": ("isFastBreak", "boolean"),
            "isSecondChance": ("isSecondChance", "boolean"),
            "isFromTurnover": ("isFromTurnover", "boolean"),
            "leadsToRebound": ("leadsToRebound", "uri"),
            "blockedBy": ("blockedBy", "uri"),
            #"associatedAction": ("associatedAction", "uri"),
            "occuredByFoul": ("occuredByFoul", "uri"),
            "causedByFoul": ("causedByFoul", "uri"),
            "causedByViolation": ("causedByViolation", "boolean"),
            "causedBySteal": ("causedBySteal", "uri"),
            # Link action to its possession container
            "belongsToPossession": ("belongsToPossession", "integer") 
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
                if value is None or value is False: continue
                    
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
        return triplets 
    
# ==================================================
# USAGE (DYNAMIC API FETCH)
# ==================================================

season_str = "2024-25"
season_code = "E2024"   
game_code = "200"       

dynamic_game_url_base = f"https://www.euroleaguebasketball.net/euroleague/game-center/{season_str}/-/{season_code}/{game_code}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

print(f"Fetching data for Game {game_code} (Season {season_code}) from Euroleague API...")

try:
    pbp_response = requests.get(f"https://live.euroleague.net/api/PlaybyPlay?gamecode={game_code}&seasoncode={season_code}", headers=headers)
    boxscore_response = requests.get(f"https://live.euroleague.net/api/Boxscore?gamecode={game_code}&seasoncode={season_code}", headers=headers)
    points_response = requests.get(f"https://live.euroleague.net/api/Points?gamecode={game_code}&seasoncode={season_code}", headers=headers)
    
    pbp_data = pbp_response.json()
    boxscore_data = boxscore_response.json()
    points_data = points_response.json()

except Exception as e:
    print(f"Error fetching data from API: {e}")
    exit(1)

print("Data fetched successfully. Processing...")

processor = GameProcessor(pbp_data, boxscore_data, points_data, dynamic_game_url_base)
processor.run()

# --- Αποθήκευση ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
output_dir = os.path.join(project_root, "data", "processed")
os.makedirs(output_dir, exist_ok=True)

output_json_path = os.path.join(output_dir, f"AllActions_{season_code}_{game_code}.json")
output_triplets_path = os.path.join(output_dir, f"Triplets_{season_code}_{game_code}.nt")

print(f"Saving merged JSON to: {output_json_path}")
# Φτιάχνουμε ένα συνολικό αντικείμενο που έχει ΚΑΙ τα Actions ΚΑΙ τα Possessions
combined_output = {
    "Possessions": processor.possessions,
    "AllActions": processor.all_actions
}

with open(output_json_path, "w", encoding="utf8") as out_file:
    json.dump(combined_output, out_file, ensure_ascii=False, indent=4)
print(f"Saving Triplets to: {output_triplets_path}")
triplets = processor.generate_triplets()
with open(output_triplets_path, "w", encoding="utf8") as out_file:
    for triple in triplets:
        out_file.write(triple + "\n")

print("Processing complete!")