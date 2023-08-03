import os
import pytest

from ayon_api.graphql import GraphQlQuery
from ayon_api.graphql_queries import (
    project_graphql_query,
    folders_graphql_query,
)


@pytest.fixture
def empty_query():
    return GraphQlQuery("ProjectQuery")

@pytest.fixture
def project_query():
    return project_graphql_query(["name"])

@pytest.fixture
def folder_query():
    return folders_graphql_query(["name"])


def test_simple_duplicate_add_variable_exception(empty_query):
    key, value_type, value = "projectName", "[String!]", "kuba_v4_sync"
    empty_query.add_variable(key, value_type, value)
    with pytest.raises(KeyError):
        empty_query.add_variable(key, value_type)


def test_exception_empty_query(empty_query):
    with pytest.raises(ValueError, match="Missing fields to query"):
        out = empty_query.calculate_query()


def test_simple_output(project_query):
    result = project_query.calculate_query()
    expected = "query ProjectQuery {\n  project {\n    name\n  }\n}"
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


def make_expected_get_variables_values(keys, values):
    expected = {}
    for i in range(len(keys)):
        expected[keys[i]] = values[i]
    return expected


@pytest.mark.parametrize(
    "keys, values, types",
    [
        (["projectName", "projectId", "numOf"], 
         ["kuba_v4_sync", "0x23", 3], 
         ["[String!]", "[String!]", "Int"]),
        (["projectName", "testStrInt"],
         ["my_name", 42],
         ["[String!]", "[String!]"]),
        (["projectName", "testIntStr"],
         ["my_name", "test_123"],
         ["[String!]", "Int"]),
    ])
def test_get_variables_values(keys, values, types):
    query = make_project_query(keys, values, types)
    # None means: unexpected exception thrown while adding variables
    assert query != None

    expected = make_expected_get_variables_values(keys, values)
    assert query.get_variables_values() == expected


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
