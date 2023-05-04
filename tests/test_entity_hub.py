import pytest
import os
from dotenv import load_dotenv
from tests.my_helper_functions import (
    my_get_folder_ids
)
from ayon_api.entity_hub import EntityHub


PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


DEBUG_PRINT = True


@pytest.mark.parametrize(
    "folder_name",
    [
        ("entity_hub_folder1"),
    ]
)
def test_order_of_simple_operations(folder_name):
    e = EntityHub(PROJECT_NAME)

    folder1 = e.add_new_folder("Folder", name=folder_name)
    e.commit_changes()

    # raises an exception (duplicated names)
    # works if the second folder is deleted (<= never created)
    """
    # create new with same name and delete the old one
    folder2 = e.add_new_folder("Folder", name=folder_name)
    e.delete_entity(folder1)

    e.commit_changes()

    assert folder1["id"] not in my_get_folder_ids()
    assert folder2["id"] in my_get_folder_ids()

    # delete created folder
    e.delete_entity(folder2)
    e.commit_changes()
    """
    # ------------------------------
    # clean up after ^^^
    e.delete_entity(folder1)
    e.commit_changes()


@pytest.mark.parametrize(
    "folder_name, subfolder_name, num_of_subfolders",
    [
        ("entity_hub_test", "subfolder", 3),
    ]
)
def test_operations_with_subfolders(
    folder_name,
    subfolder_name,
    num_of_subfolders
    ):
    e = EntityHub(PROJECT_NAME)
    
    folder1 = e.add_new_folder("Folder", name=folder_name)

    subfolder_ids = []
    for i in range(num_of_subfolders):
        subfolder = e.add_new_folder(
            "Folder",
            parent_id=folder1["id"], 
            name=f"{subfolder_name}{i:03}"
        )
        subfolder_ids.append(subfolder["id"])

        # create and delete folder with same name
        subfolder = e.add_new_folder(
            "Folder",
            parent_id=folder1["id"], 
            name=f"{subfolder_name}{i:03}"
        )
        e.delete_entity(subfolder)

    e.commit_changes()

    assert folder1["id"] in my_get_folder_ids()

    server_subfolder_ids = my_get_folder_ids(folder1["id"])
    for subfolder_id in subfolder_ids:
        assert subfolder_id in server_subfolder_ids

    # clean up
    e.delete_entity(folder1)
    e.commit_changes()


@pytest.mark.parametrize(
    "parent_folder_name, folder_name, subfolder_name, num_of_folders, num_of_subfolders",
    [
        ("entity_hub_test", "folder", "subfolder", 2, 3),
    ]
)
def test_move_folders(
    parent_folder_name,
    folder_name,
    subfolder_name,
    num_of_folders,
    num_of_subfolders
    ):
    e = EntityHub(PROJECT_NAME)

    parent_folder = e.add_new_folder(
        "Folder",
        name=parent_folder_name
    )

    folder_ids = []
    for i in range(num_of_folders):
        folder = e.add_new_folder(
            "Folder",
            parent_id=parent_folder["id"],
            name=f"{folder_name}{i:03}"
        )
        folder_ids.append(folder["id"])

    e.commit_changes()

    subfolder_ids = [] # [folder_id, list()]
    for folder_id in folder_ids:
        for i in range(num_of_subfolders):
            subfolder = e.add_new_folder(
                "Folder",
                parent_id=folder_id, 
                name=f"{subfolder_name}{i:03}"
            )
            subfolder_ids.append(subfolder["id"])

    e.commit_changes()

    # raises exception - duplicated name under parent_id
    """
    if DEBUG_PRINT:
        print()
    # move all subfolders from one folder to the next one
    # for some time are the names duplicated under one parent_id
    # -> before commit everything OK
    for i, subfolder_id in enumerate(subfolder_ids):
        # next folder (for last folder -> first folder)
        new_parent_id = folder_ids[(i // num_of_subfolders + 1) % num_of_folders]
        
        # test for me, if new_parent_id is generated correctly
        subfolder = e.get_folder_by_id(subfolder_id)
        current_parent_id = subfolder["parent_id"]
        assert new_parent_id != current_parent_id
        if DEBUG_PRINT:
            print(subfolder_id, "|", subfolder["name"], ": ", current_parent_id, " -> ", new_parent_id)
        e.set_entity_parent(subfolder_id, new_parent_id)

    e.commit_changes()

    # test if moved correctly
    for i, subfolder_id in enumerate(subfolder_ids):
        assert subfolder_id not in my_get_folder_ids(folder_ids[i // num_of_subfolders])
        assert subfolder_id in my_get_folder_ids(folder_ids[(i // num_of_subfolders + 1) % num_of_folders])
    """

    e.delete_entity(parent_folder)
    e.commit_changes()


def test_move_tasks():
    # TODO
    print("NOT DONE")
