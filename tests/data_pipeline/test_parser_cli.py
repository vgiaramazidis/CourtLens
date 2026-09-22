import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.data_pipeline import parser


class ParserCliTests(unittest.TestCase):
    def test_coach_and_substitution_actions_keep_their_entities_in_rdf(self):
        game = "https://example.org/game/1"
        processor = parser.GameProcessor(
            {"CodeTeamA": "HOM", "CodeTeamB": "AWY"},
            {
                "Stats": [
                    {"Team": "HOM", "Coach": "Home Coach", "PlayersStats": []},
                    {"Team": "AWY", "Coach": "Away Coach", "PlayersStats": []},
                ]
            },
            {"Rows": []},
            game,
        )
        cases = [
            ("C", "HOM", "", "CoachFoul", "actionCoach", "coaches/-/Home_Coach"),
            ("CCH", "AWY", "", "Challenge", "actionCoach", "coaches/-/Away_Coach"),
            ("IN", "HOM", "P123", "PlayerIn", "actionPlayer", "players/-/123"),
            ("OUT", "AWY", "P456", "PlayerOut", "actionPlayer", "players/-/456"),
        ]
        for event_id, (kind, team, player, *_expected) in enumerate(cases, 1):
            processor.extract_action_data(
                {
                    "NUMBEROFPLAY": event_id,
                    "PLAYTYPE": kind,
                    "CODETEAM": team,
                    "PLAYER_ID": player,
                    "MARKERTIME": "04:30",
                },
                "FirstQuarter",
            )

        self.assertEqual(len(processor.all_actions), 4)
        triples = processor.generate_triplets()
        namespace = "http://www.ics.forth.gr/isl/Basketball#"
        for event_id, (_, _, _, kind, relation, entity) in enumerate(cases, 1):
            subject = f"<{game}#PlayByPlay_J{event_id}>"
            self.assertIn(
                f"{subject} <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{namespace}{kind}> .",
                triples,
            )
            self.assertIn(
                f"{subject} <{namespace}{relation}> <https://www.euroleaguebasketball.net/euroleague/{entity}> .",
                triples,
            )

    def test_shot_rejected_actions_are_explicitly_excluded_from_source_scope(self):
        source = {
            "FirstQuarter": [
                {"NUMBEROFPLAY": 11, "PLAYTYPE": "BP"},
                {"NUMBEROFPLAY": 12, "PLAYTYPE": "AG"},
            ]
        }

        self.assertEqual(
            parser.source_play_events(source),
            [{"NUMBEROFPLAY": 11, "PLAYTYPE": "BP"}],
        )

    def test_source_validation_detects_a_dropped_action(self):
        source = {
            "FirstQuarter": [
                {"NUMBEROFPLAY": 11, "PLAYTYPE": "BP"},
                {"NUMBEROFPLAY": 12, "PLAYTYPE": "TO"},
            ]
        }
        actions = [{"originalEventId": 11, "actionInfo": "BP"}]

        with self.assertRaisesRegex(ValueError, "Missing"):
            parser.validate_processed_actions_against_source(source, actions)

    def test_source_validation_accepts_all_actions_in_order(self):
        source = {
            "FirstQuarter": [
                {"NUMBEROFPLAY": 11, "PLAYTYPE": "BP"},
                {"NUMBEROFPLAY": 12, "PLAYTYPE": "AG"},
                {"NUMBEROFPLAY": 13, "PLAYTYPE": "TO"},
            ]
        }
        actions = [
            {"originalEventId": 11, "actionInfo": "BP"},
            {"originalEventId": 13, "actionInfo": "TO"},
        ]

        parser.validate_processed_actions_against_source(source, actions)

    def test_season_code_builds_the_game_uri_label(self):
        self.assertEqual(parser.season_label_from_code("E2023"), "2023-24")
        self.assertEqual(parser.season_label_from_code("E2025"), "2025-26")

    def test_one_game_scope_contains_only_the_requested_game(self):
        self.assertEqual(parser.resolve_game_codes("E2023", "170"), ["170"])

    def test_full_season_uses_the_configured_maximum(self):
        game_codes = parser.resolve_game_codes("E2023")

        self.assertEqual(game_codes[0], "1")
        self.assertEqual(game_codes[-1], "333")
        self.assertEqual(len(game_codes), 333)

    def test_full_season_rejects_a_non_positive_maximum(self):
        with self.assertRaisesRegex(ValueError, "No maximum game code"):
            parser.resolve_game_codes("E2023", max_games=0)

    def test_overtime_period_start_uses_a_five_minute_clock(self):
        self.assertEqual(parser.default_marker_time("BP", "1OT"), "05:00")
        self.assertEqual(parser.default_marker_time("BP", "OT"), "05:00")
        self.assertEqual(parser.default_marker_time("BP", "2OT"), "05:00")
        self.assertEqual(parser.default_marker_time("BP", "1st"), "10:00")

    def test_negative_api_clock_is_clamped_to_end_of_period(self):
        self.assertEqual(parser.normalize_marker_time("00:-1"), "00:00")
        self.assertEqual(parser.normalize_marker_time("00:00"), "00:00")
        self.assertEqual(parser.normalize_marker_time("04:59"), "04:59")

    def test_empty_successful_api_response_is_unavailable(self):
        response = Mock(status_code=200, content=b"")
        session = Mock()
        session.get.return_value = response

        result = parser.fetch_game_data(session, "E2025", "396")

        self.assertIsNone(result)
        response.json.assert_not_called()

    def test_single_game_cli_calls_the_processor_once(self):
        with (
            tempfile.TemporaryDirectory() as output_dir,
            patch.object(parser, "create_api_session", return_value=object()),
            patch.object(parser, "process_game", return_value="generated") as mocked_process,
        ):
            result = parser.main(["E2023", "170", "--output-dir", output_dir])

        self.assertEqual(result, 0)
        mocked_process.assert_called_once()
        call = mocked_process.call_args
        self.assertEqual(call.args[1:4], ("E2023", "2023-24", "170"))
        self.assertEqual(call.args[4], str(Path(output_dir) / "all_actions"))
        self.assertEqual(
            call.args[5],
            str(Path(output_dir) / "playbyplay_triplets"),
        )

    def test_full_season_cli_accepts_a_max_games_override(self):
        with (
            tempfile.TemporaryDirectory() as output_dir,
            patch.object(parser, "create_api_session", return_value=object()),
            patch.object(parser, "process_game", return_value="skipped") as mocked_process,
            patch.object(parser.time, "sleep"),
        ):
            result = parser.main(
                [
                    "E2023",
                    "--max-games",
                    "2",
                    "--output-dir",
                    output_dir,
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(mocked_process.call_count, 2)
        self.assertEqual(
            [call.args[3] for call in mocked_process.call_args_list],
            ["1", "2"],
        )


if __name__ == "__main__":
    unittest.main()
