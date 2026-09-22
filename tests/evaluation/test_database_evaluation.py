"""Tests for the representative SPARQL benchmark definition."""

import unittest

from tools.evaluation.database import benchmark_queries


class DatabaseEvaluationTests(unittest.TestCase):
    def test_query_set_is_unique_and_read_only(self):
        queries = benchmark_queries()
        self.assertEqual(len(queries), 10)
        self.assertEqual(len({query.name for query in queries}), len(queries))
        for query in queries:
            normalized = query.query.upper()
            self.assertTrue("SELECT" in normalized or "ASK" in normalized)
            for forbidden in ("INSERT", "DELETE", "DROP", "CLEAR", "LOAD"):
                self.assertNotIn(forbidden, normalized)


if __name__ == "__main__":
    unittest.main()
