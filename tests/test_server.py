"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment. 
"""


import pytest
import os
from dotenv import load_dotenv
import json
from ayon_api.operations import (
    OperationsSession,
    new_folder_entity,
    new_subset_entity,
    new_version_entity,
    new_representation_entity
)
from ayon_api import (
    is_connection_created,
    close_connection,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get_tasks,
    get_versions,
    get_folder_by_id,
    get_folder_by_name,
    get_folders
)


AYON_BASE_URL = "https://ayon.dev"
AYON_REST_URL = "https://ayon.dev/api"
PROJECT_NAME = "demo_Commercial"

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
    # print(res.data)


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
    folder = new_folder_entity(folder_name, "Folder")

    s = OperationsSession()
    op = s.create_entity(PROJECT_NAME, "folder", folder)
    folder_id = op.entity_id
    s.commit()

    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    s.update_entity(
        PROJECT_NAME,
        "folder",
        folder_entity["id"],
        {"attrib": {"frameStart": 1002}}
    )
    s.commit()
    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    assert folder_entity["attrib"]["frameStart"] == 1002

    delete_folder(s, PROJECT_NAME, folder_entity["id"])
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None

"""
def test_operations_with_folder_exception(folder):
    try:
        s = OperationsSession()
        op = s.create_entity(PROJECT_NAME, "folder", folder)
        folder_id = op.entity_id
        s.commit()
        
        folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
        s.update_entity(
            PROJECT_NAME,
            "folder",
            folder_entity["id"],
            {"attrib": {"xyz": 1002}}
        )
        s.commit()

        folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)

        # Test that wrong attribute is not there
        with pytest.raises(KeyError):
            assert folder_entity["attrib"]["xyz"] == 1002

    finally:
        delete_folder(s, PROJECT_NAME, folder_entity["id"])
        assert get_folder_by_id(PROJECT_NAME, folder_id) is None
"""


@pytest.mark.parametrize(
    "folder_name",
    [
        ("!invalid"),
        ("in/valid"),
        ("in~valid")
    ]
)
def test_folder_name_invalid_characters(folder_name):
    """in-valid is OK
    """

    s = OperationsSession()

    with pytest.raises(KeyError):
        folder = new_folder_entity(folder_name, "Folder")
        op = s.create_entity(PROJECT_NAME, "folder", folder)
        s.commit()


@pytest.mark.parametrize(
    "folder_name",
    [
        ("test_folder1"),
    ]
)
def test_folder_duplicated_names(folder_name):
    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    op = s.create_entity(PROJECT_NAME, "folder", folder)
    folder_id = op.entity_id
    s.commit()

    with pytest.raises(KeyError):
        folder = new_folder_entity(folder_name, "Folder")
        op = s.create_entity(PROJECT_NAME, "folder", folder)
        s.commit()

    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    delete_folder(s, PROJECT_NAME, folder_entity["id"])
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name, subset_name, version_name, representation_name",
    [
        ("testfolder1", "modelMain", "version1", "representation1")
    ]
)
def test_hierarchy_folder_subset_version_repre(
    folder_name, 
    subset_name, 
    version_name, 
    representation_name
):
    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    op = s.create_entity(PROJECT_NAME, "folder", folder)    
    folder_id = op.entity_id
    s.commit()
    
    subset = new_subset_entity(subset_name, "model", folder_id)
    op = s.create_entity(PROJECT_NAME, "subset", subset)    
    subset_id = op.entity_id
    s.commit()

    version = new_version_entity(1, subset_id)
    op = s.create_entity(PROJECT_NAME, "version", version)    
    version_id = op.entity_id
    s.commit()

    version = new_representation_entity("testRepresentation", version_id)
    op = s.create_entity(PROJECT_NAME, "representation", version)    
    representation_id = op.entity_id
    s.commit()

    subset_entity = get_subset_by_id(PROJECT_NAME, subset_id)
    delete_entity(s, PROJECT_NAME, "subset", subset_entity["id"])
    # s.commit()

    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    delete_entity(s, PROJECT_NAME, "folder", folder_entity["id"])
    s.commit()


def test_large_project_hierarchy():
    s = OperationsSession()
    folders = []

    folder_name = "testFolder"

    try:
        # create folders
        for num in range(3):
            name = folder_name + str(num)
            folder = new_folder_entity(name, "Folder")
            op = s.create_entity(PROJECT_NAME, "folder", folder)
            folders.append(
            {
                "name": name,
                "id": op.entity_id,
            }
            )
            s.commit()

        # create subsets in all folders
        subset_prep = [
            ("modelMain", "model"), 
            ("modelProxy", "model"),
            ("modelSculpt", "model")
        ]
        for i, (name, family) in enumerate(subset_prep):
            subset = new_subset_entity(name, family, folders[i]["id"])
            op = s.create_entity(PROJECT_NAME, "subset", subset)
            subset_id = op.entity_id
            s.commit()

    finally:
        # delete folders
        for folder in folders:
            folder_entity = get_folder_by_id(PROJECT_NAME, folder["id"])
            delete_folder(s, PROJECT_NAME, folder_entity["id"])


@pytest.mark.parametrize(
    "folder_name",
    [
        ("testfolder1"),
        ("testFolder1"),
        ("testfolder1_1"),
        ("testFolder2")
    ]
)
def test_delete_folder_with_subset(folder_name):
    # TODO 
    s = OperationsSession()

    folder_entity = get_folder_by_name(PROJECT_NAME, folder_name)
    delete_folder(s, PROJECT_NAME, folder_entity["id"])
    s.commit()

