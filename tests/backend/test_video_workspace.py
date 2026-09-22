import unittest
from unittest.mock import AsyncMock, patch

from src.backend import app as backend
from src.backend.search_validation import bounded_editor_query


class QueryEditorTests(unittest.IsolatedAsyncioTestCase):
    async def test_editor_rejects_writes_and_remote_sources_before_database_access(self):
        for query in (
            "DELETE WHERE { ?s ?p ?o }",
            "SELECT * WHERE { SERVICE <https://example.org> { ?s ?p ?o } }",
            "SELECT * FROM <https://example.org/data> WHERE { ?s ?p ?o }",
            "DEFINE sql:signal-void-variables 1 SELECT * WHERE { ?s ?p ?o }",
        ):
            with (
                self.subTest(query=query),
                patch.object(backend, "query_sparql", AsyncMock()) as db,
            ):
                with self.assertRaises(backend.HTTPException) as caught:
                    await backend.run_editor_query(backend.SparqlRequest(query=query))
                self.assertEqual(caught.exception.status_code, 422)
                db.assert_not_called()

    def test_outer_limit_applies_even_with_nested_or_excessive_limits(self):
        for query in (
            "SELECT ?s WHERE { ?s ?p ?o } LIMIT 999999",
            "PREFIX b: <https://example.org/> SELECT ?s WHERE { { SELECT ?s WHERE { ?s b:p ?o } LIMIT 1 } }",
        ):
            limited = bounded_editor_query(query)
            self.assertTrue(limited.endswith("} } LIMIT 200"))
            self.assertIn("SELECT * WHERE { {", limited)
        self.assertEqual(bounded_editor_query("ASK { ?s ?p ?o }"), "ASK { ?s ?p ?o }")

    async def test_editor_returns_action_matches_and_preserves_boolean_answers(self):
        action = "http://www.ics.forth.gr/isl/Basketball#Action_E2023_333_10"
        rows = [{"action": {"type": "uri", "value": action}}]
        with patch.object(
            backend, "query_sparql", AsyncMock(return_value={"results": {"bindings": rows}})
        ):
            result = await backend.run_editor_query(
                backend.SparqlRequest(query="SELECT ?action WHERE { ?action ?p ?o }")
            )
        self.assertTrue(result["playbyplay_filter"])
        self.assertEqual(result["action_uris"], [action])
        with patch.object(backend, "query_sparql", AsyncMock(return_value={"boolean": False})):
            result = await backend.run_editor_query(backend.SparqlRequest(query="ASK { ?s ?p ?o }"))
        self.assertIs(result["boolean"], False)
        self.assertFalse(result["playbyplay_filter"])

    async def test_non_shot_actions_include_both_recorded_lineups(self):
        row = {
            key: {"value": value}
            for key, value in {
                "action": "urn:action:1",
                "actionType": "urn:test#FoulDrawn",
                "clock": "08:00",
                "quarter": "1st",
                "playerLabel": "LESSORT, MATHIAS",
                "homeLineup": "urn:test#Lineup_A_B_C_D_E",
                "roadLineup": "urn:test#Lineup_F_G_H_I_J",
            }.items()
        }
        with patch.object(
            backend, "analysis_data", AsyncMock(return_value={"results": {"bindings": [row]}})
        ) as db:
            result = await backend.get_match_pbp("333", "E2023")
        action = result["actions"][0]
        self.assertEqual(action["homeLineup"], row["homeLineup"]["value"])
        self.assertEqual(action["roadLineup"], row["roadLineup"]["value"])
        self.assertIn("bball:runningHomeTeamLineup ?homeLineup", db.call_args.args[0])

    async def test_query_display_keeps_normal_search_errors_and_cached_results(self):
        request = backend.ChatRequest(
            message="Shots by Lessort while Tavares is on court",
            game_code="333",
            season_code="E2023",
            show_query=True,
            workspace="video",
        )
        payload = {"results": [], "sparql_query": "SELECT ?action WHERE {} LIMIT 200"}
        with (
            patch.object(
                backend, "ai_search_configuration", return_value=("openai", "ontology", "test")
            ),
            patch.object(backend, "_get_cached_ai_search", return_value=payload),
            patch.object(backend, "generate_ai_search_text", AsyncMock()) as generate,
        ):
            result = await backend.ai_chat_handler(request)
        self.assertEqual(result["sparql_query"], payload["sparql_query"])
        generate.assert_not_called()
        with (
            patch.object(
                backend, "ai_search_configuration", return_value=("openai", "ontology", "test")
            ),
            patch.object(backend, "_get_cached_ai_search", return_value=None),
            patch.object(
                backend, "generate_ai_search_text", AsyncMock(return_value=("WITH invalid", {}))
            ) as generate,
        ):
            with self.assertRaises(backend.HTTPException) as caught:
                await backend.ai_chat_handler(request)
        self.assertEqual(generate.await_count, 2)
        self.assertNotIn("SPARQL", caught.exception.detail)
        self.assertIn("rephrasing", caught.exception.detail)
