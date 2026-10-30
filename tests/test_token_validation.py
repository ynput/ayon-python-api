"""Requests made to validate server url and token.

Does not require running AYON server.
"""
import pytest
import requests

from ayon_api import GlobalServerAPI
from ayon_api.constants import SERVER_API_ENV_KEY, SERVER_URL_ENV_KEY
from ayon_api.exceptions import ServerNotReached
from ayon_api.server_api import ServerAPI
from ayon_api.utils import get_user_info_by_token

from .fake_transfer import FakeResponse

URL = "http://localhost:0"
USER_TOKEN = "a" * 64
API_KEY = "b" * 32
LONG_API_KEY = "c" * 64


class FakeServer:
    """Answers 'users/me' and 'info' requests and records them."""
    def __init__(self, user_tokens=(), api_keys=(), is_ayon=True):
        self.user_tokens = set(user_tokens)
        self.api_keys = set(api_keys)
        self.is_ayon = is_ayon
        self.requests = []
        self.sessions = []

    def get(self, url, headers=None, **kwargs):
        headers = headers or {}
        endpoint = url[len(URL):]
        if "X-Api-Key" in headers:
            auth = "x-api-key"
            valid = headers["X-Api-Key"] in self.api_keys
        elif "Authorization" in headers:
            auth = "bearer"
            token = headers["Authorization"].split(" ", 1)[-1]
            valid = token in self.user_tokens
        else:
            auth = "none"
            valid = False
        self.requests.append((endpoint, auth))

        if not self.is_ayon:
            return FakeResponse(404)
        if endpoint == "/api/info":
            return FakeResponse(200, json_data={"version": "1.0.0"})
        if endpoint == "/api/users/me":
            if valid:
                return FakeResponse(200, json_data={"name": "user"})
            return FakeResponse(401)
        return FakeResponse(404)

    def create_session(self):
        session = FakeSession(self)
        self.sessions.append(session)
        return session


class FakeSession:
    def __init__(self, server):
        self.server = server
        self.headers = {}
        self.cert = None
        self.verify = True
        self.closed = False

    def get(self, url, **kwargs):
        return self.server.get(url, **kwargs)

    def post(self, *args, **kwargs):
        raise NotImplementedError

    put = patch = delete = post

    def close(self):
        self.closed = True


def _fail_request(*args, **kwargs):
    pytest.fail("Request without a session")


@pytest.fixture
def server(monkeypatch):
    server = FakeServer(user_tokens=[USER_TOKEN], api_keys=[API_KEY])
    monkeypatch.setattr(requests, "Session", server.create_session)
    monkeypatch.setattr(requests, "get", _fail_request)
    return server


@pytest.mark.parametrize(
    "token, expected_requests, is_service",
    [
        (USER_TOKEN, [("/api/users/me", "bearer")], False),
        # Only 64 characters long token can be used as 'Bearer'
        (API_KEY, [("/api/users/me", "x-api-key")], True),
        (
            LONG_API_KEY,
            [("/api/users/me", "bearer"), ("/api/users/me", "x-api-key")],
            True,
        ),
    ],
)
def test_user_info_by_token(token, expected_requests, is_service):
    server = FakeServer(user_tokens=[USER_TOKEN], api_keys=[LONG_API_KEY])
    server.api_keys.add(API_KEY)
    user_info = get_user_info_by_token(
        URL, token, session=server.create_session()
    )
    assert user_info.is_valid
    assert user_info.is_service is is_service
    assert server.requests == expected_requests


@pytest.mark.parametrize(
    "token, auth", [(USER_TOKEN, "bearer"), (API_KEY, "x-api-key")]
)
def test_connection_validates_with_single_request(server, token, auth):
    con = ServerAPI(URL, token)

    assert con.has_valid_token
    assert con.is_server_available
    assert server.requests == [("/api/users/me", auth)]
    # Authorized session reuses connection of the validation
    assert len(server.sessions) == 1
    assert con._session is server.sessions[0]


def test_global_connection_validates_with_single_request(
    server, monkeypatch
):
    monkeypatch.setenv(SERVER_URL_ENV_KEY, URL)
    monkeypatch.setenv(SERVER_API_ENV_KEY, API_KEY)
    con = GlobalServerAPI()

    assert con.has_valid_token
    assert server.requests == [("/api/users/me", "x-api-key")]
    assert len(server.sessions) == 1


def test_invalid_token_marks_server_available(server):
    con = ServerAPI(URL, "d" * 32)

    assert con.is_server_available
    assert not con.has_valid_token
    assert server.requests == [("/api/users/me", "x-api-key")]


def test_availability_without_token(server):
    con = ServerAPI(URL, create_session=False)

    assert con.is_server_available
    assert server.requests == [("/api/info", "none")]


def test_url_of_other_server_is_not_available(monkeypatch):
    server = FakeServer(api_keys=[API_KEY], is_ayon=False)
    monkeypatch.setattr(requests, "Session", server.create_session)
    monkeypatch.setattr(requests, "get", _fail_request)

    with pytest.raises(ServerNotReached):
        ServerAPI(URL, API_KEY)
    assert server.requests == [
        ("/api/users/me", "x-api-key"),
        ("/api/info", "none"),
    ]
