"""Tests of system, services and events related server API.

Tests run against a real AYON server and require an admin user.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_SERVER_URL and AYON_API_KEY in your environment.

All entities created by the tests use unique names and are removed after
the test. Server-wide state that is changed by a test is restored.

"""
import time
import uuid

import pytest

from ayon_api import (
    delete_event,
    delete_events,
    delete_service,
    delete_site,
    dispatch_event,
    get_addons_info,
    get_enum,
    get_enums,
    get_events,
    get_hosts,
    get_project,
    get_restart_required,
    get_server_api_connection,
    get_server_config,
    get_server_config_schema,
    get_server_version_tuple,
    get_services,
    get_sites,
    get_user,
    set_restart_required,
    spawn_service,
    update_server_config,
    update_service,
    exceptions,
)

TEST_PREFIX = "ayon-api-test"


def _unique_name(prefix=TEST_PREFIX):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _topic_filter(topic):
    """Events filter matching single topic.

    Never returns empty filter, empty filter would delete all events.

    """
    assert topic
    return {
        "conditions": [
            {
                "key": "topic",
                "value": topic,
                "operator": "eq",
            }
        ],
        "operator": "and",
    }


def _require_server_version(version, func_name):
    if get_server_version_tuple() < version:
        version_str = ".".join(str(part) for part in version)
        pytest.skip(
            f"'{func_name}' requires AYON server {version_str} or newer"
        )


def _get_service(service_name):
    for service in get_services():
        if service["name"] == service_name:
            return service
    return None


def _find_addon_service():
    """Find addon version that defines a service with an image.

    Returns:
        Optional[tuple[str, str, str]]: Addon name, addon version and
            service name.

    """
    for addon in get_addons_info(details=True)["addons"]:
        for version, version_info in addon["versions"].items():
            services = version_info.get("services") or {}
            for service_name, service_def in services.items():
                if isinstance(service_def, dict) and service_def.get("image"):
                    return addon["name"], version, service_name
    return None


# --- Services ---
def test_get_services():
    """Tests 'get_services' returns services in expected shape.

    Verifies:
        - Result is a list.
        - Each service contains name, host, addon and run state keys.

    """
    services = get_services()
    assert isinstance(services, list)
    for service in services:
        for key in (
            "name",
            "hostname",
            "addonName",
            "addonVersion",
            "service",
            "shouldRun",
            "isRunning",
            "data",
        ):
            assert key in service


def test_get_hosts():
    """Tests 'get_hosts' returns hosts in expected shape.

    Verifies:
        - Result is a list.
        - Each host contains name, last seen time and health information.

    """
    hosts = get_hosts()
    assert isinstance(hosts, list)
    for host in hosts:
        assert isinstance(host["name"], str)
        assert "lastSeen" in host
        assert set(host["health"]) >= {"cpu", "mem"}


@pytest.fixture
def addon_service():
    """Addon service definition usable for spawning a service.

    Server allows spawning only services defined by installed addon,
    the test is skipped if there is no such addon on server.

    """
    addon_service = _find_addon_service()
    if addon_service is None:
        pytest.skip("Server does not have any addon defining a service")
    return addon_service


@pytest.fixture
def spawned_service_name():
    """Unique service name, the service is deleted on teardown."""
    service_name = _unique_name()
    yield service_name
    if _get_service(service_name) is not None:
        delete_service(service_name)


def test_spawn_update_delete_service(addon_service, spawned_service_name):
    """Tests spawn, update and delete of addon service.

    Service is spawned on a non-existent hostname so no service host
        will ever run it, and it is stopped right after spawn.

    Verifies:
        - Spawned service is listed with passed hostname and addon info.
        - 'update_service' changes 'shouldRun', 'hostname' and config.
        - 'update_service' sets 'error' (server 1.16.7+).
        - Deleted service is not listed anymore.

    """
    addon_name, addon_version, service = addon_service
    service_name = spawned_service_name
    hostname = _unique_name(f"{TEST_PREFIX}-host")
    spawn_service(
        service_name,
        addon_name,
        addon_version,
        service,
        hostname,
    )
    # Stop the service immediately
    update_service(service_name, should_run=False)

    service_data = _get_service(service_name)
    assert service_data is not None
    assert service_data["hostname"] == hostname
    assert service_data["addonName"] == addon_name
    assert service_data["addonVersion"] == addon_version
    assert service_data["service"] == service
    assert service_data["shouldRun"] is False

    new_hostname = _unique_name(f"{TEST_PREFIX}-host")
    env = {"AYON_API_TEST": service_name}
    update_service(
        service_name,
        hostname=new_hostname,
        config={"env": env},
    )
    service_data = _get_service(service_name)
    assert service_data["hostname"] == new_hostname
    assert service_data["shouldRun"] is False
    assert service_data["data"]["env"] == env

    if get_server_version_tuple() >= (1, 16, 7):
        error_msg = "AYON api test error"
        update_service(service_name, should_run=False, error=error_msg)
        service_data = _get_service(service_name)
        assert service_data["data"]["error"] == error_msg

    delete_service(service_name)
    assert _get_service(service_name) is None


