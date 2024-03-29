import os
import pytest
from dotenv import load_dotenv

from ayon_api.entity_hub import EntityHub
from ayon_api._api import (
    get_folder_by_id,
    get_folders
)
from ayon_api.exceptions import HTTPRequestError


PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


@pytest.mark.parametrize(
    "folder_name, subfolder_name, folders_count",
    [
        ("entity_hub_simple_test", "subfolder", 3),
    ]
)
def test_simple_operations(
    folder_name,
    subfolder_name,
    folders_count
    ):
    """Test of simple operations with folders - create, move, delete.
    """
    e = EntityHub(PROJECT_NAME)

    folders = []
    subfolders = []
    # create folders with subfolder
    for folder_number in range(folders_count):
        folder = e.add_new_folder(
            "Folder",
            name=f"{folder_name}{folder_number:03}"
        )
        folders.append(folder)
        e.commit_changes()

        subfolder = e.add_new_folder(
            "Folder",
            name=f"{folder_name}{folder_number:03}",
            parent_id=folder["id"]
        )
        subfolders.append(subfolder)
        e.commit_changes()

    # move subfolders
    for index, subfolder in enumerate(subfolders):
        new_parent_id = folders[(index + 1) % folders_count]["id"]
        e.set_entity_parent(
            subfolder["id"],
            new_parent_id,
            subfolder["parent_id"])
        e.commit_changes()

        assert e.get_entity_by_id(
                subfolder["id"]
            )["parent_id"] == new_parent_id

    # delete subfolders
    for subfolder in subfolders:
        e.delete_entity(e.get_entity_by_id(subfolder["id"]))
        e.commit_changes()
        assert e.get_entity_by_id(subfolder["id"]) is None

    # delete folders
    for folder in folders:
        e.delete_entity(e.get_entity_by_id(folder["id"]))
        e.commit_changes()
        assert e.get_entity_by_id(folder["id"]) is None


@pytest.mark.parametrize(
    "folder_name, subfolder_name, num_of_subfolders",
    [
        ("entity_hub_test", "subfolder", 3),
    ]
)
def test_create_delete_with_duplicated_names(
    folder_name,
    subfolder_name,
    num_of_subfolders
    ):
    """Creates two folders with duplicated names 
    and delete one of them before commit.
    Exception should not be raised.
    """
    e = EntityHub(PROJECT_NAME)

    folder1 = e.add_new_folder("Folder", name=folder_name)

    subfolders = []
    for folder_number in range(num_of_subfolders):
        subfolder = e.add_new_folder(
            "Folder",
            parent_id=folder1["id"], 
            name=f"{subfolder_name}{folder_number:03}"
        )
        subfolders.append(subfolder)
        e.commit_changes()

        # create and delete folder with same name
        subfolder = e.add_new_folder(
            "Folder",
            parent_id=folder1["id"], 
            name=f"{subfolder_name}{folder_number:03}"
        )
        e.delete_entity(subfolder)
        e.commit_changes()

    assert e.get_folder_by_id(PROJECT_NAME, folder1["id"]) is not None

    for subfolder_id in subfolder_ids:
        assert e.get_folder_by_id(
            PROJECT_NAME, 
            subfolder_id) is not None

    # clean up
    e.delete_entity(folder1)
    e.commit_changes()


@pytest.mark.parametrize(
    "folder_name",
    [
        ("entity_hub_folder1"),
    ]
)
def test_move_with_duplicated_names(folder_name):
    """Test of moving folders with duplicated names to the same parent 
    folder for some time. Before the commit, everything is set correctly.
    Creates two folders with subfolders 
    and switches the parent folders of subfolders.
    """
    e = EntityHub(PROJECT_NAME)

    parent_folder = e.add_new_folder("Folder", name=folder_name)
    e.commit_changes()

    
    folders = []
    subfolders = []
    for folder_number in range(2):
        folder = e.add_new_folder(
            "Folder",
            name=f"test{folder_number:03}",
            parent_id=parent_folder["id"]
        )
        folders.append(folder)

        subfolder = e.add_new_folder(
            "Folder",
            name="duplicated",
            parent_id=folder["id"]
        )
        subfolders.append(subfolder)
    e.commit_changes()


    # raises an exception (duplicated names)
    """
    # switch the parent folders - duplicated names exception shouldn't be raised
    e.set_entity_parent(subfolders[0]["id"], folders[1]["id"])
    e.set_entity_parent(subfolders[1]["id"], folders[0]["id"])

    e.commit_changes()
    
    # check if parent ids are switched
    assert e.get_folder_by_id(
            subfolders[1]["id"]
        )["parent_id"] == folders[0]["id"]
    assert e.get_folder_by_id(
            subfolders[0]["id"]
        )["parent_id"] == folders[1]["id"]

    # move and delete -> duplicated names exception shouldn't be raised
    e.set_entity_parent(subfolders[0]["id"], folders[0]["id"])
    e.delete_entity(subfolders[1])

    e.commit_changes()

    # check if parent id is switched and the second folder is deleted
    assert e.get_folder_by_id(
            subfolders[0]["id"]
        )["parent_id"] == folders[0]["id"]
    assert e.get_folder_by_id(PROJECT_NAME, subfolders[1]["id"]) is None
    """

    # ------------------------------
    e.delete_entity(parent_folder)
    e.commit_changes()


