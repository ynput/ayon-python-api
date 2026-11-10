"""Helpers to test requests and file transfers without AYON server."""
import requests
from requests.structures import CaseInsensitiveDict


class FakeResponse:
    """Minimal stand-in for 'requests.Response'."""
    def __init__(
        self, status_code=200, content=b"", headers=None, json_data=None
    ):
        self.status_code = status_code
        self.content = content
        self.headers = CaseInsensitiveDict(headers or {})
        self._json_data = json_data
        self.reason = "Reason"
        self.text = content.decode(errors="ignore")

    @property
    def ok(self):
        return self.status_code < 400

    def raise_for_status(self):
        if not self.ok:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Error", response=self
            )

    def json(self):
        if self._json_data is None:
            raise ValueError("No json")
        return self._json_data

    def iter_content(self, chunk_size=1):
        for idx in range(0, len(self.content), chunk_size):
            yield self.content[idx:idx + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
