"""Convert EuroLeague game feeds into ordered actions, lineups and RDF artifacts."""

import argparse
import json
import os
import random
import re
import time
from collections import Counter

import requests


def clock_to_seconds(clock_str):
    if not clock_str:
        return 0
    m, s = map(int, clock_str.split(":"))
    return m * 60 + s


def normalize_marker_time(clock_str):
    """Clamp malformed negative end-of-period API clocks to game-clock zero."""
    value = str(clock_str or "").strip()
    if value and clock_to_seconds(value) < 0:
        return "00:00"
    return value


def period_length(period_name):
    normalized_period = str(period_name or "").upper()
    return 300 if "EXTRATIME" in normalized_period or "OT" in normalized_period else 600


def default_marker_time(play_type, period_name):
    if play_type == "BP":
        return f"{period_length(period_name) // 60:02d}:00"
    if play_type in ("EP", "EG"):
        return "00:00"
    return ""


def generate_uri(entity_type, value, game_url_base=None, players_set=None):
    if not value and entity_type != "lineup":
        return None

    if entity_type == "team":
        clean_code = value.strip()
        return f"https://www.euroleaguebasketball.net/euroleague/teams/-/{clean_code}"

    elif entity_type == "player":
        pid = value.replace("P", "").strip()
        return f"https://www.euroleaguebasketball.net/euroleague/players/-/{pid}"

    elif entity_type == "coach":
        clean_name = value.strip().replace(", ", "-").replace(" ", "-").lower()
        return f"https://www.euroleaguebasketball.net/euroleague/coaches/-/{clean_name}"

    elif entity_type == "action":
        return f"{game_url_base}#PlayByPlay_J{value}"

    elif entity_type == "lineup":
        if not players_set:
            return ""
        clean_ids = sorted([pid.replace("P", "").strip() for pid in players_set])
        lineup_str = "_".join(clean_ids)
        return (
            f"https://www.euroleaguebasketball.net/euroleague/teams/-/{value}#Lineup_{lineup_str}"
        )

    return None


def generate_coach_uri(coach_name):
    if not coach_name:
        return None
    clean_name = coach_name.strip().replace(", ", "_").replace(" ", "_")
    return f"https://www.euroleaguebasketball.net/euroleague/coaches/-/{clean_name}"


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
        "CCH": "Challenge",
    }
    return mapping.get(action_info, action_info)


