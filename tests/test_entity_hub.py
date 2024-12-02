from traceback import print_exc
import uuid

from requests import delete
import test

import pytest

import ayon_api
from ayon_api.entity_hub import EntityHub, UNKNOWN_VALUE

from .conftest import project_entity_fixture, TestProductData


def test_rename_status(project_entity_fixture):
    # Change statuses - add prefix 'new_'
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)
    status_mapping = {}
    for status in hub.project_entity.statuses:
        orig_name = status.name
        new_name = f"new_{orig_name}"
        status_mapping[new_name] = orig_name
        status.name = new_name
    hub.commit_changes()

    # Create new entity hub for same project and validate the changes
    #   are propagated
    hub = EntityHub(project_name)
    statuses_by_name = {
        status.name: status
        for status in hub.project_entity.statuses
    }
    if set(statuses_by_name) != set(status_mapping.keys()):
        raise AssertionError("Statuses were not renamed correctly.")

    # Change statuses back
    for status in hub.project_entity.statuses:
        status.name = status_mapping[status.name]
    hub.commit_changes()


@pytest.mark.parametrize(
    "folder_name, folders_count",
    [
        ("entity_hub_simple_test", 3),
    ]
)
def test_simple_operations(
    project_entity_fixture,
    folder_name,
    folders_count
):
    """Test of simple operations with folders - create, move, delete.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folders = []
    subfolders = []
    # create folders with subfolder
    for folder_number in range(folders_count):
        folder = hub.add_new_folder(
            folder_type="Folder",
            name=f"{folder_name}{folder_number:03}"
        )
        folders.append(folder)
        hub.commit_changes()

        subfolder = hub.add_new_folder(
            folder_type="Folder",
            name=f"{folder_name}{folder_number:03}",
            parent_id=folder["id"]
        )
        subfolders.append(subfolder)
        hub.commit_changes()

    # move subfolders
    for index, subfolder in enumerate(subfolders):
        new_parent_id = folders[(index + 1) % folders_count]["id"]
        hub.set_entity_parent(
            subfolder["id"],
            new_parent_id,
            subfolder["parent_id"])
        hub.commit_changes()

        assert hub.get_entity_by_id(
                subfolder["id"]
            )["parent_id"] == new_parent_id

    # delete subfolders
    for subfolder in subfolders:
        hub.delete_entity(hub.get_entity_by_id(subfolder["id"]))
        hub.commit_changes()
        assert hub.get_entity_by_id(subfolder["id"]) is None

    # delete folders
    for folder in folders:
        hub.delete_entity(hub.get_entity_by_id(folder["id"]))
        hub.commit_changes()
        assert hub.get_entity_by_id(folder["id"]) is None


def test_custom_values_on_entities(project_entity_fixture):
    """Test of entity hub create/update with all custom values.

    Define custom entity id, name, label, attrib and data of folder/task
    which are created and then updated.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    # --- CREATE ---
    folder_type = project_entity_fixture["folderTypes"][-1]["name"]
    root_folder = hub.add_new_folder(
        folder_type=folder_type,
        name="custom_values_root_folder"
    )

    folder_id = uuid.uuid1().hex
    folder_name = "a_folder"
    folder_label = "A Folder"
    folder_frame_start = 333
    folder_attrib = {
        "frameStart": folder_frame_start
    }
    folder_data = {"MyKey": "MyValue"}

    task_id = uuid.uuid1().hex
    task_name = "my_task"
    task_label = "My Task"
    task_frame_start = 111
    task_attrib = {
        "frameStart": task_frame_start
    }
    task_data = {"MyTaskKey": "MyTaskValue"}

    folder = hub.add_new_folder(
        folder_type=folder_type,
        name=folder_name,
        label=folder_label,
        parent_id=root_folder.id,
        entity_id=folder_id,
        active=False,
        attribs=folder_attrib,
        data=folder_data,
    )

    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    task = hub.add_new_task(
        task_type=task_type,
        name=task_name,
        label=task_label,
        folder_id=folder.id,
        data=task_data,
        attribs=task_attrib,
        entity_id=task_id,
        active=False,
    )
    hub.commit_changes()

    # Validate that entity objects don't have any changes after commit
    assert not folder.changes
    assert not task.changes

    # Fetch entities for value check after CREATE
    fetched_folder = ayon_api.get_folder_by_id(project_name, folder_id)
    fetched_task = ayon_api.get_task_by_id(project_name, task_id)

    for keys, value in (
        (["id"], folder_id),
        (["name"], folder_name),
        (["label"], folder_label),
        (["attrib", "frameStart"], folder_frame_start),
        (["data"], folder_data),
        (["active"], False),
    ):
        fetched_value = fetched_folder
        for key in keys:
            fetched_value = fetched_value[key]
        assert fetched_value == value

    for keys, value in (
        (["id"], task_id),
        (["name"], task_name),
        (["label"], task_label),
        (["attrib", "frameStart"], task_frame_start),
        (["data"], task_data),
        (["active"], False),
    ):
        fetched_value = fetched_task
        for key in keys:
            fetched_value = fetched_value[key]
        assert fetched_value == value

    # --- UPDATE ---
    # Validate update of entities
    folder_name = "b_folder"
    folder_label = "B Folder"
    folder_frame_start = 334
    folder_type = project_entity_fixture["folderTypes"][0]["name"]
    folder_data["MyKey2"] = "MyValue2"

    folder.name = folder_name
    folder.folder_type = folder_type
    folder.label = folder_label
    folder.attribs["frameStart"] = folder_frame_start
    folder.data["MyKey2"] = "MyValue2"

    task_name = "your_task"
    task_label = "Your Task"
    task_frame_start = 112
    task_data = {"MyTaskKey2": "MyTaskValue2"}
    task.name = task_name
    task.label = task_label
    task.attribs["frameStart"] = task_frame_start

    for key in tuple(task.data):
        task.data.pop(key)

    for key, value in task_data.items():
        task.data[key] = value

    hub.commit_changes()

    # Validate that entity objects don't have any changes after commit
    assert not folder.changes
    assert not task.changes

    # Fetch entities for value check on UPDATE
    fetched_folder = ayon_api.get_folder_by_id(project_name, folder_id)
    fetched_task = ayon_api.get_task_by_id(project_name, task_id)

    for keys, value in (
        (["id"], folder_id),
        (["name"], folder_name),
        (["label"], folder_label),
        (["attrib", "frameStart"], folder_frame_start),
        (["data"], folder_data),
        (["active"], False),
    ):
        fetched_value = fetched_folder
        for key in keys:
            fetched_value = fetched_value[key]
        assert fetched_value == value

    for keys, value in (
        (["id"], task_id),
        (["name"], task_name),
        (["label"], task_label),
        (["attrib", "frameStart"], task_frame_start),
        (["data"], task_data),
        (["active"], False),
    ):
        fetched_value = fetched_task
        for key in keys:
            fetched_value = fetched_value[key]
        assert fetched_value == value

    # --- CLEANUP ---
    hub.delete_entity(root_folder)
    hub.delete_entity(folder)
    hub.delete_entity(task)
    hub.commit_changes()


