"""Tests of server API.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_TOKEN in your environment.
"""

import os
import pytest

from ayon_api import (
    is_connection_created,
    close_connection,
    get,
    get_default_fields_for_type,
    get_event,
    get_events,
    get_project_names,
    get_user_by_name,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get_timeout,
    set_timeout,
    update_event,
    exceptions
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
            `close_connection()` is invoked, and that the connection 
            state is appropriately updated.
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


test_project_names = [
    (None),
    ([]),
    (["demo_Big_Episodic"]),
    (["demo_Big_Feature"]),
    (["demo_Commercial"]),
    (["AY_Tests"]),
    (["demo_Big_Episodic", "demo_Big_Feature", "demo_Commercial", "AY_Tests"])
]

test_topics = [
    (None),
    ([]),
    (["entity.folder.attrib_changed"]),
    (["entity.task.created", "entity.project.created"]),
    (["settings.changed", "entity.version.status_changed"]),
    (["entity.task.status_changed", "entity.folder.deleted"]),
    (["entity.project.changed", "entity.task.tags_changed", "entity.product.created"])
]

test_users = [
    (None),
    ([]),
    (["admin"]),                          
    (["mkolar", "tadeas.8964"]),         
    (["roy", "luke.inderwick", "ynbot"]),
    (["entity.folder.attrib_changed", "entity.project.created", "entity.task.created", "settings.changed"]),
]

# states is incorrect name for statuses
test_states = [
    (None),
    ([]),
    (["pending", "in_progress", "finished", "failed", "aborted", "restarted"]),
    (["failed", "aborted"]),
    (["pending", "in_progress"]),
    (["finished", "failed", "restarted"]),
    (["finished"]),
]

test_include_logs = [
    (None),
    (True),
    (False),
]

test_has_children = [
    (None),
    (True),
    (False),
]

from datetime import datetime, timedelta, timezone

test_newer_than = [
    (None),
    ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=5)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=20)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat()),
]

test_older_than = [
    (None),
    ((datetime.now(timezone.utc) - timedelta(days=0)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=0)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=5)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=20)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat()),
]

test_fields = [
    (None),
    ([]),
    ([])
]

@pytest.fixture(params=[3, 4, 5])
def event_ids(request):
    length = request.param
    if length == 0:
        return None

    recent_events = list(get_events(
        newer_than=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    ))

    return [recent_event["id"] for recent_event in recent_events[:length]]


# takes max 3 items in a list to reduce the number of combinations
@pytest.mark.parametrize("topics", test_topics[-3:])
@pytest.mark.parametrize(
    "event_ids", 
    [None] + [pytest.param(None, marks=pytest.mark.usefixtures("event_ids"))]
)
@pytest.mark.parametrize("project_names", test_project_names[-3:])
@pytest.mark.parametrize("states", test_states[-3:])
@pytest.mark.parametrize("users", test_users[-3:])
@pytest.mark.parametrize("include_logs", test_include_logs[-3:])
@pytest.mark.parametrize("has_children", test_has_children[2:3])
@pytest.mark.parametrize("newer_than", test_newer_than[-3:])
@pytest.mark.parametrize("older_than", test_older_than[-3:])
@pytest.mark.parametrize("fields", test_fields[-3:])
def test_get_events_all_filter_combinations(
    topics,
    event_ids,
    project_names,
    states,
    users,
    include_logs,
    has_children,
    newer_than,
    older_than,
    fields
):
    """Tests all combinations of possible filters for `get_events`.

    Verifies:
        - Calls `get_events` with the provided filter parameters.
        - Ensures each event in the result set matches the specified filters.
        - Checks that the number of returned events matches the expected count 
            based on the filters applied.
        - Confirms that each event contains only the specified fields, with 
            no extra keys.

    Note:
        - Adjusts the timeout setting if necessary to handle a large number 
            of tests and avoid timeout errors.
        - Some combinations of filter parameters may lead to a server timeout 
            error. When this occurs, the test will skip instead of failing.
        - Currently, a ServerError due to timeout may occur when `has_children` 
            is set to False.
    """
    if get_timeout() < 5:
        set_timeout(None) # default timeout

    try:
        res = list(get_events(
            topics=topics,
            event_ids=event_ids,
            project_names=project_names,
            states=states,
            users=users,
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        ))
    except exceptions.ServerError as exc:
        assert has_children == False, f"{exc} even if has_children is {has_children}."
        print("Warning: ServerError encountered, test skipped due to timeout.")
        pytest.skip("Skipping test due to server timeout.")

    for item in res:
        assert item.get("topic") in topics, (
            f"Expected 'project' one of values: {topics}, but got '{item.get('topic')}'"
        )
        assert item.get("project") in project_names, (
            f"Expected 'project' one of values: {project_names}, but got '{item.get('project')}'"
        )
        assert item.get("user") in users, (
            f"Expected 'user' one of values: {users}, but got '{item.get('user')}'"
        )
        assert item.get("status") in states, (
            f"Expected 'state' to be one of {states}, but got '{item.get('state')}'"
        )
        assert (newer_than is None) or (
            datetime.fromisoformat(item.get("createdAt")) > datetime.fromisoformat(newer_than)
        )
        assert (older_than is None) or (
            datetime.fromisoformat(item.get("createdAt")) < datetime.fromisoformat(older_than)
        )

    assert topics is None or len(res) == sum(len(list(get_events(
        topics=[topic], 
        project_names=project_names,
        states=states,
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields)
    )) for topic in topics)

    assert project_names is None or len(res) == sum(len(list(get_events(
        topics=topics, 
        project_names=[project_name],
        states=states,
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields)
    )) for project_name in project_names)
    
    assert states is None or  len(res) == sum(len(list(get_events(
        topics=topics, 
        project_names=project_names,
        states=[state],
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields)
    )) for state in states)
    
    assert users is None or len(res) == sum(len(list(get_events(
        topics=topics, 
        project_names=project_names,
        states=states,
        users=[user],
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields)
    )) for user in users)

    if fields == []:
        fields = get_default_fields_for_type("event")

    assert fields is None \
        or all(
            set(event.keys()) == set(fields)
            for event in res
        )


