"""Tests of project related server API methods.

Covers anatomy presets, project anatomy, project bundle, root overrides,
entity URIs, project files, folder search, entity grouping and entity
and project thumbnails.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_SERVER_URL and AYON_API_KEY in your
environment. Tests expect to run as an admin user.

"""
import os
import uuid

import pytest

from ayon_api import (
    create_folder,
    create_project,
    create_task,
    delete_folder,
    delete_project,
    delete_project_anatomy_preset,
    delete_project_file,
    delete_task,
    get_anatomy_schema,
    get_built_in_anatomy_preset,
    get_bundles,
    get_entity_groups,
    get_folder_by_id,
    get_folder_thumbnail,
    get_project,
    get_project_anatomy,
    get_project_anatomy_preset,
    get_project_anatomy_presets,
    get_project_bundle,
    get_project_entity_uris,
    get_project_file_info,
    get_project_root_overrides,
    get_project_stats,
    get_project_tags,
    get_project_thumbnail,
    get_server_version_tuple,
    get_task_by_id,
    get_task_thumbnail,
    rename_project,
    rename_project_anatomy_preset,
    resolve_uris,
    save_project_anatomy_preset,
    search_folders,
    set_entity_thumbnail,
    set_entity_thumbnail_from_stream,
    set_primary_anatomy_preset,
    set_project_anatomy,
    set_project_bundle,
    set_project_root_overrides,
    set_project_thumbnail,
    set_project_thumbnail_from_stream,
    unset_primary_anatomy_preset,
    unset_project_bundle,
    upload_project_file,
)
from ayon_api.exceptions import HTTPRequestError

from requests.exceptions import HTTPError

from .conftest import project_entity_fixture, project_name_fixture


RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
IMAGE_PATH = os.path.join(RESOURCES_DIR, "ayon-symbol.png")
PROJECT_THUMBNAIL_ID = "0" * 32


def _unique_suffix() -> str:
    return uuid.uuid4().hex[:12]


def _normalize_id(entity_id):
    if entity_id is None:
        return None
    return entity_id.replace("-", "")


def _require_server_version(version):
    if get_server_version_tuple() < version:
        version_str = ".".join(str(part) for part in version)
        pytest.skip(f"Requires AYON server {version_str} or newer.")


def _get_primary_preset_name():
    for preset in get_project_anatomy_presets():
        if preset.get("primary"):
            return preset["name"]
    return None


def _get_preset_names():
    return {preset["name"] for preset in get_project_anatomy_presets()}


# --- Fixtures ---
@pytest.fixture
def temp_project():
    """Temporary project created and deleted by the test.

    Yields a dictionary with 'name' and 'code' keys. A test that renames
        the project must update the 'name' key so the teardown removes
        the correct project.

    """
    suffix = _unique_suffix()
    holder = {
        "name": f"AYONApiTmp_{suffix}",
        "code": f"tmp{suffix[:8]}",
    }
    create_project(holder["name"], holder["code"])
    try:
        yield holder
    finally:
        if get_project(holder["name"]):
            delete_project(holder["name"])


@pytest.fixture
def anatomy_preset_names():
    """Unique anatomy preset names, the presets are removed on teardown.

    Original primary preset is restored on teardown.

    """
    suffix = _unique_suffix()
    names = [f"test_preset_{suffix}", f"test_preset_renamed_{suffix}"]
    orig_primary = _get_primary_preset_name()
    try:
        yield names
    finally:
        for name in names:
            delete_project_anatomy_preset(name)

        current_primary = _get_primary_preset_name()
        if current_primary != orig_primary:
            # Preset name '_' unsets any primary preset
            set_primary_anatomy_preset(orig_primary or "_")


@pytest.fixture
def test_hierarchy(project_entity_fixture):
    """Folder with a task in the shared test project.

    Folder has a unique tag. Both entities are removed on teardown.

    """
    project_name = project_entity_fixture["name"]
    suffix = _unique_suffix()
    folder_name = f"projects_api_folder_{suffix}"
    task_name = f"projects_api_task_{suffix}"
    tag = f"projects_api_tag_{suffix}"
    task_type = project_entity_fixture["taskTypes"][0]["name"]

    folder_id = create_folder(
        project_name,
        folder_name,
        folder_type="Folder",
        tags=[tag],
    )
    task_id = None
    try:
        task_id = create_task(
            project_name,
            task_name,
            task_type,
            folder_id,
        )
        yield {
            "project_name": project_name,
            "folder_id": folder_id,
            "folder_name": folder_name,
            "task_id": task_id,
            "task_name": task_name,
            "task_type": task_type,
            "tag": tag,
        }
    finally:
        if task_id is not None:
            delete_task(project_name, task_id)
        delete_folder(project_name, folder_id, force=True)


