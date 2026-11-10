"""Tests of reviewables, task assignees and entity list order endpoints.

Tests run against a real AYON server and use the test project created
by 'project_entity_fixture'. Every entity created by the tests is
removed at the end.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_SERVER_URL and AYON_API_KEY in
your environment.

"""
import os
import uuid

import pytest

from ayon_api import (
    assign_users_to_task,
    create_entity_list,
    create_entity_list_item,
    create_folder,
    create_product,
    create_task,
    create_version,
    delete_entity_list,
    delete_folder,
    get_entity_list_rest,
    get_folder_reviewables,
    get_product_reviewables,
    get_reviewables,
    get_server_version_tuple,
    get_task_by_id,
    get_task_reviewables,
    get_user,
    get_version_reviewables,
    materialize_entity_list,
    set_entity_list_items_order,
    sort_version_reviewables,
    update_reviewable,
    upload_reviewable,
)
from ayon_api.exceptions import HTTPRequestError

from .conftest import project_entity_fixture  # noqa: F401

REVIEWABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "resources",
    "ayon-symbol.png",
)


def _unique_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _find_status(project_entity, done):
    """Find project status usable on versions.

    Args:
        project_entity (dict[str, Any]): Project entity.
        done (bool): Look for status with 'done' state.

    Returns:
        Optional[str]: Status name or None if not found.

    """
    for status in project_entity["statuses"]:
        scope = status.get("scope")
        if scope and "version" not in scope:
            continue
        if (status.get("state") == "done") is done:
            return status["name"]
    return None


def _upload(project_name, version_id, label):
    response = upload_reviewable(
        project_name, version_id, REVIEWABLE_PATH, label=label
    )
    response.raise_for_status()
    return response.json()


def _get_filtered(func, *args, **kwargs):
    """Call single entity reviewables getter with 'latest' filter.

    AYON server 1.16.x builds SQL condition 'versions.id = $1AND ...'
        (missing space) for single entity endpoints with 'latest' or
        'latest_done', which PostgreSQL 15+ refuses. Mark the test as
        expected failure in that case instead of failing on server bug.

    """
    try:
        return func(*args, **kwargs)
    except HTTPRequestError as exc:
        response = exc.response
        if response is not None and response.status_code >= 500:
            pytest.xfail(
                "Server fails on 'latest' filter of single entity"
                f" reviewables endpoint: {exc}"
            )
        raise


def _reviewables_by_version_id(versions):
    return {
        version["id"]: version["reviewables"]
        for version in versions
    }


@pytest.fixture
def folder_fixture(project_entity_fixture):  # noqa: F811
    """Create a folder in test project and delete it after test."""
    project_name = project_entity_fixture["name"]
    folder_id = create_folder(
        project_name,
        _unique_name("review_test"),
        folder_type=project_entity_fixture["folderTypes"][0]["name"],
    )
    try:
        yield folder_id
    finally:
        delete_folder(project_name, folder_id, force=True)


@pytest.fixture
def task_fixture(project_entity_fixture, folder_fixture):  # noqa: F811
    """Create a task without assignees under the test folder."""
    return create_task(
        project_entity_fixture["name"],
        _unique_name("task"),
        project_entity_fixture["taskTypes"][0]["name"],
        folder_fixture,
    )


@pytest.fixture
def reviewables_fixture(
    project_entity_fixture,  # noqa: F811
    folder_fixture,
    task_fixture,
):
    """Create product with 2 versions and upload reviewables to them.

    Version 1 has 'done' status and two reviewables, version 2 has
    a not 'done' status and one reviewable. Version 3 lives in other
    product and has no reviewables.

    """
    if get_server_version_tuple() < (1, 16, 4):
        pytest.skip("Reviewables endpoints require AYON server 1.16.4+")

    project_name = project_entity_fixture["name"]
    done_status = _find_status(project_entity_fixture, True)
    not_done_status = _find_status(project_entity_fixture, False)

    product_id = create_product(
        project_name, _unique_name("review"), "review", folder_fixture
    )
    version_1_id = create_version(
        project_name,
        1,
        product_id,
        task_id=task_fixture,
        status=done_status,
    )
    version_2_id = create_version(
        project_name,
        2,
        product_id,
        task_id=task_fixture,
        status=not_done_status,
    )
    empty_product_id = create_product(
        project_name, _unique_name("empty"), "review", folder_fixture
    )
    empty_version_id = create_version(project_name, 1, empty_product_id)

    v1_reviewables = [
        _upload(project_name, version_1_id, "first"),
        _upload(project_name, version_1_id, "second"),
    ]
    v2_reviewables = [
        _upload(project_name, version_2_id, "third"),
    ]
    return {
        "project_name": project_name,
        "folder_id": folder_fixture,
        "task_id": task_fixture,
        "product_id": product_id,
        "version_1_id": version_1_id,
        "version_2_id": version_2_id,
        "empty_product_id": empty_product_id,
        "empty_version_id": empty_version_id,
        "done_status": done_status,
        "v1_activity_ids": [r["activityId"] for r in v1_reviewables],
        "v2_activity_ids": [r["activityId"] for r in v2_reviewables],
    }


