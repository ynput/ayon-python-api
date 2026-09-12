"""Auto-fix of missing 'api/' in transfer endpoints.

Does not require running AYON server.
"""
import io

import pytest

from ayon_api.server_api import ServerAPI
from ayon_api.utils import RequestTypes, TransferProgress

from .fake_transfer import FakeResponse


@pytest.fixture
def con(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    return ServerAPI("http://localhost:0", create_session=False, max_retries=1)


def test_download_frontend_page_uses_api_url(con):
    urls = []

    def get_func(url, **kwargs):
        urls.append(url)
        if "/api/" not in url:
            # Web frontend serves 'index.html' for unknown urls
            return FakeResponse(200, b"<html>", {"Content-Type": "text/html"})
        return FakeResponse(200, b"PNG", {"Content-Length": "3"})

    con._base_functions_mapping[RequestTypes.get] = get_func
    stream = io.BytesIO()
    con.download_file_to_stream("projects/p/thumbnails/1", stream)

    assert stream.getvalue() == b"PNG"
    assert urls[-1] == "http://localhost:0/api/projects/p/thumbnails/1"


def test_upload_autofix_with_single_attempt_and_progress(con):
    def put_func(url, data=None, **kwargs):
        list(data)
        if "/api/" not in url:
            return FakeResponse(404)
        return FakeResponse(200)

    con._base_functions_mapping[RequestTypes.put] = put_func
    progress = TransferProgress()
    response = con.upload_file_from_stream(
        "upload", io.BytesIO(b"0123456789"), progress
    )

    assert response.status_code == 200
    assert progress.transferred_size == 10
