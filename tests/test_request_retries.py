"""Retries of REST requests. Does not require running AYON server."""
import pytest
import requests

from ayon_api.server_api import ServerAPI
from ayon_api.utils import RequestTypes

from .fake_transfer import FakeResponse


@pytest.fixture
def con(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    return ServerAPI("http://localhost:0", create_session=False, max_retries=3)


@pytest.mark.parametrize(
    "failure",
    [requests.exceptions.ConnectionError("down"), FakeResponse(503)],
)
def test_successful_retry_returns_successful_response(con, failure):
    responses = [failure, FakeResponse(200, json_data={"ok": True})]

    # `_do_rest_request` expects a callable that takes a URL and returns a
    # response. So we just return fake responses to simulate it.
    def request_func(url, **kwargs):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    response = con._do_rest_request(
        request_func, "http://localhost:0/api/x", handle_invalid_token=False
    )
    assert response.status_code == 200
    assert response.data == {"ok": True}


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.SSLError("certificate verify failed"),
        requests.exceptions.ProxyError("proxy refused"),
    ],
)
def test_ssl_and_proxy_errors_are_not_retried(con, error):
    calls = []

    def request_func(url, **kwargs):
        calls.append(url)
        raise error

    response = con._do_rest_request(
        request_func, "http://localhost:0/api/x", handle_invalid_token=False
    )
    assert len(calls) == 1
    assert response.status_code == 500
    assert str(error) in response.data["detail"]


def test_request_without_session_uses_ssl_settings(con, monkeypatch):
    con.set_ssl_verify("/path/to/ca.pem")
    con.set_cert("/path/to/cert.pem")
    used_sessions = []

    def fake_request(session, method, url, **kwargs):
        used_sessions.append((session.verify, session.cert, method))
        return FakeResponse(200, json_data={"ok": True})

    monkeypatch.setattr(requests.Session, "request", fake_request)

    response = con._do_rest_request(
        RequestTypes.get,
        "http://localhost:0/api/x",
        handle_invalid_token=False,
    )
    assert response.status_code == 200
    assert used_sessions == [("/path/to/ca.pem", "/path/to/cert.pem", "GET")]