def test_upload_reviewable_response(reviewables_fixture):
    """Upload of reviewable returns activity ids used by other tests."""
    activity_ids = (
        reviewables_fixture["v1_activity_ids"]
        + reviewables_fixture["v2_activity_ids"]
    )
    assert len(set(activity_ids)) == 3
    assert all(activity_ids)


def test_get_version_reviewables(reviewables_fixture):
    """Version reviewables contain version info and its reviewables."""
    project_name = reviewables_fixture["project_name"]
    version_id = reviewables_fixture["version_1_id"]

    version = get_version_reviewables(project_name, version_id)
    assert version["id"] == version_id
    assert version["name"] == "v001"
    assert version["productId"] == reviewables_fixture["product_id"]
    assert version["productType"] == "review"

    reviewables = version["reviewables"]
    assert {r["activityId"] for r in reviewables} == set(
        reviewables_fixture["v1_activity_ids"]
    )
    for reviewable in reviewables:
        assert reviewable["fileId"]
        assert reviewable["filename"] == "ayon-symbol.png"
        assert reviewable["mimetype"] == "image/png"
        assert reviewable["author"]["name"] == get_user()["name"]
    assert {r["label"] for r in reviewables} == {"first", "second"}


def test_get_version_reviewables_without_reviewables(reviewables_fixture):
    """Version without reviewables returns empty 'reviewables'."""
    project_name = reviewables_fixture["project_name"]
    version_id = reviewables_fixture["empty_version_id"]

    version = get_version_reviewables(project_name, version_id)
    assert version["id"] == version_id
    assert version["reviewables"] == []

    # With 'latest' the server uses inner join and the version is not
    #   found -> server responds with error
    with pytest.raises(HTTPRequestError):
        get_version_reviewables(project_name, version_id, latest=True)


def test_get_product_reviewables(reviewables_fixture):
    """Product reviewables contain all versions and filter by latest."""
    project_name = reviewables_fixture["project_name"]
    product_id = reviewables_fixture["product_id"]
    version_1_id = reviewables_fixture["version_1_id"]
    version_2_id = reviewables_fixture["version_2_id"]

    by_id = _reviewables_by_version_id(
        get_product_reviewables(project_name, product_id)
    )
    assert set(by_id) == {version_1_id, version_2_id}
    assert len(by_id[version_1_id]) == 2
    assert len(by_id[version_2_id]) == 1

    latest = _get_filtered(
        get_product_reviewables, project_name, product_id, latest=True
    )
    assert [v["id"] for v in latest] == [version_2_id]

    if reviewables_fixture["done_status"] is None:
        pytest.skip("Project does not have status with 'done' state")

    latest_done = _get_filtered(
        get_product_reviewables, project_name, product_id, latest_done=True
    )
    assert [v["id"] for v in latest_done] == [version_1_id]


def test_get_folder_reviewables(reviewables_fixture):
    """Folder reviewables contain versions of all products in folder."""
    project_name = reviewables_fixture["project_name"]
    folder_id = reviewables_fixture["folder_id"]
    version_1_id = reviewables_fixture["version_1_id"]
    version_2_id = reviewables_fixture["version_2_id"]

    by_id = _reviewables_by_version_id(
        get_folder_reviewables(project_name, folder_id)
    )
    assert set(by_id) == {
        version_1_id,
        version_2_id,
        reviewables_fixture["empty_version_id"],
    }
    assert by_id[reviewables_fixture["empty_version_id"]] == []

    # Latest version of the empty product has no reviewables, so it is
    #   not in the output
    latest = _get_filtered(
        get_folder_reviewables, project_name, folder_id, latest=True
    )
    assert [v["id"] for v in latest] == [version_2_id]

    if reviewables_fixture["done_status"] is None:
        pytest.skip("Project does not have status with 'done' state")

    latest_done = _get_filtered(
        get_folder_reviewables, project_name, folder_id, latest_done=True
    )
    assert [v["id"] for v in latest_done] == [version_1_id]


