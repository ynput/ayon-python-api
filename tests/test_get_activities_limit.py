"""Limit of 'get_activities' must be applied on nested 'activities' field.

Does not require running AYON server.
"""
import pytest

from ayon_api.server_api import ServerAPI
from ayon_api.utils import SortOrder

from .graphql_fake_server import FakeServer, parse_query

PROJECT_NAME = "proj"
ACTIVITIES_COUNT = 700


@pytest.fixture
def server():
    data = {
        "project": {
            "activities": [
                {"activityId": f"a{idx}"}
                for idx in range(ACTIVITIES_COUNT)
            ],
        },
    }
    # AYON server returns edges of a page queried with 'last' from newest
    return FakeServer(data, max_page_size=300, reverse_last_pages=True)


@pytest.fixture
def con(monkeypatch, server):
    con = ServerAPI("http://localhost:0", create_session=False)
    monkeypatch.setattr(con, "query_graphql", server.query_graphql)
    return con


def _activities_args(server):
    """Arguments of 'activities' field for each sent query."""
    output = []
    for query_str, variables in server.calls:
        root = parse_query(query_str, variables)
        output.append(root.child("project").child("activities").args)
    return output


@pytest.mark.parametrize(
    "order, limit_key, expected_idxs",
    [
        (None, "first", range(5)),
        (SortOrder.ascending, "first", range(5)),
        (
            SortOrder.descending,
            "last",
            reversed(range(ACTIVITIES_COUNT - 5, ACTIVITIES_COUNT)),
        ),
    ],
)
def test_limit_is_applied_on_activities_field(
    con, server, order, limit_key, expected_idxs
):
    activities = list(con.get_activities(
        PROJECT_NAME, fields={"activityId"}, limit=5, order=order
    ))

    assert [activity["activityId"] for activity in activities] == [
        f"a{idx}" for idx in expected_idxs
    ]
    assert len(server.queries) == 1
    assert _activities_args(server)[0][limit_key] == 5


@pytest.mark.parametrize(
    "order, limit_key",
    [
        (SortOrder.ascending, "first"),
        (SortOrder.descending, "last"),
    ],
)
def test_limit_over_multiple_pages(con, server, order, limit_key):
    limit = 450
    activities = list(con.get_activities(
        PROJECT_NAME, fields={"activityId"}, limit=limit, order=order
    ))

    idxs = range(ACTIVITIES_COUNT)
    if order == SortOrder.descending:
        idxs = reversed(idxs)
    assert [activity["activityId"] for activity in activities] == [
        f"a{idx}" for idx in list(idxs)[:limit]
    ]
    # Second page asks only for the remaining items
    assert [
        args[limit_key] for args in _activities_args(server)
    ] == [300, 150]


def test_without_limit_returns_all_activities(con, server):
    activities = list(con.get_activities(PROJECT_NAME, fields={"activityId"}))

    assert len(activities) == ACTIVITIES_COUNT
    assert len(server.queries) == 3