# --- Anatomy ---
def test_get_anatomy_schema():
    """Anatomy schema is a JSON schema describing the anatomy model."""
    schema = get_anatomy_schema()
    assert isinstance(schema, dict)
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    for key in ("roots", "templates", "attributes", "statuses"):
        assert key in properties


def test_anatomy_preset_lifecycle(anatomy_preset_names):
    """Save, rename, set/unset primary and delete an anatomy preset.

    Verifies:
        - Saved preset is listed and its values are stored.
        - Renamed preset is listed only under the new name.
        - Preset can be marked as primary and the flag can be removed.
        - Deleted preset is no longer listed.

    """
    preset_name, new_preset_name = anatomy_preset_names

    preset = get_built_in_anatomy_preset()
    root_path = f"C:/ayon_api_test/{preset_name}"
    preset["roots"][0]["windows"] = root_path

    save_project_anatomy_preset(preset_name, preset)
    assert preset_name in _get_preset_names()
    stored = get_project_anatomy_preset(preset_name)
    assert stored["roots"][0]["windows"] == root_path

    # Update existing preset
    updated_root_path = f"{root_path}_updated"
    preset["roots"][0]["windows"] = updated_root_path
    save_project_anatomy_preset(preset_name, preset)
    stored = get_project_anatomy_preset(preset_name)
    assert stored["roots"][0]["windows"] == updated_root_path

    rename_project_anatomy_preset(preset_name, new_preset_name)
    preset_names = _get_preset_names()
    assert preset_name not in preset_names
    assert new_preset_name in preset_names
    stored = get_project_anatomy_preset(new_preset_name)
    assert stored["roots"][0]["windows"] == updated_root_path

    set_primary_anatomy_preset(new_preset_name)
    assert _get_primary_preset_name() == new_preset_name
    primary = get_project_anatomy_preset()
    assert primary["roots"][0]["windows"] == updated_root_path

    unset_primary_anatomy_preset(new_preset_name)
    assert _get_primary_preset_name() is None

    delete_project_anatomy_preset(new_preset_name)
    assert new_preset_name not in _get_preset_names()


def test_rename_missing_anatomy_preset_fails(anatomy_preset_names):
    """Renaming a preset that does not exist raises an error."""
    preset_name, new_preset_name = anatomy_preset_names
    with pytest.raises(HTTPRequestError):
        rename_project_anatomy_preset(preset_name, new_preset_name)


def test_save_builtin_anatomy_preset_fails():
    """Built-in preset cannot be overridden."""
    preset = get_built_in_anatomy_preset()
    with pytest.raises(HTTPRequestError):
        save_project_anatomy_preset("__builtin__", preset)


# --- Project ---
def test_rename_project(temp_project):
    """Rename a temporary project including its code."""
    _require_server_version((1, 15, 0))

    old_name = temp_project["name"]
    suffix = _unique_suffix()
    new_name = f"AYONApiTmpRenamed_{suffix}"
    new_code = f"ren{suffix[:8]}"

    rename_project(old_name, new_name, new_code)
    temp_project["name"] = new_name

    assert get_project(old_name) is None
    project = get_project(new_name)
    assert project is not None
    assert project["name"] == new_name
    assert project["code"] == new_code

    # Rename without code change keeps the code
    newer_name = f"AYONApiTmpRenamed2_{suffix}"
    rename_project(new_name, newer_name)
    temp_project["name"] = newer_name

    project = get_project(newer_name)
    assert project is not None
    assert project["code"] == new_code


def test_get_project_anatomy(project_entity_fixture):
    """Project anatomy is returned in anatomy preset format."""
    project_name = project_entity_fixture["name"]
    anatomy = get_project_anatomy(project_name)

    for key in ("roots", "templates", "attributes", "statuses"):
        assert key in anatomy

    root_names = {root["name"] for root in anatomy["roots"]}
    assert root_names == set(project_entity_fixture["config"]["roots"])