def test_get_task_reviewables(reviewables_fixture):
    """Task reviewables contain only versions linked to the task."""
    project_name = reviewables_fixture["project_name"]
    task_id = reviewables_fixture["task_id"]
    version_1_id = reviewables_fixture["version_1_id"]
    version_2_id = reviewables_fixture["version_2_id"]

    by_id = _reviewables_by_version_id(
        get_task_reviewables(project_name, task_id)
    )
    assert set(by_id) == {version_1_id, version_2_id}

    latest = _get_filtered(
        get_task_reviewables, project_name, task_id, latest=True
    )
    assert [v["id"] for v in latest] == [version_2_id]


@pytest.mark.parametrize(
    "entity_type", ["version", "product", "folder", "task"]
)
def test_get_reviewables(reviewables_fixture, entity_type):
    """Batch reviewables endpoint works for all supported entity types."""
    project_name = reviewables_fixture["project_name"]
    version_1_id = reviewables_fixture["version_1_id"]
    version_2_id = reviewables_fixture["version_2_id"]
    entity_ids = {
        "version": [version_1_id, version_2_id],
        "product": [reviewables_fixture["product_id"]],
        "folder": [reviewables_fixture["folder_id"]],
        "task": [reviewables_fixture["task_id"]],
    }[entity_type]

    by_id = _reviewables_by_version_id(
        get_reviewables(project_name, entity_type, entity_ids)
    )
    assert {version_1_id, version_2_id} <= set(by_id)
    assert {r["activityId"] for r in by_id[version_1_id]} == set(
        reviewables_fixture["v1_activity_ids"]
    )
    assert {r["activityId"] for r in by_id[version_2_id]} == set(
        reviewables_fixture["v2_activity_ids"]
    )

    # Iterable (not only list) of entity ids is accepted
    latest = get_reviewables(
        project_name,
        entity_type,
        iter(entity_ids),
        latest=entity_type != "version",
    )
    latest_ids = {v["id"] for v in latest}
    if entity_type == "version":
        assert latest_ids == {version_1_id, version_2_id}
    else:
        assert latest_ids == {version_2_id}


def test_get_reviewables_empty_ids(reviewables_fixture):
    """Batch reviewables endpoint with unknown ids returns empty list."""
    result = get_reviewables(
        reviewables_fixture["project_name"],
        "version",
        [uuid.uuid4().hex],
    )
    assert result == []


def test_sort_version_reviewables(reviewables_fixture):
    """Order of reviewables is changed and invalid order is refused."""
    project_name = reviewables_fixture["project_name"]
    version_id = reviewables_fixture["version_1_id"]

    current_order = [
        r["activityId"]
        for r in get_version_reviewables(
            project_name, version_id
        )["reviewables"]
    ]
    assert len(current_order) == 2

    for new_order in (
        list(reversed(current_order)),
        list(current_order),
    ):
        sort_version_reviewables(project_name, version_id, new_order)
        version = get_version_reviewables(project_name, version_id)
        assert [
            r["activityId"] for r in version["reviewables"]
        ] == new_order

    # All reviewables of the version must be passed
    with pytest.raises(HTTPRequestError):
        sort_version_reviewables(
            project_name, version_id, current_order[:1]
        )

    # Reviewables of other versions are not allowed
    with pytest.raises(HTTPRequestError):
        sort_version_reviewables(
            project_name,
            version_id,
            current_order + reviewables_fixture["v2_activity_ids"],
        )


def test_update_reviewable(reviewables_fixture):
    """Label of reviewable can be changed."""
    project_name = reviewables_fixture["project_name"]
    version_id = reviewables_fixture["version_2_id"]
    activity_id = reviewables_fixture["v2_activity_ids"][0]
    new_label = _unique_name("label")

    update_reviewable(
        project_name, version_id, activity_id, label=new_label
    )
    version = get_version_reviewables(project_name, version_id)
    labels = {
        r["activityId"]: r["label"]
        for r in version["reviewables"]
    }
    assert labels == {activity_id: new_label}

    # Nothing to change -> no error and label stays
    update_reviewable(project_name, version_id, activity_id)
    version = get_version_reviewables(project_name, version_id)
    assert version["reviewables"][0]["label"] == new_label

    # Empty label is refused by server
    with pytest.raises(HTTPRequestError):
        update_reviewable(project_name, version_id, activity_id, label="")


