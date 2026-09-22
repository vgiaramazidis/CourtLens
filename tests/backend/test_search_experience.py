"""Regression coverage for source-based answers and manual report correctness."""

import unittest
from unittest.mock import AsyncMock, patch

from src.backend import app as backend
from src.backend import queries
from src.backend.search_answers import (
    action_answer,
    evidence_for_answer,
    profile_answer,
    profile_query,
    profile_subject,
)


class QueryFilterTests(unittest.TestCase):
    def test_all_reports_share_scope_period_and_clock(self):
        for builder in (
            queries.get_filtered_shots_query,
            queries.get_top_assist_duos_query,
            queries.get_second_chance_points_query,
            queries.get_top_lineups_query,
            queries.get_foul_drawn_gravity_query,
            queries.get_defensive_anchors_query,
        ):
            with self.subTest(builder=builder.__name__):
                query = builder(
                    season_code="E2023",
                    game_code="333",
                    quarter="4th",
                    min_start="5",
                    min_end="0",
                    filter_type="on_court",
                    filter_id="Kostas Sloukas",
                )
                for fragment in (
                    '"E2023"',
                    '"333"',
                    '"4th"',
                    "<= 300",
                    ">= 0",
                    '"Kostas"',
                    '"Sloukas"',
                    "PREFIX rdfs:",
                    "FILTER EXISTS",
                ):
                    self.assertIn(fragment, query)
                self.assertNotIn("\\b", query)

    def test_invalid_scope_and_clock_are_rejected(self):
        for params in (
            {"game_code": "333"},
            {"season_code": "E2023' . }"},
            {"min_start": "0", "min_end": "5"},
            {"min_start": "5"},
            {"min_start": "x", "min_end": "0"},
            {"quarter": "OT", "min_start": "10", "min_end": "0"},
            {"filter_type": "on_court"},
            {"filter_type": "referee", "filter_id": "bad> uri"},
        ):
            with self.subTest(params=params), self.assertRaises(queries.AnalysisFilterError):
                queries.get_filtered_shots_query(**params)

    def test_names_and_alphanumeric_ids_are_both_supported(self):
        for name in ("Sloukas", "Kostas Sloukas", "001926", "TGB", "O'Bryant"):
            query = queries.get_foul_drawn_gravity_query(fouled_id=name, fouling_id=name)
            self.assertIn(queries.literal(queries.PLAYER_BASE + name), query)
            self.assertIn("occuredByFoul/bball:actionPlayer", query)

    def test_missing_locations_are_preserved_and_results_are_ordered(self):
        query = queries.get_filtered_shots_query()
        self.assertIn("OPTIONAL { ?action bball:shotCoords ?coords . }", query)
        self.assertIn("ORDER BY ?action LIMIT 500", query)

    def test_points_aggregate_unique_actions_not_distinct_point_values(self):
        query = queries.get_second_chance_points_query()
        self.assertIn("SELECT DISTINCT ?player ?action ?points", query)
        self.assertNotIn("SUM(DISTINCT", query)

    def test_all_seasons_does_not_become_a_literal_season(self):
        self.assertNotIn('"ALL"', queries.get_top_lineups_query(season_code="ALL"))
        self.assertIn('"E2023", "E2024"', queries.get_top_lineups_query(season_code="E2023,E2024"))

    def test_lineup_drilldown_rejects_untrusted_uris(self):
        with self.assertRaises(queries.AnalysisFilterError):
            queries.get_filtered_shots_query(
                lineup_uri="https://bad.test/> } SERVICE <http://bad.test>"
            )


class ProfileTests(unittest.TestCase):
    def test_profile_question_variants(self):
        for question in (
            "Who is Sloukas?",
            "Tell me about Sloukas",
            "I want some info for Sloukas",
            "Biography of Sloukas",
            "Give me information about Sloukas",
        ):
            self.assertEqual(profile_subject(question), "Sloukas")
        for question in (
            "Who scored the most points?",
            "Who is the best player?",
            "Tell me about Sloukas shots",
            "Show Sloukas assists",
        ):
            self.assertIsNone(profile_subject(question))

    def test_profile_query_escapes_names_and_has_no_game_filter(self):
        query = profile_query("Kostas Sloukas")
        self.assertIn('"Kostas"', query)
        self.assertIn('"Sloukas"', query)
        self.assertNotIn("hasSeason", query)

    def test_profile_does_not_invent_missing_biography(self):
        answer = profile_answer([{"name": {"value": "Test Player"}}], "Test")
        self.assertIn("limited biographical information", answer["profiles"][0]["paragraphs"][1])
        self.assertEqual(answer["profiles"][0]["source_url"], "")

    def test_profile_removes_stale_current_club_statement_and_separates_sentences(self):
        answer = profile_answer(
            [
                {
                    "name": {"value": "Test Player"},
                    "bio": {"value": "Signed in 2020.He's still playing there.Won a title."},
                }
            ],
            "Test",
        )
        paragraph = answer["profiles"][0]["paragraphs"][1]
        self.assertNotIn("still playing", paragraph)
        self.assertIn("2020. ", paragraph)

    def test_ambiguous_names_keep_separate_profiles(self):
        answer = profile_answer(
            [{"name": {"value": "Alex One"}}, {"name": {"value": "Alex Two"}}], "Alex"
        )
        self.assertEqual(len(answer["profiles"]), 2)

    def test_answer_evidence_is_bounded_and_marks_sampling(self):
        evidence = evidence_for_answer(
            [{"name": {"value": "a" * 4000}}] * 20,
            None,
            backend.ChatRequest(message="Compare players"),
        )
        self.assertTrue(evidence["sample_only"])
        self.assertEqual(len(evidence["sample_rows"]), 15)
        self.assertEqual(len(evidence["sample_rows"][0]["name"]), 2500)


