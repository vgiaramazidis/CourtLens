import json
from collections import defaultdict
from copy import deepcopy


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


def period_length(period_name):
    if "ExtraTime" in period_name:
        return 300
    return 600


def lineup_key(players):
    return tuple(sorted(players))


def create_stat_line():
    return {
        "seconds": 0,
        "plus_minus": 0,

        "pts_for": 0,
        "pts_against": 0,

        # offense
        "2pm": 0,
        "2pa": 0,
        "3pm": 0,
        "3pa": 0,
        "ftm": 0,
        "fta": 0,

        # opponent raw
        "opp_2pm": 0,
        "opp_2pa": 0,
        "opp_3pm": 0,
        "opp_3pa": 0,
        "opp_ftm": 0,
        "opp_fta": 0,

        # misc
        "oreb": 0,
        "dreb": 0,
        "reb": 0,
        "ast": 0,
        "stl": 0,
        "blk": 0,
        "bla": 0,
        "to": 0,
        "pf": 0,
        "fd": 0,
    }


# --------------------------------------------------
# MAIN CLASS
# --------------------------------------------------

class GameProcessor:

    def __init__(self, data, starting_lineups):

        self.data = data

        self.team_a = data["CodeTeamA"].strip()
        self.team_b = data["CodeTeamB"].strip()

        self.current_lineups = {
            self.team_a: set(starting_lineups[self.team_a]),
            self.team_b: set(starting_lineups[self.team_b]),
        }

        self.lineup_stats = {
            self.team_a: defaultdict(create_stat_line),
            self.team_b: defaultdict(create_stat_line),
        }

        self.player_names = {}

    # --------------------------------------------------

    # --------------------------------------------------
    def extract_action_data(self, event, period_name):
        if not event.get("MARKERTIME"):
            return

        play_type = event.get("PLAYTYPE", "")

        # 1. Φτιάχνουμε ΟΛΑ τα κοινά χαρακτηριστικά από την αρχή
        action_data = {
            "hasPlayByPlaySequence": event["NUMBEROFPLAY"],
            "quarter": period_name,
            "associatedTeam": event["CODETEAM"].strip(),
            "clock": event["MARKERTIME"],
            "quarterSecondsRemaining": clock_to_seconds(event["MARKERTIME"]),
            "runningHomeTeamScore": event.get("POINTS_A"),
            "runningRoadTeamScore": event.get("POINTS_B"),
            "hasHomeTeamLineup": generate_lineup_uri(self.team_a, self.current_lineups[self.team_a]),
            "hasRoadTeamLineup": generate_lineup_uri(self.team_b, self.current_lineups[self.team_b]),
            "play_type": play_type,
        }

        # 2. Λογική αν η φάση είναι Substitution
        if play_type in ("IN", "OUT"):
            player_id = event["PLAYER_ID"].strip()
            
            # Ψάχνουμε στα προηγούμενα αν υπάρχει το "μισό" αυτής της αλλαγής που να έχει ΑΔΕΙΟ το αντίστοιχο slot
            for prev_action in reversed(self.all_actions):
                if prev_action.get("play_type") == "Substitution" and prev_action["clock"] == action_data["clock"] and prev_action["associatedTeam"] == action_data["associatedTeam"]:
                    
                    if play_type == "IN" and prev_action.get("playerIn") is None:
                        prev_action["playerIn"] = player_id
                        return # Ταιριάξαμε, φεύγουμε!
                        
                    elif play_type == "OUT" and prev_action.get("playerOut") is None:
                        prev_action["playerOut"] = player_id
                        return # Ταιριάξαμε, φεύγουμε!

            # Αν δεν βρήκαμε ταίρι (ή αν η προηγούμενη αλλαγή ήταν ήδη "γεμάτη"), φτιάχνουμε νέα
            action_data["play_type"] = "Substitution"
            if play_type == "IN":
                action_data["playerIn"] = player_id
                action_data["playerOut"] = None
            else:
                action_data["playerIn"] = None
                action_data["playerOut"] = player_id
                
            self.all_actions.append(action_data)
            return
                
        else:
            # 3. Αν είναι οποιαδήποτε άλλη φάση (Σουτ, Ασίστ κτλ), απλά προσθέτουμε τον παίκτη
            action_data["associatedPlayer"] = event["PLAYER_ID"].strip()

        # Τέλος, το προσθέτουμε στη λίστα μας
        self.all_actions.append(action_data)

    # --------------------------------------------------
    def lineup_is_valid(self, st):
        return (
            st["seconds"] > 0 or
            st["pts_for"] > 0 or
            st["pts_against"] > 0 or
            st["2pa"] > 0 or
            st["3pa"] > 0 or
            st["fta"] > 0 or
            st["oreb"] > 0 or
            st["dreb"] > 0 or
            st["ast"] > 0 or
            st["stl"] > 0 or
            st["to"] > 0 or
            st["pf"] > 0
        )

    # --------------------------------------------------

    def add_time(self, team_code, seconds):

        if seconds <= 0:
            return

        lu = lineup_key(self.current_lineups[team_code])
        self.lineup_stats[team_code][lu]["seconds"] += seconds

    # --------------------------------------------------

    def add_both_lineups_time(self, seconds):
        self.add_time(self.team_a, seconds)
        self.add_time(self.team_b, seconds)

    # --------------------------------------------------

    def score_event(self, team_code, points):

        opponent = (
            self.team_b if team_code == self.team_a else self.team_a
        )

        lineup_team = lineup_key(self.current_lineups[team_code])
        lineup_opp = lineup_key(self.current_lineups[opponent])

        self.lineup_stats[team_code][lineup_team]["pts_for"] += points
        self.lineup_stats[team_code][lineup_team]["plus_minus"] += points

        self.lineup_stats[opponent][lineup_opp]["pts_against"] += points
        self.lineup_stats[opponent][lineup_opp]["plus_minus"] -= points

    # --------------------------------------------------

    # --------------------------------------------------

    def process_stat(self, event):

        team = event["CODETEAM"].strip()
        play = event["PLAYTYPE"]

        if team not in (self.team_a, self.team_b):
            return

        lineup = lineup_key(self.current_lineups[team])
        stats = self.lineup_stats[team][lineup]

        if play == "2FGM":
            stats["2pm"] += 1
            stats["2pa"] += 1
            self.score_event(team, 2)

        elif play == "2FGA":
            stats["2pa"] += 1

        elif play == "3FGM":
            stats["3pm"] += 1
            stats["3pa"] += 1
            self.score_event(team, 3)

        elif play == "3FGA":
            stats["3pa"] += 1

        elif play == "FTM":
            stats["ftm"] += 1
            stats["fta"] += 1
            self.score_event(team, 1)

        elif play == "FTA":
            stats["fta"] += 1

        elif play == "AG":
            stats["bla"] += 1

        elif play == "FV":
            stats["blk"] += 1

        elif play == "O":
            stats["oreb"] += 1
            stats["reb"] += 1

        elif play == "D":
            stats["dreb"] += 1
            stats["reb"] += 1

        elif play == "AS":
            stats["ast"] += 1

        elif play == "ST":
            stats["stl"] += 1

        elif play == "TO":
            stats["to"] += 1

        elif play in ("CM", "OF"):
            stats["pf"] += 1

        elif play == "RV":
            stats["fd"] += 1

        # 🔥 opponent stats
        self.process_opponent_stat(event)



    # --------------------------------------------------

    def process_opponent_stat(self, event):

        team = event["CODETEAM"].strip()

        if team not in (self.team_a, self.team_b):
            return

        opponent = (
            self.team_b if team == self.team_a else self.team_a
        )

        opp_lineup = lineup_key(self.current_lineups[opponent])
        stats = self.lineup_stats[opponent][opp_lineup]

        play = event["PLAYTYPE"]

        if play == "2FGM":
            stats["opp_2pm"] += 1
            stats["opp_2pa"] += 1

        elif play == "2FGA":
            stats["opp_2pa"] += 1

        elif play == "3FGM":
            stats["opp_3pm"] += 1
            stats["opp_3pa"] += 1

        elif play == "3FGA":
            stats["opp_3pa"] += 1

        elif play == "FTM":
            stats["opp_ftm"] += 1
            stats["opp_fta"] += 1

        elif play == "FTA":
            stats["opp_fta"] += 1

    # --------------------------------------------------

    def process_substitution(self, event):

        team = event["CODETEAM"].strip()

        if team not in (self.team_a, self.team_b):
            return

        player_id = event["PLAYER_ID"].strip()

        if not player_id:
            return

        if event["PLAYER"]:
            self.player_names[player_id] = event["PLAYER"]

        if event["PLAYTYPE"] == "IN":
            self.current_lineups[team].add(player_id)

        elif event["PLAYTYPE"] == "OUT":
            self.current_lineups[team].discard(player_id)

    # --------------------------------------------------

    def process_period(self, period_name):

        if period_name not in self.data:
            return

        plays = self.data[period_name]

        if not plays:
            return

        previous_clock = period_length(period_name)

        for event in plays:

            clock = event.get("MARKERTIME")

            if clock:
                current_clock = clock_to_seconds(clock)
                elapsed = previous_clock - current_clock

                if elapsed > 0:
                    self.add_both_lineups_time(elapsed)

                previous_clock = current_clock

            self.process_stat(event)

            if event["PLAYTYPE"] in ("IN", "OUT"):
                self.process_substitution(event)

        if previous_clock > 0:
            self.add_both_lineups_time(previous_clock)

    # --------------------------------------------------

    def run(self):
        for q in QUARTERS:
            self.process_period(q)

    # --------------------------------------------------

    def format_time(self, seconds):
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    # --------------------------------------------------

    def print_team(self, team_code):

        print("\n" + "=" * 70)
        print(team_code)
        print("=" * 70)

        lineups = sorted(
            [
                (lu, st)
                for lu, st in self.lineup_stats[team_code].items()
                if self.lineup_is_valid(st)
            ],
            key=lambda x: x[1]["seconds"],
            reverse=True
        )

        for lineup, st in lineups:

            names = [
                self.player_names.get(pid, pid)
                for pid in lineup
            ]

            print("\nLINEUP:")
            print(" | ".join(names))

            print(f"\nTIME: {self.format_time(st['seconds'])}")
            print(f"PLUS_MINUS: {st['plus_minus']:+d}")
            print(f"PTS_FOR: {st['pts_for']}")
            print(f"PTS_AGAINST: {st['pts_against']}")

            print(f"2PM/2PA: {st['2pm']}/{st['2pa']}")
            print(f"3PM/3PA: {st['3pm']}/{st['3pa']}")
            print(f"FTM/FTA: {st['ftm']}/{st['fta']}")


            print(f"OPP: 2PM/2PA: {st['opp_2pm']}/{st['opp_2pa']}")
            print(f"OPP: 3PM/3PA: {st['opp_3pm']}/{st['opp_3pa']}")
            print(f"OPP: FTM/FTA: {st['opp_ftm']}/{st['opp_fta']}")

            print(f"OREB: {st['oreb']}")
            print(f"DREB: {st['dreb']}")
            print(f"REB : {st['reb']}")
            print(f"AST : {st['ast']}")
            print(f"STL : {st['stl']}")
            print(f"BLK : {st['blk']}")
            print(f"BLA : {st['bla']}")
            print(f"TO  : {st['to']}")
            print(f"PF  : {st['pf']}")
            print(f"FD  : {st['fd']}")

            print("-" * 70)

    # --------------------------------------------------

    def print_results(self):
        self.print_team(self.team_a)
        self.print_team(self.team_b)


# ==================================================
# USAGE
# ==================================================

with open("data/raw/PlaybyPlay.json", "r", encoding="utf8") as f:
    data = json.load(f)

starting_lineups = {
    "ZAL": {"P007975","P003210","P011983","P007513","P005504"},
    "PAN": {"P011442","P012774","P005161","P007866","P003842"},
}

processor = GameProcessor(data, starting_lineups)
processor.run()
#processor.print_results()
#print(processor.all_actions)
