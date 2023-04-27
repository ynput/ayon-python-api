"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment. 
"""


import pytest
import os
from dotenv import load_dotenv
import json
from ayon_api import (
    is_connection_created,
    close_connection,
    get,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
)
from ayon_api.exceptions import (
    FailedOperations
)


AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "https://ayon.dev/api"
PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")

os.environ["AYON_SERVER_URL"] = AYON_BASE_URL


def test_close_connection():
    con = get_server_api_connection()
    assert is_connection_created() == True
    close_connection()
    assert is_connection_created() == False


def test_get_base_url():
    res = get_base_url()
    assert isinstance(res, str)
    assert res == AYON_BASE_URL


def test_get_rest_url():
    res = get_rest_url()
    assert isinstance(res, str)
    assert res == AYON_REST_URL


@pytest.mark.parametrize(
    "folder, name",
    [("projects", "demo_Commercial")]
)
def test_get(folder, name):
    entrypoint = folder + "/" + name
    res = get(entrypoint)
    assert res.status_code == 200
    assert isinstance(res.data, dict)
