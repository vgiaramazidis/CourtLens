"""Configuration and error handling at the database transport boundary."""

import unittest
from unittest.mock import Mock, patch

import httpx
import requests

from src.backend import app as backend
from src.backend import database


class DatabaseConfigurationTests(unittest.TestCase):
    def test_query_uses_configured_endpoint_without_changing_request_contract(self):
        payload = {"results": {"bindings": []}}
        response = Mock()
        response.json.return_value = payload
        with (
            patch.dict("os.environ", {"SPARQL_ENDPOINT": "https://db.example.test/query"}),
            patch.object(database.requests, "get", return_value=response) as get,
        ):
            result = database.query_sparql_requests("SELECT * WHERE {}")
        self.assertEqual(result, payload)
        get.assert_called_once_with(
            "https://db.example.test/query",
            params={"query": "SELECT * WHERE {}", "format": "application/sparql-results+json"},
            timeout=30,
        )
        response.raise_for_status.assert_called_once()

    def test_failures_do_not_log_deployment_addresses_or_credentials(self):
        failure = requests.ConnectionError("https://user:private-password@db.example.test/query")
        with (
            patch.object(database.requests, "get", side_effect=failure),
            self.assertLogs(database.logger, level="WARNING") as logs,
        ):
            self.assertIsNone(database.query_sparql_requests("SELECT * WHERE {}"))
        self.assertIn("ConnectionError", logs.output[0])
        self.assertNotIn("private-password", logs.output[0])
        self.assertNotIn("db.example.test", logs.output[0])


class BackendPackageTests(unittest.IsolatedAsyncioTestCase):
    async def test_package_entry_point_serves_catalog_without_live_services(self):
        transport = httpx.ASGITransport(app=backend.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/video/games")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["games"])
        self.assertTrue(all(game["game_code"] for game in response.json()["games"]))


if __name__ == "__main__":
    unittest.main()
