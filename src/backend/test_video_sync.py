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
    def test_ai_query_is_only_returned_for_evaluation_requests(self):
        payload = {
            "results": [],
            "sparql_query": "SELECT * WHERE {}",
            "ai_provider": "openai",
            "ai_model": "gpt-5-mini",
            "prompt_variant": "ontology",
            "ai_usage": {"input_tokens": 10},
        }

        frontend_response = backend_app.ai_search_response(payload, False)
        for internal_field in (
            "sparql_query",
            "ai_provider",
            "ai_model",
            "prompt_variant",
            "ai_usage",
        ):
            self.assertNotIn(internal_field, frontend_response)
        self.assertEqual(
            backend_app.ai_search_response(payload, True)["sparql_query"],
            payload["sparql_query"],
        )
        self.assertIn("sparql_query", payload)

    def test_evaluation_mode_preserves_invalid_raw_model_output(self):
        request = backend_app.ChatRequest(
            message="Test question",
            season_code="E2023",
            game_code="333",
            provider="openai",
            prompt_variant="ontology",
            openai_model="gpt-5-mini",
            include_query=True,
        )
        usage = {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "output_tokens": 5,
            "reasoning_tokens": 0,
            "total_tokens": 15,
        }
        with (
            patch.object(
                backend_app,
                "ai_search_configuration",
                return_value=("openai", "ontology", "gpt-5-mini"),
            ),
            patch.object(
                backend_app,
                "generate_ai_search_text",
                new=AsyncMock(return_value=("not a SPARQL query", usage)),
            ),
        ):
            with self.assertRaises(backend_app.HTTPException) as raised:
                asyncio.run(backend_app.ai_chat_handler(request))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(
            raised.exception.detail["sparql_query"], "not a SPARQL query"
        )
        self.assertEqual(raised.exception.detail["ai_usage"], usage)

    def test_openai_responses_text_is_extracted(self):
        payload = {
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "SELECT ?action {}"}],
            }]
        }

        self.assertEqual(
            backend_app.extract_openai_output_text(payload),
            "SELECT ?action {}",
        )

    def test_openai_mini_is_the_only_supported_openai_model(self):
        with patch.object(backend_app, "OPENAI_API_KEY", "test-key"):
            mini = backend_app.ai_search_configuration(
                "openai", "ontology", "gpt-5-mini"
            )

        self.assertEqual(mini, ("openai", "ontology", "gpt-5-mini"))

    def test_available_ai_search_models_only_exposes_configured_providers(self):
        with (
            patch.object(backend_app, "GEMINI_API_KEY", "gemini-key"),
            patch.object(backend_app, "client", object()),
            patch.object(backend_app, "OPENAI_API_KEY", ""),
            patch.object(backend_app, "AI_SEARCH_PROVIDER", "openai"),
        ):
            models = backend_app.available_ai_search_models()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["provider"], "gemini")
        self.assertTrue(models[0]["is_default"])
        self.assertNotIn("api_key", models[0])

    def test_available_ai_search_models_marks_configured_default(self):
        with (
            patch.object(backend_app, "GEMINI_API_KEY", "gemini-key"),
            patch.object(backend_app, "client", object()),
            patch.object(backend_app, "OPENAI_API_KEY", "openai-key"),
            patch.object(backend_app, "AI_SEARCH_PROVIDER", "openai"),
        ):
            models = backend_app.available_ai_search_models()

        self.assertEqual([model["provider"] for model in models], ["gemini", "openai"])
        self.assertFalse(models[0]["is_default"])
        self.assertTrue(models[1]["is_default"])

    def test_ontology_prompt_uses_virtuoso_safe_player_name_boundaries(self):
        self.assertIn(
            "(^|[^A-Za-z0-9])PLAYER_NAME([^A-Za-z0-9]|$)",
            backend_app.euroleague_system_prompt,
        )

    def test_ai_search_prompts_and_scope_context_are_english_only(self):
        model_facing_text = "\n".join(
            [
                backend_app.euroleague_system_prompt,
                backend_app.simple_sparql_system_prompt,
                *backend_app.build_ai_scope_context("E2023,E2024", "333"),
            ]
        )
        self.assertNotRegex(model_facing_text, r"[\u0370-\u03ff\u1f00-\u1fff]")
        self.assertIn("Required request context", backend_app.euroleague_system_prompt)

    def test_simple_prompt_matches_flat_vocabulary_baseline(self):
        prompt = backend_app.simple_sparql_system_prompt
        self.assertIn("flat vocabulary", prompt)
        self.assertIn("AVAILABLE PROPERTIES", prompt)
        self.assertIn("AVAILABLE CLASSES", prompt)
        self.assertIn("bball:hasPlayByPlayAction", prompt)
        self.assertIn("bball:correspondsToOCRObservation", prompt)
        self.assertIn("bball:OCRObservation", prompt)
        self.assertNotIn("CANONICAL PATTERN", prompt)
        self.assertNotIn("?shot bball:hasAssist ?assist", prompt)

    def test_ontology_prompt_documents_real_quarter_and_clock_fields(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn('FILTER(str(?quarter) = "4th")', prompt)
        self.assertIn("bball:clock ?clock", prompt)
        self.assertIn("Never use the nonexistent properties", prompt)

    def test_ontology_prompt_documents_action_scores_and_substitutions(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn("bball:runningHomeTeamScore ?homeScore", prompt)
        self.assertIn("bball:runningRoadTeamScore ?roadScore", prompt)
        self.assertIn("bball:PlayerIn bball:PlayerOut", prompt)
        self.assertIn("bball:SubstitutionIn", prompt)
        self.assertIn("do not exist", prompt)
        self.assertNotIn("bball:ShotRejected", prompt)

    def test_ontology_prompt_documents_lineups_rebounds_and_possessions(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn("?action bball:runningHomeTeamLineup ?homeLineup", prompt)
        self.assertIn("bball:leadsToRebound ?reboundAction", prompt)
        self.assertIn("bball:containsAction ?containedAction", prompt)
        self.assertIn("not a resource with bball:hasPlayByPlayAction", prompt)
        self.assertIn("not automatically available inside a subquery", prompt)
        self.assertIn("For a pure ranking", prompt)

    def test_ontology_prompt_has_team_agnostic_starting_lineup_pattern(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn("CANONICAL PATTERN — actions while", prompt)
        self.assertIn("?game bball:homeTeam ?targetTeam", prompt)
        self.assertIn("?game bball:roadTeam ?targetTeam", prompt)
        self.assertIn(
            "?periodStart bball:runningHomeTeamLineup ?startingLineup", prompt
        )
        self.assertIn(
            "?periodStart bball:runningRoadTeamLineup ?startingLineup", prompt
        )
        self.assertIn("the actions may belong", prompt)
        self.assertIn("to either team", prompt)

    def test_ontology_prompt_has_team_points_during_player_lineup_pattern(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn("CANONICAL PATTERN — points scored by", prompt)
        self.assertIn("?action bball:actionTeam ?targetTeam", prompt)
        self.assertIn("?lineup bball:includesPlayer ?player", prompt)
        self.assertIn(
            "SELECT ?game ?targetTeam ?player (SUM(xsd:integer(?subPoints))",
            prompt,
        )
        self.assertIn("?subLineup bball:includesPlayer ?player", prompt)
        self.assertIn("GROUP BY ?game ?targetTeam ?player", prompt)
        self.assertIn("regex filter is mandatory for both ?targetTeamName", prompt)
        self.assertIn("never introduce ?subTargetTeam or ?subPlayer", prompt)
        self.assertIn("creates a Cartesian product", prompt)
        self.assertIn("?actionTeam = ?game/bball:homeTeam", prompt)
        self.assertIn("Dummy triples", prompt)
        self.assertIn("After a semicolon", prompt)

    def test_ontology_prompt_documents_real_shot_zone_codes(self):
        prompt = backend_app.euroleague_system_prompt
        self.assertIn('A/B/C = close range and paint', prompt)
        self.assertIn('FILTER(?shotZone IN ("A", "B", "C"))', prompt)
        self.assertIn("?shotX <= -600 && ?shotY <= 175", prompt)

    def test_openai_request_uses_responses_api_without_storing_response(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "output_text": "SELECT * WHERE {}",
                "usage": {
                    "input_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 25},
                    "output_tokens": 30,
                    "output_tokens_details": {"reasoning_tokens": 10},
                    "total_tokens": 130,
                },
            },
        )
        with (
            patch.object(backend_app, "OPENAI_API_KEY", "test-key"),
            patch.object(backend_app.requests, "post", return_value=response) as post,
        ):
            text, usage = backend_app.request_openai_text(
                "question", "instructions", "gpt-5-mini"
            )

        self.assertEqual(text, "SELECT * WHERE {}")
        self.assertEqual(
            usage,
            {
                "input_tokens": 100,
                "cached_input_tokens": 25,
                "output_tokens": 30,
                "reasoning_tokens": 10,
                "total_tokens": 130,
            },
        )
        request = post.call_args.kwargs
        self.assertEqual(request["json"]["model"], "gpt-5-mini")
        self.assertFalse(request["json"]["store"])
        self.assertEqual(request["json"]["reasoning"], {"effort": "minimal"})
        self.assertEqual(request["json"]["text"], {"verbosity": "low"})
        self.assertEqual(
            request["json"]["max_output_tokens"],
            backend_app.OPENAI_MAX_OUTPUT_TOKENS,
        )
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-key")

    def test_gemini_usage_includes_visible_output_and_thought_tokens(self):
        response = SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=120,
                cached_content_token_count=20,
                candidates_token_count=40,
                thoughts_token_count=15,
                total_token_count=175,
            )
        )

        self.assertEqual(
            backend_app.extract_gemini_usage(response),
            {
                "input_tokens": 120,
                "cached_input_tokens": 20,
                "output_tokens": 55,
                "reasoning_tokens": 15,
                "total_tokens": 175,
            },
        )

    def test_openai_empty_response_reports_incomplete_reason_and_usage(self):
        payload = {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {
                "output_tokens": 2000,
                "output_tokens_details": {"reasoning_tokens": 2000},
            },
            "output": [{"type": "reasoning"}],
        }

        with self.assertRaisesRegex(
            ValueError,
            r"status=incomplete.*reason=max_output_tokens.*reasoning_tokens=2000",
        ):
            backend_app.extract_openai_output_text(payload)

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

    def test_period_start_metadata_uses_first_clock_within_twelve_seconds(self):
        with (
            patch.object(
                backend_app,
                "get_video_game_config",
                return_value={"timeline_file": "synthetic.csv"},
            ),
            patch.object(
                backend_app,
                "load_video_timeline_index",
                return_value={"2nd": ((588.0,), (1200.0,))},
            ),
        ):
            strict = backend_app.find_video_seconds("10:00", "2nd", "E2023", "39")
            period_start = backend_app.find_video_seconds(
                "10:00", "2nd", "E2023", "39", action_type="PeriodStart"
            )

        self.assertEqual(strict, 0)
        self.assertEqual(period_start, 1200.0)

    def test_opening_jump_ball_uses_period_start_tolerance(self):
        with (
            patch.object(
                backend_app,
                "get_video_game_config",
                return_value={"timeline_file": "synthetic.csv"},
            ),
            patch.object(
                backend_app,
                "load_video_timeline_index",
                return_value={"1st": ((588.0,), (900.0,))},
            ),
        ):
            strict = backend_app.find_video_seconds("09:59", "1st", "E2024", "301")
            jump_ball = backend_app.find_video_seconds(
                "09:59", "1st", "E2024", "301", action_type="JumpBall"
            )

        self.assertEqual(strict, 0)
        self.assertEqual(jump_ball, 900.0)

    def test_assist_uses_the_linked_made_shot_clock(self):
        row = {
            "relatedShotClock": {"value": "08:54"},
            "relatedShotQuarter": {"value": "1st"},
        }

        self.assertEqual(
            backend_app.video_sync_clock_for_action(
                "Assist", row, "08:52", "1st"
            ),
            ("08:54", "1st"),
        )

    def test_assist_clock_falls_back_when_the_link_is_missing(self):
        self.assertEqual(
            backend_app.video_sync_clock_for_action(
                "Assist", {}, "08:52", "1st"
            ),
            ("08:52", "1st"),
        )

    def test_assist_gets_more_context_without_changing_other_actions(self):
        config = {"playback_lead_seconds": 5}

        self.assertEqual(backend_app.playback_lead_for_action(config, "Assist"), 9)
        self.assertEqual(
            backend_app.playback_lead_for_action(config, "TwoPointShotMade"), 5
        )

    def test_playbyplay_query_fetches_the_shot_linked_to_an_assist(self):
        query = backend_app.get_match_playbyplay_query("333", "E2023")

        self.assertIn("?relatedShot bball:hasAssist ?action", query)
        self.assertIn("bball:TwoPointShotMade", query)
        self.assertIn("bball:ThreePointShotMade", query)
        self.assertIn("bball:FreeThrowMade", query)
        self.assertIn("ABS(xsd:decimal(?relatedShotSeconds)", query)
        self.assertIn("?relatedShotClock", query)
        self.assertIn("?relatedShotQuarter", query)

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

    def test_ai_prompt_supports_fiba_free_throw_assists(self):
        self.assertIn(
            "VALUES ?madeShotType { bball:TwoPointShotMade bball:ThreePointShotMade bball:FreeThrowMade }",
            backend_app.euroleague_system_prompt,
        )
        self.assertIn(
            "bball:FreeThrowMade may have an assist",
            backend_app.euroleague_system_prompt,
        )

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
        self.assertIn("percentage or average", prompt)
        self.assertIn("DISTINCT ?action", prompt)

    def test_ai_prompt_uses_request_context_instead_of_one_fixed_game(self):
        prompt = backend_app.euroleague_system_prompt

        self.assertIn("Required request context", prompt)
        self.assertNotIn('bball:hasCode "333"', prompt)
        self.assertNotIn('bball:hasCode "E2023"', prompt)
        self.assertNotIn("Sloukas", prompt)
        self.assertNotIn("Nunn", prompt)

    def test_ai_scope_context_omits_unselected_game(self):
        context = backend_app.build_ai_scope_context("E2024", None)

        self.assertEqual(len(context), 1)
        self.assertIn('bball:hasCode "E2024"', context[0])
        self.assertNotIn("None", " ".join(context))

    def test_ai_scope_context_uses_filter_in_for_multiple_seasons(self):
        context = backend_app.build_ai_scope_context(
            "E2023,E2024,E2025",
            None,
        )

        self.assertEqual(len(context), 1)
        self.assertIn(
            'FILTER(?seasonCode IN ("E2023", "E2024", "E2025"))',
            context[0],
        )

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
        self.assertIn("bball:TwoPointShotMade", query)
        self.assertIn("bball:ThreePointShotMade", query)
        self.assertIn("bball:FreeThrowMade", query)

    def test_assist_resolution_query_requires_at_least_one_safe_uri(self):
        self.assertIsNone(backend_app.build_assist_action_resolution_query(["invalid", ""] ))


if __name__ == "__main__":
    unittest.main()