class ActionAnswerTests(unittest.TestCase):
    def test_four_verified_threes_cannot_become_two_in_the_answer(self):
        actions = [
            {
                "uri": str(i),
                "playerName": "Kostas Sloukas",
                "action_type": "ThreePointShotMade",
                "quarter": q,
            }
            for i, q in enumerate(["1st", "3rd", "4th", "4th"])
        ]
        answer = action_answer(
            actions + actions,
            ["0", "1", "2", "3"],
            backend.ChatRequest(message="Show made threes", season_code="E2023", game_code="333"),
        )
        self.assertEqual(answer["matched_count"], 4)
        self.assertIn("4 made three-pointers", answer["paragraphs"][0])
        self.assertIn("12 points", answer["paragraphs"][0])
        self.assertIn("2 in the fourth quarter", answer["paragraphs"][1])

    def test_unmatched_actions_are_not_invented(self):
        answer = action_answer([], ["missing"], backend.ChatRequest(message="Show plays"))
        self.assertEqual(answer["matched_count"], 0)
        self.assertIn("could not be matched", answer["paragraphs"][-1])

    def test_provider_outage_is_not_an_internal_server_error(self):
        error = backend.quiz_generation_error(RuntimeError("503 UNAVAILABLE private diagnostic"))
        self.assertEqual(error.status_code, 503)
        self.assertNotIn("private diagnostic", error.detail)


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_works_without_ai_provider_and_is_not_game_scoped(self):
        with (
            patch.object(
                backend,
                "query_sparql",
                AsyncMock(
                    return_value={"results": {"bindings": [{"name": {"value": "Kostas Sloukas"}}]}}
                ),
            ) as query,
            patch.object(
                backend,
                "ai_search_configuration",
                side_effect=AssertionError("Profile must not need an AI key"),
            ),
        ):
            result = await backend.ai_chat_handler(
                backend.ChatRequest(
                    message="Who is Sloukas?",
                    include_answer=True,
                    season_code="E2023",
                    game_code="333",
                )
            )
        self.assertEqual(result["answer"]["kind"], "profile")
        self.assertNotIn("sparql_query", result)
        self.assertNotIn("hasSeason", query.call_args.args[0])

    async def test_database_failure_does_not_look_like_empty_results(self):
        with patch.object(backend, "query_sparql", AsyncMock(return_value=None)):
            with self.assertRaises(backend.HTTPException) as error:
                await backend.analysis_data("SELECT")
        self.assertEqual(error.exception.status_code, 502)

    async def test_empty_roster_does_not_crash(self):
        with patch.object(
            backend, "query_sparql", AsyncMock(return_value={"results": {"bindings": []}})
        ):
            result = await backend.get_game_lineups("999999", "E2023")
        self.assertEqual(result["lineups"], [])

    async def test_bad_and_missing_coordinates_use_unmapped_sentinel(self):
        data = {
            "results": {
                "bindings": [
                    {"coords": {"value": value}, "action_type": {"value": "#TwoPointShotMade"}}
                    for value in ("", "nan,0", "bad", "1,2,3")
                ]
            }
        }
        with patch.object(backend, "query_sparql", AsyncMock(return_value=data)):
            result = await backend.get_shots(
                game_code="333",
                season_code="E2023",
                player=None,
                assist_by=None,
                lineup_uri=None,
                filter_type=None,
                filter_id=None,
                quarter=None,
                min_start=None,
                min_end=None,
            )
        self.assertTrue(all(shot["x"] == -1 and shot["y"] == -1 for shot in result["shots"]))

    async def test_answer_provider_failure_preserves_query_results(self):
        with patch.object(backend, "request_openai_text", side_effect=RuntimeError("unavailable")):
            result = await backend.readable_answer(
                backend.ChatRequest(message="points?"),
                "openai",
                "test",
                [{"points": {"value": "4"}}],
                None,
            )
        self.assertIsNone(result)

    async def test_video_profile_wording_does_not_bypass_action_search(self):
        with patch.object(
            backend, "ai_search_configuration", side_effect=ValueError("expected provider route")
        ):
            with self.assertRaises(backend.HTTPException) as error:
                await backend.ai_chat_handler(
                    backend.ChatRequest(
                        message="Who is Sloukas?", include_answer=True, workspace="video"
                    )
                )
        self.assertIn("expected provider route", error.exception.detail)

    async def test_answer_uses_plain_paragraphs_and_english_validation(self):
        request = backend.ChatRequest(message="How many points?")
        with patch.object(
            backend,
            "request_openai_text",
            return_value=("The player scored 20 points.\n\nThis is the selected game.", {}),
        ):
            result = await backend.readable_answer(
                request, "openai", "test", [{"points": {"value": "20"}}], None
            )
        self.assertEqual(len(result["paragraphs"]), 2)


if __name__ == "__main__":
    unittest.main()
