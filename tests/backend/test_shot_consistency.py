"""Keep full-game evidence and player identity consistent across views."""

import unittest
from unittest.mock import AsyncMock, patch

from src.backend import app as backend
from src.backend import queries


class FullGameQueriesTests(unittest.TestCase):
    def test_full_games_collapse_metadata_before_any_result_limit(self):
        for game in ("331", "333", "170"):
            for query in (
                queries.get_filtered_shots_query(game_code=game, season_code="E2023"),
                queries.get_match_playbyplay_query(game, "E2023"),
            ):
                with self.subTest(game=game):
                    self.assertIn("GROUP BY ?action", query)
                    self.assertNotIn("LIMIT", query)
        broad = queries.get_filtered_shots_query(season_code="E2023")
        self.assertLess(broad.index("GROUP BY ?action"), broad.rindex("LIMIT 500"))

    def test_missing_video_mapping_is_not_a_seek_to_the_start_of_the_game(self):
        with patch.object(backend, "get_video_game_config", return_value=None):
            self.assertIsNone(backend.find_video_seconds("01:30", "4OT", "E2023", "170"))
        with (
            patch.object(backend, "get_video_game_config", return_value={"timeline_file": "test"}),
            patch.object(
                backend, "load_video_timeline_index", return_value={"1st": ((590.0,), (50.0,))}
            ),
        ):
            self.assertIsNone(backend.find_video_seconds("08:00", "1st", "E2023", "333"))
            self.assertEqual(backend.find_video_seconds("09:49", "1st", "E2023", "333"), 50.0)


class RosterIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_roster_separator_preserves_commas_in_names_and_deduplicates_ids(self):
        first = "012742|DOZIER, PJ|https://example.org/dozier.png|Guard"
        second = "012774|NUNN, KENDRICK|https://example.org/nunn.png|Guard"
        rows = [
            {"players": {"value": "@@".join([first, second, first])}, "teamType": {"value": "home"}}
        ]
        with patch.object(
            backend, "analysis_data", AsyncMock(return_value={"results": {"bindings": rows}})
        ):
            result = await backend.get_game_lineups("196", "E2023")
        self.assertEqual(result["lineups"][0]["players"], "@@".join([first, second]))