def test_label_eq_name_on_entities_1(project_entity_fixture):
    """Test label that have same values as name on folder and task.

    When the entity has same name and label, the label should be set to None.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folder_type = project_entity_fixture["folderTypes"][-1]["name"]
    root_folder = hub.add_new_folder(
        folder_type=folder_type,
        name="label_eq_name_root_folder"
    )

    folder_id = uuid.uuid1().hex
    folder_name = "a_folder"
    folder_label = "a_folder"

    task_id = uuid.uuid1().hex
    task_name = "my_task"
    task_label = "my_task"

    folder = hub.add_new_folder(
        folder_type=folder_type,
        name=folder_name,
        label=folder_label,
        parent_id=root_folder.id,
        entity_id=folder_id,
    )

    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    task = hub.add_new_task(
        task_type=task_type,
        name=task_name,
        label=task_label,
        folder_id=folder.id,
        entity_id=task_id,
    )
    hub.commit_changes()

    folder_entity = ayon_api.get_folder_by_id(
        project_name, folder_id, fields={"label"}
    )
    task_entity = ayon_api.get_task_by_id(
        project_name, task_id, fields={"label"}
    )
    # Label should be 'None'
    assert folder_entity["label"] is None
    assert task_entity["label"] is None

    hub.delete_entity(root_folder)
    hub.delete_entity(folder)
    hub.delete_entity(task)
    hub.commit_changes()


def test_data_changes_on_entities(project_entity_fixture):
    """Test label that have same values as name on folder and task.

    When the entity has same name and label, the label should be set to None.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folder_type = project_entity_fixture["folderTypes"][-1]["name"]
    root_folder = hub.add_new_folder(
        folder_type=folder_type,
        name="data_changes_on_entities"
    )

    folder_id = uuid.uuid1().hex
    folder_name = "a_folder"
    folder_data = {"key1": "value1"}

    task_id = uuid.uuid1().hex
    task_name = "my_task"
    task_data = {"key2": "value2"}

    folder = hub.add_new_folder(
        folder_type=folder_type,
        name=folder_name,
        data=folder_data,
        parent_id=root_folder.id,
        entity_id=folder_id,
    )

    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    task = hub.add_new_task(
        task_type=task_type,
        name=task_name,
        data=task_data,
        folder_id=folder.id,
        entity_id=task_id,
    )
    hub.commit_changes()

    folder_entity = ayon_api.get_folder_by_id(
        project_name, folder_id, fields={"data"}
    )
    task_entity = ayon_api.get_task_by_id(
        project_name, task_id, fields={"data"}
    )
    # Label should be 'None'
    assert folder_entity["data"] == folder_data
    assert task_entity["data"] == task_data

    hub = EntityHub(project_name)

    folder = hub.get_or_fetch_entity_by_id(folder_id, {"folder"})
    folder.data["key3"] = "value3"
    folder.data.pop("key1")

    task = hub.get_or_fetch_entity_by_id(task_id, {"task"})
    task.data["key4"] = "value4"
    task.data.pop("key2")
    hub.commit_changes()

    folder_entity = ayon_api.get_folder_by_id(
        project_name, folder_id, fields={"data"}
    )
    task_entity = ayon_api.get_task_by_id(
        project_name, task_id, fields={"data"}
    )
    # Data should not contain remved keys and should contain new keys
    assert folder_entity["data"] == {"key3": "value3"}
    assert task_entity["data"] == {"key4": "value4"}

    hub.delete_entity(root_folder)
    hub.delete_entity(folder)
    hub.delete_entity(task)
    hub.commit_changes()


