from types import SimpleNamespace

import pytest

from ayon_api.graphql import GraphQlQuery
from ayon_api.graphql_queries import (
    project_graphql_query,
    folders_graphql_query,
    versions_graphql_query,
)

from .conftest import project_name_fixture


@pytest.fixture
def empty_query():
    return GraphQlQuery("ProjectQuery")


@pytest.fixture
def folder_query():
    return folders_graphql_query(["name"])


def test_simple_duplicate_add_variable_exception(
    project_name_fixture, empty_query
):
    key, value_type, value = "projectName", "[String!]", project_name_fixture
    empty_query.add_variable(key, value_type, value)
    with pytest.raises(KeyError):
        empty_query.add_variable(key, value_type)


def test_exception_empty_query(empty_query):
    with pytest.raises(ValueError, match="Missing fields to query"):
        _out = empty_query.calculate_query()


def test_simple_project_query():
    project_query = project_graphql_query(["name"])
    result = project_query.calculate_query()
    expected = "\n".join([
        "query ProjectQuery {",
        "  project {",
        "    name",
        "  }",
        "}"
    ])
    assert result == expected


def make_project_query(keys, values, types):
    query = project_graphql_query(["name"])

    # by default from project_graphql_query(["name"])
    inserted = {"projectName"}

    for key, entity_type, value in zip(keys, types, values):
        try:
            query.add_variable(key, entity_type, value)
        except KeyError:
            if key not in inserted:
                return None
            else:
                query.set_variable_value(key, value)

        inserted.add(key)
    return query


def make_expected_get_variables_values(keys, values):
    return dict(zip(keys, values))


@pytest.mark.parametrize(
    "keys, values, types",
    [
        (
            ["projectName", "projectId", "numOf"],
            ["my_name", "0x23", 3],
            ["[String!]", "[String!]", "Int"]
        ), (
            ["projectName", "testStrInt"],
            ["my_name", 42],
            ["[String!]", "[String!]"]
        ), (
            ["projectName", "testIntStr"],
            ["my_name", "test_123"],
            ["[String!]", "Int"]
        ),
    ]
)
def test_get_variables_values(keys, values, types):
    query = make_project_query(keys, values, types)
    # None means: unexpected exception thrown while adding variables
    assert query is not None

    expected = make_expected_get_variables_values(keys, values)
    assert query.get_variables_values() == expected


class DummyConnection:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def query_graphql(self, query_str, variables):
        self.calls.append((query_str, dict(variables)))
        response = self._responses.pop(0)
        return SimpleNamespace(errors=None, data={"data": response})


def _version_link_edges(count, prefix):
    return [
        {"id": f"{prefix}-{idx}"}
        for idx in range(count)
    ]


def test_nested_edge_pagination_queries_one_parent_at_a_time():
    query = versions_graphql_query({"id", "links.id"})
    query.set_variable_value("projectName", "test_project")

    con = DummyConnection([
        {
            "project": {
                "versions": {
                    "edges": [{
                        "cursor": "version-1",
                        "node": {
                            "id": "version-1",
                            "links": {
                                "edges": _version_link_edges(300, "link-a"),
                                "pageInfo": {
                                    "endCursor": "link-page-1",
                                    "hasNextPage": True,
                                }
                            }
                        }
                    }],
                    "pageInfo": {
                        "endCursor": "versions-page-1",
                        "hasNextPage": True,
                    }
                }
            }
        },
        {
            "project": {
                "versions": {
                    "edges": [{
                        "cursor": "version-1",
                        "node": {
                            "id": "version-1",
                            "links": {
                                "edges": _version_link_edges(1, "link-b"),
                                "pageInfo": {
                                    "endCursor": "link-page-2",
                                    "hasNextPage": False,
                                }
                            }
                        }
                    }],
                    "pageInfo": {
                        "endCursor": "versions-page-1",
                        "hasNextPage": True,
                    }
                }
            }
        },
        {
            "project": {
                "versions": {
                    "edges": [{
                        "cursor": "version-2",
                        "node": {
                            "id": "version-2",
                            "links": {
                                "edges": _version_link_edges(1, "link-c"),
                                "pageInfo": {
                                    "endCursor": "link-page-3",
                                    "hasNextPage": False,
                                }
                            }
                        }
                    }],
                    "pageInfo": {
                        "endCursor": "versions-page-2",
                        "hasNextPage": False,
                    }
                }
            }
        }
    ])

    output = query.query(con)

    versions = output["project"]["versions"]
    assert len(versions) == 2
    assert versions[0]["id"] == "version-1"
    assert len(versions[0]["links"]) == 301
    assert versions[0]["links"][0]["id"] == "link-a-0"
    assert versions[0]["links"][-1]["id"] == "link-b-0"
    assert versions[1]["id"] == "version-2"
    assert versions[1]["links"] == [{"id": "link-c-0"}]

    first_query, second_query, third_query = [
        query_str for query_str, _variables in con.calls
    ]
    assert "versions(first: 1)" in first_query
    assert 'links(first: 300)' in first_query
    assert 'links(first: 300, after: "link-page-1")' in second_query
    assert 'versions(first: 1, after: "versions-page-1")' in third_query


"""
def test_filtering(empty_query):
    assert empty_query._children == []
    project_name_var = empty_query.add_variable("projectName", "String!")
    project_field = empty_query.add_field("project")
    project_field.set_filter("name", project_name_var)

    for field in empty_query._children:
        print(field.get_filters())

    print(empty_query.calculate_query())


def print_rec_filters(field):
    print(field.get_filters())
    for k in field._children:
        print_rec_filters(k)


def test_folders_graphql_query(folder_query):
    print(folder_query.calculate_query())


def test_filters(folder_query):
    print(folder_query._children[0]._children[0].get_filters())
    folder_query._children[0]._children[0].remove_filter("ids")
    print(folder_query._children[0]._children[0].get_filters())
    print(folder_query.calculate_query())
"""
