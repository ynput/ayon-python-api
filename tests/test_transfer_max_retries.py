"""Retries of file transfers. Does not require running AYON server."""
import io

import pytest
import requests

from ayon_api.server_api import ServerAPI
from ayon_api.utils import RequestTypes

from .fake_transfer import FakeResponse


@pytest.fixture
def con(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    return ServerAPI("http://localhost:0", create_session=False, max_retries=3)


def test_upload_respects_connection_max_retries(con):
    con.set_max_retries(1)
    attempts = []

    def put_func(url, data=None, **kwargs):
        attempts.append(b"".join(data))
        raise requests.exceptions.ConnectionError("broken pipe")

    con._base_functions_mapping[RequestTypes.put] = put_func
    with pytest.raises(requests.exceptions.ConnectionError):
        con.upload_file_from_stream("api/upload", io.BytesIO(b"x"))
    assert len(attempts) == 1


def test_zero_retries_still_transfers(con, monkeypatch):
    monkeypatch.setenv("AYON_SERVER_RETRIES", "0")
    con.set_max_retries(None)
    con._base_functions_mapping[RequestTypes.put] = (
        lambda url, data=None, **kwargs: (list(data), FakeResponse(204))[1]
    )
    con._base_functions_mapping[RequestTypes.get] = (
        lambda url, **kwargs: FakeResponse(
            200, b"abc", {"Content-Length": "3"}
        )
    )

    response = con.upload_file_from_stream("api/upload", io.BytesIO(b"x"))
    assert response.status_code == 204

    stream = io.BytesIO()
    con.download_file_to_stream("api/file", stream)
    assert stream.getvalue() == b"abc"
