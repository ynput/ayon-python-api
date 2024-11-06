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
    get_user,
    get_server_api_connection,
    get_base_url,
    get_rest_url,
)
from ayon_api import exceptions

AYON_BASE_URL = os.getenv("AYON_SERVER_URL")
AYON_REST_URL = "{}/api".format(AYON_BASE_URL)


def test_close_connection():
    _con = get_server_api_connection()
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
    # (None),
    # ([]),
    (["demo_Big_Episodic"]),
    (["demo_Big_Feature"]),
    (["demo_Commercial"]),
    (["AY_Tests"]),
    (["demo_Big_Episodic", "demo_Big_Feature", "demo_Commercial", "AY_Tests"])
]

test_topics = [
    # (None),
    # ([]),
    (["entity.folder.attrib_changed"]),
    (["entity.task.created", "entity.project.created"]),
    (["settings.changed", "entity.version.status_changed"]),
    (["entity.task.status_changed", "entity.folder.deleted"]),
    # (["entity.project.changed", "entity.task.tags_changed", "entity.product.created"])
]

test_users = [
    # (None),
    # ([]),
    (["admin"]),                          
    (["mkolar", "tadeas.8964"]),         
    # (["roy", "luke.inderwick", "ynbot"]),
    # (["entity.folder.attrib_changed", "entity.project.created", "entity.task.created", "settings.changed"]),
]

