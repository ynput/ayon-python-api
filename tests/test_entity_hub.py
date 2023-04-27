import pytest
import os
from dotenv import load_dotenv
from ayon_api.entity_hub import EntityHub


PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


@pytest.mark.parametrize(
    "folder_name",
    [
        ("entity_hub_folder1"),
    ]
)
def test_order_of_operations(folder_name):
    e = EntityHub(PROJECT_NAME)

    folder1 = e.add_new_folder("Folder", name=folder_name)
    e.commit_changes()

    # create new with same name and delete the old one
    folder2 = e.add_new_folder("Folder", name=folder_name)
    e.delete_entity(folder1)
    e.commit_changes()

    e.delete_entity(folder2)
    e.commit_changes()

