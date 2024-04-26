"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment. 
"""

import os
import pytest

from ayon_api import (
    is_connection_created,
    close_connection,
    get,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
)

PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")
AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "{}/api".format(AYON_BASE_URL)

def test_close_connection():
    con = get_server_api_connection()
    assert is_connection_created() is True
    close_connection()
    assert is_connection_created() is False


def test_get_base_url():
    res = get_base_url()
    assert isinstance(res, str)
    assert res == AYON_BASE_URL


def test_get_rest_url():
    res = get_rest_url()
    assert isinstance(res, str)
    assert res == AYON_REST_URL


@pytest.mark.parametrize(
    "entity_type, name",
    [("projects", PROJECT_NAME)]
)
def test_get(entity_type, name):
    entrypoint = entity_type + "/" + name
    res = get(entrypoint)
    assert res.status_code == 200
    assert isinstance(res.data, dict)
