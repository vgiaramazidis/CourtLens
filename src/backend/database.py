"""Configured HTTP transport for the read-only basketball data source."""

import logging
import os

import requests

logger = logging.getLogger(__name__)


def get_sparql_endpoint():
    """Keep deployment addresses outside source control."""
    return os.getenv("SPARQL_ENDPOINT", "http://127.0.0.1:8890/sparql").strip()


def query_sparql_requests(sparql_query):
    """Return SPARQL JSON, or None when the data source is unavailable."""
    try:
        response = requests.get(
            get_sparql_endpoint(),
            params={"query": sparql_query, "format": "application/sparql-results+json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        # Exception text can contain a deployment URL or embedded credentials.
        logger.warning("Basketball data request failed (%s)", type(error).__name__)
        return None
