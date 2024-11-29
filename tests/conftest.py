from datetime import datetime, timedelta, timezone
import pytest

from ayon_api import (
    get_project,
    create_project,
    update_project,
    delete_project,
    get_events,
    get_folders,
    get_products,
    get_tasks
)
from ayon_api.entity_hub import EntityHub


class _Cache:
    # Cache project entity as scope 'session' of a fixture does not handle
    #   parametrized fixtures.
    project_entity = None


@pytest.fixture(scope="session")
def project_name_fixture():
    return "AYONApiTestProject"


@pytest.fixture(scope="session")
def project_entity_fixture(project_name_fixture):
    project_entity = _Cache.project_entity
    created = False
    if _Cache.project_entity is None:
        created = True
        project_entity = get_project(project_name_fixture)
        if project_entity:
            delete_project(project_name_fixture)
        create_project(project_name_fixture, "AYTP")
        update_project(
            project_name_fixture,
            folder_types=[
                {
                    "name": "Folder",
                    "icon": "folder",
                    "shortName": ""
                },
                {
                    "name": "Episode",
                    "icon": "live_tv",
                    "shortName": ""
                },
                {
                    "name": "Sequence",
                    "icon": "theaters",
                    "shortName": ""
                },
                {
                    "name": "Shot",
                    "icon": "movie",
                    "shortName": ""
                }
            ]
        )
        project_entity = get_project(project_name_fixture)
        _Cache.project_entity = project_entity

    yield project_entity
    if created:
        delete_project(project_name_fixture)


@pytest.fixture
def clean_project(project_name_fixture):
    hub = EntityHub(project_name_fixture)

    for folder in get_folders(
        project_name_fixture
    ):
        # delete tasks
        for task in list(get_tasks(
            project_name_fixture,
            folder_ids=[folder["id"]]
        )):
            hub.delete_entity(hub.get_task_by_id(task["id"]))

        # delete products
        for product in list(get_products(
            project_name_fixture, folder_ids=[folder["id"]]
        )):
            product_entity = hub.get_product_by_id(product["id"])
            hub.delete_entity(product_entity)

        entity = hub.get_folder_by_id(folder["id"])
        if not entity:
            continue

        hub.delete_entity(entity)
        hub.commit_changes()


@pytest.fixture(params=[3, 4, 5])
def event_ids(request):
    length = request.param
    if length == 0:
        return None

    recent_events = list(get_events(
        newer_than=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    ))

    return [recent_event["id"] for recent_event in recent_events[:length]]


@pytest.fixture
def event_id():
    """Fixture that retrieves the ID of a recent event created within
    the last 5 days.

    Returns:
        - The event ID of the most recent event within the last 5 days
          if available.
        - `None` if no recent events are found within this time frame.

    """
    recent_events = list(get_events(
        newer_than=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    ))
    return recent_events[0]["id"] if recent_events else None


class TestEventFilters:
    project_names = [
        (None),
        ([]),
        (["demo_Big_Episodic"]),
        (["demo_Big_Feature"]),
        (["demo_Commercial"]),
        (["AY_Tests"]),
        ([
            "demo_Big_Episodic",
            "demo_Big_Feature",
            "demo_Commercial",
            "AY_Tests"
        ])
    ]

    topics = [
        (None),
        ([]),
        (["entity.folder.attrib_changed"]),
        (["entity.task.created", "entity.project.created"]),
        (["settings.changed", "entity.version.status_changed"]),
        (["entity.task.status_changed", "entity.folder.deleted"]),
        ([
            "entity.project.changed",
            "entity.task.tags_changed",
            "entity.product.created"
        ])
    ]

    users = [
        (None),
        ([]),
        (["admin"]),
        (["mkolar", "tadeas.8964"]),
        (["roy", "luke.inderwick", "ynbot"]),
        ([
            "entity.folder.attrib_changed",
            "entity.project.created",
            "entity.task.created",
            "settings.changed"
        ]),
    ]

    # states is incorrect name for statuses
    states = [
        (None),
        ([]),
        ([
            "pending",
            "in_progress",
            "finished",
            "failed",
            "aborted",
            "restarted"
        ]),
        (["failed", "aborted"]),
        (["pending", "in_progress"]),
        (["finished", "failed", "restarted"]),
        (["finished"]),
    ]

    include_logs = [
        (None),
        (True),
        (False),
    ]

    has_children = [
        (None),
        (True),
        (False),
    ]

    now = datetime.now(timezone.utc)

    newer_than = [
        (None),
        ((now - timedelta(days=2)).isoformat()),
        ((now - timedelta(days=5)).isoformat()),
        ((now - timedelta(days=10)).isoformat()),
        ((now - timedelta(days=20)).isoformat()),
        ((now - timedelta(days=30)).isoformat()),
    ]

    older_than = [
        (None),
        ((now - timedelta(days=0)).isoformat()),
        ((now - timedelta(days=5)).isoformat()),
        ((now - timedelta(days=10)).isoformat()),
        ((now - timedelta(days=20)).isoformat()),
        ((now - timedelta(days=30)).isoformat()),
    ]

    fields = [
        (None),
        ([]),
    ]


class TestInvalidEventFilters:
    topics = [
        (None),
        (["invalid_topic_name_1", "invalid_topic_name_2"]),
        (["invalid_topic_name_1"]),
    ]

    project_names = [
        (None),
        (["invalid_project"]),
        (["invalid_project", "demo_Big_Episodic", "demo_Big_Feature"]),
        (["invalid_name_2", "demo_Commercial"]),
        (["demo_Commercial"]),
    ]

    states = [
        (None),
        (["pending_invalid"]),
        (["in_progress_invalid"]),
        (["finished_invalid", "failed_invalid"]),
    ]

    users = [
        (None),
        (["ayon_invalid_user"]),
        (["ayon_invalid_user1", "ayon_invalid_user2"]),
        (["ayon_invalid_user1", "ayon_invalid_user2", "admin"]),
    ]

    newer_than = [
        (None),
        ((datetime.now(timezone.utc) + timedelta(days=2)).isoformat()),
        ((datetime.now(timezone.utc) + timedelta(days=5)).isoformat()),
        ((datetime.now(timezone.utc) - timedelta(days=5)).isoformat()),
    ]


class TestUpdateEventData:
    update_sender = [
        ("test.server.api"),
    ]

    update_username = [
        ("testing_user"),
    ]

    update_status = [
        ("pending"),
        ("in_progress"),
        ("finished"),
        ("failed"),
        ("aborted"),
        ("restarted")
    ]

    update_description = [
        (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
            " Fusce vivera."
        ),
        ("Updated description test...")
    ]

    update_retries = [
        (1),
        (0),
        (10),
    ]


class TestProductData:
    names = [
        ("test_name"),
        ("test_123"),
    ]

    product_types = [
        ("animation"),
        ("camera"),
        ("render"),
        ("workfile"),
    ]