class GameProcessor:
    """Track game state while linking actions, possessions and five-player lineups."""

    def __init__(self, pbp_data, boxscore_data, points_data, game_url_base):
        self.data = pbp_data
        self.game_url_base = game_url_base
        self.team_a = pbp_data["CodeTeamA"].strip()
        self.team_b = pbp_data["CodeTeamB"].strip()
        self.current_score_a = 0
        self.current_score_b = 0
        self.play_seq = 1

        # Deduplicate lineups before exporting RDF.
        self.unique_lineups = set()
        # Track possession boundaries independently of lineup changes.
        self.possessions = []
        self.pos_seq = 1

        self.current_lineups = self._extract_starters(boxscore_data)
        self._update_unique_lineups()

        self.current_coaches = {}
        for team_stat in boxscore_data["Stats"]:
            team_code = team_stat["Team"].strip()
            matched_code = self.team_a if team_code.startswith(self.team_a[:3]) else self.team_b
            self.current_coaches[matched_code] = generate_coach_uri(team_stat.get("Coach", ""))

        self.shots_extra_data = self._map_points_data(points_data)
        self.all_actions = []

    def _extract_starters(self, boxscore_data):
        starters = {self.team_a: set(), self.team_b: set()}
        for index, team_stat in enumerate(boxscore_data["Stats"]):
            # Index 0 is the home team; index 1 is the road team.
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
                "isFromTurnover": bool(int(row.get("POINTS_OFF_TURNOVER", "0"))),
            }
        return shot_map

    def _update_unique_lineups(self):
        # Partial lineups must not become five-player groups in the RDF export.
        if len(self.current_lineups[self.team_a]) == 5:
            self.unique_lineups.add((self.team_a, tuple(sorted(self.current_lineups[self.team_a]))))

        if len(self.current_lineups[self.team_b]) == 5:
            self.unique_lineups.add((self.team_b, tuple(sorted(self.current_lineups[self.team_b]))))

    def extract_action_data(self, event, period_name):
        play_type = event.get("PLAYTYPE", "")
        if play_type == "AG":
            return  # Intentionally excluded from generated action artifacts.

        player_id = event.get("PLAYER_ID", "").strip() if event.get("PLAYER_ID") else None

        euroleague_number_of_play = event.get("NUMBEROFPLAY")

        # Normalize regulation and overtime period labels.
        quarter_mapping = {
            "FirstQuarter": "1st",
            "SecondQuarter": "2nd",
            "ThirdQuarter": "3rd",
            "ForthQuarter": "4th",
            "ExtraTime1": "OT",
            "ExtraTime2": "2OT",
            "ExtraTime3": "3OT",
            "ExtraTime4": "4OT",
        }
        mapped_quarter = quarter_mapping.get(period_name, period_name)

        # Period boundaries can omit the clock in the source feed.
        markertime = normalize_marker_time(
            event.get("MARKERTIME") or default_marker_time(play_type, mapped_quarter)
        )

        if event.get("POINTS_A") is not None:
            self.current_score_a = event["POINTS_A"]
        if event.get("POINTS_B") is not None:
            self.current_score_b = event["POINTS_B"]

        action_data = {
            "hasPlayByPlaySequence": self.play_seq,
            "originalEventId": euroleague_number_of_play,
            "quarter": mapped_quarter,
            "actionTeam": generate_uri("team", event.get("CODETEAM", "").strip()),
            "clock": markertime,
            "quarterSecondsRemaining": clock_to_seconds(markertime),
            "runningHomeTeamScore": self.current_score_a,
            "runningRoadTeamScore": self.current_score_b,
            "runningHomeTeamLineup": generate_uri(
                "lineup", self.team_a, players_set=self.current_lineups[self.team_a]
            ),
            "runningRoadTeamLineup": generate_uri(
                "lineup", self.team_b, players_set=self.current_lineups[self.team_b]
            ),
            "actionInfo": play_type,
        }
        self.play_seq += 1

        # Link related events while preserving each source action's identity.
        if play_type == "AS":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if (
                    prev_action.get("actionInfo") in ("2FGM", "3FGM", "FTM")
                    and prev_action["actionTeam"] == action_data["actionTeam"]
                ):
                    prev_action["hasAssist"] = generate_uri(
                        "action", euroleague_number_of_play, self.game_url_base
                    )
                    break

        elif play_type == "FV":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if (
                    prev_action.get("actionInfo") in ("2FGA", "3FGA")
                    and prev_action["actionTeam"] != action_data["actionTeam"]
                ):
                    prev_action["blockedBy"] = generate_uri(
                        "action", euroleague_number_of_play, self.game_url_base
                    )
                    break

        elif play_type == "ST":
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if (
                    abs(
                        prev_action["quarterSecondsRemaining"]
                        - action_data["quarterSecondsRemaining"]
                    )
                    > 3
                ):
                    break
                if (
                    prev_action.get("actionInfo") == "TO"
                    and prev_action["actionTeam"] != action_data["actionTeam"]
                ):
                    prev_action["causedBySteal"] = generate_uri(
                        "action", euroleague_number_of_play, self.game_url_base
                    )
                    break

        elif play_type == "TO":
            action_data["causedByFoul"] = None
            action_data["causedByViolation"] = None
            action_data["causedBySteal"] = None
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if (
                    abs(
                        prev_action["quarterSecondsRemaining"]
                        - action_data["quarterSecondsRemaining"]
                    )
                    > 3
                ):
                    break
                if prev_action.get("actionInfo") == "OF":
                    action_data["causedByFoul"] = generate_uri(
                        "action", prev_action["originalEventId"], self.game_url_base
                    )
                    break

            play_info = event.get("PLAYINFO", "").lower()
            violation_keywords = [
                "travel",
                "second",
                "out of bound",
                "step",
                "violation",
                "carry",
                "goaltend",
            ]
            if any(kw in play_info for kw in violation_keywords):
                action_data["causedByViolation"] = True

        elif play_type in ("O", "D"):
            for prev_action in reversed(self.all_actions):
                if prev_action.get("actionInfo") in ("2FGA", "3FGA", "FTA"):
                    prev_action["leadsToRebound"] = generate_uri(
                        "action", euroleague_number_of_play, self.game_url_base
                    )
                    break

        elif play_type in ("CM", "OF", "CMU"):
            for prev_action in reversed(self.all_actions):
                if prev_action["quarter"] != action_data["quarter"]:
                    break
                if (
                    abs(
                        prev_action["quarterSecondsRemaining"]
                        - action_data["quarterSecondsRemaining"]
                    )
                    > 3
                ):
                    break
                if prev_action.get("actionInfo") == "RV" and not prev_action.get("occuredByFoul"):
                    prev_action["occuredByFoul"] = generate_uri(
                        "action", action_data["originalEventId"], self.game_url_base
                    )
                    break

        elif play_type in ("CCH", "C"):
            action_data["actionCoach"] = self.current_coaches.get(event.get("CODETEAM", "").strip())

        # Preserve each substitution as a separate event.
        if play_type in ("IN", "OUT"):
            action_data["actionPlayer"] = generate_uri("player", player_id)
            self.all_actions.append(action_data)

            # Multiple substitutions can share the same game clock.
            # Compute the lineup after the substitution.
            final_home = generate_uri(
                "lineup", self.team_a, players_set=self.current_lineups[self.team_a]
            )
            final_road = generate_uri(
                "lineup", self.team_b, players_set=self.current_lineups[self.team_b]
            )

            # Apply that lineup to substitution events at the same clock time.
            for prev_action in reversed(self.all_actions):
                if prev_action["clock"] != action_data["clock"]:
                    break  # Earlier clock times belong to a different substitution sequence.

                if prev_action.get("actionInfo") in ("IN", "OUT"):
                    prev_action["runningHomeTeamLineup"] = final_home
                    prev_action["runningRoadTeamLineup"] = final_road

            self._update_unique_lineups()
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

                    if extra["coord_x"] is not None and extra["coord_y"] is not None:
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

    def _build_possessions(self):
        """Group ordered actions by changes in team control and period boundaries."""
        self.possessions = []
        current_possession = None
        previous_action_id = None  # The next possession starts after this event.

        # These action types establish which team controls the ball.
        offensive_actions = {
            "TwoPointShotMade",
            "TwoPointShotMissed",
            "ThreePointShotMade",
            "ThreePointShotMissed",
            "FreeThrowMade",
            "FreeThrowMissed",
            "Turnover",
            "OffensiveRebound",
            "OffensiveFoul",
            "Assist",
            "FoulDrawn",
        }

        for action in self.all_actions:
            play_type = convert_action_info(action.get("actionInfo", ""))
            team = action.get("actionTeam")
            action_id = action["originalEventId"]

            # A period boundary always ends the current possession.
            if play_type in ("PeriodStart", "PeriodEnd", "GameEnd"):
                if current_possession:
                    if current_possession["containsAction"]:
                        current_possession["endsWithAction"] = current_possession["containsAction"][
                            -1
                        ]
                    self.possessions.append(current_possession)
                    current_possession = None
                previous_action_id = action_id
                continue

            # Neutral events, such as broadcast timeouts, stay in the current possession.
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

                # An action by the other team can signal a change in possession.
                if play_type == "DefensiveRebound" and team != current_off_team:
                    change_possession = True
                elif play_type == "Steal" and team != current_off_team:
                    change_possession = True
                elif play_type in offensive_actions and team != current_off_team:
                    change_possession = True

            if change_possession:
                if current_possession:
                    # End at the last recorded action before control changed.
                    if current_possession["containsAction"]:
                        current_possession["endsWithAction"] = current_possession["containsAction"][
                            -1
                        ]
                    self.possessions.append(current_possession)

                current_possession = {
                    "possession_id": self.pos_seq,
                    "possessionTeam": team,
                    "startsAfterAction": previous_action_id,
                    "endsWithAction": None,  # Filled when this possession ends.
                    "containsAction": [],
                }
                self.pos_seq += 1

            if current_possession:
                current_possession["containsAction"].append(action_id)

            previous_action_id = action_id

        # Flush the final possession when the game ends.
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

        # Possessions depend on the complete ordered action list.
        self._build_possessions()

    def generate_triplets(self):
        """Export game links, actions, possessions and lineups as N-Triples."""
        triplets = []
        NS = "http://www.ics.forth.gr/isl/Basketball#"
        RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        XSD = "http://www.w3.org/2001/XMLSchema#"
        subj = f"<{self.game_url_base}"

        # Game membership.
        for plays in self.all_actions:
            triplets.append(
                f"{subj}> <{NS}hasPlayByPlayAction> {subj}#PlayByPlay_J{plays['originalEventId']}> ."
            )

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

        # Action types and properties.
        for action in self.all_actions:
            action_type = convert_action_info(action.get("actionInfo", ""))
            begin = f"{subj}#PlayByPlay_J{action['originalEventId']}>"

            if action.get("hasPlayByPlaySequence"):
                triplets.append(
                    f'{begin} <{NS}hasPlayByPlaySequence> "{action["hasPlayByPlaySequence"]}" .'
                )

            triplets.append(f"{begin} <{RDF}> <{NS}{action_type}> .")

            for key, (predicate, data_type) in PROPERTY_MAPPING.items():
                value = action.get(key)
                if value is None:
                    continue

                if data_type == "uri":
                    triplets.append(f"{begin} <{NS}{predicate}> <{value}> .")
                elif data_type == "string":
                    triplets.append(f'{begin} <{NS}{predicate}> "{value}" .')
                elif data_type == "integer":
                    triplets.append(f'{begin} <{NS}{predicate}> "{int(value)}"^^<{XSD}integer> .')
                elif data_type == "boolean":
                    triplets.append(
                        f'{begin} <{NS}{predicate}> "{str(value).lower()}"^^<{XSD}boolean> .'
                    )

            triplets.append("\n")

        # Possession boundaries and membership.
        for pos in self.possessions:
            pos_uri = f"{subj}#Possession_{pos['possession_id']}>"

            triplets.append(f"{pos_uri} <{RDF}> <{NS}Possession> .")

            if pos.get("possessionTeam"):
                triplets.append(f"{pos_uri} <{NS}possessionTeam> <{pos['possessionTeam']}> .")

            if pos.get("startsAfterAction"):
                start_act_uri = f"{subj}#PlayByPlay_J{pos['startsAfterAction']}>"
                triplets.append(f"{pos_uri} <{NS}startsAfterAction> {start_act_uri} .")

            if pos.get("endsWithAction"):
                end_act_uri = f"{subj}#PlayByPlay_J{pos['endsWithAction']}>"
                triplets.append(f"{pos_uri} <{NS}endsWithAction> {end_act_uri} .")

            if "containsAction" in pos:
                for act_id in pos["containsAction"]:
                    act_uri = f"{subj}#PlayByPlay_J{act_id}>"
                    triplets.append(f"{pos_uri} <{NS}containsAction> {act_uri} .")

            triplets.append("\n")

        # Canonical lineup and player resources.
        for team_code, players in self.unique_lineups:
            if not players:
                continue

            lineup_url = generate_uri("lineup", team_code, players_set=players)
            team_url = generate_uri("team", team_code)

            lineup_uri = f"<{lineup_url}>"
            team_uri = f"<{team_url}>"

            triplets.append(f"{lineup_uri} <{RDF}> <{NS}Lineup> .")
            triplets.append(f"{lineup_uri} <{NS}lineupTeam> {team_uri} .")

            for pid in players:
                player_url = generate_uri("player", pid)
                player_uri = f"<{player_url}>"
                triplets.append(f"{lineup_uri} <{NS}includesPlayer> {player_uri} .")

            triplets.append("\n")

        return triplets


