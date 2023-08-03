"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment. 
"""

import json
import os
import pytest
from dotenv import load_dotenv

from ayon_api import (
    is_connection_created,
    close_connection,
    get,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get_tasks,
    get_versions,
    get_representation_by_id,
    get_version_by_id,
    get_folder_by_id,
    get_product_by_id,
    get_folder_by_name,
    get_product_by_name,
    get_representation_by_name,
    get_folders,
    get_products,
    get_versions,
    get_representations
)
from ayon_api.exceptions import (
    FailedOperations
)


AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "{}/api".format(AYON_BASE_URL )
PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


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
    [("projects", PROJECT_NAME)]
)
def test_get(folder, name):
    entrypoint = folder + "/" + name
    res = get(entrypoint)
    assert res.status_code == 200
    assert isinstance(res.data, dict)