@pytest.mark.parametrize("has_children", test_has_children)
def test_get_events_timeout_has_children(has_children):
    """Test `get_events` function with the `has_children` filter.

    Verifies:
        - The `get_events` function handles requests correctly and does 
          not time out when using the `has_children` filter with events 
          created within the last 5 days.
        - If a `ServerError` (likely due to a timeout) is raised:
            - Logs a warning message and skips the test to avoid failure.
            - Asserts that the `ServerError` should occur only when 
              `has_children` is set to False.
    """
    try:
        _ = list(get_events(
            has_children=has_children,
            newer_than=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        ))
    except exceptions.ServerError as exc:
        has_children = True
        assert has_children == False, f"{exc} even if has_children is {has_children}."
        print("Warning: ServerError encountered, test skipped due to timeout.")
        pytest.skip("Skipping test due to server timeout.")


def test_get_events_event_ids(event_ids):
    """Test `get_events` function using specified event IDs.

    Verifies:
        - Each item returned has an ID in the `event_ids` list.
        - The number of items returned matches the expected count 
            when filtered by each individual event ID.
    """
    res = list(get_events(event_ids=event_ids))

    for item in res:
        assert item.get("id") in event_ids
    
    assert len(res) == sum(len(list(get_events(event_ids=[event_id]))) for event_id in event_ids)


@pytest.mark.parametrize("project_names", test_project_names)
def test_get_events_project_name(project_names):
    """Test `get_events` function using specified project names.

    Verifies:
        - Each item returned has a project in the `project_names` list.
        - The count of items matches the expected number when filtered 
            by each individual project name.
    """
    res = list(get_events(project_names=project_names))
    
    for item in res:
        assert item.get("project") in project_names, f"Expected 'project' value '{project_names}', but got '{item.get('project')}'"

    # test if the legths are equal
    assert len(res) == sum(len(list(get_events(project_names=[project_name]))) for project_name in project_names)


@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("topics", test_topics)
def test_get_events_project_name_topic(project_names, topics):
    """Test `get_events` function using both project names and topics.

    Verifies:
        - Each item returned has a project in `project_names` and a topic 
            in `topics`.
        - The item count matches the expected number when filtered by 
            each project name and topic combination.
    """
    res = list(get_events(
        topics=topics,
        project_names=project_names
    ))

    for item in res:
        assert item.get("topic") in topics
        assert item.get("project") in project_names, f"Expected 'project' value '{project_names}', but got '{item.get('project')}'"
    
    # test if the legths are equal
    assert len(res) == sum(len(list(get_events(project_names=[project_name], topics=topics))) for project_name in project_names)
    assert len(res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)


@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("topics", test_topics)
@pytest.mark.parametrize("users", test_users)
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
        assert item.get("topic") in topics, f"Expected 'project' one of values: {topics}, but got '{item.get('topic')}'"
        assert item.get("project") in project_names, f"Expected 'project' one of values: {project_names}, but got '{item.get('project')}'"
        assert item.get("user") in project_names, f"Expected 'project' one of values: {users}, but got '{item.get('user')}'"

    # test if the legths are equal
    assert len(res) == sum(len(list(get_events(project_names=[project_name], topics=topics))) for project_name in project_names)
    assert len(res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)
    assert len(res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)


