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

    print("\n#", folder1.parent_id, "#")

    e.delete_entity(folder1)
    e.commit_changes()