def _get_assignees(project_name, task_id):
    task = get_task_by_id(
        project_name, task_id, fields={"id", "assignees"}
    )
    return set(task["assignees"])


def test_assign_users_to_task(
    project_entity_fixture,  # noqa: F811
    task_fixture,
):
    """Current user is added, removed and set as task assignee."""
    project_name = project_entity_fixture["name"]
    task_id = task_fixture
    username = get_user()["name"]

    assert _get_assignees(project_name, task_id) == set()

    # Default mode is 'add'
    assign_users_to_task(project_name, task_id, [username])
    assert _get_assignees(project_name, task_id) == {username}

    # Adding already assigned user does not change anything
    assign_users_to_task(project_name, task_id, [username], mode="add")
    assert _get_assignees(project_name, task_id) == {username}

    assign_users_to_task(project_name, task_id, [username], mode="remove")
    assert _get_assignees(project_name, task_id) == set()

    # Removing not assigned user does not change anything
    assign_users_to_task(project_name, task_id, [username], mode="remove")
    assert _get_assignees(project_name, task_id) == set()

    # Iterable (not only list) of users is accepted
    assign_users_to_task(
        project_name, task_id, iter([username]), mode="set"
    )
    assert _get_assignees(project_name, task_id) == {username}

    assign_users_to_task(project_name, task_id, [], mode="set")
    assert _get_assignees(project_name, task_id) == set()


@pytest.fixture
def entity_list_fixture(
    project_entity_fixture,  # noqa: F811
    folder_fixture,
):
    """Create entity list of folders with 3 items.

    Yields:
        tuple[str, str, list[str]]: Project name, list id and item ids
            in their initial order.

    """
    project_name = project_entity_fixture["name"]
    folder_type = project_entity_fixture["folderTypes"][0]["name"]
    folder_ids = [
        create_folder(
            project_name,
            _unique_name("list_item"),
            folder_type=folder_type,
            parent_id=folder_fixture,
        )
        for _ in range(3)
    ]
    list_id = create_entity_list(
        project_name, "folder", _unique_name("test_list")
    )
    try:
        item_ids = [
            create_entity_list_item(
                project_name, list_id, folder_id, position=idx
            )
            for idx, folder_id in enumerate(folder_ids)
        ]
        yield project_name, list_id, item_ids
    finally:
        delete_entity_list(project_name, list_id)


def _get_list_item_ids_in_order(project_name, list_id):
    entity_list = get_entity_list_rest(project_name, list_id)
    items = sorted(entity_list["items"], key=lambda i: i["position"])
    return [item["id"] for item in items]


def test_set_entity_list_items_order(entity_list_fixture):
    """Order of entity list items is changed."""
    if get_server_version_tuple() < (1, 15, 9):
        pytest.skip("Items order endpoint requires AYON server 1.15.9+")

    project_name, list_id, item_ids = entity_list_fixture
    assert _get_list_item_ids_in_order(project_name, list_id) == item_ids

    new_order = [item_ids[2], item_ids[0], item_ids[1]]
    set_entity_list_items_order(project_name, list_id, new_order)
    assert _get_list_item_ids_in_order(project_name, list_id) == new_order

    # Order must contain each item exactly once
    for invalid_order in (
        new_order[:2],
        new_order + [new_order[0]],
        new_order[:2] + [uuid.uuid4().hex],
    ):
        with pytest.raises(HTTPRequestError):
            set_entity_list_items_order(
                project_name, list_id, invalid_order
            )
    assert _get_list_item_ids_in_order(project_name, list_id) == new_order


def test_materialize_entity_list(entity_list_fixture):
    """Materialize entity list returns list summary.

    Materialization is not implemented on some server versions
        (e.g. 1.16.8 responds with 501), in that case the test is skipped.

    """
    project_name, list_id, item_ids = entity_list_fixture
    try:
        summary = materialize_entity_list(project_name, list_id)
    except HTTPRequestError as exc:
        if exc.response is not None and exc.response.status_code == 501:
            pytest.skip("Materialize is not implemented on server")
        raise

    assert summary["id"] == list_id
    assert summary["entityType"] == "folder"
    assert "label" in summary
    assert summary["count"] >= len(item_ids)