def test_set_project_anatomy(temp_project):
    """Changed project anatomy is stored on the project."""
    project_name = temp_project["name"]
    anatomy = get_project_anatomy(project_name)

    new_fps = 37.0
    if anatomy["attributes"].get("fps") == new_fps:
        new_fps = 41.0
    anatomy["attributes"]["fps"] = new_fps

    root_path = f"C:/ayon_api_test/{project_name}"
    anatomy["roots"][0]["windows"] = root_path
    root_name = anatomy["roots"][0]["name"]

    set_project_anatomy(project_name, anatomy)

    stored = get_project_anatomy(project_name)
    assert stored["attributes"]["fps"] == new_fps
    assert stored["roots"][0]["windows"] == root_path

    project = get_project(project_name)
    assert project["attrib"]["fps"] == new_fps
    assert project["config"]["roots"][root_name]["windows"] == root_path


def test_get_project_stats(test_hierarchy):
    """Project statistics contain counts of entities."""
    project_name = test_hierarchy["project_name"]
    stats = get_project_stats(project_name)

    counts = stats["counts"]
    assert set(counts) == {
        "folders",
        "products",
        "versions",
        "representations",
        "tasks",
    }
    for value in counts.values():
        assert isinstance(value, int)
    assert counts["folders"] >= 1
    assert counts["tasks"] >= 1


def test_get_project_tags(test_hierarchy):
    """Tags used on project entities are returned by entity type."""
    project_name = test_hierarchy["project_name"]
    tags = get_project_tags(project_name)

    assert set(tags) == {
        "folders",
        "tasks",
        "products",
        "versions",
        "representations",
        "workfiles",
    }
    assert test_hierarchy["tag"] in tags["folders"]
    assert test_hierarchy["tag"] not in tags["tasks"]


def test_project_bundle(temp_project):
    """Freeze and unfreeze project bundle of a temporary project.

    An empty addons mapping is used so no addon settings are changed.

    """
    project_name = temp_project["name"]
    variant = "production"
    bundle_name = f"__project__{project_name}__{variant}"
    has_production_bundle = bool(get_bundles().get("productionBundle"))

    if has_production_bundle:
        bundle_info = get_project_bundle(project_name, variant=variant)
        for key in (
            "addons",
            "addonMetadata",
            "installerOptions",
            "dependencyPackageOptions",
        ):
            assert key in bundle_info
    else:
        # Information can't be received without production bundle
        with pytest.raises(HTTPRequestError):
            get_project_bundle(project_name, variant=variant)

    try:
        set_project_bundle(project_name, {}, variant=variant)

        project = get_project(project_name)
        assert project["data"]["bundle"][variant] == bundle_name

        if has_production_bundle:
            bundle_info = get_project_bundle(project_name, variant=variant)
            # All addons are disabled by the frozen project bundle
            for addon_version in bundle_info["addons"].values():
                assert addon_version == "__disable__"

    finally:
        unset_project_bundle(project_name, variant=variant)

    project = get_project(project_name)
    assert variant not in project["data"].get("bundle", {})


def test_set_project_root_overrides(project_entity_fixture):
    """Set and remove root overrides of a site for the logged user.

    Uses a unique site id that is not used by any real site.

    """
    project_name = project_entity_fixture["name"]
    root_name = next(iter(project_entity_fixture["config"]["roots"]))
    site_id = f"ayon-api-test-site-{_unique_suffix()}"
    root_path = f"C:/ayon_api_test/{site_id}"

    try:
        set_project_root_overrides(
            project_name, site_id, {root_name: root_path}
        )
        overrides = get_project_root_overrides(project_name)
        assert overrides[site_id] == {root_name: root_path}

        # Empty value removes the root override, which removes all
        #   overrides of the site
        set_project_root_overrides(project_name, site_id, {root_name: None})
        overrides = get_project_root_overrides(project_name)
        assert site_id not in overrides

    finally:
        set_project_root_overrides(project_name, site_id, {})

    assert site_id not in get_project_root_overrides(project_name)


def test_get_project_entity_uris(test_hierarchy):
    """URIs of folder and task are built from their path."""
    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]
    task_id = test_hierarchy["task_id"]
    folder_uri = (
        f"ayon+entity://{project_name}/{test_hierarchy['folder_name']}"
    )
    task_uri = f"{folder_uri}?task={test_hierarchy['task_name']}"

    folder_uris = get_project_entity_uris(
        project_name, "folder", [folder_id]
    )
    assert len(folder_uris) == 1
    assert _normalize_id(folder_uris[0]["id"]) == folder_id
    assert folder_uris[0]["uri"] == folder_uri

    task_uris = get_project_entity_uris(project_name, "task", {task_id})
    assert len(task_uris) == 1
    assert _normalize_id(task_uris[0]["id"]) == task_id
    assert task_uris[0]["uri"] == task_uri

    assert get_project_entity_uris(project_name, "folder", []) == []


