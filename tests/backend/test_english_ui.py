import json
import unittest
from unittest.mock import AsyncMock, patch

from src.backend import app as backend


class EnglishInterfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_generated_copy_is_checked_recursively(self):
        payload = {"hints": ["A point guard."], "secret_player_name": "Kostas Sloukas"}
        self.assertEqual(backend.parse_english_quiz_response(json.dumps(payload)), payload)
        with self.assertRaisesRegex(ValueError, "non-English"):
            backend.parse_english_quiz_response('{"hints":["\u03a0\u03bf\u03b9\u03bf\u03c2;"]}')

    async def test_unconfigured_quiz_returns_english_error(self):
        with patch.object(backend, "OPENAI_API_KEY", ""):
            with self.assertRaises(backend.HTTPException) as caught:
                await backend.generate_who_am_i("easy")
        self.assertIn("Quiz generation is unavailable", caught.exception.detail)

    async def test_who_am_i_instructs_english_and_preserves_quiz_contract(self):
        result = {
            "secret_player_name": "Kostas Sloukas",
            "hints": ["A guard.", "A teammate.", "Initials K. S."],
        }
        generate = AsyncMock(return_value=dict(result, secret_player_name="Wrong model name"))
        roster = {
            "results": {"bindings": [{"homeLineup": {"value": "https://example.com/#Lineup_123"}}]}
        }
        profile = {
            "results": {
                "bindings": [{"name": {"value": "Kostas Sloukas"}, "position": {"value": "Guard"}}]
            }
        }
        with (
            patch.object(backend, "OPENAI_API_KEY", "test"),
            patch.object(backend, "generate_quiz_text", generate),
            patch.object(backend, "query_sparql_requests", side_effect=[roster, profile]),
        ):
            actual = await backend.generate_who_am_i("easy")
        self.assertEqual(actual["secret_player_name"], result["secret_player_name"])
        self.assertEqual(actual["hints"], result["hints"])
        self.assertEqual(actual["secret_player"]["id"], "123")
        self.assertIn("Write exclusively in English", generate.call_args.args[0])

    async def test_top_five_question_and_units_are_english(self):
        stats = {
            "results": {
                "bindings": [
                    {
                        "player": {"value": f"https://example.com/{i}"},
                        "totalBlocks": {"value": str(10 - i)},
                    }
                    for i in range(5)
                ]
            }
        }

        def query(value):
            if value.startswith("name:"):
                return {"results": {"bindings": [{"name": {"value": f"Player {value[5:]}"}}]}}
            return stats

        def choice(values):
            return values[1] if isinstance(values[0], dict) else values[0]

        with (
            patch.object(backend, "client", object()),
            patch.object(backend.random, "choice", side_effect=choice),
            patch.object(backend, "query_sparql_requests", side_effect=query),
            patch.object(backend, "get_player_name_query", side_effect=lambda pid: "name:" + pid),
        ):
            actual = await backend.generate_top_5("easy")
        self.assertEqual(len(actual["answers"]), 5)
        self.assertEqual(
            actual["question_text"],
            "Who were the top five players for blocked shots in the 2023-24 season?",
        )
        self.assertEqual(actual["answers"][0]["stat"], "10 blocks")


if __name__ == "__main__":
    unittest.main()
