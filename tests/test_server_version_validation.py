"""Tests of server version validation of version dependent methods.

Methods using endpoints or arguments that were added in newer AYON server
versions raise 'UnsupportedServerVersion' when the connected server is older.
These tests patch the server version of a 'ServerAPI' instance and replace
all request methods so no request can reach any server.

These tests do NOT need a running AYON server.

"""
import io

import pytest

from ayon_api import ServerAPI
from ayon_api.exceptions import UnsupportedServerVersion

# Minimal PNG signature so mime type detection recognizes the content
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

# Methods that send a request to server (or would fetch server info)
REQUEST_METHODS = (
    "get_info",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "raw_get",
    "raw_post",
    "raw_put",
    "raw_patch",
    "raw_delete",
    "query_graphql",
    "upload_file",
    "upload_file_from_stream",
    "_upload_file",
    "_do_rest_request",
)


class RequestSent(Exception):
    """Raised by patched request methods instead of sending a request."""
    def __init__(self, method_name, args, kwargs):
        super().__init__(method_name)
        self.method_name = method_name
        self.call_args = args
        self.call_kwargs = kwargs


def _version_below(threshold):
    """Version tuple just below the threshold version."""
    major, minor, patch = threshold
    if patch > 0:
        return major, minor, patch - 1, "", ""
    return major, minor - 1, 99, "", ""


def _version_at(threshold):
    major, minor, patch = threshold
    return major, minor, patch, "", ""


def _create_blocker(method_name):
    def _blocker(*args, **kwargs):
        raise RequestSent(method_name, args, kwargs)
    return _blocker


def _create_api(server_version):
    """Create 'ServerAPI' that cannot send any request.

    Args:
        server_version (ServerVersion): Version returned by
            'get_server_version_tuple'.

    Returns:
        ServerAPI: Server api object.

    """
    api = ServerAPI(
        "http://127.0.0.1:1",
        site_id=None,
        create_session=False,
    )
    api.get_server_version_tuple = lambda: server_version
    for method_name in REQUEST_METHODS:
        setattr(api, method_name, _create_blocker(method_name))
    return api


@pytest.fixture
def thumbnail_path(tmp_path):
    path = tmp_path / "thumbnail.png"
    path.write_bytes(PNG_CONTENT)
    return str(path)


# Each item contains test id, minimum server version and callback that
#   calls the gated method with gated argument.
GATED_CALLS = [
    (
        "rename_project",
        (1, 15, 0),
        lambda api, path: api.rename_project("old_name", "new_name"),
    ),
    (
        "get_project_thumbnail",
        (1, 15, 0),
        lambda api, path: api.get_project_thumbnail("project"),
    ),
    (
        "set_project_thumbnail",
        (1, 15, 0),
        lambda api, path: api.set_project_thumbnail("project", path),
    ),
    (
        "set_project_thumbnail_from_stream",
        (1, 15, 0),
        lambda api, path: api.set_project_thumbnail_from_stream(
            "project", io.BytesIO(PNG_CONTENT)
        ),
    ),
    (
        "search_folders-search",
        (1, 15, 4),
        lambda api, path: api.search_folders("project", search="text"),
    ),
    (
        "update_server_config",
        (1, 15, 9),
        lambda api, path: api.update_server_config({"studio_name": "x"}),
    ),
    (
        "set_entity_list_items_order",
        (1, 15, 9),
        lambda api, path: api.set_entity_list_items_order(
            "project", "list_id", ["item_id"]
        ),
    ),
    (
        "get_enums",
        (1, 16, 4),
        lambda api, path: api.get_enums(),
    ),
    (
        "get_reviewables",
        (1, 16, 4),
        lambda api, path: api.get_reviewables(
            "project", "version", ["version_id"]
        ),
    ),
    (
        "get_version_reviewables-latest",
        (1, 16, 4),
        lambda api, path: api.get_version_reviewables(
            "project", "version_id", latest=True
        ),
    ),
    (
        "get_version_reviewables-latest_done",
        (1, 16, 4),
        lambda api, path: api.get_version_reviewables(
            "project", "version_id", latest_done=True
        ),
    ),
    (
        "get_product_reviewables-latest",
        (1, 16, 4),
        lambda api, path: api.get_product_reviewables(
            "project", "product_id", latest=True
        ),
    ),
    (
        "get_folder_reviewables-latest_done",
        (1, 16, 4),
        lambda api, path: api.get_folder_reviewables(
            "project", "folder_id", latest_done=True
        ),
    ),
    (
        "get_task_reviewables-latest",
        (1, 16, 4),
        lambda api, path: api.get_task_reviewables(
            "project", "task_id", latest=True
        ),
    ),
    (
        "update_service-error",
        (1, 16, 7),
        lambda api, path: api.update_service(
            "service", should_run=False, error="Failed"
        ),
    ),
    (
        "migrate_addon_settings",
        (1, 16, 8),
        lambda api, path: api.migrate_addon_settings(
            "addon", "1.0.0", "1.0.1"
        ),
    ),
]

