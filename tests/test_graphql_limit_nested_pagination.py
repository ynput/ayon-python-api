"""Limit of a field with nested pagination.

Does not require running AYON server.
"""
from ayon_api.graphql_queries import versions_graphql_query

from .graphql_fake_server import FakeServer


def test_parent_limit_with_nested_pagination():
    data = {"project": {"name": "proj", "versions": [
        {
            "id": f"v{idx}",
            "links": [{"id": f"v{idx}-l{n}"} for n in range(700)],
        }
        for idx in range(5)
    ]}}
    query = versions_graphql_query({"id", "links.id"})
    query.set_variable_value("projectName", "proj")
    query.get_field_by_path("project/versions").set_limit(3)

    output = query.query(FakeServer(data, max_page_size=300))

    versions = output["project"]["versions"]
    assert [version["id"] for version in versions] == ["v0", "v1", "v2"]
    for version in versions:
        assert len(version["links"]) == 700