# --- Sites ---
@pytest.fixture
def temp_site():
    """Register temporary site on server.

    Server registers a site when '/api/info' is requested with site
        headers 'x-ayon-site-id', 'x-ayon-platform', 'x-ayon-hostname'
        and 'x-ayon-version'. Site is deleted on teardown if still exists.

    """
    site_id = _unique_name()
    site_info = {
        "id": site_id,
        "platform": "linux",
        "hostname": _unique_name(f"{TEST_PREFIX}-host"),
        "version": "0.0.0",
    }
    con = get_server_api_connection()
    headers = con.get_headers()
    headers.update({
        "x-ayon-site-id": site_info["id"],
        "x-ayon-platform": site_info["platform"],
        "x-ayon-hostname": site_info["hostname"],
        "x-ayon-version": site_info["version"],
    })
    response = con.raw_get("info", headers=headers)
    response.raise_for_status()

    yield site_info

    if any(site["id"] == site_id for site in get_sites()):
        delete_site(site_id)


def test_get_sites(temp_site):
    """Tests 'get_sites' with and without filters.

    Verifies:
        - Registered site is listed with platform, hostname, version
            and the current user.
        - Filter by hostname returns only the registered site.
        - Filter by different platform does not return the site.

    """
    sites = get_sites()
    assert isinstance(sites, list)
    site_by_id = {site["id"]: site for site in sites}
    assert temp_site["id"] in site_by_id
    site = site_by_id[temp_site["id"]]
    assert site["platform"] == temp_site["platform"]
    assert site["hostname"] == temp_site["hostname"]
    assert site["version"] == temp_site["version"]
    assert get_user()["name"] in site["users"]

    sites = get_sites(hostname=temp_site["hostname"])
    assert [site["id"] for site in sites] == [temp_site["id"]]

    sites = get_sites(
        platform_name=temp_site["platform"],
        hostname=temp_site["hostname"],
    )
    assert [site["id"] for site in sites] == [temp_site["id"]]

    sites = get_sites(
        platform_name="windows",
        hostname=temp_site["hostname"],
    )
    assert sites == []


def test_delete_site(temp_site):
    """Tests 'delete_site' unregisters site.

    Verifies:
        - Deleted site is not listed anymore.
        - Deleting a non-existent site raises an error.

    """
    site_id = temp_site["id"]
    delete_site(site_id)
    assert all(site["id"] != site_id for site in get_sites())

    with pytest.raises(exceptions.HTTPRequestError):
        delete_site(site_id)


# --- Restart required ---
def test_get_restart_required():
    """Tests 'get_restart_required' response shape."""
    result = get_restart_required()
    assert isinstance(result["required"], bool)
    if result["required"]:
        assert isinstance(result["reason"], str)


def test_set_restart_required():
    """Tests set and clear of server restart required flag.

    Test is skipped if server already requires restart, so the original
        flag is not changed.

    Verifies:
        - Flag is set after 'set_restart_required(True)'.
        - Flag is cleared after 'set_restart_required(False)'.

    """
    original = get_restart_required()
    if original["required"]:
        pytest.skip("Server already requires restart, not changing the flag")

    try:
        set_restart_required(True, reason="AYON api test")
        # Server ignores restart required events younger than 2 seconds
        time.sleep(2.5)
        result = get_restart_required()
        assert result["required"] is True
        assert isinstance(result["reason"], str)

    finally:
        set_restart_required(False)

    assert get_restart_required()["required"] is False


# --- Server config ---
def test_get_server_config_schema():
    """Tests 'get_server_config_schema' returns JSON schema.

    Verifies:
        - Schema has object properties containing 'studio_name' which
            is also available in server config.

    """
    schema = get_server_config_schema()
    assert isinstance(schema, dict)
    assert schema["title"] == "Server Configuration"
    assert "studio_name" in schema["properties"]
    assert "studio_name" in get_server_config()


