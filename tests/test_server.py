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
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get, post, put, patch, delete,
    raw_get, raw_post, raw_put, raw_patch, raw_delete
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
    # print(res.data)

"""
@pytest.mark.parametrize("entrypoint, data_to_insert, data_to_change", [
    ("projects/demo_Commercial", {"foo" : "1", "bar" : 42}, {"foo" : "2"})
])
def test_basic_requests(entrypoint, data_to_insert, data_to_change):
    # insert and test if is in
    res = get(entrypoint)
    assert res.status_code == 200


    res = post(entrypoint, json=data_to_insert)
    assert res.status_code == 200
    res = get(entrypoint)
    assert res.status_code == 200
    assert data_to_insert in res.data
    
    # insert and test if has changed
    res = put(entrypoint + "/", json=data_to_change)
    assert res.status_code == 200
    res = get(entrypoint)
    assert res.status_code == 200
    assert data_to_change in res.data
    # ...
    assert data_to_insert not in res.data

    # delete and test if not in
    res = delete(entrypoint + "/", json=data_to_change)
    assert res.status_code == 200
    res = get(entrypoint)
    assert res.status_code == 200
    assert data_to_insert not in res.data
    assert data_to_change not in res.data
"""

from ayon_api import get_folder_by_id
from ayon_api.operations import OperationsSession, new_folder_entity


@pytest.fixture
def folder():
    folder_name = "testingFolder"
    return new_folder_entity(folder_name, "Folder")


def delete_folder(s, name, id):
    s.delete_entity(name, "folder", id)
    s.commit()


@pytest.mark.parametrize(
    "folder_name",
    [
        ("testfolder1"),
        ("testfolder2"),
        ("testfolder3")
    ]
)
def test_operations_with_folder(folder_name):
    project_name = "demo_Commercial"

    folder = new_folder_entity(folder_name, "Folder")

    s = OperationsSession()
    op = s.create_entity(project_name, "folder", folder)
    folder_id = op.entity_id
    s.commit()

    folder_entity = get_folder_by_id(project_name, folder_id)
    s.update_entity(
        project_name,
        "folder",
        folder_entity["id"],
        {"attrib": {"frameStart": 1002}}
    )
    s.commit()
    folder_entity = get_folder_by_id(project_name, folder_id)
    assert folder_entity["attrib"]["frameStart"] == 1002

    delete_folder(s, project_name, folder_entity["id"])
    assert get_folder_by_id(project_name, folder_id) is None

"""
def test_operations_with_folder_exception(folder):
    # Want to test invalid attribs - rights etc.

    project_name = "demo_Commercial"

    s = OperationsSession()
    op = s.create_entity(project_name, "folder", folder)
    folder_id = op.entity_id
    s.commit()

    folder_entity = get_folder_by_id(project_name, folder_id)
    s.update_entity(
        project_name,
        "folder",
        folder_entity["id"],
        {"attrib": {"xyz": 1002}}
    )
    s.commit()
    folder_entity = get_folder_by_id(project_name, folder_id)
    assert folder_entity["attrib"]["xyz"] == 1002

    delete_folder(s, project_name, folder_entity["id"])

    assert get_folder_by_id(project_name, folder_id) is None
"""