# Batch processing defaults.

DEFAULT_MAX_GAMES = {
    "E2023": 333,
    "E2024": 330,
    "E2025": 406,
}


def season_label_from_code(season_code):
    """Convert an API season code such as E2023 to the URI label 2023-24."""
    if not re.fullmatch(r"E\d{4}", season_code or ""):
        raise ValueError(f"Invalid season code {season_code!r}. Expected a value such as E2023.")
    start_year = int(season_code[1:])
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def resolve_game_codes(season_code, game_code=None, max_games=None):
    """Return one requested game or the configured numeric range for a season."""
    if game_code is not None:
        try:
            numeric_game_code = int(str(game_code))
        except (TypeError, ValueError) as exc:
            raise ValueError("game_code must be a positive integer") from exc
        if numeric_game_code <= 0:
            raise ValueError("game_code must be a positive integer")
        return [str(numeric_game_code)]

    season_max_games = DEFAULT_MAX_GAMES.get(season_code) if max_games is None else max_games
    if not season_max_games or season_max_games <= 0:
        raise ValueError(
            f"No maximum game code is configured for {season_code}. "
            "Provide --max-games when processing a full season."
        )
    return [str(value) for value in range(1, season_max_games + 1)]


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Download EuroLeague game data and generate AllActions JSON plus "
            "RDF N-Triples for one game or a complete season."
        )
    )
    parser.add_argument(
        "season_code",
        help="EuroLeague API season code, for example E2023",
    )
    parser.add_argument(
        "game_code",
        nargs="?",
        help="Optional numeric game code. Omit it to process the complete season.",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        help="Override the highest game code used for a complete season.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Processed-data root containing all_actions and "
            "playbyplay_triplets subdirectories "
            "(default: <project>/data/processed)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate files that already exist.",
    )
    return parser


