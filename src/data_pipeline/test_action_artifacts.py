import unittest

from src.data_pipeline.validate_action_artifacts import validate_action_payload


class ActionArtifactValidationTests(unittest.TestCase):
    def test_valid_overtime_clock_is_accepted(self):
        payload = {
            "Possessions": [],
            "AllActions": [{
                "hasPlayByPlaySequence": 1,
                "originalEventId": 525,
                "quarter": "1OT",
                "clock": "05:00",
                "quarterSecondsRemaining": 300,
            }],
        }

        _actions, errors = validate_action_payload(payload)

        self.assertEqual(errors, [])

    def test_ten_minute_overtime_clock_is_rejected(self):
        payload = {
            "Possessions": [],
            "AllActions": [{
                "hasPlayByPlaySequence": 1,
                "originalEventId": 525,
                "quarter": "1OT",
                "clock": "10:00",
                "quarterSecondsRemaining": 600,
            }],
        }

        _actions, errors = validate_action_payload(payload)

        self.assertTrue(any("allowed range is 0-300" in error for error in errors))

    def test_sequence_gaps_are_rejected(self):
        payload = {
            "Possessions": [],
            "AllActions": [{
                "hasPlayByPlaySequence": 2,
                "originalEventId": 11,
                "quarter": "1st",
                "clock": "10:00",
                "quarterSecondsRemaining": 600,
            }],
        }

        _actions, errors = validate_action_payload(payload)

        self.assertIn("hasPlayByPlaySequence is not continuous from 1", errors)


if __name__ == "__main__":
    unittest.main()
