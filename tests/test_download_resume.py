"""Interrupted downloads. Does not require running AYON server."""
import io

import pytest

from ayon_api.server_api import ServerAPI
from ayon_api.utils import RequestTypes

from .fake_transfer import FakeResponse

CONTENT = b"0123456789"
SIZE_HEADER = {"Content-Length": str(len(CONTENT))}


@pytest.fixture
def con(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    return ServerAPI("http://localhost:0", create_session=False, max_retries=3)


def _download(con, get_func):
    con._base_functions_mapping[RequestTypes.get] = get_func
    stream = io.BytesIO()
    progress = con.download_file_to_stream("api/file", stream)
    return stream.getvalue(), progress


def test_incomplete_download_is_continued(con):
    def get_func(url, **kwargs):
        if "Range" not in kwargs["headers"]:
            # Connection closed after 4 bytes without an exception
            return FakeResponse(200, CONTENT[:4], SIZE_HEADER)
        assert kwargs["headers"]["Range"] == "bytes=4-"
        return FakeResponse(206, CONTENT[4:], {"Content-Length": "6"})

    content, progress = _download(con, get_func)
    assert content == CONTENT
    assert progress.transferred_size == len(CONTENT)


def test_resume_without_range_support_does_not_duplicate(con):
    calls = []

    def get_func(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(200, CONTENT[:4], SIZE_HEADER)
        # Server ignores 'Range' header and sends whole file again
        return FakeResponse(200, CONTENT, SIZE_HEADER)

    content, progress = _download(con, get_func)
    assert content == CONTENT
    assert progress.transferred_size == len(CONTENT)


def test_download_without_content_length(con):
    content, _ = _download(
        con, lambda url, **kwargs: FakeResponse(200, CONTENT)
    )
    assert content == CONTENT
