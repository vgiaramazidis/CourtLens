import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app as backend
from sparql_queries import get_simulator_crunch_time_query, get_team_roster_query, get_game_roster_query


class CoachScopeTests(unittest.IsolatedAsyncioTestCase):
    def test_same_numbered_games_and_partial_player_ids_do_not_share_scope(self):
        query = get_simulator_crunch_time_query("7", "4th", ["12", "2", "3", "4", "5"], "E2024")
        self.assertIn("?game bball:hasCode '7'", query)
        self.assertIn("?season bball:hasCode 'E2024'", query)
        self.assertIn("?lineup bball:includesPlayer <https://www.euroleaguebasketball.net/euroleague/players/-/12>", query)
        self.assertNotIn("CONTAINS", query)
        roster_query = get_team_roster_query("7", "PAN", "E2024")
        self.assertIn("?season bball:hasCode 'E2024'", roster_query)
        # The missing-player quiz also chooses a game within one season.
        self.assertIn("?season bball:hasCode 'E2024'", get_game_roster_query("7", "E2024"))

    async def test_simulation_counts_points_for_and_against_separately(self):
        rows = [
            {"actionTeam": {"value": "home"}, "lineupTeam": {"value": "home"}, "totalPoints": {"value": "9"}},
            {"actionTeam": {"value": "away"}, "lineupTeam": {"value": "home"}, "totalPoints": {"value": "4"}},
        ]
        query = AsyncMock(return_value={"results": {"bindings": rows}})
        with patch.object(backend, "query_sparql", query):
            result = await backend.run_simulator("1", "2", "3", "4", "5", "7", "4th", "E2024")
        self.assertEqual(result, {"points_for": 9, "points_against": 4, "plus_minus": 5})
        # These names must match the endpoint's expected SPARQL result bindings.
        self.assertIn("SELECT ?actionTeam ?lineupTeam", query.call_args.args[0])

    async def test_scenario_keeps_full_team_names_and_season_in_roster_request(self):
        row = {key: {"value": value} for key, value in {
            "game": "https://www.euroleaguebasketball.net/euroleague/game-center/2023-24/-/E2023/333",
            "clock": "00:30", "homeScore": "80", "roadScore": "90",
            "homeLineup": "https://www.euroleaguebasketball.net/euroleague/teams/-/MAD#Lineup_1_2_3_4_5",
            "roadLineup": "https://www.euroleaguebasketball.net/euroleague/teams/-/PAN#Lineup_6_7_8_9_10",
            "homeLabel": "Real Madrid", "awayLabel": "Panathinaikos",
        }.items()}
        query = AsyncMock(side_effect=[{"results": {"bindings": [row]}}, {"results": {"bindings": []}}])
        with patch.object(backend, "query_sparql", query):
            result = await backend.get_simulator_scenario("E2023")
        self.assertEqual(result["user_team_name"], "Real Madrid")
        self.assertEqual(result["opponent_name"], "Panathinaikos")
        self.assertIn("?season bball:hasCode 'E2023'", query.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
