import pytest
import os
from dotenv import load_dotenv
from ayon_api.entity_hub import EntityHub
from ayon_api._api import (
    get_folder_by_id,
    get_folders
)


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

    parent_folder = e.add_new_folder("Folder", name=folder_name)
    e.commit_changes()

    
    folders = []
    subfolders = []
    for i in range(2):
        folder = e.add_new_folder("Folder", name="test"+str(i), parent_id=parent_folder["id"])
        folders.append(folder)

        subfolder = e.add_new_folder("Folder", name="duplicated", parent_id=folder["id"])
        subfolders.append(subfolder)
    e.commit_changes()


    # raises an exception (duplicated names)
    """
    # switch the parent folders - duplicated names exception shouldn't be raised
    e.set_entity_parent(subfolders[0]["id"], folders[1]["id"])
    e.set_entity_parent(subfolders[1]["id"], folders[0]["id"])

    e.commit_changes()

    # check if parent ids are switched
    assert subfolders[1]["parent_id"] == folders[0]["id"]
    assert subfolders[0]["parent_id"] == folders[1]["id"]

    # move and delete -> duplicated names exception shouldn't be raised
    e.set_entity_parent(subfolders[0]["id"], folders[0]["id"])
    e.delete_entity(subfolders[1])

    e.commit_changes()

    # check if parent id is switched and the second folder is deleted
    assert subfolders[0]["parent_id"] == folders[0]["id"]
    assert get_folder_by_id(PROJECT_NAME, subfolders[1]["id"]) is None
    """

    # ------------------------------
    e.delete_entity(parent_folder)
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

    assert get_folder_by_id(PROJECT_NAME, folder1["id"]) is not None

    for subfolder_id in subfolder_ids:
        assert get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id, 
            parent_ids=folder1["id"]) is not None

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

    # e.commit_changes()

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
        print("GET_FOLDERS =", get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id,
            parent_ids=folder_ids[i // num_of_subfolders]))

        assert get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id, 
            parent_ids=folder_ids[i // num_of_subfolders]) is None

        assert get_folders(
            PROJECT_NAME, 
            folder_ids=subfolder_id, 
            parent_ids=folder_ids[(i // num_of_subfolders + 1) % num_of_folders]) is not None
        # assert subfolder_id not in my_get_folder_ids(folder_ids[i // num_of_subfolders])
        # assert subfolder_id in my_get_folder_ids(folder_ids[(i // num_of_subfolders + 1) % num_of_folders])


    e.delete_entity(parent_folder)
    e.commit_changes()


def test_move_tasks():
    # TODO
    print("NOT DONE")
