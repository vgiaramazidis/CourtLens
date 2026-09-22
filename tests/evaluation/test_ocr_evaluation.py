import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluation.ocr import (
    DEFAULT_CATALOG_FILE,
    GROUND_TRUTH_FILES,
    SYSTEMS,
    EvaluationResult,
    GroundTruthAction,
    load_ground_truth,
    metric_summary,
    temporal_error_band,
)


class OcrEvaluationTests(unittest.TestCase):
    def test_scope_is_the_three_games_and_two_systems(self):
        self.assertEqual(
            [path.stem for path in GROUND_TRUTH_FILES],
            ["E2023_333", "E2024_220", "E2023_170"],
        )
        self.assertEqual(set(SYSTEMS), {"baseline", "production"})

    def test_full_catalog_coverage_has_a_baseline_for_every_game(self):
        # The annotated sample uses three games, but coverage compares the whole catalog.
        catalog = json.loads(DEFAULT_CATALOG_FILE.read_text())
        for game in catalog["games"]:
            filename = f"{game['season_code']}_{game['game_code']}.csv"
            with self.subTest(game=filename):
                self.assertTrue((SYSTEMS["baseline"] / filename).is_file())

    def test_metrics_use_all_events_for_accuracy_and_mapped_for_error(self):
        events = [
            GroundTruthAction("E2023", "1", 1, "made_field_goal", 100.0),
            GroundTruthAction("E2023", "1", 2, "made_field_goal", 200.0),
            GroundTruthAction("E2023", "1", 3, "made_field_goal", 300.0),
        ]
        results = [
            EvaluationResult("production", events[0], "2FGM", 100.5),
            EvaluationResult("production", events[1], "2FGM", 202.0),
            EvaluationResult("production", events[2], "2FGM", None),
        ]

        metrics = metric_summary(results)

        self.assertEqual(metrics["total"], 3)
        self.assertEqual(metrics["mapped"], 2)
        self.assertAlmostEqual(metrics["uer_pct"], 100 / 3)
        self.assertAlmostEqual(metrics["mae_seconds"], 1.25)
        self.assertAlmostEqual(metrics["median_absolute_error_seconds"], 1.25)
        self.assertAlmostEqual(metrics["acc_at_1_pct"], 100 / 3)
        self.assertAlmostEqual(metrics["acc_at_2_pct"], 200 / 3)
        self.assertAlmostEqual(metrics["acc_at_5_pct"], 200 / 3)

    def test_error_bands_cover_boundaries_and_unmapped(self):
        event = GroundTruthAction("E2023", "1", 1, "made_field_goal", 100.0)
        expected = {
            101.0: "within_1_second",
            102.0: "over_1_to_2_seconds",
            105.0: "over_2_to_5_seconds",
            110.0: "over_5_to_10_seconds",
            130.0: "over_10_to_30_seconds",
            131.0: "over_30_seconds",
            None: "unmapped",
        }
        for prediction, band in expected.items():
            with self.subTest(prediction=prediction):
                result = EvaluationResult("production", event, "2FGM", prediction)
                self.assertEqual(temporal_error_band(result), band)

    def test_ground_truth_loader_combines_files_and_counts_statuses(self):
        header = (
            "season_code,game_code,original_event_id,action_category,"
            "annotation_status,ground_truth_video_seconds\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first.csv"
            second = Path(temporary_directory) / "second.csv"
            first.write_text(
                header
                + "E2023,333,1,made_field_goal,Annotated,100\n"
                + "E2023,333,2,assist,Exclude,\n",
                encoding="utf-8",
            )
            second.write_text(
                header + "E2024,220,1,rebound,Annotated,200\n" + "E2024,220,2,timeout,Pending,\n",
                encoding="utf-8",
            )
            events, pending, excluded = load_ground_truth([first, second])

        self.assertEqual(len(events), 2)
        self.assertEqual(pending, 1)
        self.assertEqual(excluded, 1)

    def test_duplicate_ground_truth_event_is_rejected(self):
        content = (
            "season_code,game_code,original_event_id,action_category,"
            "annotation_status,ground_truth_video_seconds\n"
            "E2023,333,1,made_field_goal,Annotated,100\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first.csv"
            second = Path(temporary_directory) / "second.csv"
            first.write_text(content, encoding="utf-8")
            second.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_ground_truth([first, second])


if __name__ == "__main__":
    unittest.main()
