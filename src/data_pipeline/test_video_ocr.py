import unittest

from src.data_pipeline.video_ocr import (
    DEFAULT_CATALOG_FILE,
    DEFAULT_PROFILES_FILE,
    ClockTracker,
    find_game_config,
    load_game_catalog,
    load_profiles,
    parse_clock,
    remove_temporally_impossible_results,
    roi_pixels,
    sanitize_timeline_results,
)


class VideoOcrConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = load_profiles(DEFAULT_PROFILES_FILE)
        cls.profile = cls.profiles["euroleague_left_scorebug_16_9"]
        cls.bottom_profile = cls.profiles["euroleague_bottom_left_scorebug_16_9"]

    def test_current_layout_scales_to_original_720p_crop(self):
        self.assertEqual(roi_pixels(self.profile, 1280, 720), (10, 300, 100, 50))

    def test_current_game_uses_reusable_profile(self):
        game = find_game_config(load_game_catalog(DEFAULT_CATALOG_FILE), "E2023", "333")
        self.assertIsNotNone(game)
        self.assertEqual(game["ocr_profile"], "euroleague_left_scorebug_16_9")
        self.assertEqual(game["youtube_id"], "xRuH1qSD2dE")

    def test_clock_parser_supports_regular_and_decimal_clocks(self):
        self.assertEqual(parse_clock(" 09:23 "), "09:23")
        self.assertEqual(parse_clock("7.24"), "7:24")
        self.assertEqual(parse_clock("O:45"), "0:45")
        self.assertEqual(parse_clock("15.9"), "15.9")
        self.assertIsNone(parse_clock("12:99"))

    def test_tracker_rejects_impossible_clock_jump(self):
        tracker = ClockTracker.from_profile(self.profile)
        self.assertEqual(tracker.accept("0.1"), ("1st", "0.1"))
        self.assertIsNone(tracker.accept("5.9"))

    def test_tracker_detects_next_quarter(self):
        tracker = ClockTracker.from_profile(self.profile)
        self.assertEqual(tracker.accept("0.1"), ("1st", "0.1"))
        self.assertEqual(tracker.accept("10:00"), ("2nd", "10:00"))

    def test_tracker_does_not_treat_regular_period_replay_as_overtime(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 3
        self.assertEqual(tracker.accept("0.0", 100.0), ("4th", "0.0"))
        self.assertIsNone(tracker.accept("7:24", 200.0))
        self.assertEqual(tracker.period, "4th")

    def test_bottom_scorebug_tolerates_short_broadcast_ocr_gap(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("9:37", 100.0), ("1st", "9:37"))
        self.assertEqual(tracker.accept("9:18", 120.0), ("1st", "9:18"))

    def test_tracker_rejects_clock_drop_faster_than_video_time(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("1:08", 100.0), ("1st", "1:08"))
        self.assertIsNone(tracker.accept("1.0", 102.0))
        self.assertEqual(tracker.accept("1:06", 103.0), ("1st", "1:06"))

    def test_timeline_cleanup_keeps_latest_monotonic_sequence(self):
        cleaned, removed = sanitize_timeline_results([
            (100.0, "1st", "7:14"),
            (101.0, "1st", "7:10"),
            (130.0, "1st", "7:13"),
            (131.0, "1st", "7:12"),
            (132.0, "1st", "7:12"),
        ])
        self.assertEqual(cleaned, [
            (100.0, "1st", "7:14"),
            (130.0, "1st", "7:13"),
            (132.0, "1st", "7:12"),
        ])
        self.assertEqual(removed, 2)

    def test_temporal_cleanup_rejects_impossible_drop(self):
        cleaned, removed = remove_temporally_impossible_results([
            (100.0, "2nd", "5:50"),
            (101.0, "2nd", "5:29"),
            (121.0, "2nd", "5:28"),
        ])
        self.assertEqual(cleaned, [
            (100.0, "2nd", "5:50"),
            (121.0, "2nd", "5:28"),
        ])
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
