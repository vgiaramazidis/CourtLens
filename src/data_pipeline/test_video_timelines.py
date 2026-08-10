import csv
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.validate_video_timelines import validate_timeline


class VideoTimelineValidationTests(unittest.TestCase):
    def test_incomplete_period_coverage_is_reported_as_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            timeline_path = Path(temp_dir) / "timeline.csv"
            video_seconds = 0.0
            with timeline_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["video_time_sec", "quarter", "game_clock"])
                for quarter in ("1st", "2nd", "3rd", "4th"):
                    start_clock = 560 if quarter == "3rd" else 600
                    for clock_seconds in range(start_clock, -1, -1):
                        if quarter == "4th" and 480 < clock_seconds < 500:
                            continue
                        if quarter == "4th" and clock_seconds == 480:
                            video_seconds += 20
                        minutes, seconds = divmod(clock_seconds, 60)
                        writer.writerow([video_seconds, quarter, f"{minutes}:{seconds:02d}"])
                        video_seconds += 1

            summary, errors = validate_timeline(timeline_path)

        self.assertEqual(errors, [])
        self.assertTrue(any("3rd starts" in warning for warning in summary["warnings"]))
        self.assertTrue(any("4th has a" in warning for warning in summary["warnings"]))


if __name__ == "__main__":
    unittest.main()
