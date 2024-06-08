import uuid

import pytest

import ayon_api
from ayon_api.entity_hub import EntityHub

from .conftest import project_entity_fixture


def test_rename_status(project_entity_fixture):
    # Change statuses - add prefix 'new_'
    project_name = project_entity_fixture["name"]
    e = EntityHub(project_name)
    status_mapping = {}
    for status in e.project_entity.statuses:
        orig_name = status.name
        new_name = f"new_{orig_name}"
        status_mapping[new_name] = orig_name
        status.name = new_name
    e.commit_changes()

    # Create new entity hub for same project and validate the changes
    #   are propagated
    e = EntityHub(project_name)
    statuses_by_name = {
        status.name: status
        for status in e.project_entity.statuses
    }
    if set(statuses_by_name) != set(status_mapping.keys()):
        raise AssertionError("Statuses were not renamed correctly.")

    # Change statuses back
    for status in e.project_entity.statuses:
        status.name = status_mapping[status.name]
    e.commit_changes()


@pytest.mark.parametrize(
    "folder_name, subfolder_name, folders_count",
    [
        ("entity_hub_simple_test", "subfolder", 3),
    ]
)
def test_simple_operations(
    project_entity_fixture,
    folder_name,
    subfolder_name,
    folders_count
):
    """Test of simple operations with folders - create, move, delete.
    """
    project_name = project_entity_fixture["name"]
    e = EntityHub(project_name)

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

    # delete subfolders
    for subfolder in subfolders:
        e.delete_entity(e.get_entity_by_id(subfolder["id"]))
        e.commit_changes()
        assert e.get_entity_by_id(subfolder["id"]) is None

    # delete folders
    for folder in folders:
        e.delete_entity(e.get_entity_by_id(folder["id"]))
        e.commit_changes()
        assert e.get_entity_by_id(folder["id"]) is None


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
        folder_type, name="custom_values_root_folder"
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
        folder_type,
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
        task_type,
        name=task_name,
        label=task_label,
        parent_id=folder.id,
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


def test_label_eq_name_on_entities(project_entity_fixture):
    """Test label that have same values as name on folder and task.

    When the entity has same name and label, the label should be set to None.
    """
    project_name = project_entity_fixture["name"]
    hub = EntityHub(project_name)

    folder_type = project_entity_fixture["folderTypes"][-1]["name"]
    root_folder = hub.add_new_folder(
        folder_type, name="label_eq_name_root_folder"
    )

    folder_id = uuid.uuid1().hex
    folder_name = "a_folder"
    folder_label = "a_folder"

    task_id = uuid.uuid1().hex
    task_name = "my_task"
    task_label = "my_task"

    folder = hub.add_new_folder(
        folder_type,
        name=folder_name,
        label=folder_label,
        parent_id=root_folder.id,
        entity_id=folder_id,
    )

    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    task = hub.add_new_task(
        task_type,
        name=task_name,
        label=task_label,
        parent_id=folder.id,
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
        folder_type, name="data_changes_on_entities"
    )

    folder_id = uuid.uuid1().hex
    folder_name = "a_folder"
    folder_data = {"key1": "value1"}

    task_id = uuid.uuid1().hex
    task_name = "my_task"
    task_data = {"key2": "value2"}

    folder = hub.add_new_folder(
        folder_type,
        name=folder_name,
        data=folder_data,
        parent_id=root_folder.id,
        entity_id=folder_id,
    )

    task_type = project_entity_fixture["taskTypes"][-1]["name"]
    task = hub.add_new_task(
        task_type,
        name=task_name,
        data=task_data,
        parent_id=folder.id,
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

    folder = hub.get_or_query_entity_by_id(folder_id, {"folder"})
    folder.data["key3"] = "value3"
    folder.data.pop("key1")

    task = hub.get_or_query_entity_by_id(task_id, {"task"})
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


def test_label_eq_name_on_entities(project_entity_fixture):
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
        folder_type,
        name="status_root_folder",
        entity_id=folder_id,
        status=init_status_name,
    )

    task_name = "my_task"
    task_label = "my_task"
    task = hub.add_new_task(
        task_type,
        name=task_name,
        label=task_label,
        parent_id=folder.id,
        entity_id=task_id,
        status=init_status_name,
    )
    hub.commit_changes()

    hub = EntityHub(project_name)
    folder = hub.get_or_query_entity_by_id(folder_id, {"folder"})
    task = hub.get_or_query_entity_by_id(task_id, {"task"})

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
    e = EntityHub(project_name)

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

    assert e.get_folder_by_id(project_name, folder1["id"]) is not None

    for subfolder in subfolders:
        assert e.get_folder_by_id(
            project_name,
            subfolder["id"]) is not None

    # clean up
    e.delete_entity(folder1)
    e.commit_changes()


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
#     parent_folder = e.add_new_folder("Folder", name=folder_name)
#     e.commit_changes()
#
#
#     folders = []
#     subfolders = []
#     for folder_number in range(2):
#         folder = e.add_new_folder(
#             "Folder",
#             name=f"test{folder_number:03}",
#             parent_id=parent_folder["id"]
#         )
#         folders.append(folder)
#
#         subfolder = e.add_new_folder(
#             "Folder",
#             name="duplicated",
#             parent_id=folder["id"]
#         )
#         subfolders.append(subfolder)
#     e.commit_changes()
#
#
#     # raises an exception (duplicated names)
#     """
#     # switch the parent folders - duplicated names exception shouldn't be raised
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
#     "parent_folder_name, folder_name, subfolder_name, num_of_folders, num_of_subfolders",
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
#         "Folder",
#         name=parent_folder_name
#     )
#
#     folder_ids = []
#     for folder_number in range(num_of_folders):
#         folder = e.add_new_folder(
#             "Folder",
#             parent_id=parent_folder["id"],
#             name=f"{folder_name}{folder_number:03}"
#         )
#         folder_ids.append(folder["id"])
#
#     subfolder_ids = []
#     for folder_id in folder_ids:
#         for subfolder_number in range(num_of_subfolders):
#             subfolder = e.add_new_folder(
#                 "Folder",
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
#         new_parent_id = folder_ids[(index // num_of_subfolders + 1) % num_of_folders]
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
#             parent_ids=folder_ids[(index // num_of_subfolders + 1) % num_of_folders]) is not None
#         # assert subfolder_id not in my_get_folder_ids(folder_ids[i // num_of_subfolders])
#         # assert subfolder_id in my_get_folder_ids(folder_ids[(i // num_of_subfolders + 1) % num_of_folders])
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
#
#
# def test_rename_status():
#     e = EntityHub(PROJECT_NAME)
#
#     for status in e.project_entity.statuses:
#         print(status.name)
#
#
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
