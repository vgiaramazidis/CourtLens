import json
import unittest
from unittest.mock import AsyncMock, patch

from src.backend import app as backend
from src.backend.queries import get_game_lineups_query, get_player_name_query
from src.backend.quiz_support import game_stage, missing_lineup, quiz_player_profile


def binding(**values):
    return {key: {"value": str(value)} for key, value in values.items()}


class QuizDataTests(unittest.TestCase):
    def test_stages_come_from_metadata_not_game_number(self):
        for group, expected in [
            ("CHAMPIONSHIP GAME", "Final"),
            ("SEMIFINALS", "Semi-final"),
            ("THIRD PLACE GAME", "Third-place game"),
        ]:
            self.assertEqual(game_stage(binding(phase="Final Four", phaseGroup=group)), expected)
        self.assertEqual(
            game_stage(binding(phase="Regular Season", phaseGroup="GROUP A")), "Regular season"
        )
        self.assertEqual(game_stage(binding(gameCode="333")), "")

    def test_profile_keeps_canonical_identity_and_source_information(self):
        result = quiz_player_profile(
            "123",
            {
                "results": {
                    "bindings": [
                        binding(
                            name="Shane Larkin",
                            position="Guard",
                            img="https://example.org/player.png",
                            country="http://www.ics.forth.gr/isl/Basketball/entities/USA",
                            bio="Played for a club.",
                            achievements_text="Won a title.",
                        )
                    ]
                }
            },
        )
        self.assertEqual(result["id"], "123")
        self.assertEqual(result["country"], "United States")
        self.assertEqual(result["name"], "Shane Larkin")
        self.assertEqual(result["img"], "https://example.org/player.png")
        self.assertIn("He won a title.", result["paragraphs"])
        self.assertTrue(result["source_url"].endswith("/123"))

    def test_missing_court_contains_four_photos_and_no_secret_identity(self):
        profiles = [
            dict(id=str(i), name=f"Player {i}", position=role, img=f"https://example.org/{i}.png")
            for i, role in enumerate(["Guard", "Forward", "Center", "Guard", "Forward"])
        ]
        lineup = missing_lineup(profiles, 0)
        self.assertEqual(len(lineup), 5)
        self.assertEqual(sum(bool(slot["player"]) for slot in lineup), 4)
        missing = next(slot for slot in lineup if slot["missing"])
        self.assertEqual(missing, {"missing": True, "position": "Guard", "player": None})
        self.assertNotIn("Player 0", json.dumps(lineup))
        self.assertEqual(lineup[0]["position"], "Center")

    def test_names_prefer_full_name_and_roster_includes_position(self):
        self.assertIn("COALESCE(?fullName, ?jerseyName)", get_player_name_query("123"))
        self.assertIn("bball:hasPosition ?position", get_game_lineups_query("333", "E2023"))

    def test_fast_break_quiz_statistics_are_scoped_to_the_stated_season(self):
        query = backend.get_fast_break_specialists_query(
            season_code="E2024", game_code="10", quarter="4th"
        )
        self.assertIn('FILTER(?seasonCode IN ("E2024"))', query)
        self.assertIn('FILTER(?gameCode IN ("10"))', query)
        self.assertIn('FILTER(STR(?filterQuarter) = "4th")', query)
        self.assertIn("SELECT DISTINCT ?player ?action ?points", query)


class QuizEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_quiz_uses_gpt_mini_even_when_search_uses_gemini(self):
        with (
            patch.object(backend, "OPENAI_API_KEY", "test"),
            patch.object(backend, "AI_SEARCH_PROVIDER", "gemini"),
            patch.object(backend, "client", None),
            patch.object(
                backend, "request_openai_text", return_value=('{"hint":"A guard."}', {})
            ) as generate,
        ):
            result = await backend.generate_quiz_text("quiz facts")
        self.assertEqual(result, {"hint": "A guard."})
        self.assertEqual(generate.call_args.args[2], "gpt-5-mini")

    async def test_missing_question_keeps_real_identities_despite_model_output(self):
        games = {
            "results": {"bindings": [binding(gameCode="333", homeLabel="Home", awayLabel="Away")]}
        }
        roster = {
            "results": {
                "bindings": [
                    binding(homeLineup="x#Lineup_1_2_3_4_5", roadLineup="x#Lineup_1_2_3_4_5")
                ]
            }
        }

        async def profile(pid):
            return dict(
                id=pid, name=f"Player {pid}", position="Guard", img=f"https://example.org/{pid}.png"
            )

        with (
            patch.object(backend, "OPENAI_API_KEY", "test"),
            patch.object(backend, "query_sparql_requests", side_effect=[games, roster]),
            patch.object(backend, "load_quiz_player", side_effect=profile),
            patch.object(
                backend,
                "generate_quiz_text",
                AsyncMock(
                    return_value={
                        "hint": "Initial P.",
                        "secret_player_name": "Invented",
                        "known_players": [],
                    }
                ),
            ),
            patch.object(backend.random, "randint", return_value=0),
        ):
            result = await backend.generate_who_is_missing("easy")
        self.assertEqual(result["secret_player_name"], "Player 1")
        self.assertEqual(result["secret_player"]["id"], "1")
        self.assertEqual(result["known_players"], ["Player 2", "Player 3", "Player 4", "Player 5"])
        self.assertEqual(len(result["lineup"]), 5)

    async def test_games_endpoint_retains_game_numbers_and_metadata(self):
        rows = [
            binding(
                gameCode="333",
                homeLabel="Real Madrid",
                awayLabel="Panathinaikos",
                phase="Final Four",
                phaseGroup="CHAMPIONSHIP GAME",
                round="43",
            ),
            binding(gameCode="1", homeLabel="A", awayLabel="B"),
        ]
        with patch.object(
            backend, "analysis_data", AsyncMock(return_value={"results": {"bindings": rows}})
        ):
            result = await backend.get_games("E2023")
        self.assertEqual(result["games"][0]["stage"], "Final")
        self.assertEqual(result["games"][0]["gameCode"], "333")
        self.assertEqual(result["games"][1]["stage"], "")


class DifficultyTests(unittest.IsolatedAsyncioTestCase):
    async def test_easy_comparison_uses_full_game_points_and_large_gap(self):
        games = {"results": {"bindings": [binding(gameCode="333", homeLabel="A", awayLabel="B")]}}
        stats = {
            "results": {
                "bindings": [
                    binding(player="x/1", totalPoints=20),
                    binding(player="x/2", totalPoints=10),
                ]
            }
        }
        with (
            patch.object(backend, "OPENAI_API_KEY", "test"),
            patch.object(backend, "query_sparql_requests", side_effect=[games, stats]) as query,
            patch.object(backend, "quiz_player_name", side_effect=lambda pid: f"Player {pid}"),
            patch.object(
                backend, "generate_quiz_text", AsyncMock(return_value={"question_text": "Compare."})
            ),
        ):
            result = await backend.generate_higher_or_lower("easy")
        self.assertEqual(abs(result["player_a"]["stat"] - result["player_b"]["stat"]), 10)
        self.assertIn("points scored", result["category_name"])
        self.assertIn("hint", result)
        self.assertNotIn("bball:quarter", query.call_args_list[1].args[0])

    async def test_easy_does_not_fall_back_to_a_hard_comparison(self):
        games = {"results": {"bindings": [binding(gameCode="333")]}}
        stats = {
            "results": {
                "bindings": [
                    binding(player="x/1", totalPoints=20),
                    binding(player="x/2", totalPoints=19),
                ]
            }
        }
        with (
            patch.object(backend, "OPENAI_API_KEY", "test"),
            patch.object(backend, "query_sparql_requests", side_effect=[games, stats] * 30),
            patch.object(backend, "generate_quiz_text", AsyncMock()) as generate,
        ):
            with self.assertRaises(backend.HTTPException) as error:
                await backend.generate_higher_or_lower("easy")
        self.assertEqual(error.exception.status_code, 404)
        generate.assert_not_called()

    def test_points_query_counts_events_not_profile_labels(self):
        query = backend.get_quiz_points_query(game_code="333", season_code="E2023")
        self.assertIn("SELECT DISTINCT ?player ?action ?points", query)
        self.assertIn('FILTER(?gameCode IN ("333"))', query)
        self.assertNotIn("rdfs:label ?", query)

    async def test_top_five_retries_ties_at_the_answer_cutoff(self):
        def stats(values):
            return {
                "results": {
                    "bindings": [
                        binding(player=f"x/{i}", totalPoints=v) for i, v in enumerate(values)
                    ]
                }
            }

        with (
            patch.object(
                backend,
                "query_sparql_requests",
                side_effect=[stats([20, 19, 18, 17, 16, 16]), stats([20, 19, 18, 17, 16, 15])],
            ) as query,
            patch.object(backend, "quiz_player_name", side_effect=lambda pid: f"Player {pid}"),
        ):
            result = await backend.generate_top_5("easy")
        self.assertEqual(query.call_count, 2)
        self.assertEqual(len(result["answers"]), 5)


if __name__ == "__main__":
    unittest.main()
