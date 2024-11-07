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
    get_events,
    get_project_names,
    get_user_by_name,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
    get_timeout,
    set_timeout
)

AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "{}/api".format(AYON_BASE_URL)


def test_close_connection():
    _ = get_server_api_connection()
    assert is_connection_created() is True
    close_connection()
    assert is_connection_created() is False


def test_get_base_url():
    res = get_base_url()
    assert isinstance(res, str)
    assert res == AYON_BASE_URL


def test_get_rest_url():
    res = get_rest_url()
    assert isinstance(res, str)
    assert res == AYON_REST_URL


def test_get():
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

# incorrect name for statuses
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
    # (False),
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
]


# takes max 3 items in a list to reduce the number of combinations
@pytest.mark.parametrize("topics", test_topics[-3:])
@pytest.mark.parametrize("project_names", test_project_names[-3:])
@pytest.mark.parametrize("states", test_states[-3:])
@pytest.mark.parametrize("users", test_users[-3:])
@pytest.mark.parametrize("include_logs", test_include_logs[-3:])
@pytest.mark.parametrize("has_children", test_has_children[-3:])
@pytest.mark.parametrize("newer_than", test_newer_than[-3:])
@pytest.mark.parametrize("older_than", test_older_than[-3:])
@pytest.mark.parametrize("fields", test_fields[-3:])
def test_get_events_all_filter_combinations(
    topics, 
    project_names,
    states,
    users,
    include_logs,
    has_children,
    newer_than,
    older_than,
    fields
):
    """Tests all combination of possible filters.
    """
    # with many tests - ayon_api.exceptions.ServerError: Connection timed out.
    # TODO - maybe some better solution
    if get_timeout() < 5:
        set_timeout(20.0)

    res = list(get_events(
        topics=topics, 
        project_names=project_names,
        states=states,
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields
    ))

    # test if filtering was correct
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

    # test if all events were given
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

    assert fields is None or len(res) == sum(len(list(get_events(
        topics=topics, 
        project_names=project_names,
        states=states,
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=[field])
    )) for field in fields)


@pytest.mark.parametrize("project_names", test_project_names)
def test_get_events_project_name(project_names):
    res = list(get_events(project_names=project_names))
    
    for item in res:
        assert item.get("project") in project_names, f"Expected 'project' value '{project_names}', but got '{item.get('project')}'"

    # test if the legths are equal
    assert len(res) == sum(len(list(get_events(project_names=[project_name]))) for project_name in project_names)


@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("topics", test_topics)
def test_get_events_project_name_topic(project_names, topics):
    print(project_names, "", topics)
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
def test_get_events_timestamp(newer_than, older_than):
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
    # with many tests - ayon_api.exceptions.ServerError: Connection timed out.
    # TODO - maybe some better solution
    if get_timeout() < 5:
        set_timeout(20.0)

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


test_update_sender = [
    (),
]

# def test_update_event():