def test_resolve_uris(test_hierarchy):
    """Resolve folder and task URIs back to entity ids."""
    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]
    task_id = test_hierarchy["task_id"]
    folder_uri = f"ayon://{project_name}/{test_hierarchy['folder_name']}"
    task_uri = f"{folder_uri}?task={test_hierarchy['task_name']}"
    missing_uri = f"{folder_uri}_missing"

    result = resolve_uris([folder_uri, task_uri, missing_uri])
    assert [item["uri"] for item in result] == [
        folder_uri, task_uri, missing_uri
    ]
    folder_result, task_result, missing_result = result

    assert not folder_result.get("error")
    assert len(folder_result["entities"]) == 1
    folder_entity = folder_result["entities"][0]
    assert folder_entity["projectName"] == project_name
    assert folder_entity["target"] == "folder"
    assert _normalize_id(folder_entity["folderId"]) == folder_id

    assert not task_result.get("error")
    assert len(task_result["entities"]) == 1
    task_entity = task_result["entities"][0]
    assert task_entity["target"] == "task"
    assert _normalize_id(task_entity["folderId"]) == folder_id
    assert _normalize_id(task_entity["taskId"]) == task_id

    assert missing_result["entities"] == []

    path_only_result = resolve_uris([folder_uri], path_only=True)
    assert len(path_only_result) == 1
    assert len(path_only_result[0]["entities"]) == 1
    # Only file path is returned which is not available for folders
    assert "folderId" not in path_only_result[0]["entities"][0]


def test_resolve_uris_invalid():
    """Invalid URI and unknown project are reported as errors."""
    missing_project = f"AYONApiMissing_{_unique_suffix()}"
    invalid_uri = "invalid://project/path"
    missing_uri = f"ayon://{missing_project}/folder"

    result = resolve_uris([invalid_uri, missing_uri])
    assert len(result) == 2
    invalid_result, missing_result = result
    assert invalid_result["uri"] == invalid_uri
    assert invalid_result["error"]
    assert missing_result["uri"] == missing_uri
    assert missing_project in missing_result["error"]


def test_get_project_file_info(project_entity_fixture):
    """Uploaded project file information is returned."""
    project_name = project_entity_fixture["name"]
    filename = f"projects_api_{_unique_suffix()}.png"

    response = upload_project_file(
        project_name,
        IMAGE_PATH,
        filename=filename,
        content_type="image/png",
    )
    file_id = response.json()["id"]
    try:
        file_info = get_project_file_info(project_name, file_id)
        assert file_info["size"] == os.path.getsize(IMAGE_PATH)
        assert file_info["filename"] == filename
        assert file_info["contentType"] == "image/png"

    finally:
        delete_project_file(project_name, file_id)

    with pytest.raises(HTTPRequestError):
        get_project_file_info(project_name, file_id)


# --- Folders ---
def test_search_folders(test_hierarchy):
    """Search folders by text and by filters on folders and tasks."""
    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]
    folder_name = test_hierarchy["folder_name"]
    task_name = test_hierarchy["task_name"]

    assert search_folders(
        project_name, folder_search=folder_name
    ) == [folder_id]

    assert search_folders(project_name, task_search=task_name) == [folder_id]

    folder_filter = {
        "conditions": [
            {"key": "name", "value": folder_name, "operator": "eq"},
        ],
        "operator": "and",
    }
    assert search_folders(
        project_name, folder_filter=folder_filter
    ) == [folder_id]

    task_filter = {
        "conditions": [
            {"key": "name", "value": task_name, "operator": "eq"},
        ],
        "operator": "and",
    }
    assert search_folders(project_name, task_filter=task_filter) == [
        folder_id
    ]

    # Folder name does not match task conditions
    assert search_folders(project_name, task_search=folder_name) == []
    assert search_folders(
        project_name, folder_search=f"{folder_name}_missing"
    ) == []


def test_search_folders_global_search(test_hierarchy):
    """Global search matches folders and folders of matching tasks."""
    _require_server_version((1, 15, 4))

    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]

    assert search_folders(
        project_name, search=test_hierarchy["folder_name"]
    ) == [folder_id]
    assert search_folders(
        project_name, search=test_hierarchy["task_name"]
    ) == [folder_id]


