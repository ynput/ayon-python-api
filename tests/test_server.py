"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment. 
"""


import pytest
import os
from dotenv import load_dotenv
from ayon_api import (
    is_connection_created,
    close_connection,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get, 
    post,
    put,
    patch,
    delete,
    get_project,
    get_users
)

AYON_BASE_URL = "https://ayon.dev"
AYON_REST_URL = "https://ayon.dev/api"


os.environ["AYON_SERVER_URL"] = AYON_BASE_URL


def test_close_connection():
    con = get_server_api_connection()
    assert is_connection_created() == True
    close_connection()
    assert is_connection_created() == False


"""
def test_change_token():

def test_set_environments():

def test_get_server_api_connection():
"""


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



@pytest.mark.parametrize(
    "entrypoint, my_data",
    [
        ("projects/demo_Commercial", {"foo" : "bar"})
    ]
)
def test_post_put_patch_delete(entrypoint, my_data):
    res = get(entrypoint)

    # TODO
    if "foo" not in res.data:
        post(entrypoint, json=my_data)


