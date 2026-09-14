"""Descending GraphQl pagination must not return duplicates.

Does not require running AYON server.
"""
from ayon_api.graphql_queries import events_graphql_query
from ayon_api.utils import SortOrder

from .graphql_fake_server import FakeServer


def test_descending_pagination_has_no_duplicates():
    data = {"events": [{"id": f"e{idx}"} for idx in range(700)]}
    query = events_graphql_query({"id"}, SortOrder.descending)
    # AYON server returns edges of a page queried with 'last' from newest
    server = FakeServer(data, max_page_size=300, reverse_last_pages=True)

    output = query.query(server)

    ids = [event["id"] for event in output["events"]]
    assert ids == [f"e{idx}" for idx in reversed(range(700))]
    assert len(server.queries) == 3