# Calls of gated methods without the gated argument, they must work
#   with server older than the version required by the argument.
UNGATED_ARG_CALLS = [
    (
        "search_folders-no-search",
        (1, 15, 4),
        lambda api: api.search_folders("project", folder_search="text"),
    ),
    (
        "get_version_reviewables",
        (1, 16, 4),
        lambda api: api.get_version_reviewables("project", "version_id"),
    ),
    (
        "get_product_reviewables",
        (1, 16, 4),
        lambda api: api.get_product_reviewables("project", "product_id"),
    ),
    (
        "get_folder_reviewables",
        (1, 16, 4),
        lambda api: api.get_folder_reviewables("project", "folder_id"),
    ),
    (
        "get_task_reviewables",
        (1, 16, 4),
        lambda api: api.get_task_reviewables("project", "task_id"),
    ),
    (
        "update_service-no-error",
        (1, 16, 7),
        lambda api: api.update_service("service", should_run=False),
    ),
]


def _gated_params(calls):
    return [
        pytest.param(threshold, func, id=test_id)
        for test_id, threshold, func in calls
    ]


@pytest.mark.parametrize("threshold, func", _gated_params(GATED_CALLS))
def test_unsupported_version_raises(threshold, func, thumbnail_path):
    """Gated method raises before any request on older server.

    Verifies:
        - 'UnsupportedServerVersion' is raised when server version is
            just below the required version.
        - No request method is called (blocked request methods would
            raise 'RequestSent' instead).

    """
    api = _create_api(_version_below(threshold))
    with pytest.raises(UnsupportedServerVersion):
        func(api, thumbnail_path)


@pytest.mark.parametrize("threshold, func", _gated_params(GATED_CALLS))
def test_supported_version_sends_request(threshold, func, thumbnail_path):
    """Gated method sends request on server with the required version.

    Verifies:
        - Version check does not raise when server version equals
            the required version and request is sent.

    """
    api = _create_api(_version_at(threshold))
    with pytest.raises(RequestSent):
        func(api, thumbnail_path)


@pytest.mark.parametrize(
    "threshold, func", _gated_params(UNGATED_ARG_CALLS)
)
def test_ungated_arguments_on_older_server(threshold, func):
    """Method without gated argument works on older server.

    Verifies:
        - Request is sent when the gated argument is not used even if
            server version is below the version required by the argument.

    """
    api = _create_api(_version_below(threshold))
    with pytest.raises(RequestSent):
        func(api)


class _FakeResponse:
    def raise_for_status(self):
        pass


def _create_rename_user_api(server_version):
    api = _create_api(server_version)
    calls = []

    def _create_recorder(method_name):
        def _recorder(entrypoint, **kwargs):
            calls.append((method_name, entrypoint, kwargs))
            return _FakeResponse()
        return _recorder

    api.post = _create_recorder("post")
    api.patch = _create_recorder("patch")
    return api, calls


@pytest.mark.parametrize(
    "server_version",
    [(1, 14, 99, "", ""), (1, 14, 0, "", ""), (1, 13, 5, "", "")]
)
def test_rename_user_old_server_uses_patch(server_version):
    """'rename_user' uses deprecated PATCH endpoint before 1.15.0.

    Verifies:
        - Single PATCH request is sent to 'users/{name}/rename'.
        - New name is passed in 'newName' key.

    """
    api, calls = _create_rename_user_api(server_version)
    api.rename_user("old_user", "new_user")
    assert calls == [
        ("patch", "users/old_user/rename", {"newName": "new_user"})
    ]


@pytest.mark.parametrize(
    "server_version",
    [(1, 15, 0, "", ""), (1, 15, 1, "", ""), (1, 16, 8, "", "")]
)
def test_rename_user_new_server_uses_post(server_version):
    """'rename_user' uses POST endpoint from 1.15.0.

    Verifies:
        - Single POST request is sent to 'users/{name}/rename'.
        - New name is passed in 'name' key.

    """
    api, calls = _create_rename_user_api(server_version)
    api.rename_user("old_user", "new_user")
    assert calls == [
        ("post", "users/old_user/rename", {"name": "new_user"})
    ]