@pytest.mark.parametrize("newer_than", test_newer_than)
@pytest.mark.parametrize("older_than", test_older_than)
def test_get_events_timestamps(newer_than, older_than):
    """Test `get_events` function using date filters `newer_than` and `older_than`.

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
            datetime.fromisoformat(item.get("createdAt") > datetime.fromisoformat(newer_than))
        )
        assert (older_than is None) or (
            datetime.fromisoformat(item.get("createdAt") < datetime.fromisoformat(older_than))
        )


test_invalid_topics = [
    (None),
    (["invalid_topic_name_1", "invalid_topic_name_2"]),
    (["invalid_topic_name_1"]),
]

test_invalid_project_names = [
    (None),
    (["invalid_project"]),
    (["invalid_project", "demo_Big_Episodic", "demo_Big_Feature"]),
    (["invalid_name_2", "demo_Commercial"]),
    (["demo_Commercial"]),
]

test_invalid_states = [
    (None),
    (["pending_invalid"]),
    (["in_progress_invalid"]), 
    (["finished_invalid", "failed_invalid"]),
]

test_invalid_users = [
    (None),
    (["ayon_invalid_user"]),
    (["ayon_invalid_user1", "ayon_invalid_user2"]),
    (["ayon_invalid_user1", "ayon_invalid_user2", "admin"]),
]

test_invalid_newer_than = [
    (None),
    ((datetime.now(timezone.utc) + timedelta(days=2)).isoformat()),
    ((datetime.now(timezone.utc) + timedelta(days=5)).isoformat()),
    ((datetime.now(timezone.utc) - timedelta(days=5)).isoformat()),
]


@pytest.mark.parametrize("topics", test_invalid_topics)
@pytest.mark.parametrize("project_names", test_invalid_project_names)
@pytest.mark.parametrize("states", test_invalid_states)
@pytest.mark.parametrize("users", test_invalid_users)
@pytest.mark.parametrize("newer_than", test_invalid_newer_than)
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
        - Confirms that the result is either empty or aligns with expected valid 
            entries:
            - `topics`: Result is empty or topics is set to `None`.
            - `project_names`: Result is empty or project names exist in the 
            list of valid project names.
            - `states`: Result is empty or states is set to `None`.
            - `users`: Result is empty or each user exists as a valid user.
            - `newer_than`: Result is empty or `newer_than` date is in the past.

    Note:
        - Adjusts the timeout setting if necessary to handle a large number 
            of tests and avoid timeout errors.
    """

    if get_timeout() < 5:
        set_timeout(None) # default timeout value

    res = list(get_events(
        topics=topics, 
        project_names=project_names,
        states=states,
        users=users,
        newer_than=newer_than
    ))

    valid_project_names = get_project_names()

    assert res == [] \
        or topics is None 
    assert res == [] \
        or project_names is None \
        or any(project_name in valid_project_names for project_name in project_names)
    assert res == [] \
        or states is None
    assert res == [] \
        or users is None \
        or any(get_user_by_name(user) is not None for user in users)
    assert res == [] \
        or newer_than is None \
        or datetime.fromisoformat(newer_than) < datetime.now(timezone.utc)


@pytest.fixture
def event_id():
    """Fixture that retrieves the ID of a recent event created within 
    the last 5 days.

    Returns:
        - The event ID of the most recent event within the last 5 days 
          if available.
        - `None` if no recent events are found within this time frame.
    """
    recent_event = list(get_events(
        newer_than=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    ))
    return recent_event[0]["id"] if recent_event else None

test_update_sender = [
    ("test.server.api"),
]

test_update_username = [
    ("testing_user"),
]

test_update_status = [
    ("pending"),
    ("in_progress"),
    ("finished"),
    ("failed"),
    ("aborted"),
    ("restarted")
]

test_update_description = [
    ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce viverra."),
    ("Updated description test...")
]

test_update_retries = [
    (1),
    (0),
    (10),
]

@pytest.mark.parametrize("sender", test_update_sender)
@pytest.mark.parametrize("username", test_update_username)
@pytest.mark.parametrize("status", test_update_status)
@pytest.mark.parametrize("description", test_update_description)
@pytest.mark.parametrize("retries", test_update_retries)
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
    """Verifies that the `update_event` function correctly updates event fields.

    Verifies:
        - The function updates the specified event fields based on the provided
            parameters (`sender`, `username`, `status`, `description`, `retries`,
            etc.).
        - Only the fields specified in `kwargs` are updated, and other fields 
            remain unchanged.
        - The `updatedAt` field is updated and the change occurs within a 
            reasonable time frame (within one minute).
        - The event's state before and after the update matches the expected 
            values for the updated fields.
    
    Notes:
        - Parameters like `event_id`, `sender`, `username`, `status`, 
            `description`, `retries`, etc., are passed dynamically to the function.
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
                datetime.fromisoformat(value) - datetime.now(timezone.utc) < timedelta(minutes=1)
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
        - Confirms that an `HTTPRequestError` is raised for invalid status values
            when attempting to update an event with an unsupported status.
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
        - Confirms that an `HTTPRequestError` is raised for invalid progress values
            when attempting to update an event with unsupported progress.
    """
    with pytest.raises(exceptions.HTTPRequestError):
        update_event(event_id, progress=progress)
