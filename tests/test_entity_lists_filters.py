"""Advanced filters of 'get_entity_lists' are sent to server.

Does not require running AYON server.
"""
import json

import pytest

from ayon_api.server_api import ServerAPI

from .graphql_fake_server import FakeServer, parse_query

PROJECT_NAME = "proj"


@pytest.fixture
def server():
    data = {
        "project": {
            "entityLists": [
                {"id": f"l{idx}", "label": f"list {idx}"}
                for idx in range(3)
            ],
        },
    }
    return FakeServer(data)


@pytest.fixture
def con(monkeypatch, server):
    con = ServerAPI("http://localhost:0", create_session=False)
    monkeypatch.setattr(con, "query_graphql", server.query_graphql)
    return con


def _entity_lists_args(server):
    """Arguments of 'entityLists' field for each sent query."""
    output = []
    for query_str, variables in server.calls:
        root = parse_query(query_str, variables)
        output.append(root.child("project").child("entityLists").args)
    return output


def test_filters_are_sent_to_server(con, server):
    filters = {
        "conditions": [
            {"key": "label", "operator": "in", "value": ["list 1"]},
        ],
    }

    list(con.get_entity_lists(PROJECT_NAME, filters=filters, fields={"id"}))

    args = _entity_lists_args(server)
    assert len(args) == 1
    assert json.loads(args[0]["filter"]) == filters


def test_no_filters_are_not_sent_to_server(con, server):
    entity_lists = list(con.get_entity_lists(PROJECT_NAME, fields={"id"}))

    assert len(entity_lists) == 3
    assert "filter" not in _entity_lists_args(server)[0]
