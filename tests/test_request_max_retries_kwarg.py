"""'max_retries' request argument. Does not require running AYON server."""
import requests

from ayon_api.server_api import ServerAPI


def test_max_retries_kwarg_is_not_passed_to_request(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *args, **kwargs: None)
    con = ServerAPI("http://localhost:0", create_session=False, max_retries=5)
    calls = []

    def request_func(url, **kwargs):
        # Real request functions raise TypeError on unknown arguments
        if "max_retries" in kwargs:
            raise TypeError("unexpected keyword argument 'max_retries'")
        calls.append(kwargs)
        raise requests.exceptions.ConnectionError("down")

    response = con._do_rest_request(
        request_func,
        "http://localhost:0/api/x",
        handle_invalid_token=False,
        max_retries=2,
    )
    assert len(calls) == 2
    assert response.status_code == 500