def test_label_eq_name_on_entities_2(project_entity_fixture):
    """Test label that have same values as name on folder and task.

    When the entity has same name and label, the label should be set to None.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folder_type = project_entity_fixture["folderTypes"][-1]["name"]
    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    init_status_name = project_entity_fixture["statuses"][0]["name"]
    folder_id = uuid.uuid1().hex
    task_id = uuid.uuid1().hex
    folder = hub.add_new_folder(
        folder_type=folder_type,
        name="status_root_folder",
        entity_id=folder_id,
        status=init_status_name,
    )

    task_name = "my_task"
    task_label = "my_task"
    task = hub.add_new_task(
        task_type=task_type,
        name=task_name,
        label=task_label,
        folder_id=folder.id,
        entity_id=task_id,
        status=init_status_name,
    )
    hub.commit_changes()

    hub = EntityHub(project_name)
    folder = hub.get_or_fetch_entity_by_id(folder_id, {"folder"})
    task = hub.get_or_fetch_entity_by_id(task_id, {"task"})

    assert folder.status == init_status_name, (
        "Folder status set on create was not propagated"
    )
    assert task.status == init_status_name, (
        "Task status set on create was not propagated"
    )

    new_folder_status = None
    new_task_status = None
    for status in project_entity_fixture["statuses"]:
        status_name = status["name"]
        if not new_folder_status and folder.status != status_name:
            new_folder_status = status_name

        if not new_task_status and task.status != status_name:
            new_task_status = status_name

        if new_folder_status and new_task_status:
            break
    folder.status = new_folder_status
    task.status = new_task_status
    hub.commit_changes()

    folder_entity = ayon_api.get_folder_by_id(
        project_name, folder_id, fields={"status"}
    )
    task_entity = ayon_api.get_task_by_id(
        project_name, task_id, fields={"status"}
    )
    assert folder_entity["status"] == new_folder_status, (
        "Folder status set on update was not propagated"
    )
    assert task_entity["status"] == new_task_status, (
        "Task status set on update was not propagated"
    )
    with pytest.raises(ValueError):
        folder.status = "invalidStatusName1"

    with pytest.raises(ValueError):
        task.status = "invalidStatusName2"


    hub.delete_entity(folder)
    hub.delete_entity(task)
    hub.commit_changes()


@pytest.mark.parametrize(
    "folder_name, subfolder_name, num_of_subfolders",
    [
        ("entity_hub_test", "subfolder", 3),
    ]
)
def test_create_delete_with_duplicated_names(
    project_entity_fixture,
    folder_name,
    subfolder_name,
    num_of_subfolders
):
    """Creates two folders with duplicated names
    and delete one of them before commit.
    Exception should not be raised.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folder1 = hub.add_new_folder(folder_type="Folder", name=folder_name)

    subfolders = []
    for folder_number in range(num_of_subfolders):
        subfolder = hub.add_new_folder(
            folder_type="Folder",
            parent_id=folder1.id,
            name=f"{subfolder_name}{folder_number:03}"
        )
        subfolders.append(subfolder)
        hub.commit_changes()

        # create and delete folder with same name
        subfolder = hub.add_new_folder(
            folder_type="Folder",
            parent_id=folder1.id,
            name=f"{subfolder_name}{folder_number:03}"
        )
        hub.delete_entity(subfolder)
        hub.commit_changes()

    assert hub.get_folder_by_id(project_name, folder1.id) is not None

    for subfolder in subfolders:
        assert hub.get_folder_by_id(
            project_name,
            subfolder.id) is not None

    # clean up
    hub.delete_entity(folder1)
    hub.commit_changes()


