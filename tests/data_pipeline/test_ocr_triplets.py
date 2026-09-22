import json
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.ocr_triplets import (
    BASKETBALL_NS,
    OCRObservation,
    PlayByPlayAction,
    build_observation_index,
    find_nearest_observation,
    generate_game_triplets,
    load_actions,
    normalize_quarter,
    synchronization_tolerance,
)


class OCRTripletTests(unittest.TestCase):
    def setUp(self):
        self.video_uri = (
            "https://www.euroleaguebasketball.net/euroleague/game-center/"
            "2023-24/-/E2023/170#BroadcastVideo"
        )
        self.observations = [
            OCRObservation(1, f"{self.video_uri}/ocr-observation/1", 934.0, "1st", "9:56", 596.0),
            OCRObservation(2, f"{self.video_uri}/ocr-observation/2", 9000.0, "OT", "4:59", 299.0),
            OCRObservation(3, f"{self.video_uri}/ocr-observation/3", 9001.0, "OT", "4:58", 298.0),
        ]

    def test_overtime_aliases_use_one_canonical_value(self):
        self.assertEqual(normalize_quarter("OT"), "OT")
        self.assertEqual(normalize_quarter("1OT"), "OT")
        self.assertEqual(normalize_quarter("OT1"), "OT")
        self.assertEqual(normalize_quarter("4OT"), "4OT")

    def test_first_overtime_action_matches_ot_observation(self):
        observation, difference = find_nearest_observation(
            build_observation_index(self.observations),
            "1OT",
            300,
        )

        self.assertEqual(observation, self.observations[1])
        self.assertEqual(difference, 1.0)

    def test_distant_action_is_not_synchronized(self):
        observation, difference = find_nearest_observation(
            build_observation_index(self.observations),
            "OT",
            280,
        )

        self.assertIsNone(observation)
        self.assertEqual(difference, 18.0)

    def test_invalid_youtube_url_is_rejected(self):
        game = {
            "season_code": "E2023",
            "game_code": "170",
            "youtube_url": "not-a-url",
        }

        with self.assertRaisesRegex(ValueError, "Invalid youtube_url"):
            generate_game_triplets(game, self.observations, [])

    def test_generated_rdf_links_action_to_ocr_observation(self):
        game = {
            "season_code": "E2023",
            "game_code": "170",
            "youtube_id": "video-id",
            "youtube_url": "https://www.youtube.com/watch?v=video-id",
            "ocr_profile": "test-profile",
            "enabled": True,
        }
        actions = [
            PlayByPlayAction(
                uri=(
                    "https://www.euroleaguebasketball.net/euroleague/game-center/"
                    "2023-24/-/E2023/170#PlayByPlay_J700"
                ),
                quarter="1OT",
                quarter_seconds_remaining=300,
            )
        ]

        triples, linked, matched, unmatched = generate_game_triplets(
            game,
            self.observations,
            actions,
        )
        rdf = "\n".join(triples)

        self.assertEqual(linked, 1)
        self.assertEqual(matched, 1)
        self.assertEqual(unmatched, 0)
        self.assertIn(f"<{BASKETBALL_NS}BroadcastVideo>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}OCRObservation>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}correspondsToOCRObservation>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}ocrQuarter>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}ocrClock>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}quarter>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}clock>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}quarterSecondsRemaining>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}correspondsToPlayByPlayAction>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}videoOfGame>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}youtubeVideoId>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}hasSynchronizedOCRObservation>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}synchronizedVideoTimeSeconds>", rdf)
        self.assertIn(
            f"<{BASKETBALL_NS}youtubeURL> <https://www.youtube.com/watch?v=video-id> .",
            rdf,
        )
        self.assertIn(
            f"<{actions[0].uri}> "
            f"<{BASKETBALL_NS}correspondsToOCRObservation> "
            f"<{self.observations[1].uri}> .",
            rdf,
        )
        self.assertIn(f"<{self.observations[1].uri}>", rdf)
        self.assertNotIn(f"<{self.observations[0].uri}>", rdf)
        self.assertNotIn(f"<{self.observations[2].uri}>", rdf)
        self.assertIn('"OT"', rdf)

    def test_actions_are_loaded_from_local_all_actions_json(self):
        payload = {
            "AllActions": [
                {
                    "originalEventId": 11,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 596,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AllActions_E2023_170.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            actions = load_actions(path, "https://example/game/170")

        self.assertEqual(
            actions,
            [
                PlayByPlayAction(
                    uri="https://example/game/170#PlayByPlay_J11",
                    quarter="1st",
                    quarter_seconds_remaining=596.0,
                )
            ],
        )

    def test_assist_is_synchronized_to_its_made_field_goal(self):
        assist_uri = "https://example/game/170#PlayByPlay_J12"
        payload = {
            "AllActions": [
                {
                    "originalEventId": 11,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 596,
                    "actionInfo": "2FGM",
                    "hasAssist": assist_uri,
                },
                {
                    "originalEventId": 12,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 594,
                    "actionInfo": "AS",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AllActions_E2023_170.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            actions = load_actions(path, "https://example/game/170")

        self.assertEqual(
            actions[1],
            PlayByPlayAction(
                uri=assist_uri,
                quarter="1st",
                quarter_seconds_remaining=596.0,
                action_info="AS",
            ),
        )

    def test_distant_field_goal_is_not_used_as_an_assist_anchor(self):
        assist_uri = "https://example/game/170#PlayByPlay_J12"
        payload = {
            "AllActions": [
                {
                    "originalEventId": 11,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 596,
                    "actionInfo": "3FGM",
                    "hasAssist": assist_uri,
                },
                {
                    "originalEventId": 12,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 580,
                    "actionInfo": "AS",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AllActions_E2023_170.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            actions = load_actions(path, "https://example/game/170")

        self.assertEqual(actions[1].quarter_seconds_remaining, 580.0)

    def test_made_free_throw_is_used_as_a_fiba_assist_anchor(self):
        assist_uri = "https://example/game/170#PlayByPlay_J12"
        payload = {
            "AllActions": [
                {
                    "originalEventId": 11,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 596,
                    "actionInfo": "FTM",
                    "hasAssist": assist_uri,
                },
                {
                    "originalEventId": 12,
                    "quarter": "1st",
                    "quarterSecondsRemaining": 594,
                    "actionInfo": "AS",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AllActions_E2023_170.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            actions = load_actions(path, "https://example/game/170")

        self.assertEqual(actions[1].quarter_seconds_remaining, 596.0)

    def test_period_start_metadata_can_use_first_clock_within_ten_seconds(self):
        first_visible_clock = OCRObservation(
            4,
            f"{self.video_uri}/ocr-observation/4",
            1000.0,
            "1st",
            "9:53",
            593.0,
        )
        action = PlayByPlayAction(
            uri="https://example/game#PlayByPlay_J2",
            quarter="1st",
            quarter_seconds_remaining=600.0,
            action_info="BP",
        )

        self.assertEqual(synchronization_tolerance(action), 12.0)
        observation, difference = find_nearest_observation(
            build_observation_index([first_visible_clock]),
            action.quarter,
            action.quarter_seconds_remaining,
            max_difference=synchronization_tolerance(action),
        )

        self.assertEqual(observation, first_visible_clock)
        self.assertEqual(difference, 7.0)

    def test_regular_play_keeps_five_second_tolerance(self):
        action = PlayByPlayAction(
            uri="https://example/game#PlayByPlay_J3",
            quarter="1st",
            quarter_seconds_remaining=590.0,
            action_info="3FGA",
        )

        self.assertEqual(synchronization_tolerance(action), 5.0)

    def test_opening_jump_ball_uses_period_start_tolerance(self):
        action = PlayByPlayAction(
            uri="https://example/game#PlayByPlay_J3",
            quarter="1st",
            quarter_seconds_remaining=599.0,
            action_info="JB",
        )

        self.assertEqual(synchronization_tolerance(action), 12.0)


if __name__ == "__main__":
    unittest.main()
