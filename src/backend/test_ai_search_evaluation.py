"""Tests for the repeatable AI Search evaluation harness."""

import tempfile
import unittest
from pathlib import Path

from ai_search_evaluation import (
    DEFAULT_QUESTIONS,
    execute_question,
    estimate_standard_cost_usd,
    is_read_only_query,
    load_questions,
    query_contains_scope,
    select_questions,
    usage_columns,
)


class AiSearchEvaluationTests(unittest.TestCase):
    def test_select_questions_preserves_requested_order(self):
        questions = [
            {"id": "Q01"},
            {"id": "Q02"},
            {"id": "Q03"},
        ]

        selected = select_questions(questions, ["Q03", "Q01", "Q03"])

        self.assertEqual([question["id"] for question in selected], ["Q03", "Q01"])

    def test_select_questions_rejects_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "Unknown benchmark question"):
            select_questions([{"id": "Q01"}], ["Q99"])

    def test_openai_provider_model_and_prompt_are_sent_to_backend(self):
        class Response:
            status_code = 200

            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {
                    "results": [],
                    "action_uris": [],
                    "playbyplay_filter": False,
                    "sparql_query": (
                        'SELECT * WHERE { ?season ?p "E2023" . '
                        '?game ?p2 "333" . } LIMIT 1'
                    ),
                    "ai_provider": "openai",
                    "ai_model": "gpt-5-mini",
                    "prompt_variant": "simple",
                    "ai_usage": {
                        "input_tokens": 1000,
                        "cached_input_tokens": 100,
                        "output_tokens": 200,
                        "reasoning_tokens": 50,
                        "total_tokens": 1200,
                    },
                }

        class Session:
            request_json = None

            def post(self, _url, json, timeout):
                self.request_json = json
                self.timeout = timeout
                return Response()

        session = Session()
        question = {
            "id": "QX",
            "category": "test",
            "message": "Test question",
            "season_code": "E2023",
            "game_code": "333",
            "expected_playbyplay_filter": False,
        }
        row = execute_question(
            session,
            "http://test/api/chat",
            question,
            "openai",
            "simple",
            "gpt-5-mini",
            30,
        )

        self.assertEqual(session.request_json["provider"], "openai")
        self.assertEqual(session.request_json["openai_model"], "gpt-5-mini")
        self.assertEqual(session.request_json["prompt_variant"], "simple")
        self.assertEqual(row["model"], "gpt-5-mini")
        self.assertEqual(row["total_tokens"], 1200)
        self.assertEqual(row["estimated_standard_cost_usd"], 0.0006275)

    def test_cost_estimate_uses_cached_and_uncached_rates(self):
        self.assertEqual(
            estimate_standard_cost_usd("openai", "gpt-5-mini", 1000, 100, 200),
            0.0006275,
        )
        self.assertEqual(
            estimate_standard_cost_usd("unknown", "model", 1000, 0, 200), ""
        )

    def test_usage_columns_normalize_backend_diagnostics(self):
        columns = usage_columns(
            {
                "ai_usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 100,
                    "output_tokens": 200,
                    "reasoning_tokens": 50,
                    "total_tokens": 1200,
                }
            },
            "openai",
            "gpt-5-mini",
        )

        self.assertEqual(columns["total_tokens"], 1200)
        self.assertEqual(columns["estimated_standard_cost_usd"], 0.0006275)

    def test_fixed_benchmark_has_twenty_complete_questions(self):
        questions = load_questions(DEFAULT_QUESTIONS)
        self.assertEqual(len(questions), 20)
        for question in questions:
            self.assertTrue(question["message"])
            self.assertTrue(question["category"])
            self.assertEqual(question["season_code"], "E2023")
            self.assertEqual(question["game_code"], "333")

    def test_query_safety_check(self):
        self.assertTrue(is_read_only_query("SELECT ?action WHERE { ?s ?p ?o } LIMIT 1"))
        self.assertTrue(
            is_read_only_query(
                "PREFIX bball: <http://example/> ASK WHERE { ?s ?p ?o }"
            )
        )
        self.assertFalse(is_read_only_query("DELETE WHERE { ?s ?p ?o }"))
        self.assertFalse(
            is_read_only_query("SELECT * WHERE { SERVICE <http://x> { ?s ?p ?o } }")
        )

    def test_scope_requires_exact_literals(self):
        query = 'SELECT * WHERE { ?season <code> "E2023" . ?game <code> "333" . }'
        self.assertTrue(query_contains_scope(query, "E2023", "333"))
        self.assertFalse(query_contains_scope(query, "E2023", "33"))

    def test_duplicate_question_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "questions.json"
            path.write_text(
                '{"questions": [{"id": "Q1"}, {"id": "Q1"}]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unique"):
                load_questions(path)


if __name__ == "__main__":
    unittest.main()