# @pytest.mark.parametrize(
#     "folder_name",
#     [
#         ("entity_hub_folder1", ),
#     ]
# )
# def test_move_with_duplicated_names(folder_name):
#     """Test of moving folders with duplicated names to the same parent
#     folder for some time. Before the commit, everything is set correctly.
#     Creates two folders with subfolders
#     and switches the parent folders of subfolders.
#     """
#     e = EntityHub(PROJECT_NAME)
#
#     parent_folder = e.add_new_folder(folder_type="Folder", name=folder_name)
#     e.commit_changes()
#
#
#     folders = []
#     subfolders = []
#     for folder_number in range(2):
#         folder = e.add_new_folder(
#             folder_type="Folder",
#             name=f"test{folder_number:03}",
#             parent_id=parent_folder["id"]
#         )
#         folders.append(folder)
#
#         subfolder = e.add_new_folder(
#             folder_type="Folder",
#             name="duplicated",
#             parent_id=folder["id"]
#         )
#         subfolders.append(subfolder)
#     e.commit_changes()
#
#
#     # raises an exception (duplicated names)
#     """
#     # switch the parent folders
#     # - duplicated names exception shouldn't be raised
#     e.set_entity_parent(subfolders[0]["id"], folders[1]["id"])
#     e.set_entity_parent(subfolders[1]["id"], folders[0]["id"])
#
#     e.commit_changes()
#
#     # check if parent ids are switched
#     assert e.get_folder_by_id(
#             subfolders[1]["id"]
#         )["parent_id"] == folders[0]["id"]
#     assert e.get_folder_by_id(
#             subfolders[0]["id"]
#         )["parent_id"] == folders[1]["id"]
#
#     # move and delete -> duplicated names exception shouldn't be raised
#     e.set_entity_parent(subfolders[0]["id"], folders[0]["id"])
#     e.delete_entity(subfolders[1])
#
#     e.commit_changes()
#
#     # check if parent id is switched and the second folder is deleted
#     assert e.get_folder_by_id(
#             subfolders[0]["id"]
#         )["parent_id"] == folders[0]["id"]
#     assert e.get_folder_by_id(PROJECT_NAME, subfolders[1]["id"]) is None
#     """
#
#     # ------------------------------
#     e.delete_entity(parent_folder)
#     e.commit_changes()
#
#
# @pytest.mark.parametrize(
#     (
#         "parent_folder_name, folder_name, subfolder_name,"
#         " num_of_folders, num_of_subfolders"
#     ),
#     [
#         ("entity_hub_test", "folder", "subfolder", 2, 3),
#     ]
# )
# def test_large_move_of_folders__with_duplicated_names(
#     parent_folder_name,
#     folder_name,
#     subfolder_name,
#     num_of_folders,
#     num_of_subfolders
# ):
#     """Test of moving folders with duplicated names to the same parent
#     folder for some time. Before the commit, everything is set correctly.
#     """
#
#     # create the starting hierarchy
#     e = EntityHub(PROJECT_NAME)
#
#     parent_folder = e.add_new_folder(
#         folder_type="Folder",
#         name=parent_folder_name
#     )
#
#     folder_ids = []
#     for folder_number in range(num_of_folders):
#         folder = e.add_new_folder(
#             folder_type="Folder",
#             parent_id=parent_folder["id"],
#             name=f"{folder_name}{folder_number:03}"
#         )
#         folder_ids.append(folder["id"])
#
#     subfolder_ids = []
#     for folder_id in folder_ids:
#         for subfolder_number in range(num_of_subfolders):
#             subfolder = e.add_new_folder(
#                 folder_type="Folder",
#                 parent_id=folder_id,
#                 name=f"{subfolder_name}{subfolder_number:03}"
#             )
#             subfolder_ids.append(subfolder["id"])
#
#     e.commit_changes()
#
#     # raises exception - duplicated name under parent_id
#     """
#     # move all subfolders from one folder to the next one
#     for index, subfolder_id in enumerate(subfolder_ids):
#         # next folder (for last folder -> first folder)
#         new_parent_id = folder_ids[
#             (index // num_of_subfolders + 1) % num_of_folders
#         ]
#
#         # test for me, if new_parent_id is generated correctly
#         subfolder = e.get_folder_by_id(subfolder_id)
#         current_parent_id = subfolder["parent_id"]
#         assert new_parent_id != current_parent_id
#         e.set_entity_parent(subfolder_id, new_parent_id)
#
#     e.commit_changes()
#
#     # test if moved correctly
#     for index, subfolder_id in enumerate(subfolder_ids):
#         print("GET_FOLDERS =", get_folders(
#             PROJECT_NAME,
#             folder_ids=subfolder_id,
#             parent_ids=folder_ids[index // num_of_subfolders]))
#
#         assert get_folders(
#             PROJECT_NAME,
#             folder_ids=subfolder_id,
#             parent_ids=folder_ids[index // num_of_subfolders]) is None
#
#         assert get_folders(
#             PROJECT_NAME,
#             folder_ids=subfolder_id,
#             parent_ids=folder_ids[
#                 (index // num_of_subfolders + 1) % num_of_folders
#             ]
#         ) is not None
#         # assert subfolder_id not in my_get_folder_ids(
#         #     folder_ids[i // num_of_subfolders]
#         # )
#         # assert subfolder_id in my_get_folder_ids(
#         #     folder_ids[(i // num_of_subfolders + 1) % num_of_folders]
#         # )
#     """
#
#     # e.delete_entity(parent_folder)
#     # e.commit_changes()
#
#
# def test_move_tasks():
#     raise NotImplementedError()
#
#
# def test_duplicated_status_name():
#     e = EntityHub(PROJECT_NAME)
#
#     e.project_entity.statuses.create(
#         "test_status",
#         "TEST",
#         "blocked",
#         "play_arrow",
#         "#ff0000"
#     )
#
#     e.project_entity.statuses.create(
#         "test_status2",
#         "TEST2",
#         "blocked",
#         "play_arrow",
#         "#00ff00"
#     )
#
#     e.commit_changes()
#
#     status = e.project_entity.statuses.get("test_status")
#     status.name = "test_status2"
#
#     with pytest.raises(HTTPRequestError):
#         e.commit_changes()
#     # print(list(e.project_entity.statuses)[0])


