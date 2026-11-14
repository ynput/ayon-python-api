"""Filtering of 'get_entity_lists' by labels.

Does not require running AYON server.
"""
import json

import pytest

from ayon_api.server_api import ServerAPI

from .graphql_fake_server import FakeServer, parse_query

PROJECT_NAME = "proj"
LABELS = ["a", "b", "c", "d"]


@pytest.fixture
def server():
    data = {
        "project": {
            "entityLists": [
                {"id": f"l{idx}", "label": label}
                for idx, label in enumerate(LABELS)
            ],
        },
    }
    return FakeServer(data)


def _create_con(monkeypatch, server, server_version):
    con = ServerAPI("http://localhost:0", create_session=False)
    monkeypatch.setattr(con, "query_graphql", server.query_graphql)
    monkeypatch.setattr(
        con, "get_server_version_tuple", lambda: (*server_version, "", "")
    )
    return con


def _entity_lists_args(server):
    """Arguments of 'entityLists' field for each sent query."""
    output = []
    for query_str, variables in server.calls:
        root = parse_query(query_str, variables)
        output.append(root.child("project").child("entityLists").args)
    return output


def test_labels_filter_is_sent_to_server(monkeypatch, server):
    con = _create_con(monkeypatch, server, (1, 8, 3))

    list(con.get_entity_lists(
        PROJECT_NAME, labels=["b", "c"], fields={"id"}
    ))

    args = _entity_lists_args(server)
    assert len(args) == 1
    query_filter = json.loads(args[0]["filter"])
    assert query_filter["conditions"][0]["key"] == "label"
    assert query_filter["conditions"][0]["operator"] == "in"
    assert set(query_filter["conditions"][0]["value"]) == {"b", "c"}


def test_labels_filter_on_client_for_old_server(monkeypatch, server):
    con = _create_con(monkeypatch, server, (1, 8, 2))

    entity_lists = list(con.get_entity_lists(
        PROJECT_NAME, labels=["b", "c"], fields={"id"}
    ))

    assert [entity_list["id"] for entity_list in entity_lists] == [
        "l1", "l2"
    ]
    assert "filter" not in _entity_lists_args(server)[0]


@pytest.mark.parametrize("server_version", [(1, 8, 2), (1, 8, 3)])
def test_empty_labels_return_nothing(monkeypatch, server, server_version):
    con = _create_con(monkeypatch, server, server_version)

    assert list(con.get_entity_lists(
        PROJECT_NAME, labels=[], fields={"id"}
    )) == []
    assert not server.calls


def test_no_labels_does_not_filter(monkeypatch, server):
    con = _create_con(monkeypatch, server, (1, 8, 3))

    entity_lists = list(con.get_entity_lists(PROJECT_NAME, fields={"id"}))

    assert len(entity_lists) == len(LABELS)
    assert "filter" not in _entity_lists_args(server)[0]
