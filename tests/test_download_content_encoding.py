"""Download of compressed responses and responses without size."""
import gzip
import http.server
import json
import threading

import pytest

from ayon_api import ServerAPI

CONTENT = bytes(range(256)) * 64
API_KEY = "s" * 32


def _range_offset(headers):
    value = headers.get("Range")
    if not value:
        return 0
    return int(value[len("bytes="):].split("-")[0])


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        if "Transfer-Encoding" not in (headers or {}):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        self.server.requests.append((path, dict(self.headers)))
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        if path == "/gzip-if-accepted":
            # Compresses content when client accepts it
            if accepts_gzip:
                self._send(200, gzip.compress(CONTENT), {
                    "Content-Encoding": "gzip",
                })
            else:
                self._send(200, CONTENT)
            return

        if path == "/gzip-always":
            # Compresses content even if client asks for 'identity'
            self._send(200, gzip.compress(CONTENT), {
                "Content-Encoding": "gzip",
            })
            return

        if path == "/gzip-drop-once":
            # Compressed content, first response is cut in half
            body = gzip.compress(CONTENT)
            self.server.drop_count += 1
            if self.server.drop_count == 1:
                self.send_response(200)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:len(body) // 2])
                self.close_connection = True
                return
            self._send(200, body, {"Content-Encoding": "gzip"})
            return

        if path == "/chunked-resume-short":
            # 1. chunked response without size is cut
            # 2. resumed response ends before its 'Content-Length'
            # 3. resumed response is complete
            self.server.drop_count += 1
            offset = _range_offset(self.headers)
            if self.server.drop_count == 1:
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                chunk = CONTENT[:4000]
                self.wfile.write(f"{len(chunk):X}\r\n".encode())
                self.wfile.write(chunk + b"\r\n")
                self.close_connection = True
                return
            body = CONTENT[offset:]
            headers = {
                "Content-Range": (
                    f"bytes {offset}-{len(CONTENT) - 1}/{len(CONTENT)}"
                ),
            }
            if self.server.drop_count == 2:
                self.send_response(206)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:len(body) // 2])
                self.close_connection = True
                return
            self._send(206, body, headers)
            return

        if path == "/resume-then-gzip":
            # 1. uncompressed response is cut
            # 2. resumed response is compressed and cut
            # 3. must download whole content again without 'Range'
            self.server.drop_count += 1
            offset = _range_offset(self.headers)
            if self.server.drop_count == 1:
                self.send_response(200)
                self.send_header("Content-Length", str(len(CONTENT)))
                self.end_headers()
                self.wfile.write(CONTENT[:4000])
                self.close_connection = True
                return
            if self.server.drop_count == 2:
                body = gzip.compress(CONTENT[offset:])
                self.send_response(206)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:len(body) // 2])
                self.close_connection = True
                return
            if offset:
                self._send(416)
                return
            self._send(200, CONTENT)
            return

        if path == "/chunked":
            # No 'Content-Length' header
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for idx in range(0, len(CONTENT), 1000):
                chunk = CONTENT[idx:idx + 1000]
                self.wfile.write(f"{len(chunk):X}\r\n".encode())
                self.wfile.write(chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            return

        if path == "/api/users/me":
            self._send(
                200,
                json.dumps({"name": "service"}).encode(),
                {"Content-Type": "application/json"},
            )
            return

        self._send(
            200,
            json.dumps({"version": "1.17.3", "uptime": 1}).encode(),
            {"Content-Type": "application/json"},
        )

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.requests = []
    httpd.drop_count = 0
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def api(server, monkeypatch):
    for key in ("AYON_CA_FILE", "AYON_CERT_FILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    port = server.server_address[1]
    con = ServerAPI(f"http://127.0.0.1:{port}", token=API_KEY)
    yield con
    con.close_session()


def _download(server, api, tmp_path, endpoint):
    server.requests.clear()
    filepath = tmp_path / "file.bin"
    # Small chunks, so content received before connection drop is written
    progress = api.download_file(endpoint, str(filepath), chunk_size=1000)
    downloads = [
        headers for path, headers in server.requests if path == endpoint
    ]
    return filepath.read_bytes(), progress, downloads


def test_download_asks_for_uncompressed_content(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/gzip-if-accepted"
    )
    assert content == CONTENT
    assert progress.get_content_size() == len(CONTENT)
    assert progress.get_transferred_size() == len(CONTENT)
    assert len(downloads) == 1
    assert "Range" not in downloads[0]


def test_download_compressed_content(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/gzip-always"
    )
    assert content == CONTENT
    assert progress.get_transferred_size() == len(CONTENT)
    assert len(downloads) == 1
    assert "Range" not in downloads[0]


def test_download_compressed_content_restarts(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/gzip-drop-once"
    )
    assert content == CONTENT
    assert progress.get_transferred_size() == len(CONTENT)
    # 'Range' of compressed content can't be used to continue
    assert len(downloads) == 2
    assert all("Range" not in headers for headers in downloads)


def test_download_resumed_response_is_complete(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/chunked-resume-short"
    )
    assert content == CONTENT
    assert len(downloads) == 3
    assert "Range" not in downloads[0]
    assert downloads[1]["Range"] == "bytes=4000-"


def test_download_restart_does_not_keep_range(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/resume-then-gzip"
    )
    assert content == CONTENT
    assert len(downloads) == 3
    assert downloads[1]["Range"] == "bytes=4000-"
    assert "Range" not in downloads[2]


def test_download_without_content_length(server, api, tmp_path):
    content, progress, downloads = _download(
        server, api, tmp_path, "/chunked"
    )
    assert content == CONTENT
    assert progress.get_content_size() is None
    assert progress.get_transferred_size() == len(CONTENT)
    assert len(downloads) == 1