# def test_rename_status(project_entity_fixture):
#     hub = EntityHub(project_entity_fixture["name"])

#     for status in hub.project_entity.statuses:
#         print(status.name)

# def test_task_types():
#     raise NotImplementedError()
#
# def test_status_color():
#     raise NotImplementedError()
#
# def test_status_order():
#     raise NotImplementedError()
#
# def test_status_icon():
#     raise NotImplementedError()


# def test_project_statuses(project_entity_fixture):
#     statuses = project_entity_fixture.get_statuses()
#     pass



@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("folder_name", TestProductData.names)
@pytest.mark.parametrize("product_name", TestProductData.names)
@pytest.mark.parametrize("product_type", TestProductData.product_types)
def test_create_delete_products(
    project_entity_fixture,
    folder_name,
    product_name,
    product_type
):
    """
    Test the creation and deletion of products within a project.

    Verifies:
        - the product is created and can be retrieved by its ID
        - the product name, type, and folder ID are set correctly
        - the product is deleted and cannot be retrieved by its ID
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    for num, folder_type in enumerate(project_entity_fixture["folderTypes"]):
        assert list(ayon_api.get_folders(
            project_name=project_name, folder_names=[folder_name]
        )) == []
        folder = hub.add_new_folder(
            name=f"{folder_name}{num:02}",
            folder_type=folder_type["name"],
        )

        hub.commit_changes()

        product = hub.add_new_product(
            name=product_name,
            product_type=product_type,
            folder_id=folder.id
        )

        hub.commit_changes()

        assert hub.get_product_by_id(product.id)
        assert product.get_name() == product_name
        assert product.get_product_type() == product_type
        assert product.get_folder_id() == folder.id

        hub.delete_entity(product)
        hub.commit_changes()

        assert hub.get_product_by_id(product.id) is None
        assert ayon_api.get_product_by_id(project_name, product.id) is None


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("folder_name", TestProductData.names)
@pytest.mark.parametrize("product_name", TestProductData.names)
@pytest.mark.parametrize("product_type", TestProductData.product_types)
def test_create_delete_products_bonus(
    project_entity_fixture,
    folder_name,
    product_name,
    product_type
):
    """
    Test the creation and deletion of products within a project.

    Verifies:
        - the product is created and can be retrieved by its ID
        - the product name, type, and folder ID are set correctly
        - the product is deleted with a new EntityHub and cannot be retrieved
            by its ID
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    products = []
    for num, folder_type in enumerate(project_entity_fixture["folderTypes"]):
        assert list(ayon_api.get_folders(
            project_name=project_name, folder_names=[folder_name]
        )) == []
        folder = hub.add_new_folder(
            name=f"{folder_name}{num:02}",
            folder_type=folder_type["name"],
        )

        hub.commit_changes()

        product = hub.add_new_product(
            name=product_name,
            product_type=product_type,
            folder_id=folder.id
        )

        hub.commit_changes()

        assert hub.get_product_by_id(product.id)
        assert product.get_name() == product_name
        assert product.get_product_type() == product_type
        assert product.get_folder_id() == folder.id

        products.append(product)

    # create new entity hub for same project and validate the changes
    # are propagated
    new_hub = EntityHub(project_name)

    for product in products:
        new_product = new_hub.get_product_by_id(product.id)
        assert new_product is not None
        assert new_product.get_name() == product_name
        assert new_product.get_product_type() == product_type

        new_hub.delete_entity(new_product)
        new_hub.commit_changes()

        assert ayon_api.get_product_by_id(
            project_name, new_product.id, fields={"id"}
        ) is None
        assert new_hub.get_product_by_id(new_product.id) is None


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("name", TestProductData.names)
def test_create_delete_folders(project_entity_fixture, name):
    """Tests the creation and deletion of folders within a project.

    Verifies:
        - A folder can be successfully created for each folder type specified
            in the project.
        - The created folder exists both locally (in `hub`) and remotely (via
            `ayon_api`) after committing changes.
        - The folder can be deleted, and its deletion is confirmed locally
            and remotely.

    """
    project_name = project_entity_fixture["name"]

    hub = EntityHub(project_name)

    for folder_type in project_entity_fixture["folderTypes"]:
        folder = hub.add_new_folder(
            folder_type=folder_type["name"],
            name=name,
        )

        hub.commit_changes()

        assert hub.get_folder_by_id(folder.id)
        assert ayon_api.get_folder_by_id(
            project_name, folder.id
        )

        hub.delete_entity(folder)
        hub.commit_changes()

        assert hub.get_folder_by_id(folder.id) is None
        assert ayon_api.get_folder_by_id(
            project_name, folder.id
        ) is None


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("name", TestProductData.names)
def test_create_delete_folders_bonus(project_entity_fixture, name):
    """Tests the creation, persistence, and deletion of multiple folders within
    a project.

    Verifies:
        - After creation, folders are accessible locally (via `hub`) and
            remotely (via `ayon_api`).
        - Folder persistence is confirmed using a new `EntityHub` instance to
            simulate a fresh session.
        - Folders can be deleted, and their deletion is reflected both locally
            and remotely.

    """
    project_name = project_entity_fixture["name"]

    hub = EntityHub(project_name)

    folders = []
    for num, folder_type in enumerate(project_entity_fixture["folderTypes"]):
        folder = hub.add_new_folder(
            folder_type=folder_type["name"],
            name=f"{name}{num:02}",
        )

        hub.commit_changes()

        assert hub.get_folder_by_id(folder.id)
        assert ayon_api.get_folder_by_id(
            project_name, folder.id
        )
        folders.append(folder)

    new_hub = EntityHub(project_name)

    for folder in folders:
        assert new_hub.get_folder_by_id(folder.id)
        assert ayon_api.get_folder_by_id(
            project_name, folder.id
        )

        new_hub.delete_entity(folder)
        new_hub.commit_changes()

        assert new_hub.get_folder_by_id(folder.id) is None
        assert ayon_api.get_folder_by_id(
            project_name, folder.id
        ) is None


