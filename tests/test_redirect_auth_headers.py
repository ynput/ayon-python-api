"""Service api key headers are not sent to other host on redirect."""
import http.server
import json
import threading

import pytest

from ayon_api import ServerAPI

SERVICE_KEY = "s" * 32


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        # 'download_file' does not prepend '/api'
        if path.startswith("/api/redirect/"):
            path = path[len("/api"):]
        if path.startswith("/redirect/"):
            # '/redirect/<host>/<name>'
            host, name = path[len("/redirect/"):].split("/", 1)
            port = self.server.server_address[1]
            self._send(302, headers={
                "Location": f"http://{host}:{port}/echo/{name}"
            })
            return

        if path.startswith("/echo/"):
            self.server.received[path[len("/echo/"):]] = dict(self.headers)
            self._send(200, b"content", {
                "Content-Type": "application/octet-stream"
            })
            return

        if path == "/api/users/me":
            if self.headers.get("X-Api-Key") == SERVICE_KEY:
                self._send(
                    200,
                    json.dumps({"name": "service"}).encode(),
                    {"Content-Type": "application/json"},
                )
            else:
                self._send(401, b"{}", {"Content-Type": "application/json"})
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
    httpd.received = {}
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
    port = server.server_address[1]
    con = ServerAPI(
        f"http://localhost:{port}", token=SERVICE_KEY, max_retries=0
    )
    yield con
    con.close_session()


def _api_key_headers(headers):
    return {
        key.lower()
        for key in headers
        if key.lower() in ("x-api-key", "x-as-user")
    }


def test_other_host_redirect_strips_api_key(server, api):
    with api.as_username("artist"):
        api.get("redirect/127.0.0.1/other")
    assert _api_key_headers(server.received["other"]) == set()


def test_same_host_redirect_keeps_api_key(server, api):
    with api.as_username("artist"):
        api.get("redirect/localhost/same")
    assert _api_key_headers(server.received["same"]) == {
        "x-api-key", "x-as-user"
    }


def test_download_redirect_strips_api_key(server, api, tmp_path):
    with api.as_username("artist"):
        api.download_file(
            "redirect/127.0.0.1/download", str(tmp_path / "file.bin")
        )
    assert _api_key_headers(server.received["download"]) == set()
    assert (tmp_path / "file.bin").read_bytes() == b"content"
