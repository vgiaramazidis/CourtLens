import unittest

from src.data_pipeline.video_ocr import (
    DEFAULT_CATALOG_FILE,
    DEFAULT_PROFILES_FILE,
    ClockTracker,
    InitialClockGate,
    find_game_config,
    load_game_catalog,
    load_profiles,
    parse_clock,
    remove_temporally_impossible_results,
    roi_pixels,
    sanitize_timeline_results,
    timeline_completeness_errors,
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
        self.assertEqual(game["ocr_profile"], "euroleague_bottom_left_scorebug_16_9")
        self.assertEqual(game["youtube_id"], "xRuH1qSD2dE")

    def test_clock_parser_supports_regular_and_decimal_clocks(self):
        self.assertEqual(parse_clock(" 09:23 "), "09:23")
        self.assertEqual(parse_clock("7.24"), "7:24")
        self.assertEqual(parse_clock("O:45"), "0:45")
        self.assertEqual(parse_clock("15.9"), "15.9")
        self.assertEqual(parse_clock("741"), "7:41")
        self.assertEqual(parse_clock("1000"), "10:00")
        self.assertIsNone(parse_clock("9368"))
        self.assertIsNone(parse_clock("12:99"))

    def test_initial_clock_gate_rejects_pregame_token_and_confirms_game_clock(self):
        gate = InitialClockGate(period_seconds=600, minimum_start_ratio=0.9)

        self.assertFalse(gate.accept("3:10", 903.0))
        self.assertEqual(gate.last_decision, "initial_clock_below_start_window")
        self.assertFalse(gate.accept("9:55", 917.0))
        self.assertFalse(gate.accept("9:54", 918.0))
        self.assertTrue(gate.accept("9:53", 919.0))
        self.assertEqual(gate.last_decision, "initial_clock_confirmation_confirmed")
        self.assertIsNone(gate.take_confirmed_backfill())

    def test_initial_clock_gate_backfills_frozen_tipoff_clock(self):
        gate = InitialClockGate(period_seconds=600, minimum_start_ratio=0.9)

        self.assertFalse(gate.accept("10:00", 983.0))
        self.assertFalse(gate.accept("10:00", 984.0))
        # A table/clock correction delays the first moving game-clock sequence.
        self.assertFalse(gate.accept("9:55", 1224.0))
        self.assertFalse(gate.accept("9:54", 1225.0))
        self.assertFalse(gate.accept("9:53", 1226.0))
        self.assertTrue(gate.accept("9:52", 1227.0))
        self.assertEqual(gate.take_confirmed_backfill(), (983.0, "10:00"))
        self.assertIsNone(gate.take_confirmed_backfill())

    def test_initial_clock_gate_does_not_backfill_single_unconfirmed_frame(self):
        gate = InitialClockGate(period_seconds=600, minimum_start_ratio=0.9)

        self.assertFalse(gate.accept("10:00", 700.0))
        self.assertFalse(gate.accept("9:55", 917.0))
        self.assertFalse(gate.accept("9:54", 918.0))
        self.assertFalse(gate.accept("9:53", 919.0))
        self.assertTrue(gate.accept("9:52", 920.0))
        self.assertIsNone(gate.take_confirmed_backfill())

    def test_tracker_rejects_impossible_clock_jump(self):
        tracker = ClockTracker.from_profile(self.profile)
        self.assertEqual(tracker.accept("0.1"), ("1st", "0.1"))
        self.assertIsNone(tracker.accept("5.9"))

    def test_tracker_detects_next_quarter(self):
        tracker = ClockTracker.from_profile(self.profile)
        self.assertEqual(tracker.accept("0.1"), ("1st", "0.1"))
        self.assertEqual(tracker.accept("10:00"), ("2nd", "10:00"))

    def test_tracker_rebases_short_highlight_fragment_before_real_period(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 1
        readings = [
            (3932.0, "0.0"),
            (4237.0, "9:22"),
            (4238.0, "9:21"),
            (4239.0, "9:20"),
            (4240.0, "9:19"),
            (4241.0, "9:18"),
            # E2024/330 returns to the real Monaco-Fenerbahce third period
            # after a long halftime highlight package.
            (4865.0, "9:56"),
            (4866.0, "9:55"),
            (4867.0, "9:54"),
        ]
        accepted = []
        for video_time, clock in readings:
            result = tracker.accept(clock, video_time)
            if result:
                accepted.append((video_time, *result))

        self.assertEqual(tracker.period, "3rd")
        self.assertEqual(accepted[-1], (4867.0, "3rd", "9:54"))
        cleaned, removed = sanitize_timeline_results(accepted)
        self.assertEqual(cleaned, [
            (3932.0, "2nd", "0.0"),
            (4867.0, "3rd", "9:54"),
        ])
        self.assertEqual(removed, 5)

    def test_tracker_rolls_back_temporally_compressed_highlight_period(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 1
        self.assertEqual(tracker.accept("0.0", 3932.0), ("2nd", "0.0"))

        self.assertEqual(tracker.accept("9:22", 4237.0), ("3rd", "9:22"))
        # Each individual drop is just inside the local grace window, but the
        # accumulated clock span is physically impossible for the elapsed
        # video and must roll the whole highlight period back.
        for step in range(1, 35):
            offset = 4237.0 + step * 4
            seconds = 562 - step * 9
            clock = f"{seconds // 60}:{seconds % 60:02d}"
            result = tracker.accept(clock, offset)
            if step < 34:
                self.assertEqual(result, ("3rd", clock))
            else:
                self.assertIsNone(result)
        self.assertEqual(
            tracker.take_invalidated_period(),
            ("3rd", 4237.0),
        )
        self.assertEqual(tracker.period, "2nd")
        self.assertEqual(tracker.last_clock, "0.0")
        self.assertEqual(tracker.accept("9:56", 4865.0), ("3rd", "9:56"))

    def test_normal_period_transition_is_not_rebased(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 1
        self.assertEqual(tracker.accept("0.0", 100.0), ("2nd", "0.0"))
        self.assertEqual(tracker.accept("9:55", 180.0), ("3rd", "9:55"))
        self.assertEqual(tracker.accept("9:54", 181.0), ("3rd", "9:54"))
        self.assertEqual(tracker.accept("9:53", 182.0), ("3rd", "9:53"))
        self.assertIsNone(tracker.pending_period_rebase)

    def test_established_period_rejects_late_opening_replay(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 1
        self.assertEqual(tracker.accept("0.0", 100.0), ("2nd", "0.0"))
        for offset, seconds in enumerate(range(595, 583, -1), start=200):
            clock = f"{seconds // 60}:{seconds % 60:02d}"
            self.assertEqual(tracker.accept(clock, float(offset)), ("3rd", clock))

        self.assertGreater(tracker.period_observation_count, 10)
        self.assertIsNone(tracker.accept("9:58", 900.0))
        self.assertIsNone(tracker.pending_period_rebase)
        self.assertEqual(tracker.last_clock, "9:44")

    def test_official_clock_correction_remains_allowed(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("36.0", 100.0), ("1st", "36.0"))
        self.assertEqual(tracker.accept("36.6", 101.0), ("1st", "36.6"))
        self.assertIsNone(tracker.pending_period_rebase)

    def test_tracker_reports_why_a_clock_was_discarded(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("52.9", 100.0), ("1st", "52.9"))
        self.assertEqual(tracker.last_decision, "accepted")

        self.assertIsNone(tracker.accept("5.3", 101.0))
        self.assertEqual(
            tracker.last_decision,
            "single_digit_decimal_confirmation_pending",
        )

        self.assertIsNone(tracker.accept("1:20", 102.0))
        self.assertEqual(tracker.last_decision, "upward_jump_too_large")

    def test_stopped_clock_blocks_transient_correction_animation(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("4:12", 8.0), ("1st", "4:12"))

        self.assertIsNone(tracker.accept("4:12", 51.0))
        self.assertEqual(tracker.last_video_time, 8.0)
        self.assertEqual(tracker.last_seen_video_time, 51.0)
        self.assertIsNone(tracker.accept("3:22", 55.0))
        self.assertEqual(
            tracker.last_decision,
            "gapped_clock_drop_confirmation_pending",
        )
        # The correction graphic moves about four clock seconds per video
        # second, so it never confirms as a running game clock.
        self.assertIsNone(tracker.accept("3:18", 56.0))
        self.assertIsNone(tracker.accept("3:14", 57.0))

        # The official correction is only three seconds upward and remains
        # valid for the configured bottom-left scorebug profile.
        self.assertEqual(tracker.accept("4:15", 65.0), ("1st", "4:15"))
        self.assertEqual(tracker.take_confirmed_backfills(), ())

    def test_stopped_clock_accepts_confirmed_live_resumption(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("9:00", 100.0), ("1st", "9:00"))
        self.assertIsNone(tracker.accept("9:00", 180.0))

        self.assertIsNone(tracker.accept("8:24", 181.0))
        self.assertIsNone(tracker.accept("8:23", 182.0))
        self.assertEqual(tracker.accept("8:22", 183.0), ("1st", "8:22"))
        self.assertEqual(
            tracker.last_decision,
            "accepted_confirmed_gapped_clock_drop",
        )
        self.assertEqual(
            tracker.take_confirmed_backfills(),
            (
                (181.0, "1st", "8:24"),
                (182.0, "1st", "8:23"),
            ),
        )

    def test_isolated_clock_after_ocr_gap_does_not_poison_live_resumption(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("6:45", 100.0), ("1st", "6:45"))

        # This one-frame 6:05 misread occurred in both E2023/82 and
        # E2024/271 after a long broadcast gap. It must remain provisional.
        self.assertIsNone(tracker.accept("6:05", 175.0))
        self.assertEqual(
            tracker.last_decision,
            "gapped_clock_drop_confirmation_pending",
        )

        # The real scorebug returns at 6:39. It invalidates the isolated
        # candidate and is a plausible continuation of the last trusted clock.
        self.assertEqual(tracker.accept("6:39", 219.0), ("1st", "6:39"))
        self.assertEqual(tracker.take_confirmed_backfills(), ())
        self.assertEqual(tracker.accept("6:38", 220.0), ("1st", "6:38"))

    def test_repeated_truncated_decimal_does_not_poison_later_clocks(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("43.3", 100.0), ("1st", "43.3"))

        self.assertIsNone(tracker.accept("3.3", 101.0))
        self.assertIsNone(tracker.accept("3.3", 102.0))
        self.assertEqual(tracker.last_clock, "43.3")
        self.assertEqual(tracker.accept("42.7", 103.0), ("1st", "42.7"))

    def test_descending_final_seconds_confirm_a_real_large_drop(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("43.3", 100.0), ("1st", "43.3"))

        self.assertIsNone(tracker.accept("3.3", 200.0))
        self.assertEqual(tracker.accept("2.3", 201.0), ("1st", "2.3"))
        self.assertEqual(
            tracker.last_decision,
            "accepted_confirmed_single_digit_decimal",
        )

    def test_decimal_final_clock_is_not_mistaken_for_next_period(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("11.4", 100.0), ("1st", "11.4"))

        # EasyOCR read the visible 9.4 in E2023/82 as 9:24. Two elapsed video
        # seconds are not enough for 11.4 seconds of game clock to reach zero.
        self.assertIsNone(tracker.accept("9:24", 102.0))
        self.assertEqual(tracker.period, "1st")
        self.assertEqual(tracker.accept("8.4", 103.0), ("1st", "8.4"))

    def test_tracker_does_not_treat_regular_period_replay_as_overtime(self):
        tracker = ClockTracker.from_profile(self.profile)
        tracker.period_index = 3
        self.assertEqual(tracker.accept("0.0", 100.0), ("4th", "0.0"))
        self.assertIsNone(tracker.accept("7:24", 200.0))
        self.assertEqual(tracker.period, "4th")

    def test_tracker_rejects_late_postgame_overtime_replay(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        tracker.period_index = 3
        self.assertEqual(tracker.accept("0.0", 100.0), ("4th", "0.0"))

        self.assertIsNone(tracker.accept("4:30", 614.0))
        self.assertEqual(tracker.period, "4th")

    def test_tracker_accepts_overtime_after_normal_break(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        tracker.period_index = 3
        self.assertEqual(tracker.accept("0.0", 100.0), ("4th", "0.0"))

        self.assertEqual(tracker.accept("4:58", 270.0), ("OT", "4:58"))

    def test_bottom_scorebug_confirms_live_clock_after_broadcast_gap(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("9:37", 100.0), ("1st", "9:37"))
        self.assertIsNone(tracker.accept("9:18", 120.0))
        self.assertIsNone(tracker.accept("9:16", 141.0))
        self.assertEqual(tracker.accept("9:15", 142.0), ("1st", "9:15"))
        self.assertEqual(
            tracker.take_confirmed_backfills(),
            (
                (120.0, "1st", "9:18"),
                (141.0, "1st", "9:16"),
            ),
        )

    def test_tracker_rejects_clock_drop_faster_than_video_time(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("1:08", 100.0), ("1st", "1:08"))
        self.assertIsNone(tracker.accept("1.0", 102.0))
        self.assertEqual(tracker.accept("1:06", 103.0), ("1st", "1:06"))

    def test_tracker_recovers_when_ocr_drops_a_decimal_clock_digit(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("52.9", 7938.0), ("1st", "52.9"))

        # This is the failure observed in E2025/406: a clock around 51.3 was
        # read as 5.3. The next correct frame must still be accepted.
        self.assertIsNone(tracker.accept("5.3", 8073.0))
        self.assertEqual(tracker.accept("50.3", 8074.0), ("1st", "50.3"))

    def test_tracker_confirms_a_real_large_drop_into_final_seconds(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("52.9", 100.0), ("1st", "52.9"))

        self.assertIsNone(tracker.accept("5.3", 200.0))
        self.assertEqual(tracker.accept("4.3", 201.0), ("1st", "4.3"))

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

    def test_timeline_cleanup_keeps_first_period_end_zero(self):
        cleaned, removed = sanitize_timeline_results([
            (9000.0, "4th", "0.0"),
            (9010.0, "4th", "0.0"),
            (9340.0, "4th", "0.0"),
        ])

        self.assertEqual(cleaned, [(9000.0, "4th", "0.0")])
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

    def test_tracker_rejects_descending_replay_faster_than_video(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("4:34", 1519.0), ("1st", "4:34"))

        # A replay clock descends normally, but it is 207 game seconds behind
        # after only 48 video seconds and therefore cannot be live action.
        for video_time, clock in (
            (1567.0, "1:07"),
            (1568.0, "1:06"),
            (1569.0, "1:05"),
        ):
            self.assertIsNone(tracker.accept(clock, video_time))
            self.assertEqual(
                tracker.last_decision,
                "gapped_clock_drop_faster_than_video",
            )

        # The later genuine sequence can still be confirmed and backfilled.
        self.assertIsNone(tracker.accept("3:34", 1750.0))
        self.assertIsNone(tracker.accept("3:33", 1751.0))
        self.assertEqual(tracker.accept("3:32", 1752.0), ("1st", "3:32"))
        self.assertEqual(
            tracker.take_confirmed_backfills(),
            (
                (1750.0, "1st", "3:34"),
                (1751.0, "1st", "3:33"),
            ),
        )

    def test_tracker_recovers_from_small_misread_after_long_video_gap(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("7:12", 6179.0), ("1st", "7:12"))

        # In E2023/327 the first two readings after a long break were 7:03
        # and 7:02, although the real scorebug returned at 7:09. Keep the
        # short suspicious sequence provisional so it cannot reject 7:09 as
        # an upward jump.
        self.assertIsNone(tracker.accept("7:03", 6340.0))
        self.assertIsNone(tracker.accept("7:02", 6342.0))
        self.assertEqual(tracker.accept("7:09", 6355.0), ("1st", "7:09"))
        self.assertEqual(tracker.take_confirmed_backfills(), ())
        self.assertEqual(tracker.accept("7:07", 6357.0), ("1st", "7:07"))

    def test_tracker_preserves_intermediate_confirmed_gapped_clocks(self):
        tracker = ClockTracker.from_profile(self.bottom_profile)
        self.assertEqual(tracker.accept("30.6", 8235.0), ("1st", "30.6"))

        # These E2024/124 readings are all valid. Confirmation must not retain
        # only the first and last clocks and silently lose the middle one.
        self.assertIsNone(tracker.accept("20.6", 8245.0))
        self.assertIsNone(tracker.accept("20.5", 8249.0))
        self.assertEqual(tracker.accept("19.5", 8357.0), ("1st", "19.5"))
        self.assertEqual(
            tracker.take_confirmed_backfills(),
            (
                (8245.0, "1st", "20.6"),
                (8249.0, "1st", "20.5"),
            ),
        )

    def test_full_game_completeness_rejects_missing_and_truncated_periods(self):
        results = [
            (100.0, "1st", "9:55"),
            (700.0, "1st", "0.0"),
            (800.0, "2nd", "9:58"),
            (1400.0, "2nd", "0.0"),
            (2200.0, "3rd", "9:57"),
            (2800.0, "3rd", "0.0"),
            (2900.0, "4th", "9:58"),
            (3000.0, "4th", "8:00"),
        ]

        self.assertEqual(
            timeline_completeness_errors(results),
            ["4th ends too early at 480s"],
        )

    def test_full_game_completeness_accepts_regulation_and_overtime(self):
        results = []
        for index, period in enumerate(("1st", "2nd", "3rd", "4th")):
            results.extend([
                (index * 1000.0, period, "9:55"),
                (index * 1000.0 + 900, period, "0.0"),
            ])
        results.extend([(5000.0, "OT", "4:58"), (5900.0, "OT", "0.0")])

        self.assertEqual(timeline_completeness_errors(results), [])


if __name__ == "__main__":
    unittest.main()