test_version_numbers = [
    ([1, 2, 3, 4]),
    ([8, 10, 4, 5]),
]


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("version_numbers", test_version_numbers)
def test_create_delete_versions(project_entity_fixture, version_numbers):
    """Tests the creation and deletion of versions within a product hierarchy.

    Verifies:
        - A folder and product can be created as a prerequisite hierarchy.
        - Versions can be added to a product, with their IDs correctly
            reflected in the product's children.
        - Versions exist in the local `hub` after creation.
        - Versions can be successfully deleted, and their removal is confirmed
            both in the `hub` and in the product's children.

    """
    project_name = project_entity_fixture["name"]
    # prepare hierarchy
    folder_types = [
        type["name"] for type in project_entity_fixture["folderTypes"]
    ]
    hub = EntityHub(project_name)

    folder = hub.add_new_folder(
        folder_type=folder_types[0],
        name="test_folder",
    )

    product = hub.add_new_product(
        name="test_product",
        product_type="animation",
        folder_id=folder.id
    )

    assert product.get_children_ids() == set()

    # add
    versions = []
    for version in version_numbers:
        versions.append(
            hub.add_new_version(
                version,
                product.id
            )
        )

    hub.commit_changes()

    res = product.get_children_ids()

    assert len(versions) == len(res)
    for version in versions:
        assert hub.get_version_by_id(version.id)
        assert version.id in res

        # delete
        hub.delete_entity(version)
        hub.commit_changes()

        assert hub.get_version_by_id(version.id) is None
        assert ayon_api.get_version_by_id(project_name, version.id) is None