def test_get_entity_groups(test_hierarchy, project_entity_fixture):
    """Group folders by folder type and tasks by task type."""
    project_name = test_hierarchy["project_name"]

    result = get_entity_groups(project_name, "folder", "folderType")
    assert result["key"] == "folderType"
    assert result["entityType"] == "folder"
    groups_by_value = {group["value"]: group for group in result["groups"]}
    assert groups_by_value["Folder"]["count"] >= 1
    for group in result["groups"]:
        assert group["count"] > 0

    result = get_entity_groups(
        project_name, "folder", "folderType", empty=True
    )
    group_values = {group["value"] for group in result["groups"]}
    folder_type_names = {
        folder_type["name"]
        for folder_type in project_entity_fixture["folderTypes"]
    }
    assert folder_type_names <= group_values

    result = get_entity_groups(project_name, "task", "taskType")
    assert result["entityType"] == "task"
    groups_by_value = {group["value"]: group for group in result["groups"]}
    assert groups_by_value[test_hierarchy["task_type"]]["count"] >= 1


def test_get_entity_groups_invalid_key(project_entity_fixture):
    """Invalid grouping key raises an error."""
    with pytest.raises(HTTPRequestError):
        get_entity_groups(
            project_entity_fixture["name"], "folder", "invalidKey"
        )


# --- Thumbnails ---
def test_set_entity_thumbnail(test_hierarchy):
    """Upload thumbnail of a folder from a file path."""
    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]

    thumbnail_id = set_entity_thumbnail(
        project_name, "folder", folder_id, IMAGE_PATH
    )
    assert thumbnail_id

    folder = get_folder_by_id(
        project_name, folder_id, fields={"id", "thumbnailId"}
    )
    assert _normalize_id(folder["thumbnailId"]) == thumbnail_id

    thumbnail = get_folder_thumbnail(project_name, folder_id)
    assert thumbnail.is_valid
    assert _normalize_id(thumbnail.id) == thumbnail_id
    assert thumbnail.content


def test_set_entity_thumbnail_from_stream(test_hierarchy):
    """Upload thumbnail of a task from a byte stream."""
    project_name = test_hierarchy["project_name"]
    task_id = test_hierarchy["task_id"]

    with open(IMAGE_PATH, "rb") as stream:
        thumbnail_id = set_entity_thumbnail_from_stream(
            project_name, "task", task_id, stream
        )
    assert thumbnail_id

    task = get_task_by_id(
        project_name, task_id, fields={"id", "thumbnailId"}
    )
    assert _normalize_id(task["thumbnailId"]) == thumbnail_id

    thumbnail = get_task_thumbnail(project_name, task_id)
    assert thumbnail.is_valid
    assert _normalize_id(thumbnail.id) == thumbnail_id
    assert thumbnail.content


def test_set_entity_thumbnail_invalid(test_hierarchy):
    """Missing file is refused before request, unsupported type by server."""
    project_name = test_hierarchy["project_name"]
    folder_id = test_hierarchy["folder_id"]

    with pytest.raises(ValueError):
        set_entity_thumbnail(
            project_name,
            "folder",
            folder_id,
            os.path.join(RESOURCES_DIR, "missing-image.png"),
        )

    with pytest.raises(HTTPError):
        set_entity_thumbnail(
            project_name, "product", folder_id, IMAGE_PATH
        )


def test_project_thumbnail(temp_project):
    """Set project thumbnail from file path and from stream."""
    _require_server_version((1, 15, 0))

    project_name = temp_project["name"]

    # Project without thumbnail returns placeholder which is not valid
    thumbnail = get_project_thumbnail(project_name)
    assert not thumbnail.is_valid

    thumbnail_id = set_project_thumbnail(project_name, IMAGE_PATH)
    assert thumbnail_id == PROJECT_THUMBNAIL_ID
    thumbnail = get_project_thumbnail(project_name)
    assert thumbnail.is_valid
    assert thumbnail.id == PROJECT_THUMBNAIL_ID
    assert thumbnail.content
    assert thumbnail.content_type == "image/png"

    with open(IMAGE_PATH, "rb") as stream:
        thumbnail_id = set_project_thumbnail_from_stream(
            project_name, stream
        )
    assert thumbnail_id == PROJECT_THUMBNAIL_ID
    thumbnail = get_project_thumbnail(project_name)
    assert thumbnail.is_valid
    assert thumbnail.id == PROJECT_THUMBNAIL_ID
    assert thumbnail.content

    with pytest.raises(ValueError):
        set_project_thumbnail(
            project_name,
            os.path.join(RESOURCES_DIR, "missing-image.png"),
        )