def create_api_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.euroleaguebasketball.net/",
            "Origin": "https://www.euroleaguebasketball.net",
        }
    )
    return session


def remove_nulls(obj):
    if isinstance(obj, list):
        return [remove_nulls(item) for item in obj if item is not None]
    if isinstance(obj, dict):
        return {key: remove_nulls(value) for key, value in obj.items() if value is not None}
    return obj


def source_play_events(pbp_data):
    """Return every official event included by the action data model."""
    period_names = (
        "FirstQuarter",
        "SecondQuarter",
        "ThirdQuarter",
        "ForthQuarter",
        "ExtraTime",
    )
    return [
        event
        for period_name in period_names
        for event in (pbp_data.get(period_name, []) or [])
        if isinstance(event, dict) and event.get("PLAYTYPE") != "AG"
    ]


def validate_processed_actions_against_source(pbp_data, actions):
    """Fail when an official event is lost, duplicated, or changes identity."""
    source = [
        (event.get("NUMBEROFPLAY"), event.get("PLAYTYPE", ""))
        for event in source_play_events(pbp_data)
    ]
    processed = [
        (action.get("originalEventId"), action.get("actionInfo", "")) for action in actions
    ]
    if processed != source:
        source_counter = Counter(source)
        processed_counter = Counter(processed)
        missing = list((source_counter - processed_counter).elements())
        unexpected = list((processed_counter - source_counter).elements())
        raise ValueError(
            "Processed actions do not match the official Play-by-Play source. "
            f"Missing: {missing[:10]}; unexpected: {unexpected[:10]}"
        )