test_invalid_version_number = [
    ("a"),
    (None),
    ("my_version_number")
]


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("version_number", test_invalid_version_number)
def test_create_invalid_versions(project_entity_fixture, version_number):
    # prepare hierarchy
    folder_types = [
        type["name"] for type in project_entity_fixture["folderTypes"]
    ]
    hub = EntityHub(project_entity_fixture["name"])

    folder = hub.add_new_folder(
        folder_type=folder_types[0],
        name="test_folder",
    )

    product = hub.add_new_product(
        name="test_product",
        product_type="animation",
        folder_id=folder["id"]
    )

    assert product.get_children_ids() == set()

    hub.add_new_version(
        version_number,
        product["id"]
    )

    with pytest.raises(ayon_api.exceptions.FailedOperations):
        hub.commit_changes()


@pytest.mark.usefixtures("clean_project")
def test_change_status_on_version(project_entity_fixture):
    folder_types = [
        type["name"] for type in project_entity_fixture["folderTypes"]
    ]
    status_names = [
        status["name"]
        for status in project_entity_fixture["statuses"]
        if "version" in status["scope"]
    ]

    hub = EntityHub(project_entity_fixture["name"])

    folder = hub.add_new_folder(
        folder_type=folder_types[0],
        name="test_folder",
    )

    product = hub.add_new_product(
        name="test_product",
        product_type="animation",
        folder_id=folder["id"]
    )

    version = hub.add_new_version(
        1,
        product["id"]
    )

    hub.commit_changes

    for status_name in status_names:
        version.set_status(status_name)
        hub.commit_changes()

        assert version.get_status() == status_name


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("version", test_version_numbers)
def test_set_invalid_status_on_version(project_entity_fixture, version):
    folder_types = [
        type["name"] for type in project_entity_fixture["folderTypes"]
    ]
    valid_names = [
        status["name"]
        for status in project_entity_fixture["statuses"]
        if "version" in status["scope"]
    ]
    invalid_names = [
        status["name"]
        for status in project_entity_fixture["statuses"]
        if "version" not in status["scope"]
    ]

    hub = EntityHub(project_entity_fixture["name"])

    folder = hub.add_new_folder(
        folder_type=folder_types[0],
        name="test_folder",
    )

    product = hub.add_new_product(
        name="test_product",
        product_type="animation",
        folder_id=folder["id"]
    )

    version = hub.add_new_version(
        1,
        product["id"]
    )

    # test on version without status
    for status_name in invalid_names:
        with pytest.raises(ValueError):
            version.set_status(status_name)
            hub.commit_changes()

        assert version.get_status() == UNKNOWN_VALUE

    # test valid statuses
    for status_name in valid_names:
        version.set_status(status_name)
        hub.commit_changes()

        assert version.get_status() == status_name

    current_status = version.get_status()

    # test on version with status
    for status_name in invalid_names:
        with pytest.raises(ValueError):
            version.set_status(status_name)
            hub.commit_changes()

        assert version.get_status() == current_status


