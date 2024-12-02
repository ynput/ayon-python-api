"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment.

"""

from datetime import datetime, timedelta, timezone
import os
import sys
import subprocess
import time

import pytest

from ayon_api import (
    close_connection,
    create_folder,
    create_project,
    create_thumbnail,
    delete_addon_version,
    delete_event,
    delete_project,
    dispatch_event,
    download_addon_private_file,
    enroll_event_job,
    get,
    get_addons_info,
    get_event,
    get_events,
    get_folder_thumbnail,
    get_project,
    get_project_names,
    get_user_by_name,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get_timeout,
    is_connection_created,
    set_timeout,
    trigger_server_restart,
    update_event,
    upload_addon_zip,
    ServerAPI,
    exceptions
)
from .conftest import (
    TestEventFilters,
    TestInvalidEventFilters,
    TestUpdateEventData,
    event_id,
    event_ids
)


AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "{}/api".format(AYON_BASE_URL)


def test_close_connection():
    """Tests the functionality of opening and closing the server API
    connection.

    Verifies:
        - Confirms that the connection is successfully created when
            `get_server_api_connection()` is called.
        - Ensures that the connection is closed correctly when
            `close_connection()` is invoked, and that the connection state
            is appropriately updated.

    """
    _ = get_server_api_connection()
    assert is_connection_created() is True
    close_connection()
    assert is_connection_created() is False


def test_get_base_url():
    """Tests the retrieval of the base URL for the API.

    Verifies:
        - Confirms that `get_base_url()` returns a string.
        - Ensures that the returned URL matches the expected `AYON_BASE_URL`.

    """
    res = get_base_url()
    assert isinstance(res, str)
    assert res == AYON_BASE_URL


def test_get_rest_url():
    """Tests the retrieval of the REST API URL.

    Verifies:
        - Confirms that `get_rest_url()` returns a string.
        - Ensures that the returned URL matches the expected `AYON_REST_URL`.

    """
    res = get_rest_url()
    assert isinstance(res, str)
    assert res == AYON_REST_URL


def test_get():
    """Tests the `get` method for making API requests.

    Verifies:
        - Ensures that a successful GET request to the endpoint 'info'
            returns a status code of 200.
        - Confirms that the response data is in the form of a dictionary.

    """
    res = get("info")
    assert res.status_code == 200
    assert isinstance(res.data, dict)


@pytest.mark.parametrize("has_children", TestEventFilters.has_children)
def test_get_events_timeout_has_children(has_children):
    """Test `get_events` function with the `has_children` filter.

    Verifies:
        - The `get_events` function handles requests correctly and does not
          time out when using the `has_children` filter with events created
          within the last 5 days.
        - If a `ServerError` (likely due to a timeout) is raised:
            - Logs a warning message and skips the test to avoid failure.
            - Asserts that the `ServerError` should occur only when
                `has_children` is set to False.

    """
    try:
        _ = list(get_events(
            has_children=has_children,
            newer_than=(
                    datetime.now(timezone.utc) - timedelta(days=5)
            ).isoformat()
        ))
    except exceptions.ServerError as exc:
        assert has_children is False, (
            f"{exc} even if has_children is {has_children}."
        )
        print(
            "Warning: ServerError encountered, test skipped due to timeout."
        )
        pytest.skip("Skipping test due to server timeout.")


def test_get_events_event_ids(event_ids):
    """Test `get_events` function using specified event IDs.

    Verifies:
        - Each item returned has an ID in the `event_ids` list.
        - The number of items returned matches the expected count when
            filtered by each individual event ID.

    """
    res = list(get_events(event_ids=event_ids))

    for item in res:
        assert item.get("id") in event_ids

    assert event_ids is None or len(res) == sum(len(
        list(get_events(
            event_ids=[event_id]
        )) or []
    ) for event_id in event_ids)


@pytest.mark.parametrize("project_names", TestEventFilters.project_names)
def test_get_events_project_name(project_names):
    """Test `get_events` function using specified project names.

    Verifies:
        - Each item returned has a project in the `project_names` list.
        - The count of items matches the expected number when filtered
            by each individual project name.

    """
    res = list(get_events(project_names=project_names))

    for item in res:
        assert item.get("project") in project_names

    # test if the legths are equal
    assert len(res) == sum(len(
        list(get_events(
            project_names=[project_name]
        )) or []
    ) for project_name in project_names)


@pytest.mark.parametrize("project_names", TestEventFilters.project_names)
@pytest.mark.parametrize("topics", TestEventFilters.topics)
def test_get_events_project_name_topic(project_names, topics):
    """Test `get_events` function using both project names and topics.

    Verifies:
        - Each item returned has a project in `project_names` and a topic
            in `topics`.
        - The item count matches the expected number when filtered by each
        project name and topic combination.

    """
    res = list(get_events(
        topics=topics,
        project_names=project_names
    ))

    for item in res:
        assert item.get("topic") in topics
        assert item.get("project") in project_names

    # test if the legths are equal
    assert project_names is None or len(res) == sum(len(
        list(get_events(
            project_names=[project_name],
            topics=topics
        )) or []
    ) for project_name in project_names)

    assert topics is None or len(res) == sum(len(
        list(get_events(
            project_names=project_names,
            topics=[topic]
        )) or []
    ) for topic in topics)


@pytest.mark.parametrize("project_names", TestEventFilters.project_names)
@pytest.mark.parametrize("topics", TestEventFilters.topics)
@pytest.mark.parametrize("users", TestEventFilters.users)
def test_get_events_project_name_topic_user(project_names, topics, users):
    """Test `get_events` function using project names, topics, and users.

    Verifies:
        - Each item has a project in `project_names`, a topic in `topics`,
            and a user in `users`.
        - The item count matches the expected number when filtered by
            combinations of project names, topics, and users.

    """
    res = list(get_events(
        topics=topics,
        project_names=project_names,
        users=users
    ))

    for item in res:
        assert topics is None or item.get("topic") in topics
        assert project_names is None or item.get("project") in project_names
        assert users is None or item.get("user") in users

    # test if the legths are equal
    assert project_names is None or len(res) == sum(len(
        list(get_events(
            project_names=[project_name],
            topics=topics,
            users=users
        )) or []
    ) for project_name in project_names)

    assert topics is None or len(res) == sum(len(
        list(get_events(
            project_names=project_names,
            topics=[topic],
            users=users
        )) or []
    ) for topic in topics)

    assert users is None or len(res) == sum(len(
        list(get_events(
            project_names=project_names,
            topics=topics,
            users=[user]
        )) or []
    ) for user in users)


@pytest.mark.parametrize("newer_than", TestEventFilters.newer_than)
@pytest.mark.parametrize("older_than", TestEventFilters.older_than)
def test_get_events_timestamps(newer_than, older_than):
    """Test `get_events` function using date filters `newer_than` and
    `older_than`.

    Verifies:
        - Each item's creation date falls within the specified date
            range between `newer_than` and `older_than`.

    """
    res = list(get_events(
        newer_than=newer_than,
        older_than=older_than
    ))

    for item in res:
        assert (newer_than is None) or (
            datetime.fromisoformat(item.get("createdAt"))
            > datetime.fromisoformat(newer_than)
        )
        assert (older_than is None) or (
            datetime.fromisoformat(item.get("createdAt"))
            < datetime.fromisoformat(older_than)
        )


@pytest.mark.parametrize("topics", TestInvalidEventFilters.topics)
@pytest.mark.parametrize(
    "project_names",
    TestInvalidEventFilters.project_names)
@pytest.mark.parametrize("states", TestInvalidEventFilters.states)
@pytest.mark.parametrize("users", TestInvalidEventFilters.users)
@pytest.mark.parametrize("newer_than", TestInvalidEventFilters.newer_than)
def test_get_events_invalid_data(
    topics,
    project_names,
    states,
    users,
    newer_than
):
    """Tests `get_events` with invalid filter data to ensure correct handling
    of invalid input and prevent errors or unexpected results.

    Verifies:
        - Confirms that the result is either empty or aligns with expected
            valid entries:
            - `topics`: Result is empty or topics is set to `None`.
            - `project_names`: Result is empty or project names exist in the
            list of valid project names.
            - `states`: Result is empty or states is set to `None`.
            - `users`: Result is empty or each user exists as a valid user.
            - `newer_than`: Result is empty or `newer_than` date is in the
            past.

    Note:
        - Adjusts the timeout setting if necessary to handle a large number
            of tests and avoid timeout errors.

    """
    if get_timeout() < 5:
        set_timeout(None) # default timeout value

    res = list(get_events(
        topics=topics,
        project_names=project_names,
        statuses=states,
        users=users,
        newer_than=newer_than
    ))

    valid_project_names = get_project_names()

    assert res == [] \
        or topics is None
    assert res == [] \
        or project_names is None \
        or any(
            project_name in valid_project_names
            for project_name in project_names
        )
    assert res == [] \
        or states is None
    assert res == [] \
        or users is None \
        or any(get_user_by_name(user) is not None for user in users)
    assert res == [] \
        or newer_than is None \
        or datetime.fromisoformat(newer_than) < datetime.now(timezone.utc)


@pytest.mark.parametrize("sender", TestUpdateEventData.update_sender)
@pytest.mark.parametrize("username", TestUpdateEventData.update_username)
@pytest.mark.parametrize("status", TestUpdateEventData.update_status)
@pytest.mark.parametrize(
    "description",
    TestUpdateEventData.update_description)
@pytest.mark.parametrize("retries", TestUpdateEventData.update_retries)
def test_update_event(
        event_id,
        sender,
        username,
        status,
        description,
        retries,
        project_name=None,
        summary=None,
        payload=None,
        progress=None,
):
    """Verifies that the `update_event` function correctly updates event
    fields.

    Verifies:
        - The function updates the specified event fields based on the provided
            parameters (`sender`, `username`, `status`, `description`,
            `retries`, etc.).
        - Only the fields specified in `kwargs` are updated, and other fields
            remain unchanged.
        - The `updatedAt` field is updated and the change occurs within
            a reasonable time frame (within one minute).
        - The event's state before and after the update matches the expected
            values for the updated fields.

    Notes:
        - Parameters like `event_id`, `sender`, `username`, `status`,
            `description`, `retries`, etc., are passed dynamically to
            the function.
        - If any parameter is `None`, it is excluded from the update request.

    """
    kwargs = {
        key: value
        for key, value in (
            ("event_id", event_id),
            ("sender", sender),
            ("project", project_name),
            ("username", username),
            ("status", status),
            ("description", description),
            ("summary", summary),
            ("payload", payload),
            ("progress", progress),
            ("retries", retries),
        )
        if value is not None
    }

    prev = get_event(event_id=event_id)
    update_event(**kwargs)
    res = get_event(event_id=event_id)

    for key, value in res.items():
        assert value == prev.get(key) \
        or key in kwargs.keys() and value == kwargs.get(key) \
        or (
            key == "updatedAt" and (
                (datetime.fromisoformat(value) - datetime.now(timezone.utc))
                <
                timedelta(minutes=1)
            )
        )


test_update_invalid_status = [
    ("finisheddd"),
    ("pending_pending"),
    (42),
    (False),
    ("_in_progress")
]

@pytest.mark.parametrize("status", test_update_invalid_status)
def test_update_event_invalid_status(status):
    """Tests `update_event` with invalid status values to ensure correct
    error handling for unsupported status inputs.

    Verifies:
        - Confirms that an `HTTPRequestError` is raised for invalid status
            values when attempting to update an event with an unsupported
            status.

    """
    with pytest.raises(exceptions.HTTPRequestError):
        update_event(event_id, status=status)


test_update_invalid_progress = [
    ("good"),
    ("bad"),
    (-1),
    ([0, 1, 2]),
    (101)
]

@pytest.mark.parametrize("progress", test_update_invalid_progress)
def test_update_event_invalid_progress(event_id, progress):
    """Tests `update_event` with invalid progress values to ensure correct
    error handling for unsupported progress inputs.

    Verifies:
        - Confirms that an `HTTPRequestError` is raised for invalid progress
            values when attempting to update an event with unsupported
            progress.

    """
    with pytest.raises(exceptions.HTTPRequestError):
        update_event(event_id, progress=progress)


TEST_SOURCE_TOPIC = "test.source.topic"
TEST_TARGET_TOPIC = "test.target.topic"
DEFAULT_NUMBER_OF_EVENTS = 3

test_sequential = [
    (True),
    (False),
    (None)
]

@pytest.fixture
def clean_up_events(topics=[TEST_SOURCE_TOPIC, TEST_TARGET_TOPIC]):
    """Used before running marked testt to close any pending events that may
    interfere with the test setup or outcomes by marking them as 'finished'.

    """
    pending_events = list(get_events(topics=topics))
    for event in pending_events:
        if event["status"] not in ["finished", "failed"]:
            update_event(event["id"], status="finished")


@pytest.fixture
def create_test_events(num_of_events=DEFAULT_NUMBER_OF_EVENTS):
    """This fixture dispatches events to the `TEST_SOURCE_TOPIC` and returns
    the list of event IDs for the created events.

    """
    return [
        dispatch_event(
            topic=TEST_SOURCE_TOPIC,
            sender="tester",
            description=f"New test event n. {num}"
        )["id"]
        for num in range(num_of_events)
    ]


@pytest.fixture
def delete_events(topics=[TEST_SOURCE_TOPIC, TEST_TARGET_TOPIC]):
    """Cleans up events from the specified topics after the test completes.
    """
    yield

    for event in list(get_events(topics=topics)):
        delete_event(event["id"])


# clean_up should be below create_test to ensure it is called first
# pytest probably does not guarantee the order of execution
# delete_events is disabled for now - until new sever version
# @pytest.mark.usefixtures("delete_events")
@pytest.mark.usefixtures("create_test_events")
@pytest.mark.usefixtures("clean_up_events")
@pytest.mark.parametrize("sequential", test_sequential)
def test_enroll_event_job(sequential):
    """Tests the `enroll_event_job` function for proper event job enrollment
    based on sequential argument.

    Verifies:
        - When `sequential` is set to `True`, only one job can be enrolled at
            a time, preventing new enrollments until the first job is closed
            or updated.
        - When `sequential` is `False` or `None`, multiple jobs can be
            enrolled concurrently without conflicts.
        - The `update_event` function updates the `status` of a job to
            allowing next sequential job processing.

    Notes:
        - `update_event` is used to set `job_1`'s status to "failed" to test
          re-enrollment behavior.
        - TODO - delete events after test if possible

    """
    job_1 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender_1",
        sequential=sequential
    )

    job_2 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender_2",
        sequential=sequential
    )

    assert sequential is False \
        or sequential is None \
        or job_2 is None

    update_event(job_1["id"], status="finished")

    job_2 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender_2",
        sequential=sequential
    )

    assert job_2 is not None \
        and job_1 != job_2


# disabled for now - until new sever version
# delete_events is disabled for now - until new sever version
# @pytest.mark.usefixtures("delete_events")
@pytest.mark.usefixtures("create_test_events")
@pytest.mark.usefixtures("clean_up_events")
@pytest.mark.parametrize("sequential", test_sequential)
def test_enroll_event_job_failed(sequential):
    """Tests `enroll_event_job` behavior when the initial job fails and
    sequential processing is enabled.

    Verifies:
        - `enroll_event_job` creates a job (`job_1`) with specified parameters
          `(`source_topic`, `target_topic`, `sender`, and `sequential`).
        - After `job_1` fails (status set to "failed"), a new job (`job_2`)
            can be enrolled with the same parameters.
        - When `sequential` is `True`, the test verifies that `job_1` and
            `job_2` are identical, as a failed sequential job should not allow
            a new job to be enrolled separately.
        - When `sequential` is `False`, `job_1` and `job_2` are allowed to
            differ, as concurrent processing is permitted.

    Notes:
        - `update_event` is used to set `job_1`'s status to "failed" to test
            re-enrollment behavior.
        - TODO - delete events after test if possible

    """
    job_1 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender_1",
        sequential=sequential
    )

    update_event(job_1["id"], status="failed")

    job_2 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender_2",
        sequential=sequential
    )

    assert sequential is not True or job_1 == job_2


# delete_events is disabled for now - until new sever version
# @pytest.mark.usefixtures("delete_events")
@pytest.mark.usefixtures("clean_up_events")
@pytest.mark.parametrize("sequential", test_sequential)
def test_enroll_event_job_same_sender(sequential):
    """Tests `enroll_event_job` behavior when multiple jobs are enrolled
    by the same sender.

    Verifies:
        - `enroll_event_job` creates a `job_1` and `job_2` with the same
            parameters (`source_topic`, `target_topic`, `sender`, and
            `sequential`).
        - The test checks that `job_1` and `job_2` are identical, ensuring
            that no duplicate jobs are created for the same sender.

    Notes:
        - TODO - delete events after test if possible

    """
    job_1 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender",
        sequential=sequential
    )

    job_2 = enroll_event_job(
        source_topic=TEST_SOURCE_TOPIC,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender",
        sequential=sequential
    )

    assert job_1 == job_2


test_invalid_topic = [
    ("invalid_source_topic"),
    ("nonexisting_source_topic"),
]


# delete_events is disabled for now - until new sever version
# @pytest.mark.usefixtures("delete_events")
@pytest.mark.usefixtures("clean_up_events")
@pytest.mark.parametrize("topic", TestInvalidEventFilters.topics)
@pytest.mark.parametrize("sequential", test_sequential)
def test_enroll_event_job_invalid_topic(topic, sequential):
    """Tests `enroll_event_job` behavior when provided with invalid topics.

    Verifies:
        - `enroll_event_job` returns `None` when given invalid `source_topic`
            or `target_topic`, indicating that the function properly rejects
            invalid topic values.
        - The function correctly handles both sequential and non-sequential
            job processing modes when invalid topics are used.

    Notes:
        - `clean_up_events()` is called at the beginning to close any pending
            jobs that may interfere with the test setup or outcomes.

    """
    job = enroll_event_job(
        source_topic=topic,
        target_topic=TEST_TARGET_TOPIC,
        sender="test_sender",
        sequential=sequential
    )

    assert job is None


# clean_up should be below create_test to ensure it is called first
# pytest probably does not guarantee the order of execution
# delete_events is disabled for now - until new sever version
# @pytest.mark.usefixtures("delete_events")
@pytest.mark.usefixtures("create_test_events")
@pytest.mark.usefixtures("clean_up_events")
def test_enroll_event_job_sequential_false():
    """Tests `enroll_event_job` behavior when `sequential` is set to `False`.

    Verifies:
        - `enroll_event_job` creates a unique job for each sender even when
            `sequential` is set to `False`, allowing concurrent job processing.
        - Each job has a unique `dependsOn` identifier

    Notes:
        - The `depends_on_ids` set is used to track `dependsOn` identifiers
            and verify that each job has a unique dependency state, as
            required for concurrent processing.
        - TODO - delete events after test if possible

    """
    depends_on_ids = set()

    for sender in ["tester_1", "tester_2", "tester_3"]:
        job = enroll_event_job(
            source_topic=TEST_SOURCE_TOPIC,
            target_topic=TEST_TARGET_TOPIC,
            sender=sender,
            sequential=False
        )

        assert job is not None \
            and job["dependsOn"] not in depends_on_ids

        depends_on_ids.add(job["dependsOn"])


TEST_PROJECT_NAME = "test_API_project"
TEST_PROJECT_CODE = "apitest"
AYON_THUMBNAIL_PATH = "tests/resources/ayon-symbol.png"


def test_thumbnail_operations(
    project_name=TEST_PROJECT_NAME,
    project_code=TEST_PROJECT_CODE,
    thumbnail_path=AYON_THUMBNAIL_PATH
):
    """Tests thumbnail operations for a project.

    Verifies:
        - A thumbnail is created for the project and associated with a folder.
        - The thumbnail associated with the folder is correctly retrieved,
            with attributes matching the project name and thumbnail ID.
        - The content of the retrieved thumbnail matches the expected image
            bytes read from the specified `thumbnail_path`.

    Notes:
        - `delete_project` is called initially to remove any pre-existing
            project with the same name, ensuring no conflicts during testing.
        - At the end of the test, the project is deleted to clean up
            resources.

    """
    if get_project(project_name):
        delete_project(TEST_PROJECT_NAME)

    project = create_project(project_name, project_code)

    thumbnail_id = create_thumbnail(project_name, thumbnail_path)

    folder_id = create_folder(
        project_name,
        "my_test_folder",
        thumbnail_id=thumbnail_id
    )
    thumbnail = get_folder_thumbnail(project_name, folder_id, thumbnail_id)

    assert thumbnail.project_name == project_name
    assert thumbnail.thumbnail_id == thumbnail_id

    with open(thumbnail_path, "rb") as file:
        image_bytes = file.read()

    assert image_bytes == thumbnail.content

    delete_project(project["name"])


def test_addon_methods():
    """Tests addon methods, including upload and download of private file.

    Verifies:
        - An addon with the specified name and version does not exist at the
            start.
        - Uploads an addon package `.zip` file and triggers a server restart.
        - Ensures the server restart completes, and verifies the uploaded
            addon is available in the list of addons after the restart.
        - Downloads a private file associated with the addon, verifying its
            existence and correct download location.
        - Cleans up downloaded files and directories after the test to
            maintain a clean state.

    Notes:
        - `time.sleep()` is used to allow for a brief pause for the server
            restart.
        - The `finally` block removes downloaded files and the directory to
            prevent residual test artifacts.

    """
    addon_name = "tests"
    addon_version = "1.0.0"
    download_path = "tests/resources/tmp_downloads"
    private_file_path = os.path.join(download_path, "ayon-symbol.png")
    for addon in get_addons_info()["addons"]:
        if addon["name"] == addon_name and addon["version"] == addon_version:
            delete_addon_version(addon_name, addon_version)
            break

    assert all(
        addon_name != addon["name"] for addon in get_addons_info()["addons"]
    )

    subprocess.run([sys.executable, "tests/resources/addon/create_package.py"])
    try:
        _ = upload_addon_zip("tests/resources/addon/package/tests-1.0.0.zip")

        trigger_server_restart()

        # need to wait at least 0.1 sec. to restart server
        last_check = time.time()
        time.sleep(0.5)
        while True:
            try:
                addons = get_addons_info()["addons"]
                break
            except exceptions.ServerError as exc:
                pass

            if time.time() - last_check > 60:
                assert False, "Server timeout"
            time.sleep(0.5)

        assert any(addon_name == addon["name"] for addon in addons)

        downloaded_file = download_addon_private_file(
            addon_name,
            addon_version,
            "ayon-symbol.png",
            download_path
        )

        assert downloaded_file == private_file_path
        assert os.path.isfile(private_file_path)

    finally:
        if os.path.isfile(private_file_path):
            os.remove(private_file_path)

        if os.path.isdir(download_path):
            os.rmdir(download_path)


@pytest.fixture
def api_artist_user():
    """Fixture that sets up an API connection for a non-admin artist user.

    Workflow:
        - Checks if the project exists; if not, it creates one with specified
            `TEST_PROJECT_NAME` and `TEST_PROJECT_CODE`.
        - Establishes a server API connection and retrieves the list
            of available access groups.
        - Configures a new user with limited permissions (`isAdmin` and
            `isManager` set to `False`) and assigns all available access
            groups as default and project-specific groups.
        - Creates a new API connection using the artist user's credentials
            (`username` and `password`) and logs in with it.

    Returns:
        new_api: A `ServerAPI` instance authenticated with the artist user's
          credentials, ready to use in tests.

    """
    project = get_project(TEST_PROJECT_NAME)
    if project is None:
        project = create_project(TEST_PROJECT_NAME, TEST_PROJECT_CODE)

    api = get_server_api_connection()

    username = "testUser"
    password = "testUserPassword"
    response = api.get("accessGroups/_")
    access_groups = [
        item["name"]
        for item in response.data
    ]
    api.put(
        f"users/{username}",
        password=password,
        data={
            "isAdmin": False,
            "isManager": False,
            "defaultAccessGroups": access_groups,
            "accessGroups": {
                project["name"]: access_groups
            },
        }
    )
    new_api = ServerAPI(api.base_url)
    new_api.login(username, password)

    return new_api


def test_server_restart_as_user(api_artist_user):
    """Tests that a non-admin artist user is not permitted to trigger a server
    restart.

    Verifies:
        - An attempt to call `trigger_server_restart` as a non-admin artist
            user raises an exception, ensuring that only users with the
            appropriate permissions (e.g., admins) can perform server restart
            operations.

    Notes:
        - The exception is not specified as there is a todo to raise more
            specific exception.

    """
    with pytest.raises(Exception):
        api_artist_user.trigger_server_restart()
