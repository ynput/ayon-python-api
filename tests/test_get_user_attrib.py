"""'get_user' fills default attribute values only if 'fill_attrib' is 'True'.

Does not require running AYON server.
"""
import pytest

from ayon_api.server_api import ServerAPI
from ayon_api.utils import RestApiResponse


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        pass


@pytest.fixture
def con(monkeypatch):
    con = ServerAPI("http://localhost:0", create_session=False)
    requested = []

    def get(entrypoint, **kwargs):
        requested.append(entrypoint)
        return RestApiResponse(FakeResponse(), {
            "name": "artist",
            "attrib": {"email": "artist@example.com"},
            "ownAttrib": ["email"],
        })

    def get_attributes_for_type(entity_type):
        requested.append(f"attributes/{entity_type}")
        return {
            "email": {"default": None},
            "fullName": {"default": ""},
        }

    monkeypatch.setattr(con, "get", get)
    monkeypatch.setattr(
        con, "get_attributes_for_type", get_attributes_for_type
    )
    con.requested = requested
    return con


def test_get_user_fills_default_attributes(con):
    user = con.get_user("artist")
    assert con.requested == ["users/artist", "attributes/user"]
    assert user["attrib"] == {
        "email": "artist@example.com",
        "fullName": "",
    }


def test_get_user_without_attributes(con):
    user = con.get_user("artist", fill_attrib=False)
    assert con.requested == ["users/artist"]
    assert user["name"] == "artist"
    assert user["attrib"] == {"email": "artist@example.com"}
    assert "own_attributes" not in user


def test_get_user_without_attributes_own_attributes(con):
    user = con.get_user("artist", own_attributes=True, fill_attrib=False)
    assert con.requested == ["users/artist"]
    assert user["own_attributes"] == {"email": "artist@example.com"}