@pytest.mark.parametrize(
    "parent_folder_name, folder_name, subfolder_name, num_of_folders, num_of_subfolders",
    [
        ("entity_hub_test", "folder", "subfolder", 2, 3),
    ]
)
def test_large_move_of_folders__with_duplicated_names(
    parent_folder_name,
    folder_name,
    subfolder_name,
    num_of_folders,
    num_of_subfolders
    ):
    """Test of moving folders with duplicated names to the same parent 
    folder for some time. Before the commit, everything is set correctly.
    """

    # create the starting hierarchy
    e = EntityHub(PROJECT_NAME)

    parent_folder = e.add_new_folder(
        "Folder",
        name=parent_folder_name
    )

    folder_ids = []
    for folder_number in range(num_of_folders):
        folder = e.add_new_folder(
            "Folder",
            parent_id=parent_folder["id"],
            name=f"{folder_name}{folder_number:03}"
        )
        folder_ids.append(folder["id"])

    subfolder_ids = []
    for folder_id in folder_ids:
        for subfolder_number in range(num_of_subfolders):
            subfolder = e.add_new_folder(
                "Folder",
                parent_id=folder_id, 
                name=f"{subfolder_name}{subfolder_number:03}"
            )
            subfolder_ids.append(subfolder["id"])

    e.commit_changes()

    # raises exception - duplicated name under parent_id
    """
    # move all subfolders from one folder to the next one
    for index, subfolder_id in enumerate(subfolder_ids):
        # next folder (for last folder -> first folder)
        new_parent_id = folder_ids[(index // num_of_subfolders + 1) % num_of_folders]
        
        # test for me, if new_parent_id is generated correctly
        subfolder = e.get_folder_by_id(subfolder_id)
        current_parent_id = subfolder["parent_id"]
        assert new_parent_id != current_parent_id
        e.set_entity_parent(subfolder_id, new_parent_id)

    e.commit_changes()

    # test if moved correctly
    for index, subfolder_id in enumerate(subfolder_ids):
        print("GET_FOLDERS =", get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id,
            parent_ids=folder_ids[index // num_of_subfolders]))

        assert get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id, 
            parent_ids=folder_ids[index // num_of_subfolders]) is None

        assert get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id, 
            parent_ids=folder_ids[(index // num_of_subfolders + 1) % num_of_folders]) is not None
        # assert subfolder_id not in my_get_folder_ids(folder_ids[i // num_of_subfolders])
        # assert subfolder_id in my_get_folder_ids(folder_ids[(i // num_of_subfolders + 1) % num_of_folders])
    """

    # e.delete_entity(parent_folder)
    # e.commit_changes()


def test_move_tasks():
    raise NotImplementedError()


@pytest.mark.parametrize(
    "status_name1, status_name2",
    [
        ("entity_hub_folder1"),
    ]
)
def test_duplicated_status_name():
    e = EntityHub(PROJECT_NAME)

    e.project_entity.statuses.create(
        "test_status",
        "TEST",
        "blocked",
        "play_arrow",
        "#ff0000"
    )

    e.project_entity.statuses.create(
        "test_status2",
        "TEST2",
        "blocked",
        "play_arrow",
        "#00ff00"
    )

    e.commit_changes()

    status = e.project_entity.statuses.get("test_status")
    status.name = "test_status2"

    with pytest.raises(HTTPRequestError):
        e.commit_changes()
    # print(list(e.project_entity.statuses)[0])


def test_rename_status():
    e = EntityHub(PROJECT_NAME)

    for status in e.project_entity.statuses:
        print(status.name)

def test_change_name():
    # test if all relations didnt change
    raise NotImplementedError()

def test_task_types():
    raise NotImplementedError()

def test_status_color():
    raise NotImplementedError()

def test_status_order():
    raise NotImplementedError()

def test_status_icon():
    raise NotImplementedError()




"""
task = "child folder"
task under task
"""