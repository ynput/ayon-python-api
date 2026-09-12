"""Retries of REST requests. Does not require running AYON server."""
import pytest
import requests

from ayon_api.server_api import ServerAPI

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