def fetch_game_data(session, season_code, game_code):
    endpoint_names = ("PlaybyPlay", "Boxscore", "Points")
    payloads = []
    for index, endpoint_name in enumerate(endpoint_names):
        url = (
            f"https://live.euroleague.net/api/{endpoint_name}"
            f"?gamecode={game_code}&seasoncode={season_code}"
        )
        response = session.get(url, timeout=30)
        if response.status_code in (403, 429):
            print(
                f"  -> {endpoint_name} returned {response.status_code}; "
                "waiting 10 seconds before one retry..."
            )
            time.sleep(10)
            response = session.get(url, timeout=30)
        if response.status_code != 200:
            print(f"  -> {endpoint_name} unavailable (HTTP {response.status_code}).")
            return None
        if not response.content:
            print(f"  -> {endpoint_name} unavailable (empty HTTP 200 response).")
            return None
        try:
            payloads.append(response.json())
        except (requests.exceptions.JSONDecodeError, ValueError):
            print(f"  -> {endpoint_name} unavailable (HTTP 200 response is not valid JSON).")
            return None
        if index < len(endpoint_names) - 1:
            time.sleep(0.5)
    return tuple(payloads)


def process_game(
    session,
    season_code,
    season_label,
    game_code,
    all_actions_dir,
    triplets_dir,
    overwrite=False,
):
    os.makedirs(all_actions_dir, exist_ok=True)
    os.makedirs(triplets_dir, exist_ok=True)
    output_json_path = os.path.join(all_actions_dir, f"AllActions_{season_code}_{game_code}.json")
    output_triplets_path = os.path.join(triplets_dir, f"Triplets_{season_code}_{game_code}.nt")

    if not overwrite and os.path.exists(output_json_path) and os.path.exists(output_triplets_path):
        print("  -> Both output files already exist; skipping. Use --overwrite to regenerate.")
        return "skipped"

    game_data = fetch_game_data(session, season_code, game_code)
    if not game_data:
        return "unavailable"
    pbp_data, boxscore_data, points_data = game_data
    if not pbp_data or not boxscore_data:
        print("  -> The game has no valid Play-by-Play or Boxscore data.")
        return "unavailable"

    game_url_base = (
        "https://www.euroleaguebasketball.net/euroleague/game-center/"
        f"{season_label}/-/{season_code}/{game_code}"
    )
    processor = GameProcessor(pbp_data, boxscore_data, points_data, game_url_base)
    processor.run()
    validate_processed_actions_against_source(pbp_data, processor.all_actions)

    combined_output = {
        "Possessions": processor.possessions,
        "AllActions": processor.all_actions,
    }
    cleaned_output = remove_nulls(combined_output)
    with open(output_json_path, "w", encoding="utf8") as out_file:
        json.dump(cleaned_output, out_file, ensure_ascii=False, indent=4)

    triplets = processor.generate_triplets()
    with open(output_triplets_path, "w", encoding="utf8") as out_file:
        for triple in triplets:
            out_file.write(triple + "\n")

    triple_count = sum(1 for triple in triplets if triple.strip())
    print(
        f"  -> Saved {len(processor.all_actions)} actions and "
        f"{triple_count} RDF triples:\n"
        f"     {output_json_path}\n"
        f"     {output_triplets_path}"
    )
    return "generated"