# incorrect name for statuses
test_states = [
    # (None),
    # ([]),
    (["pending", "in_progress", "finished", "failed", "aborted", "restarted"]),
    # (["failed", "aborted"]),
    # (["pending", "in_progress"]),
    # (["finished", "failed", "restarted"]),
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

from datetime import datetime, timedelta

test_newer_than = [
    (None),
    ((datetime.now() - timedelta(days=2)).isoformat()),
    ((datetime.now() - timedelta(days=5)).isoformat()),
    # ((datetime.now() - timedelta(days=10)).isoformat()),
    # ((datetime.now() - timedelta(days=20)).isoformat()),
    # ((datetime.now() - timedelta(days=30)).isoformat()),
]

test_older_than = [
    (None),
    ((datetime.now() - timedelta(days=0)).isoformat()),
    ((datetime.now() - timedelta(days=0)).isoformat()),
    # ((datetime.now() - timedelta(days=5)).isoformat()),
    # ((datetime.now() - timedelta(days=10)).isoformat()),
    # ((datetime.now() - timedelta(days=20)).isoformat()),
    # ((datetime.now() - timedelta(days=30)).isoformat()),
]

test_fields = [
    (None),
    ([]),
]


@pytest.mark.parametrize("topics", test_topics)
@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("states", test_states)
@pytest.mark.parametrize("users", test_users)
@pytest.mark.parametrize("include_logs", test_include_logs)
@pytest.mark.parametrize("has_children", test_has_children)
@pytest.mark.parametrize("newer_than", test_newer_than)
@pytest.mark.parametrize("older_than", test_older_than)
@pytest.mark.parametrize("fields", test_fields)
def test_get_events_all_filter_combinations(
    topics, 
    project_names,
    states,
    users,
    include_logs,
    has_children,
    newer_than,
    older_than,
    fields):
    """Tests all combination of possible filters.
    """
    res = get_events(
        topics=topics, 
        project_names=project_names,
        states=states,
        users=users,
        include_logs=include_logs,
        has_children=has_children,
        newer_than=newer_than,
        older_than=older_than,
        fields=fields
    )

    list_res = list(res)

    for item in list_res:
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
            datetime.fromisoformat(item.get("createdAt") > datetime.fromisoformat(newer_than))
        )
        assert (older_than is None) or (
            datetime.fromisoformat(item.get("createdAt") < datetime.fromisoformat(older_than))
        )

    assert topics is None or len(list_res) == sum(len(list(get_events(
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

    assert project_names is None or len(list_res) == sum(len(list(get_events(
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
    
    assert states is None or  len(list_res) == sum(len(list(get_events(
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
    
    assert users is None or len(list_res) == sum(len(list(get_events(
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

    assert fields is None or len(list_res) == sum(len(list(get_events(
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
    

########################
# topics=None, event_ids=None, project_names=None, states=None, users=None, include_logs=None, has_children=None, newer_than=None, older_than=None, fields=None

# [
#     {
#         'description': 'Changed task animation status to In progress',
#         'hash': 'a259521612b611ef95920242c0a81005',
#         'project': 'demo_Big_Episodic',
#         'id': 'a259521612b611ef95920242c0a81005',
#         'status': 'finished',
#         'user': 'admin',
#         'createdAt': '2024-05-15T14:28:28.889144+02:00',
#         'dependsOn': None,
#         'updatedAt': '2024-05-15T14:28:28.889144+02:00',
#         'retries': 0,
#         'sender': 'wWN64PyUo1kqAxechtJucy',
#         'topic': 'entity.task.status_changed'
#     },
#     {
#         'description': 'Changed task animation status to On hold',
#         'hash': 'a8fb977812b611ef95920242c0a81005',
#         'project': 'demo_Big_Episodic',
#         'id': 'a8fb977812b611ef95920242c0a81005',
#         'status': 'finished',
#         'user': 'admin',
#         'createdAt': '2024-05-15T14:28:40.018934+02:00',
#         'dependsOn': None,
#         'updatedAt': '2024-05-15T14:28:40.018934+02:00',
#         'retries': 0,
#         'sender': 'fx5SG26FHvhFKkDsXHp53k',
#         'topic': 'entity.task.status_changed'
#     },
#     {
#         'description': 'Changed task animation status to Pending review',
#         'hash': 'f0686ec412b611ef95920242c0a81005',
#         'project': 'demo_Big_Episodic',
#         'id': 'f0686ec412b611ef95920242c0a81005',
#         'status': 'finished',
#         'user': 'admin',
#         'createdAt': '2024-05-15T14:30:39.850258+02:00',
#         'dependsOn': None,
#         'updatedAt': '2024-05-15T14:30:39.850258+02:00',
#         'retries': 0,
#         'sender': 'v9ciM94XnfJ33X1bYr5ESv',
#         'topic': 'entity.task.status_changed'
#     }
# ]


@pytest.mark.parametrize("project_names", test_project_names)
def test_get_events_project_name(project_names):
    res = get_events(project_names=project_names)

    list_res = list(res)

    users = set()
    for item in list_res:
        users.add(item.get("user"))
        assert item.get("project") in project_names, f"Expected 'project' value '{project_names}', but got '{item.get('project')}'"

    print(users)
    # test if the legths are equal
    assert len(list_res) == sum(len(list(get_events(project_names=[project_name]))) for project_name in project_names)


@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("topics", test_topics)
def test_get_events_project_name_topic(project_names, topics):
    print(project_names, "", topics)
    res = get_events(topics=topics, project_names=project_names)

    list_res = list(res)

    for item in list_res:
        assert item.get("topic") in topics
        assert item.get("project") in project_names, f"Expected 'project' value '{project_names}', but got '{item.get('project')}'"
    
    # test if the legths are equal
    assert len(list_res) == sum(len(list(get_events(project_names=[project_name], topics=topics))) for project_name in project_names)
    assert len(list_res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)


@pytest.mark.parametrize("project_names", test_project_names)
@pytest.mark.parametrize("topics", test_topics)
@pytest.mark.parametrize("users", test_users)
def test_get_events_project_name_topic_user(project_names, topics, users):
    # print(project_names, "", topics)
    res = get_events(topics=topics, project_names=project_names, users=users)

    list_res = list(res)

    for item in list_res:
        assert item.get("topic") in topics, f"Expected 'project' one of values: {topics}, but got '{item.get('topic')}'"
        assert item.get("project") in project_names, f"Expected 'project' one of values: {project_names}, but got '{item.get('project')}'"
        assert item.get("user") in project_names, f"Expected 'project' one of values: {users}, but got '{item.get('user')}'"


    # test if the legths are equal
    assert len(list_res) == sum(len(list(get_events(project_names=[project_name], topics=topics))) for project_name in project_names)
    assert len(list_res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)
    assert len(list_res) == sum(len(list(get_events(project_names=project_names, topics=[topic]))) for topic in topics)
