"""Unexpected GraphQl responses must not cause infinite loop.

Does not require running AYON server.
"""
import pytest

from ayon_api.exceptions import GraphQlQueryError
from ayon_api.graphql_queries import events_graphql_query
from ayon_api.utils import SortOrder

from .graphql_fake_server import FakeResponse


class _ScriptedServer:
    """Return prepared responses, fail if queried too many times."""
    def __init__(self, responses):
        self._responses = responses
        self.queries = []

    def query_graphql(self, query_str, variables):
        self.queries.append(query_str)
        if len(self.queries) > 10:
            raise RuntimeError("Infinite query loop")
        idx = min(len(self.queries), len(self._responses)) - 1
        return FakeResponse(self._responses[idx])


def test_null_data_raises_instead_of_infinite_loop():
    server = _ScriptedServer([{"data": None}])
    query = events_graphql_query({"id"}, SortOrder.ascending)
    with pytest.raises(GraphQlQueryError, match="does not contain 'data'"):
        query.query(server)


def test_missing_cursor_stops_pagination():
    def page(ids, end_cursor):
        return {"data": {"events": {
            "edges": [{"node": {"id": id_}} for id_ in ids],
            "pageInfo": {"endCursor": end_cursor, "hasNextPage": True},
        }}}

    server = _ScriptedServer([page(["e0"], "c0"), page([], None)])
    query = events_graphql_query({"id"}, SortOrder.ascending)

    assert query.query(server) == {"events": [{"id": "e0"}]}
    assert len(server.queries) == 2