def main(argv=None):
    cli_parser = build_argument_parser()
    args = cli_parser.parse_args(argv)
    try:
        season_label = season_label_from_code(args.season_code)
        game_codes = resolve_game_codes(
            args.season_code,
            game_code=args.game_code,
            max_games=args.max_games,
        )
    except ValueError as exc:
        cli_parser.error(str(exc))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    output_root = os.path.abspath(
        args.output_dir or os.path.join(project_root, "data", "processed")
    )
    all_actions_dir = os.path.join(output_root, "all_actions")
    triplets_dir = os.path.join(output_root, "playbyplay_triplets")
    os.makedirs(all_actions_dir, exist_ok=True)
    os.makedirs(triplets_dir, exist_ok=True)

    scope = f"game {game_codes[0]}" if len(game_codes) == 1 else f"games 1-{game_codes[-1]}"
    print(f"Processing {args.season_code} ({season_label}), {scope}...")
    session = create_api_session()
    generated = skipped = unavailable = failed = 0

    for index, game_code in enumerate(game_codes, start=1):
        print(f"\n[{index}/{len(game_codes)}] Game {game_code}")
        try:
            status = process_game(
                session,
                args.season_code,
                season_label,
                game_code,
                all_actions_dir,
                triplets_dir,
                overwrite=args.overwrite,
            )
            if status == "generated":
                generated += 1
            elif status == "skipped":
                skipped += 1
            else:
                unavailable += 1
        except (OSError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
            failed += 1
            print(f"  -> Failed: {exc}")

        if len(game_codes) > 1 and index < len(game_codes):
            time.sleep(random.uniform(2.5, 4.5))

    print(
        "\nProcessing complete: "
        f"{generated} generated, {skipped} skipped, "
        f"{unavailable} unavailable, {failed} failed."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
