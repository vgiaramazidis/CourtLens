import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app as backend_app


class VideoSynchronizationTests(unittest.TestCase):
    def test_overtime_aliases_share_one_canonical_label(self):
        self.assertEqual(backend_app.normalize_quarter("OT"), "OT")
        self.assertEqual(backend_app.normalize_quarter("1OT"), "OT")
        self.assertEqual(backend_app.normalize_quarter("OT1"), "OT")
        self.assertEqual(backend_app.normalize_quarter("2OT"), "2OT")

    def test_overtime_play_uses_the_existing_ocr_timeline(self):
        from_ot = backend_app.find_video_seconds("04:35", "OT", "E2023", "328")
        from_alias = backend_app.find_video_seconds("04:35", "1OT", "E2023", "328")

        self.assertGreater(from_ot, 0)
        self.assertEqual(from_alias, from_ot)

    def test_successful_sparql_response_is_cached(self):
        with backend_app._sparql_cache_lock:
            backend_app._sparql_cache.clear()

        with patch.object(
            backend_app,
            "query_sparql_requests",
            return_value={"results": {"bindings": []}},
        ) as mocked_query:
            first = backend_app._query_sparql_cached("SELECT * WHERE {}")
            second = backend_app._query_sparql_cached("SELECT * WHERE {}")

        self.assertEqual(first, second)
        mocked_query.assert_called_once()

    def test_assist_intent_is_detected_in_english_and_greek(self):
        self.assertTrue(backend_app.query_mentions_assists("Show Sloukas assists to Nunn"))
        self.assertTrue(backend_app.query_mentions_assists("Δείξε τις ασίστ του Σλούκα"))
        self.assertFalse(backend_app.query_mentions_assists("Show all Sloukas points"))

    def test_playbyplay_intents_are_classified_for_ai_overlay(self):
        cases = {
            "Show all assists by Sloukas": "assists",
            "Show all rebounds by Lessort": "rebounds",
            "Show Campazzo turnovers": "turnovers",
            "Show fouls drawn by Nunn": "fouls",
            "Show every made three-pointer": "shots",
            "Show every made free throw": "shots",
            "Deikse ta lathi tou Campazzo": "turnovers",
            "Δείξε όλους τους πόντους": "points",
        }
        for message, expected_kind in cases.items():
            with self.subTest(message=message):
                self.assertEqual(backend_app.classify_playbyplay_action_kind(message), expected_kind)

    def test_percentage_prompt_requires_basketball_makes_attempts_and_percentage(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn("?made", prompt)
        self.assertIn("?attempts", prompt)
        self.assertIn("?percentage", prompt)
        self.assertIn("TwoPointShotMade", prompt)
        self.assertIn("TwoPointShotMissed", prompt)
        self.assertIn("percentage ή average", prompt)
        self.assertIn("DISTINCT ?action", prompt)

    def test_ai_prompt_uses_request_context_instead_of_one_fixed_game(self):
        prompt = backend_app.euroleague_system_prompt

        self.assertIn("Υποχρεωτικό context", prompt)
        self.assertNotIn('bball:hasCode "333"', prompt)
        self.assertNotIn('bball:hasCode "E2023"', prompt)
        self.assertNotIn("Sloukas", prompt)
        self.assertNotIn("Nunn", prompt)

    def test_percentage_ai_response_is_aggregate_and_does_not_filter_playbyplay(self):
        generated_query = """
PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
SELECT ?playerName (SUM(?madeValue) AS ?made) (COUNT(?action) AS ?attempts)
       (100.0 * SUM(?madeValue) / COUNT(?action) AS ?percentage)
WHERE {
  ?game bball:hasPlayByPlayAction ?action .
  ?action a ?actionType ; bball:actionPlayer ?player .
  VALUES ?actionType { bball:TwoPointShotMade bball:TwoPointShotMissed }
  BIND(IF(?actionType = bball:TwoPointShotMade, 1, 0) AS ?madeValue)
  ?player <http://www.w3.org/2000/01/rdf-schema#label> ?playerName .
}
GROUP BY ?playerName
LIMIT 200
"""
        percentage_bindings = [{
            "playerName": {"type": "literal", "value": "Kostas Sloukas"},
            "made": {"type": "literal", "value": "2"},
            "attempts": {"type": "literal", "value": "2"},
            "percentage": {"type": "literal", "value": "100"},
        }]
        fake_models = SimpleNamespace(generate_content=AsyncMock(
            return_value=SimpleNamespace(text=generated_query)
        ))
        fake_client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))
        request = backend_app.ChatRequest(
            message="the percentage 2 shots of sloukas",
            game_code="333",
            season_code="E2023",
        )
        with backend_app._ai_search_cache_lock:
            backend_app._ai_search_cache.clear()
        with patch.object(backend_app, "client", fake_client), patch.object(
            backend_app,
            "query_sparql",
            new=AsyncMock(return_value={"results": {"bindings": percentage_bindings}}),
        ):
            payload = asyncio.run(backend_app.ai_chat_handler(request))

        self.assertEqual(payload["results"], percentage_bindings)
        self.assertFalse(payload["playbyplay_filter"])
        self.assertEqual(payload["action_uris"], [])

    def test_aggregate_action_count_is_not_mistaken_for_projected_action_uri(self):
        aggregate_query = "SELECT (COUNT(?action) AS ?attempts) WHERE { ?game ?p ?action . }"
        action_query = "SELECT DISTINCT ?action ?playerName WHERE { ?game ?p ?action . }"

        self.assertFalse(backend_app.query_selects_playbyplay_actions(aggregate_query))
        self.assertTrue(backend_app.query_selects_playbyplay_actions(action_query))

    def test_ai_search_cache_uses_the_full_game_context(self):
        cache_key = ("E2023", "333", "show sloukas assists")
        payload = {"results": [], "playbyplay_action_kind": "assists"}
        with backend_app._ai_search_cache_lock:
            backend_app._ai_search_cache.clear()

        backend_app._cache_ai_search(cache_key, payload)

        self.assertEqual(backend_app._get_cached_ai_search(cache_key), payload)
        self.assertIsNone(backend_app._get_cached_ai_search(("E2023", "328", cache_key[2])))

    def test_assist_resolution_query_keeps_only_safe_unique_uris(self):
        query = backend_app.build_assist_action_resolution_query([
            "http://example.test/action/shot-1",
            "http://example.test/action/shot-1",
            "not-an-action-uri",
            "http://example.test/action/unsafe>uri",
        ])

        self.assertIsNotNone(query)
        self.assertEqual(query.count("<http://example.test/action/shot-1>"), 1)
        self.assertNotIn("not-an-action-uri", query)
        self.assertNotIn("unsafe>uri", query)
        self.assertIn("bball:hasAssist ?action", query)

    def test_assist_resolution_query_requires_at_least_one_safe_uri(self):
        self.assertIsNone(backend_app.build_assist_action_resolution_query(["invalid", ""] ))


if __name__ == "__main__":
    unittest.main()