def test_update_server_config():
    """Tests partial update of server config.

    Studio name is changed and restored afterwards.

    Verifies:
        - Studio name is changed.
        - Other config values are unchanged.
        - Original studio name is restored.

    """
    _require_server_version((1, 15, 9), "update_server_config")

    original_config = get_server_config()
    original_name = original_config["studio_name"]
    new_name = f"AYON api test {uuid.uuid4().hex[:8]}"
    try:
        update_server_config({"studio_name": new_name})
        config = get_server_config()
        assert config["studio_name"] == new_name

        config.pop("studio_name")
        expected = dict(original_config)
        expected.pop("studio_name")
        assert config == expected

    finally:
        update_server_config({"studio_name": original_name})

    assert get_server_config()["studio_name"] == original_name


# --- Enums ---
def test_get_enums():
    """Tests 'get_enums' lists enum resolvers.

    Verifies:
        - Each resolver has name, label and accepted params.
        - Built-in resolvers are available.

    """
    _require_server_version((1, 16, 4), "get_enums")

    enums = get_enums()
    assert isinstance(enums, list)
    for enum_info in enums:
        assert isinstance(enum_info["name"], str)
        assert isinstance(enum_info["label"], str)
        assert isinstance(enum_info["acceptedParams"], dict)

    enums_by_name = {enum_info["name"]: enum_info for enum_info in enums}
    assert {"folderTypes", "taskTypes", "statuses"} <= set(enums_by_name)
    assert "project_name" in enums_by_name["folderTypes"]["acceptedParams"]


def test_get_enum(project_entity_fixture):
    """Tests 'get_enum' with project, user and context parameters.

    Verifies:
        - Items without project have value and label.
        - Project folder types match folder types of the project.
        - Resolving for user (admin only) works.
        - Context parameters are passed to the resolver.
        - Invalid context value raises an error.

    """
    project_name = project_entity_fixture["name"]
    project_entity = get_project(project_name)

    items = get_enum("folderTypes")
    assert isinstance(items, list)
    for item in items:
        assert "value" in item
        assert isinstance(item["label"], str)

    items = get_enum("folderTypes", project_name=project_name)
    expected_folder_types = {
        folder_type["name"]
        for folder_type in project_entity["folderTypes"]
    }
    assert {item["value"] for item in items} == expected_folder_types

    items = get_enum(
        "folderTypes",
        project_name=project_name,
        user_name=get_user()["name"],
    )
    assert {item["value"] for item in items} == expected_folder_types

    expected_statuses = {
        status["name"]
        for status in project_entity["statuses"]
        if "task" in (status.get("scope") or [])
    }
    items = get_enum(
        "statuses",
        project_name=project_name,
        context={"entity_type": "task"},
    )
    assert {item["value"] for item in items} == expected_statuses

    with pytest.raises(exceptions.HTTPRequestError):
        get_enum(
            "statuses",
            project_name=project_name,
            context={"entity_type": "invalid"},
        )


# --- Events ---
@pytest.fixture
def event_topics():
    """Two unique event topics, events are deleted on teardown."""
    topics = [
        f"ayon_api.test.delete_events.{uuid.uuid4().hex}"
        for _ in range(2)
    ]
    yield topics
    for event in list(get_events(topics=topics, fields={"id"})):
        delete_event(event["id"])


def _get_event_ids(topic):
    return {
        event["id"]
        for event in get_events(topics=[topic], fields={"id"})
    }


def test_delete_events(event_topics):
    """Tests 'delete_events' removes only events matching filter.

    Verifies:
        - Events with filtered topic are deleted.
        - Events with other topic are kept.

    """
    topic_to_delete, topic_to_keep = event_topics
    created_ids = {}
    for topic in event_topics:
        created_ids[topic] = {
            dispatch_event(
                topic,
                sender="ayon_api_tests",
                description=f"AYON api test event {idx}",
            )["id"]
            for idx in range(3)
        }

    for topic in event_topics:
        assert _get_event_ids(topic) == created_ids[topic]

    delete_events(_topic_filter(topic_to_delete))

    assert _get_event_ids(topic_to_delete) == set()
    assert _get_event_ids(topic_to_keep) == created_ids[topic_to_keep]


@pytest.mark.parametrize(
    "events_filter",
    [
        None,
        {},
        {"conditions": [], "operator": "and"},
    ],
)
def test_delete_events_without_conditions_raises(events_filter):
    """Tests 'delete_events' refuses filter that would delete all events."""
    with pytest.raises(ValueError):
        delete_events(events_filter)
