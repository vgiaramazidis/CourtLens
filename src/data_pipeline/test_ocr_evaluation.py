import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.ocr_evaluation import (
    ActionRecord,
    EvaluationRow,
    GroundTruthEvent,
    action_category,
    deterministic_stratified_sample,
    load_ground_truth,
    metric_summary,
)
from src.data_pipeline.ocr_triplets import PlayByPlayAction


class OcrEvaluationTests(unittest.TestCase):
    def test_action_categories_cover_professor_requested_groups(self):
        self.assertEqual(action_category("3FGM"), "made_field_goal")
        self.assertEqual(action_category("FTA"), "missed_free_throw")
        self.assertEqual(action_category("D"), "rebound")
        self.assertEqual(action_category("TOUT"), "timeout")

    def test_accuracy_uses_all_events_and_mae_uses_only_mapped_events(self):
        event_a = GroundTruthEvent("E2023", "1", 1, "made_field_goal", 100.0)
        event_b = GroundTruthEvent("E2023", "1", 2, "made_field_goal", 200.0)
        event_c = GroundTruthEvent("E2023", "1", 3, "made_field_goal", 300.0)
        rows = [
            EvaluationRow("candidate", event_a, "2FGM", 100.5),
            EvaluationRow("candidate", event_b, "2FGM", 202.0),
            EvaluationRow("candidate", event_c, "2FGM", None),
        ]

        metrics = metric_summary(rows, (1.0, 2.0))

        self.assertEqual(metrics["total"], 3)
        self.assertEqual(metrics["mapped"], 2)
        self.assertAlmostEqual(metrics["uer_pct"], 100 / 3)
        self.assertAlmostEqual(metrics["mae_seconds"], 1.25)
        self.assertAlmostEqual(metrics["acc_at_1_pct"], 100 / 3)
        self.assertAlmostEqual(metrics["acc_at_2_pct"], 200 / 3)

    def test_stratified_sample_is_deterministic_and_capped_per_category(self):
        records = []
        for event_id in range(1, 8):
            action_info = "2FGM" if event_id <= 4 else "TOUT"
            records.append(ActionRecord(
                season_code="E2023",
                game_code="1",
                event_id=event_id,
                action=PlayByPlayAction(
                    uri=f"game#PlayByPlay_J{event_id}",
                    quarter="1st",
                    quarter_seconds_remaining=600 - event_id,
                    action_info=action_info,
                ),
                action_info=action_info,
                category=action_category(action_info),
                pbp_quarter="1st",
                pbp_clock=f"09:{60 - event_id:02d}",
                youtube_url="https://www.youtube.com/watch?v=test",
            ))

        first = deterministic_stratified_sample(records, 2, "seed")
        second = deterministic_stratified_sample(records, 2, "seed")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertEqual(
            {category: sum(row.category == category for row in first)
             for category in {row.category for row in first}},
            {"made_field_goal": 2, "timeout": 2},
        )

    def test_ground_truth_loader_tracks_pending_and_excluded_rows(self):
        content = (
            "season_code,game_code,original_event_id,action_category,"
            "annotation_status,ground_truth_video_seconds\n"
            "E2023,39,10,made_field_goal,Annotated,123.5\n"
            "E2023,39,11,timeout,Pending,\n"
            "E2023,39,12,foul,Exclude,\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ground_truth.csv"
            path.write_text(content, encoding="utf-8")
            events, pending, excluded = load_ground_truth(path)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].ground_truth_video_seconds, 123.5)
        self.assertEqual(pending, 1)
        self.assertEqual(excluded, 1)


if __name__ == "__main__":
    unittest.main()
