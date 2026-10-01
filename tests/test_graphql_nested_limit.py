"""Limit of nested edge field is applied per parent item.

Does not require running AYON server.
"""
from ayon_api.graphql_queries import versions_graphql_query

from .graphql_fake_server import FakeServer


def test_nested_field_limit_is_per_parent():
    data = {"project": {"name": "proj", "versions": [
        {"id": f"v{idx}", "links": [{"id": f"v{idx}-l{n}"} for n in range(5)]}
        for idx in range(3)
    ]}}
    query = versions_graphql_query({"id", "links.id"})
    query.set_variable_value("projectName", "proj")
    query.get_field_by_path("project/versions/links").set_limit(2)
    server = FakeServer(data)

    output = query.query(server)

    for version in output["project"]["versions"]:
        assert len(version["links"]) == 2
    for query_str in server.queries:
        assert "first: 0" not in query_str
        assert "first: -" not in query_str