test_tags = [
    (["tag1", "tag2", "tag3"]),
    (["tag4"]),
    (["tag5", "tag6"]),
]


@pytest.mark.usefixtures("clean_project")
@pytest.mark.parametrize("tags", test_tags)
def test_set_tag_on_version(project_entity_fixture, tags):
    folder_types = [
        type["name"] for type in project_entity_fixture["folderTypes"]
    ]


    hub = EntityHub(project_entity_fixture["name"])

    folder = hub.add_new_folder(
        folder_type=folder_types[0],
        name="test_folder",
    )

    product = hub.add_new_product(
        name="test_product",
        product_type="animation",
        folder_id=folder["id"]
    )

    version = hub.add_new_version(
        1,
        product["id"]
    )

    assert version.get_tags() == []

    for tag in tags:
        version.set_tags([tag])
        hub.commit_changes()

        assert tag in version.get_tags()


# def test_set_invalid_tag_on_version():
#     raise NotImplementedError()


test_statuses = [
    ("status1"),
    ("status2"),
    ("status3"),
]

test_icon = [
    ("arrow_forward"),
    ("expand_circle_down"),
    ("done_outline"),
]

test_color = [
    ("#ff0000"),
    ("#00ff00"),
    ("#0000ff"),
]


@pytest.mark.parametrize("status_name", test_statuses)
@pytest.mark.parametrize("icon_name", test_icon)
@pytest.mark.parametrize("color", test_color)
def test_status_definition_on_project(
    project_entity_fixture,
    status_name,
    icon_name,
    color
):
    hub = EntityHub(project_entity_fixture["name"])
    statuses = hub.project_entity.get_statuses()

    # create status
    statuses.create(
        name=status_name,
        icon=icon_name,
        color=color
    )
    assert status_name == statuses.get(status_name).get_name()
    assert icon_name == statuses.get(status_name).get_icon()
    assert color == statuses.get(status_name).get_color()

    # delete status
    statuses.remove_by_name(status_name)
    assert statuses.get(status_name) is None


def test_status_definition_on_project_with_invalid_values(
        project_entity_fixture
):
    hub = EntityHub(project_entity_fixture["name"])
    statuses = hub.project_entity.get_statuses()

    # invalid color
    with pytest.raises(ValueError):
        statuses.create(
            name="status2",
            icon="arrow_forward",
            color="invalid_color"
        )

    # invalid name
    with pytest.raises(ValueError):
        statuses.create(
            name="&_invalid_name",
            icon="invalid_icon",
            color="invalid_color"
        )
