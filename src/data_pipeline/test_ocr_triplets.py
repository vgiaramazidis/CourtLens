import json
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.ocr_triplets import (
    BASKETBALL_NS,
    OCRObservation,
    PlayByPlayAction,
    action_artifact_paths,
    build_observation_index,
    find_nearest_observation,
    generate_game_triplets,
    load_actions,
    normalize_quarter,
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

    def test_action_artifacts_use_separate_category_directories(self):
        json_path, triples_path = action_artifact_paths(
            Path("all-actions"),
            Path("playbyplay-triplets"),
            "E2024",
            "209",
        )

        self.assertEqual(
            json_path,
            Path("all-actions/AllActions_E2024_209.json"),
        )
        self.assertEqual(
            triples_path,
            Path("playbyplay-triplets/Triplets_E2024_209.nt"),
        )

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

    def test_generated_rdf_links_action_to_ocr_observation(self):
        game = {
            "season_code": "E2023",
            "game_code": "170",
            "youtube_id": "video-id",
            "youtube_url": "https://www.youtube.com/watch?v=video-id",
            "ocr_profile": "test-profile",
            "enabled": True,
        }
        actions = [PlayByPlayAction(
            uri=(
                "https://www.euroleaguebasketball.net/euroleague/game-center/"
                "2023-24/-/E2023/170#PlayByPlay_J700"
            ),
            quarter="1OT",
            quarter_seconds_remaining=300,
        )]

        triples, matched, unmatched = generate_game_triplets(
            game,
            self.observations,
            actions,
        )
        rdf = "\n".join(triples)

        self.assertEqual(matched, 1)
        self.assertEqual(unmatched, 0)
        self.assertIn(f"<{BASKETBALL_NS}BroadcastVideo>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}OCRObservation>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}correspondsToPlayByPlayAction>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}quarter>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}clock>", rdf)
        self.assertIn(f"<{BASKETBALL_NS}quarterSecondsRemaining>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}ocrQuarter>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}hasSynchronizedOCRObservation>", rdf)
        self.assertNotIn(f"<{BASKETBALL_NS}synchronizedVideoTimeSeconds>", rdf)
        self.assertIn('"OT"', rdf)

    def test_actions_are_loaded_from_local_all_actions_json(self):
        payload = {
            "AllActions": [{
                "originalEventId": 11,
                "quarter": "1st",
                "quarterSecondsRemaining": 596,
            }]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AllActions_E2023_170.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            actions = load_actions(path, "https://example/game/170")

        self.assertEqual(actions, [PlayByPlayAction(
            uri="https://example/game/170#PlayByPlay_J11",
            quarter="1st",
            quarter_seconds_remaining=596.0,
        )])


if __name__ == "__main__":
    unittest.main()
