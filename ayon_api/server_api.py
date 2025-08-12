"""Server API.

Provides access to server API.

"""
from __future__ import annotations

import os
import re
import io
import json
import time
import logging
import collections
import platform
import copy
import uuid
import warnings
from contextlib import contextmanager
import typing
from typing import Optional, Iterable, Tuple, Generator, Dict, List, Set, Any

import requests

from .constants import (
    SERVER_RETRIES_ENV_KEY,
    DEFAULT_FOLDER_TYPE_FIELDS,
    DEFAULT_TASK_TYPE_FIELDS,
    DEFAULT_PROJECT_STATUSES_FIELDS,
    DEFAULT_PROJECT_TAGS_FIELDS,
    DEFAULT_PRODUCT_TYPE_FIELDS,
    DEFAULT_PROJECT_FIELDS,
    DEFAULT_FOLDER_FIELDS,
    DEFAULT_TASK_FIELDS,
    DEFAULT_PRODUCT_FIELDS,
    DEFAULT_VERSION_FIELDS,
    DEFAULT_REPRESENTATION_FIELDS,
    REPRESENTATION_FILES_FIELDS,
    DEFAULT_WORKFILE_INFO_FIELDS,
    DEFAULT_EVENT_FIELDS,
    DEFAULT_ACTIVITY_FIELDS,
    DEFAULT_USER_FIELDS,
    DEFAULT_ENTITY_LIST_FIELDS,
)
from .graphql import GraphQlQuery, INTROSPECTION_QUERY
from .graphql_queries import (
    product_types_query,
    tasks_graphql_query,
    tasks_by_folder_paths_graphql_query,
    products_graphql_query,
    versions_graphql_query,
    representations_graphql_query,
    representations_hierarchy_qraphql_query,
    workfiles_info_graphql_query,
    users_graphql_query,
)
from .exceptions import (
    FailedOperations,
    UnauthorizedError,
    AuthenticationError,
    ServerNotReached,
)
from .utils import (
    RequestType,
    RequestTypes,
    RestApiResponse,
    RepresentationParents,
    RepresentationHierarchy,
    prepare_query_string,
    logout_from_server,
    create_entity_id,
    entity_data_json_default,
    failed_json_default,
    TransferProgress,
    get_default_timeout,
    get_default_settings_variant,
    get_default_site_id,
    NOT_SET,
    get_media_mime_type,
    get_machine_name,
    fill_own_attribs,
    prepare_list_filters,
    PatternType,
)
from ._actions import _ActionsAPI
from ._activities import _ActivitiesAPI
from ._addons import _AddonsAPI
from ._events import _EventsAPI
from ._folders import _FoldersAPI
from ._links import _LinksAPI
from ._lists import _ListsAPI
from ._projects import _ProjectsAPI
from ._thumbnails import _ThumbnailsAPI

if typing.TYPE_CHECKING:
    from typing import Union
    from .typing import (
        ServerVersion,
        AttributeScope,
        AttributeSchemaDataDict,
        AttributeSchemaDict,
        AttributesSchemaDict,
        InstallersInfoDict,
        DependencyPackagesDict,
        DevBundleAddonInfoDict,
        BundlesInfoDict,
        AnatomyPresetDict,
        SecretDict,

        AnyEntityDict,
        TaskDict,
        ProductDict,
        VersionDict,
        RepresentationDict,
        WorkfileInfoDict,

        ProductTypeDict,
        StreamType,
    )

_PLACEHOLDER = object()

VERSION_REGEX = re.compile(
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?"
    r"(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?"
)


class GraphQlResponse:
    """GraphQl response."""

    def __init__(self, data):
        self.data = data
        self.errors = data.get("errors")

    def __len__(self):
        if self.errors:
            return 0
        return 1

    def __repr__(self):
        if self.errors:
            message = self.errors[0]["message"]
            return f"<{self.__class__.__name__} errors={message}>"
        return f"<{self.__class__.__name__}>"


class _AsUserStack:
    """Handle stack of users used over server api connection in service mode.

    ServerAPI can behave as other users if it is using special API key.

    Examples:
        >>> stack = _AsUserStack()
        >>> stack.set_default_username("DefaultName")
        >>> print(stack.username)
        DefaultName
        >>> with stack.as_user("Other1"):
        ...     print(stack.username)
        ...     with stack.as_user("Other2"):
        ...         print(stack.username)
        ...     print(stack.username)
        ...     stack.clear()
        ...     print(stack.username)
        Other1
        Other2
        Other1
        None
        >>> print(stack.username)
        None
        >>> stack.set_default_username("DefaultName")
        >>> print(stack.username)
        DefaultName

    """
    def __init__(self):
        self._users_by_id = {}
        self._user_ids = []
        self._last_user = None
        self._default_user = None

    def clear(self):
        self._users_by_id = {}
        self._user_ids = []
        self._last_user = None
        self._default_user = None

    @property
    def username(self):
        # Use '_user_ids' for boolean check to have ability "unset"
        #   default user
        if self._user_ids:
            return self._last_user
        return self._default_user

    def get_default_username(self):
        return self._default_user

    def set_default_username(self, username=None):
        self._default_user = username

    default_username = property(get_default_username, set_default_username)

    @contextmanager
    def as_user(self, username):
        self._last_user = username
        user_id = uuid.uuid4().hex
        self._user_ids.append(user_id)
        self._users_by_id[user_id] = username
        try:
            yield
        finally:
            self._users_by_id.pop(user_id, None)
            if not self._user_ids:
                return

            # First check if is the user id the last one
            was_last = self._user_ids[-1] == user_id
            # Remove id from variables
            if user_id in self._user_ids:
                self._user_ids.remove(user_id)

            if not was_last:
                return

            new_last_user = None
            if self._user_ids:
                new_last_user = self._users_by_id.get(self._user_ids[-1])
            self._last_user = new_last_user


class ServerAPI(
    _ActionsAPI,
    _ActivitiesAPI,
    _AddonsAPI,
    _EventsAPI,
    _FoldersAPI,
    _LinksAPI,
    _ListsAPI,
    _ProjectsAPI,
    _ThumbnailsAPI,
):
    """Base handler of connection to server.

    Requires url to server which is used as base for api and graphql calls.

    Login cause that a session is used

    Args:
        base_url (str): Example: http://localhost:5000
        token (Optional[str]): Access token (api key) to server.
        site_id (Optional[str]): Unique name of site. Should be the same when
            connection is created from the same machine under same user.
        client_version (Optional[str]): Version of client application (used in
            desktop client application).
        default_settings_variant (Optional[Literal["production", "staging"]]):
            Settings variant used by default if a method for settings won't
            get any (by default is 'production').
        sender_type (Optional[str]): Sender type of requests. Used in server
            logs and propagated into events.
        sender (Optional[str]): Sender of requests, more specific than
            sender type (e.g. machine name). Used in server logs and
            propagated into events.
        ssl_verify (Optional[Union[bool, str]]): Verify SSL certificate
            Looks for env variable value ``AYON_CA_FILE`` by default. If not
            available then 'True' is used.
        cert (Optional[str]): Path to certificate file. Looks for env
            variable value ``AYON_CERT_FILE`` by default.
        create_session (Optional[bool]): Create session for connection if
            token is available. Default is True.
        timeout (Optional[float]): Timeout for requests.
        max_retries (Optional[int]): Number of retries for requests.

    """
    _default_max_retries = 3
    # 1 MB chunk by default
    # TODO find out if these are reasonable default value
    default_download_chunk_size = 1024 * 1024
    default_upload_chunk_size = 1024 * 1024

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        site_id: Optional[str] = NOT_SET,
        client_version: Optional[str] = None,
        default_settings_variant: Optional[str] = None,
        sender_type: Optional[str] = None,
        sender: Optional[str] = None,
        ssl_verify: Optional["Union[bool, str]"]=None,
        cert: Optional[str] = None,
        create_session: bool = True,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        if not base_url:
            raise ValueError(f"Invalid server URL {str(base_url)}")

        base_url = base_url.rstrip("/")
        self._base_url: str = base_url
        self._rest_url: str = f"{base_url}/api"
        self._graphql_url: str = f"{base_url}/graphql"
        self._log: logging.Logger = logging.getLogger(self.__class__.__name__)
        self._access_token: Optional[str] = token
        # Allow to have 'site_id' to 'None'
        if site_id is NOT_SET:
            site_id = get_default_site_id()
        self._site_id: Optional[str] = site_id
        self._client_version: Optional[str] = client_version
        self._default_settings_variant: str = (
            default_settings_variant
            or get_default_settings_variant()
        )
        self._sender: Optional[str] = sender
        self._sender_type: Optional[str] = sender_type

        self._timeout: float = 0.0
        self._max_retries: int = 0

        # Set timeout and max retries based on passed values
        self.set_timeout(timeout)
        self.set_max_retries(max_retries)

        if ssl_verify is None:
            # Custom AYON env variable for CA file or 'True'
            # - that should cover most default behaviors in 'requests'
            #   with 'certifi'
            ssl_verify = os.environ.get("AYON_CA_FILE") or True

        if cert is None:
            cert = os.environ.get("AYON_CERT_FILE")

        self._ssl_verify = ssl_verify
        self._cert = cert

        self._access_token_is_service = None
        self._token_is_valid = None
        self._token_validation_started = False
        self._server_available = None
        self._server_version = None
        self._server_version_tuple = None

        self._graphql_allows_traits_in_representations: Optional[bool] = None

        self._session = None

        self._base_functions_mapping = {
            RequestTypes.get: requests.get,
            RequestTypes.post: requests.post,
            RequestTypes.put: requests.put,
            RequestTypes.patch: requests.patch,
            RequestTypes.delete: requests.delete
        }
        self._session_functions_mapping = {}

        # Attributes cache
        self._attributes_schema = None
        self._entity_type_attributes_cache = {}

        self._as_user_stack = _AsUserStack()

        # Create session
        if self._access_token and create_session:
            self.validate_server_availability()
            self.create_session()

    @property
    def log(self) -> logging.Logger:
        return self._log

    def get_base_url(self):
        return self._base_url

    def get_rest_url(self):
        return self._rest_url

    base_url = property(get_base_url)
    rest_url = property(get_rest_url)

    def get_ssl_verify(self):
        """Enable ssl verification.

        Returns:
            bool: Current state of ssl verification.

        """
        return self._ssl_verify

    def set_ssl_verify(self, ssl_verify):
        """Change ssl verification state.

        Args:
            ssl_verify (Union[bool, str, None]): Enabled/disable
                ssl verification, can be a path to file.

        """
        if self._ssl_verify == ssl_verify:
            return
        self._ssl_verify = ssl_verify
        if self._session is not None:
            self._session.verify = ssl_verify

    def get_cert(self):
        """Current cert file used for connection to server.

        Returns:
            Union[str, None]: Path to cert file.

        """
        return self._cert

    def set_cert(self, cert):
        """Change cert file used for connection to server.

        Args:
            cert (Union[str, None]): Path to cert file.

        """
        if cert == self._cert:
            return
        self._cert = cert
        if self._session is not None:
            self._session.cert = cert

    ssl_verify = property(get_ssl_verify, set_ssl_verify)
    cert = property(get_cert, set_cert)

    @classmethod
    def get_default_timeout(cls):
        """Default value for requests timeout.

        Utils function 'get_default_timeout' is used by default.

        Returns:
            float: Timeout value in seconds.

        """
        return get_default_timeout()

    @classmethod
    def get_default_max_retries(cls):
        """Default value for requests max retries.

        First looks for environment variable SERVER_RETRIES_ENV_KEY, which
        can affect max retries value. If not available then use class
        attribute '_default_max_retries'.

        Returns:
            int: Max retries value.

        """
        try:
            return int(os.environ.get(SERVER_RETRIES_ENV_KEY))
        except (ValueError, TypeError):
            pass

        return cls._default_max_retries

    def get_timeout(self) -> float:
        """Current value for requests timeout.

        Returns:
            float: Timeout value in seconds.

        """
        return self._timeout

    def set_timeout(self, timeout: Optional[float]):
        """Change timeout value for requests.

        Args:
            timeout (Optional[float]): Timeout value in seconds.

        """
        if timeout is None:
            timeout = self.get_default_timeout()
        self._timeout = float(timeout)

    def get_max_retries(self) -> int:
        """Current value for requests max retries.

        Returns:
            int: Max retries value.

        """
        return self._max_retries

    def set_max_retries(self, max_retries: Optional[int]):
        """Change max retries value for requests.

        Args:
            max_retries (Optional[int]): Max retries value.

        """
        if max_retries is None:
            max_retries = self.get_default_max_retries()
        self._max_retries = int(max_retries)

    timeout = property(get_timeout, set_timeout)
    max_retries = property(get_max_retries, set_max_retries)

    @property
    def access_token(self) -> Optional[str]:
        """Access token used for authorization to server.

        Returns:
            Optional[str]: Token string or None if not authorized yet.

        """
        return self._access_token

    def is_service_user(self) -> bool:
        """Check if connection is using service API key.

        Returns:
            bool: Used api key belongs to service user.

        """
        if not self.has_valid_token:
            raise ValueError("User is not logged in.")
        return bool(self._access_token_is_service)

    def get_site_id(self) -> Optional[str]:
        """Site id used for connection.

        Site id tells server from which machine/site is connection created and
        is used for default site overrides when settings are received.

        Returns:
            Optional[str]: Site id value or None if not filled.

        """
        return self._site_id

    def set_site_id(self, site_id: Optional[str]):
        """Change site id of connection.

        Behave as specific site for server. It affects default behavior of
        settings getter methods.

        Args:
            site_id (Optional[str]): Site id value, or 'None' to unset.

        """
        if self._site_id == site_id:
            return
        self._site_id = site_id
        # Recreate session on machine id change
        self._update_session_headers()

    site_id = property(get_site_id, set_site_id)

    def get_client_version(self) -> Optional[str]:
        """Version of client used to connect to server.

        Client version is AYON client build desktop application.

        Returns:
            str: Client version string used in connection.

        """
        return self._client_version

    def set_client_version(self, client_version: Optional[str]):
        """Set version of client used to connect to server.

        Client version is AYON client build desktop application.

        Args:
            client_version (Optional[str]): Client version string.

        """
        if self._client_version == client_version:
            return

        self._client_version = client_version
        self._update_session_headers()

    client_version = property(get_client_version, set_client_version)

    def get_default_settings_variant(self) -> str:
        """Default variant used for settings.

        Returns:
            Union[str, None]: name of variant or None.

        """
        return self._default_settings_variant

    def set_default_settings_variant(self, variant: str):
        """Change default variant for addon settings.

        Note:
            It is recommended to set only 'production' or 'staging' variants
                as default variant.

        Args:
            variant (str): Settings variant name. It is possible to use
                'production', 'staging' or name of dev bundle.

        """
        self._default_settings_variant = variant

    default_settings_variant = property(
        get_default_settings_variant,
        set_default_settings_variant
    )

    def get_sender(self) -> str:
        """Sender used to send requests.

        Returns:
            Union[str, None]: Sender name or None.

        """
        return self._sender

    def set_sender(self, sender: Optional[str]):
        """Change sender used for requests.

        Args:
            sender (Optional[str]): Sender name or None.

        """
        if sender == self._sender:
            return
        self._sender = sender
        self._update_session_headers()

    sender = property(get_sender, set_sender)

    def get_sender_type(self) -> Optional[str]:
        """Sender type used to send requests.

        Sender type is supported since AYON server 1.5.5 .

        Returns:
            Optional[str]: Sender type or None.

        """
        return self._sender_type

    def set_sender_type(self, sender_type: Optional[str]):
        """Change sender type used for requests.

        Args:
            sender_type (Optional[str]): Sender type or None.

        """
        if sender_type == self._sender_type:
            return
        self._sender_type = sender_type
        self._update_session_headers()

    sender_type = property(get_sender_type, set_sender_type)

    def get_default_service_username(self) -> Optional[str]:
        """Default username used for callbacks when used with service API key.

        Returns:
            Union[str, None]: Username if any was filled.

        """
        return self._as_user_stack.get_default_username()

    def set_default_service_username(self, username: Optional[str] = None):
        """Service API will work as other user.

        Service API keys can work as other user. It can be temporary using
        context manager 'as_user' or it is possible to set default username if
        'as_user' context manager is not entered.

        Args:
            username (Optional[str]): Username to work as when service.

        Raises:
            ValueError: When connection is not yet authenticated or api key
                is not service token.

        """
        current_username = self._as_user_stack.get_default_username()
        if current_username == username:
            return

        if not self.has_valid_token:
            raise ValueError(
                "Authentication of connection did not happen yet."
            )

        if not self._access_token_is_service:
            raise ValueError(
                "Can't set service username. API key is not a service token."
            )

        self._as_user_stack.set_default_username(username)
        if self._as_user_stack.username == username:
            self._update_session_headers()

    @contextmanager
    def as_username(
        self,
        username: "Union[str, None]",
        ignore_service_error: bool = False,
    ):
        """Service API will temporarily work as other user.

        This method can be used only if service API key is logged in.

        Args:
            username (Union[str, None]): Username to work as when service.
            ignore_service_error (Optional[bool]): Ignore error when service
                API key is not used.

        Raises:
            ValueError: When connection is not yet authenticated or api key
                is not service token.

        """
        if not self.has_valid_token:
            raise ValueError(
                "Authentication of connection did not happen yet."
            )

        if not self._access_token_is_service:
            if ignore_service_error:
                yield None
                return
            raise ValueError(
                "Can't set service username. API key is not a service token."
            )

        try:
            with self._as_user_stack.as_user(username) as o:
                self._update_session_headers()
                yield o
        finally:
            self._update_session_headers()

    @property
    def is_server_available(self) -> bool:
        if self._server_available is None:
            response = requests.get(
                self._base_url,
                cert=self._cert,
                verify=self._ssl_verify
            )
            self._server_available = response.status_code == 200
        return self._server_available

    @property
    def has_valid_token(self) -> bool:
        if self._access_token is None:
            return False

        if self._token_is_valid is None:
            self.validate_token()
        return self._token_is_valid

    def validate_server_availability(self):
        if not self.is_server_available:
            raise ServerNotReached(
                f"Server \"{self._base_url}\" can't be reached"
            )

    def validate_token(self) -> bool:
        try:
            self._token_validation_started = True
            # TODO add other possible validations
            # - existence of 'user' key in info
            # - validate that 'site_id' is in 'sites' in info
            self.get_info()
            self.get_user()
            self._token_is_valid = True

        except UnauthorizedError:
            self._token_is_valid = False

        finally:
            self._token_validation_started = False
        return self._token_is_valid

    def set_token(self, token: Optional[str]):
        self.reset_token()
        self._access_token = token
        self.get_user()

    def reset_token(self):
        self._access_token = None
        self._token_is_valid = None
        self.close_session()

    def create_session(
        self, ignore_existing: bool = True, force: bool = False
    ):
        """Create a connection session.

        Session helps to keep connection with server without
        need to reconnect on each call.

        Args:
            ignore_existing (bool): If session already exists,
                ignore creation.
            force (bool): If session already exists, close it and
                create new.

        """
        if force and self._session is not None:
            self.close_session()

        if self._session is not None:
            if ignore_existing:
                return
            raise ValueError("Session is already created.")

        self._as_user_stack.clear()
        # Validate token before session creation
        self.validate_token()

        session = requests.Session()
        session.cert = self._cert
        session.verify = self._ssl_verify
        session.headers.update(self.get_headers())

        self._session_functions_mapping = {
            RequestTypes.get: session.get,
            RequestTypes.post: session.post,
            RequestTypes.put: session.put,
            RequestTypes.patch: session.patch,
            RequestTypes.delete: session.delete
        }
        self._session = session

    def close_session(self):
        if self._session is None:
            return

        session = self._session
        self._session = None
        self._session_functions_mapping = {}
        session.close()

    def _update_session_headers(self):
        if self._session is None:
            return

        # Header keys that may change over time
        for key, value in (
            ("X-as-user", self._as_user_stack.username),
            ("x-ayon-version", self._client_version),
            ("x-ayon-site-id", self._site_id),
            ("x-sender-type", self._sender_type),
            ("x-sender", self._sender),
        ):
            if value is not None:
                self._session.headers[key] = value
            elif key in self._session.headers:
                self._session.headers.pop(key)

    def get_info(self) -> Dict[str, Any]:
        """Get information about current used api key.

        By default, the 'info' contains only 'uptime' and 'version'. With
        logged user info also contains information about user and machines on
        which was logged in.

        Todos:
            Use this method for validation of token instead of 'get_user'.

        Returns:
            dict[str, Any]: Information from server.

        """
        response = self.get("info")
        response.raise_for_status()
        return response.data

    def get_server_version(self) -> str:
        """Get server version.

        Version should match semantic version (https://semver.org/).

        Returns:
            str: Server version.

        """
        if self._server_version is None:
            self._server_version = self.get_info()["version"]
        return self._server_version

    def get_server_version_tuple(self) -> "ServerVersion":
        """Get server version as tuple.

        Version should match semantic version (https://semver.org/).

        This function only returns first three numbers of version.

        Returns:
            Tuple[int, int, int, Union[str, None], Union[str, None]]: Server
                version.

        """
        if self._server_version_tuple is None:
            re_match = VERSION_REGEX.fullmatch(
                self.get_server_version())
            self._server_version_tuple = (
                int(re_match.group("major")),
                int(re_match.group("minor")),
                int(re_match.group("patch")),
                re_match.group("prerelease") or "",
                re_match.group("buildmetadata") or "",
            )
        return self._server_version_tuple

    server_version = property(get_server_version)
    server_version_tuple: "ServerVersion" = property(
        get_server_version_tuple
    )

    @property
    def graphql_allows_traits_in_representations(self) -> bool:
        """Check server support for representation traits."""
        if self._graphql_allows_traits_in_representations is None:
            major, minor, patch, _, _ = self.server_version_tuple
            self._graphql_allows_traits_in_representations = (
                (major, minor, patch) >= (1, 7, 5)
            )
        return self._graphql_allows_traits_in_representations

    def _get_user_info(self) -> Optional[Dict[str, Any]]:
        if self._access_token is None:
            return None

        if self._access_token_is_service is not None:
            response = self.get("users/me")
            if response.status == 200:
                return response.data
            return None

        self._access_token_is_service = False
        response = self.get("users/me")
        if response.status == 200:
            return response.data

        self._access_token_is_service = True
        response = self.get("users/me")
        if response.status == 200:
            return response.data

        self._access_token_is_service = None
        return None

    def get_users(
        self,
        project_name: Optional[str] = None,
        usernames: Optional[Iterable[str]] = None,
        emails: Optional[Iterable[str]] = None,
        fields: Optional[Iterable[str]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Get Users.

        Only administrators and managers can fetch all users. For other users
            it is required to pass in 'project_name' filter.

        Args:
            project_name (Optional[str]): Project name.
            usernames (Optional[Iterable[str]]): Filter by usernames.
            emails (Optional[Iterable[str]]): Filter by emails.
            fields (Optional[Iterable[str]]): Fields to be queried
                for users.

        Returns:
            Generator[dict[str, Any]]: Queried users.

        """
        filters = {}
        if usernames is not None:
            usernames = set(usernames)
            if not usernames:
                return
            filters["userNames"] = list(usernames)

        if emails is not None:
            emails = set(emails)
            if not emails:
                return

            major, minor, patch, _, _ = self.server_version_tuple
            emails_filter_available = (major, minor, patch) > (1, 7, 3)
            if not emails_filter_available:
                server_version = self.get_server_version()
                raise ValueError(
                    "Filtering by emails is not supported by"
                    f" server version {server_version}."
                )

            filters["emails"] = list(emails)

        if project_name is not None:
            filters["projectName"] = project_name

        if not fields:
            fields = self.get_default_fields_for_type("user")

        query = users_graphql_query(set(fields))
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        attributes = self.get_attributes_for_type("user")
        for parsed_data in query.continuous_query(self):
            for user in parsed_data["users"]:
                access_groups = user.get("accessGroups")
                if isinstance(access_groups, str):
                    user["accessGroups"] = json.loads(access_groups)
                all_attrib = user.get("allAttrib")
                if isinstance(all_attrib, str):
                    user["allAttrib"] = json.loads(all_attrib)
                if "attrib" in user:
                    user["ownAttrib"] = user["attrib"].copy()
                    attrib = user["attrib"]
                    for key, value in tuple(attrib.items()):
                        if value is not None:
                            continue
                        attr_def = attributes.get(key)
                        if attr_def is not None:
                            attrib[key] = attr_def["default"]
                yield user

    def get_user_by_name(
        self,
        username: str,
        project_name: Optional[str] = None,
        fields: Optional[Iterable[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get user by name using GraphQl.

        Only administrators and managers can fetch all users. For other users
            it is required to pass in 'project_name' filter.

        Args:
            username (str): Username.
            project_name (Optional[str]): Define scope of project.
            fields (Optional[Iterable[str]]): Fields to be queried
                for users.

        Returns:
            Union[dict[str, Any], None]: User info or None if user is not
                found.

        """
        if not username:
            return None

        for user in self.get_users(
            project_name=project_name,
            usernames={username},
            fields=fields,
        ):
            return user
        return None

    def get_user(
        self, username: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get user info using REST endpoint.

        User contains only explicitly set attributes in 'attrib'.

        Args:
            username (Optional[str]): Username.

        Returns:
            Optional[Dict[str, Any]]: User info or None if user is not
                found.

        """
        if username is None:
            user = self._get_user_info()
            if user is None:
                raise UnauthorizedError("User is not authorized.")
        else:
            response = self.get(f"users/{username}")
            response.raise_for_status()
            user = response.data

        # NOTE Server does return only filled attributes right now.
        #   This would fill all missing attributes with 'None'.
        # for attr_name in self.get_attributes_for_type("user"):
        #     user["attrib"].setdefault(attr_name, None)

        fill_own_attribs(user)
        return user

    def get_headers(
        self, content_type: Optional[str] = None
    ) -> Dict[str, str]:
        if content_type is None:
            content_type = "application/json"

        headers = {
            "Content-Type": content_type,
            "x-ayon-platform": platform.system().lower(),
            "x-ayon-hostname": get_machine_name(),
            "referer": self.get_base_url(),
        }
        if self._site_id is not None:
            headers["x-ayon-site-id"] = self._site_id

        if self._client_version is not None:
            headers["x-ayon-version"] = self._client_version

        if self._sender_type is not None:
            headers["x-sender-type"] = self._sender_type

        if self._sender is not None:
            headers["x-sender"] = self._sender

        if self._access_token:
            if self._access_token_is_service:
                headers["X-Api-Key"] = self._access_token
                username = self._as_user_stack.username
                if username:
                    headers["X-as-user"] = username
            else:
                headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def login(
        self, username: str, password: str, create_session: bool = True
    ):
        """Login to server.

        Args:
            username (str): Username.
            password (str): Password.
            create_session (Optional[bool]): Create session after login.
                Default: True.

        Raises:
            AuthenticationError: Login failed.

        """
        if self.has_valid_token:
            try:
                user_info = self.get_user()
            except UnauthorizedError:
                user_info = {}

            current_username = user_info.get("name")
            if current_username == username:
                self.close_session()
                if create_session:
                    self.create_session()
                return

        self.reset_token()

        self.validate_server_availability()

        self._token_validation_started = True

        try:
            response = self.post(
                "auth/login",
                name=username,
                password=password
            )
            if response.status_code != 200:
                _detail = response.data.get("detail")
                details = ""
                if _detail:
                    details = f" {_detail}"

                raise AuthenticationError(f"Login failed {details}")

        finally:
            self._token_validation_started = False

        self._access_token = response["token"]

        if not self.has_valid_token:
            raise AuthenticationError("Invalid credentials")

        if create_session:
            self.create_session()

    def logout(self, soft: bool = False):
        if self._access_token:
            if not soft:
                self._logout()
            self.reset_token()

    def _logout(self):
        logout_from_server(self._base_url, self._access_token)

    def _do_rest_request(self, function, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        max_retries = kwargs.get("max_retries", self.max_retries)
        if max_retries < 1:
            max_retries = 1
        if self._session is None:
            # Validate token if was not yet validated
            #    - ignore validation if we're in middle of
            #       validation
            if (
                self._token_is_valid is None
                and not self._token_validation_started
            ):
                self.validate_token()

            if "headers" not in kwargs:
                kwargs["headers"] = self.get_headers()

            if isinstance(function, RequestType):
                function = self._base_functions_mapping[function]

        elif isinstance(function, RequestType):
            function = self._session_functions_mapping[function]

        response = None
        new_response = None
        for retry_idx in reversed(range(max_retries)):
            try:
                response = function(url, **kwargs)
                break

            except ConnectionRefusedError:
                if retry_idx == 0:
                    self.log.warning(
                        "Connection error happened.", exc_info=True
                    )

                # Server may be restarting
                new_response = RestApiResponse(
                    None,
                    {
                        "detail": (
                            "Unable to connect the server. Connection refused"
                        )
                    }
                )

            except requests.exceptions.Timeout:
                # Connection timed out
                new_response = RestApiResponse(
                    None,
                    {"detail": "Connection timed out."}
                )

            except requests.exceptions.ConnectionError:
                # Log warning only on last attempt
                if retry_idx == 0:
                    self.log.warning(
                        "Connection error happened.", exc_info=True
                    )

                new_response = RestApiResponse(
                    None,
                    {
                        "detail": (
                            "Unable to connect the server. Connection error"
                        )
                    }
                )

            time.sleep(0.1)

        if new_response is not None:
            return new_response

        new_response = RestApiResponse(response)
        self.log.debug(f"Response {str(new_response)}")
        return new_response

    def raw_post(self, entrypoint: str, **kwargs):
        url = self._endpoint_to_url(entrypoint)
        self.log.debug(f"Executing [POST] {url}")
        return self._do_rest_request(
            RequestTypes.post,
            url,
            **kwargs
        )

    def raw_put(self, entrypoint: str, **kwargs):
        url = self._endpoint_to_url(entrypoint)
        self.log.debug(f"Executing [PUT] {url}")
        return self._do_rest_request(
            RequestTypes.put,
            url,
            **kwargs
        )

    def raw_patch(self, entrypoint: str, **kwargs):
        url = self._endpoint_to_url(entrypoint)
        self.log.debug(f"Executing [PATCH] {url}")
        return self._do_rest_request(
            RequestTypes.patch,
            url,
            **kwargs
        )

    def raw_get(self, entrypoint: str, **kwargs):
        url = self._endpoint_to_url(entrypoint)
        self.log.debug(f"Executing [GET] {url}")
        return self._do_rest_request(
            RequestTypes.get,
            url,
            **kwargs
        )

    def raw_delete(self, entrypoint: str, **kwargs):
        url = self._endpoint_to_url(entrypoint)
        self.log.debug(f"Executing [DELETE] {url}")
        return self._do_rest_request(
            RequestTypes.delete,
            url,
            **kwargs
        )

    def post(self, entrypoint: str, **kwargs):
        return self.raw_post(entrypoint, json=kwargs)

    def put(self, entrypoint: str, **kwargs):
        return self.raw_put(entrypoint, json=kwargs)

    def patch(self, entrypoint: str, **kwargs):
        return self.raw_patch(entrypoint, json=kwargs)

    def get(self, entrypoint: str, **kwargs):
        return self.raw_get(entrypoint, params=kwargs)

    def delete(self, entrypoint: str, **kwargs):
        return self.raw_delete(entrypoint, params=kwargs)

    def _endpoint_to_url(
        self,
        endpoint: str,
        use_rest: Optional[bool] = True
    ) -> str:
        """Cleanup endpoint and return full url to AYON server.

        If endpoint already starts with server url only slashes are removed.

        Args:
            endpoint (str): Endpoint to be cleaned.
            use_rest (Optional[bool]): Use only base server url if set to
                False, otherwise REST endpoint is used.

        Returns:
            str: Full url to AYON server.

        """
        endpoint = endpoint.lstrip("/").rstrip("/")
        if endpoint.startswith(self._base_url):
            return endpoint
        base_url = self._rest_url if use_rest else self._graphql_url
        return f"{base_url}/{endpoint}"

    def _download_file_to_stream(
        self, url: str, stream, chunk_size, progress
    ):
        kwargs = {"stream": True}
        if self._session is None:
            kwargs["headers"] = self.get_headers()
            get_func = self._base_functions_mapping[RequestTypes.get]
        else:
            get_func = self._session_functions_mapping[RequestTypes.get]

        with get_func(url, **kwargs) as response:
            response.raise_for_status()
            progress.set_content_size(response.headers["Content-length"])
            for chunk in response.iter_content(chunk_size=chunk_size):
                stream.write(chunk)
                progress.add_transferred_chunk(len(chunk))

    def download_file_to_stream(
        self,
        endpoint: str,
        stream: "StreamType",
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> TransferProgress:
        """Download file from AYON server to IOStream.

        Endpoint can be full url (must start with 'base_url' of api object).

        Progress object can be used to track download. Can be used when
        download happens in thread and other thread want to catch changes over
        time.

        Todos:
            Use retries and timeout.
            Return RestApiResponse.

        Args:
            endpoint (str): Endpoint or URL to file that should be downloaded.
            stream (StreamType): Stream where output will
                be stored.
            chunk_size (Optional[int]): Size of chunks that are received
                in single loop.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        """
        if not chunk_size:
            chunk_size = self.default_download_chunk_size

        url = self._endpoint_to_url(endpoint)

        if progress is None:
            progress = TransferProgress()

        progress.set_source_url(url)
        progress.set_started()

        try:
            self._download_file_to_stream(
                url, stream, chunk_size, progress
            )

        except Exception as exc:
            progress.set_failed(str(exc))
            raise

        finally:
            progress.set_transfer_done()
        return progress

    def download_file(
        self,
        endpoint: str,
        filepath: str,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> TransferProgress:
        """Download file from AYON server.

        Endpoint can be full url (must start with 'base_url' of api object).

        Progress object can be used to track download. Can be used when
        download happens in thread and other thread want to catch changes over
        time.

        Todos:
            Use retries and timeout.
            Return RestApiResponse.

        Args:
            endpoint (str): Endpoint or URL to file that should be downloaded.
            filepath (str): Path where file will be downloaded.
            chunk_size (Optional[int]): Size of chunks that are received
                in single loop.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        """
        # Create dummy object so the function does not have to check
        #   'progress' variable everywhere
        if progress is None:
            progress = TransferProgress()

        progress.set_destination_url(filepath)

        dst_directory = os.path.dirname(filepath)
        os.makedirs(dst_directory, exist_ok=True)

        try:
            with open(filepath, "wb") as stream:
                self.download_file_to_stream(
                    endpoint, stream, chunk_size, progress
                )

        except Exception as exc:
            progress.set_failed(str(exc))
            raise

        return progress

    @staticmethod
    def _upload_chunks_iter(
        file_stream: "StreamType",
        progress: TransferProgress,
        chunk_size: int,
    ) -> Generator[bytes, None, None]:
        """Generator that yields chunks of file.

        Args:
            file_stream (StreamType): Byte stream.
            progress (TransferProgress): Object to track upload progress.
            chunk_size (int): Size of chunks that are uploaded at once.

        Yields:
            bytes: Chunk of file.

        """
        # Get size of file
        file_stream.seek(0, io.SEEK_END)
        size = file_stream.tell()
        file_stream.seek(0)
        # Set content size to progress object
        progress.set_content_size(size)

        while True:
            chunk = file_stream.read(chunk_size)
            if not chunk:
                break
            progress.add_transferred_chunk(len(chunk))
            yield chunk

    def _upload_file(
        self,
        url: str,
        stream: "StreamType",
        progress: TransferProgress,
        request_type: Optional[RequestType] = None,
        chunk_size: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """Upload file to server.

        Args:
            url (str): Url where file will be uploaded.
            stream (StreamType): File stream.
            progress (TransferProgress): Object that gives ability to track
                progress.
            request_type (Optional[RequestType]): Type of request that will
                be used. Default is PUT.
            chunk_size (Optional[int]): Size of chunks that are uploaded
                at once.
            **kwargs (Any): Additional arguments that will be passed
                to request function.

        Returns:
            requests.Response: Server response.

        """
        if request_type is None:
            request_type = RequestTypes.put

        if self._session is None:
            headers = kwargs.setdefault("headers", {})
            for key, value in self.get_headers().items():
                if key not in headers:
                    headers[key] = value
            post_func = self._base_functions_mapping[request_type]
        else:
            post_func = self._session_functions_mapping[request_type]

        if not chunk_size:
            chunk_size = self.default_upload_chunk_size

        response = post_func(
            url,
            data=self._upload_chunks_iter(stream, progress, chunk_size),
            **kwargs
        )

        response.raise_for_status()
        return response

    def upload_file_from_stream(
        self,
        endpoint: str,
        stream: "StreamType",
        progress: Optional[TransferProgress] = None,
        request_type: Optional[RequestType] = None,
        **kwargs
    ) -> requests.Response:
        """Upload file to server from bytes.

        Todos:
            Use retries and timeout.
            Return RestApiResponse.

        Args:
            endpoint (str): Endpoint or url where file will be uploaded.
            stream (StreamType): File content stream.
            progress (Optional[TransferProgress]): Object that gives ability
                to track upload progress.
            request_type (Optional[RequestType]): Type of request that will
                be used to upload file.
            **kwargs (Any): Additional arguments that will be passed
                to request function.

        Returns:
            requests.Response: Response object

        """
        url = self._endpoint_to_url(endpoint)

        # Create dummy object so the function does not have to check
        #   'progress' variable everywhere
        if progress is None:
            progress = TransferProgress()

        progress.set_destination_url(url)
        progress.set_started()

        try:
            return self._upload_file(
                url, stream, progress, request_type, **kwargs
            )

        except Exception as exc:
            progress.set_failed(str(exc))
            raise

        finally:
            progress.set_transfer_done()

    def upload_file(
        self,
        endpoint: str,
        filepath: str,
        progress: Optional[TransferProgress] = None,
        request_type: Optional[RequestType] = None,
        **kwargs
    ) -> requests.Response:
        """Upload file to server.

        Todos:
            Use retries and timeout.
            Return RestApiResponse.

        Args:
            endpoint (str): Endpoint or url where file will be uploaded.
            filepath (str): Source filepath.
            progress (Optional[TransferProgress]): Object that gives ability
                to track upload progress.
            request_type (Optional[RequestType]): Type of request that will
                be used to upload file.
            **kwargs (Any): Additional arguments that will be passed
                to request function.

        Returns:
            requests.Response: Response object

        """
        if progress is None:
            progress = TransferProgress()

        progress.set_source_url(filepath)

        with open(filepath, "rb") as stream:
            return self.upload_file_from_stream(
                endpoint, stream, progress, request_type, **kwargs
            )

    def upload_reviewable(
        self,
        project_name: str,
        version_id: str,
        filepath: str,
        label: Optional[str] = None,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        progress: Optional[TransferProgress] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """Upload reviewable file to server.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            filepath (str): Reviewable file path to upload.
            label (Optional[str]): Reviewable label. Filled automatically
                server side with filename.
            content_type (Optional[str]): MIME type of the file.
            filename (Optional[str]): User as original filename. Filename from
                'filepath' is used when not filled.
            progress (Optional[TransferProgress]): Progress.
            headers (Optional[Dict[str, Any]]): Headers.

        Returns:
            requests.Response: Server response.

        """
        if not content_type:
            content_type = get_media_mime_type(filepath)

        if not content_type:
            raise ValueError(
                f"Could not determine MIME type of file '{filepath}'"
            )

        if headers is None:
            headers = self.get_headers(content_type)
        else:
            # Make sure content-type is filled with file content type
            content_type_key = next(
                (
                    key
                    for key in headers
                    if key.lower() == "content-type"
                ),
                "Content-Type"
            )
            headers[content_type_key] = content_type

        # Fill original filename if not explicitly defined
        if not filename:
            filename = os.path.basename(filepath)
        headers["x-file-name"] = filename

        query = prepare_query_string({"label": label or None})
        endpoint = (
            f"/projects/{project_name}"
            f"/versions/{version_id}/reviewables{query}"
        )
        return self.upload_file(
            endpoint,
            filepath,
            progress=progress,
            headers=headers,
            request_type=RequestTypes.post,
            **kwargs
        )

    def trigger_server_restart(self):
        """Trigger server restart.

        Restart may be required when a change of specific value happened on
        server.

        """
        result = self.post("system/restart")
        if result.status_code != 204:
            # TODO add better exception
            raise ValueError("Failed to restart server")

    def query_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> GraphQlResponse:
        """Execute GraphQl query.

        Args:
            query (str): GraphQl query string.
            variables (Optional[dict[str, Any]): Variables that can be
                used in query.

        Returns:
            GraphQlResponse: Response from server.

        """
        data = {"query": query, "variables": variables or {}}
        response = self._do_rest_request(
            RequestTypes.post,
            self._graphql_url,
            json=data
        )
        response.raise_for_status()
        return GraphQlResponse(response)

    def get_graphql_schema(self) -> Dict[str, Any]:
        return self.query_graphql(INTROSPECTION_QUERY).data["data"]

    def get_server_schema(self) -> Optional[Dict[str, Any]]:
        """Get server schema with info, url paths, components etc.

        Todos:
            Cache schema - How to find out it is outdated?

        Returns:
            dict[str, Any]: Full server schema.

        """
        url = f"{self._base_url}/openapi.json"
        response = self._do_rest_request(RequestTypes.get, url)
        if response:
            return response.data
        return None

    def get_schemas(self) -> Dict[str, Any]:
        """Get components schema.

        Name of components does not match entity type names e.g. 'project' is
        under 'ProjectModel'. We should find out some mapping. Also, there
        are properties which don't have information about reference to object
        e.g. 'config' has just object definition without reference schema.

        Returns:
            dict[str, Any]: Component schemas.

        """
        server_schema = self.get_server_schema()
        return server_schema["components"]["schemas"]

    def get_attributes_schema(
        self, use_cache: bool = True
    ) -> "AttributesSchemaDict":
        if not use_cache:
            self.reset_attributes_schema()

        if self._attributes_schema is None:
            result = self.get("attributes")
            result.raise_for_status()
            self._attributes_schema = result.data
        return copy.deepcopy(self._attributes_schema)

    def reset_attributes_schema(self):
        self._attributes_schema = None
        self._entity_type_attributes_cache = {}

    def set_attribute_config(
        self,
        attribute_name: str,
        data: "AttributeSchemaDataDict",
        scope: List["AttributeScope"],
        position: Optional[int] = None,
        builtin: bool = False,
    ):
        if position is None:
            attributes = self.get("attributes").data["attributes"]
            origin_attr = next(
                (
                    attr for attr in attributes
                    if attr["name"] == attribute_name
                ),
                None
            )
            if origin_attr:
                position = origin_attr["position"]
            else:
                position = len(attributes)

        response = self.put(
            f"attributes/{attribute_name}",
            data=data,
            scope=scope,
            position=position,
            builtin=builtin
        )
        if response.status_code != 204:
            # TODO raise different exception
            raise ValueError(
                f"Attribute \"{attribute_name}\" was not created/updated."
                f" {response.detail}"
            )

        self.reset_attributes_schema()

    def remove_attribute_config(self, attribute_name: str):
        """Remove attribute from server.

        This can't be un-done, please use carefully.

        Args:
            attribute_name (str): Name of attribute to remove.

        """
        response = self.delete(f"attributes/{attribute_name}")
        response.raise_for_status(
            f"Attribute \"{attribute_name}\" was not created/updated."
            f" {response.detail}"
        )

        self.reset_attributes_schema()

    def get_attributes_for_type(
        self, entity_type: "AttributeScope"
    ) -> Dict[str, "AttributeSchemaDict"]:
        """Get attribute schemas available for an entity type.

        Example::

            ```
            # Example attribute schema
            {
                # Common
                "type": "integer",
                "title": "Clip Out",
                "description": null,
                "example": 1,
                "default": 1,
                # These can be filled based on value of 'type'
                "gt": null,
                "ge": null,
                "lt": null,
                "le": null,
                "minLength": null,
                "maxLength": null,
                "minItems": null,
                "maxItems": null,
                "regex": null,
                "enum": null
            }
            ```

        Args:
            entity_type (str): Entity type for which should be attributes
                received.

        Returns:
            dict[str, dict[str, Any]]: Attribute schemas that are available
                for entered entity type.

        """
        attributes = self._entity_type_attributes_cache.get(entity_type)
        if attributes is None:
            attributes_schema = self.get_attributes_schema()
            attributes = {}
            for attr in attributes_schema["attributes"]:
                if entity_type not in attr["scope"]:
                    continue
                attr_name = attr["name"]
                attributes[attr_name] = attr["data"]

            self._entity_type_attributes_cache[entity_type] = attributes

        return copy.deepcopy(attributes)

    def get_attributes_fields_for_type(
        self, entity_type: "AttributeScope"
    ) -> Set[str]:
        """Prepare attribute fields for entity type.

        Returns:
            set[str]: Attributes fields for entity type.

        """
        attributes = self.get_attributes_for_type(entity_type)
        return {
            f"attrib.{attr}"
            for attr in attributes
        }

    def get_default_fields_for_type(self, entity_type: str) -> Set[str]:
        """Default fields for entity type.

        Returns most of commonly used fields from server.

        Args:
            entity_type (str): Name of entity type.

        Returns:
            set[str]: Fields that should be queried from server.

        """
        # Event does not have attributes
        if entity_type == "event":
            return set(DEFAULT_EVENT_FIELDS)

        if entity_type == "activity":
            return set(DEFAULT_ACTIVITY_FIELDS)

        if entity_type == "project":
            entity_type_defaults = set(DEFAULT_PROJECT_FIELDS)
            maj_v, min_v, patch_v, _, _ = self.server_version_tuple
            if (maj_v, min_v, patch_v) > (1, 10, 0):
                entity_type_defaults.add("productTypes")

        elif entity_type == "folder":
            entity_type_defaults = set(DEFAULT_FOLDER_FIELDS)

        elif entity_type == "task":
            entity_type_defaults = set(DEFAULT_TASK_FIELDS)

        elif entity_type == "product":
            entity_type_defaults = set(DEFAULT_PRODUCT_FIELDS)

        elif entity_type == "version":
            entity_type_defaults = set(DEFAULT_VERSION_FIELDS)

        elif entity_type == "representation":
            entity_type_defaults = (
                DEFAULT_REPRESENTATION_FIELDS
                | REPRESENTATION_FILES_FIELDS
            )

            if not self.graphql_allows_traits_in_representations:
                entity_type_defaults.discard("traits")

        elif entity_type == "productType":
            entity_type_defaults = set(DEFAULT_PRODUCT_TYPE_FIELDS)

        elif entity_type == "workfile":
            entity_type_defaults = set(DEFAULT_WORKFILE_INFO_FIELDS)

        elif entity_type == "user":
            entity_type_defaults = set(DEFAULT_USER_FIELDS)

        elif entity_type == "entityList":
            entity_type_defaults = set(DEFAULT_ENTITY_LIST_FIELDS)

        else:
            raise ValueError(f"Unknown entity type \"{entity_type}\"")
        return (
            entity_type_defaults
            | self.get_attributes_fields_for_type(entity_type)
        )

    def get_installers(
        self,
        version: Optional[str] = None,
        platform_name: Optional[str] = None,
    ) -> "InstallersInfoDict":
        """Information about desktop application installers on server.

        Desktop application installers are helpers to download/update AYON
        desktop application for artists.

        Args:
            version (Optional[str]): Filter installers by version.
            platform_name (Optional[str]): Filter installers by platform name.

        Returns:
            InstallersInfoDict: Information about installers known for server.

        """
        query = prepare_query_string({
            "version": version or None,
            "platform": platform_name or None,
        })
        response = self.get(f"desktop/installers{query}")
        response.raise_for_status()
        return response.data

    def create_installer(
        self,
        filename: str,
        version: str,
        python_version: str,
        platform_name: str,
        python_modules: Dict[str, str],
        runtime_python_modules: Dict[str, str],
        checksum: str,
        checksum_algorithm: str,
        file_size: int,
        sources: Optional[List[Dict[str, Any]]] = None,
    ):
        """Create new installer information on server.

        This step will create only metadata. Make sure to upload installer
            to the server using 'upload_installer' method.

        Runtime python modules are modules that are required to run AYON
            desktop application, but are not added to PYTHONPATH for any
            subprocess.

        Args:
            filename (str): Installer filename.
            version (str): Version of installer.
            python_version (str): Version of Python.
            platform_name (str): Name of platform.
            python_modules (dict[str, str]): Python modules that are available
                in installer.
            runtime_python_modules (dict[str, str]): Runtime python modules
                that are available in installer.
            checksum (str): Installer file checksum.
            checksum_algorithm (str): Type of checksum used to create checksum.
            file_size (int): File size.
            sources (Optional[list[dict[str, Any]]]): List of sources that
                can be used to download file.

        """
        body = {
            "filename": filename,
            "version": version,
            "pythonVersion": python_version,
            "platform": platform_name,
            "pythonModules": python_modules,
            "runtimePythonModules": runtime_python_modules,
            "checksum": checksum,
            "checksumAlgorithm": checksum_algorithm,
            "size": file_size,
        }
        if sources:
            body["sources"] = sources

        response = self.post("desktop/installers", **body)
        response.raise_for_status()

    def update_installer(self, filename: str, sources: List[Dict[str, Any]]):
        """Update installer information on server.

        Args:
            filename (str): Installer filename.
            sources (list[dict[str, Any]]): List of sources that
                can be used to download file. Fully replaces existing sources.

        """
        response = self.patch(
            f"desktop/installers/{filename}",
            sources=sources
        )
        response.raise_for_status()

    def delete_installer(self, filename: str):
        """Delete installer from server.

        Args:
            filename (str): Installer filename.

        """
        response = self.delete(f"desktop/installers/{filename}")
        response.raise_for_status()

    def download_installer(
        self,
        filename: str,
        dst_filepath: str,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None
    ):
        """Download installer file from server.

        Args:
            filename (str): Installer filename.
            dst_filepath (str): Destination filepath.
            chunk_size (Optional[int]): Download chunk size.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        """
        self.download_file(
            f"desktop/installers/{filename}",
            dst_filepath,
            chunk_size=chunk_size,
            progress=progress
        )

    def upload_installer(
        self,
        src_filepath: str,
        dst_filename: str,
        progress: Optional[TransferProgress] = None,
    ):
        """Upload installer file to server.

        Args:
            src_filepath (str): Source filepath.
            dst_filename (str): Destination filename.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        Returns:
            requests.Response: Response object.

        """
        return self.upload_file(
            f"desktop/installers/{dst_filename}",
            src_filepath,
            progress=progress
        )

    def _get_dependency_package_route(
        self, filename: Optional[str] = None
    ) -> str:
        endpoint = "desktop/dependencyPackages"
        if filename:
            return f"{endpoint}/{filename}"
        return endpoint

    def get_dependency_packages(self) -> "DependencyPackagesDict":
        """Information about dependency packages on server.

        To download dependency package, use 'download_dependency_package'
        method and pass in 'filename'.

        Example data structure::

            {
                "packages": [
                    {
                        "filename": str,
                        "platform": str,
                        "checksum": str,
                        "checksumAlgorithm": str,
                        "size": int,
                        "sources": list[dict[str, Any]],
                        "supportedAddons": dict[str, str],
                        "pythonModules": dict[str, str]
                    }
                ]
            }

        Returns:
            DependencyPackagesDict: Information about dependency packages
                known for server.

        """
        endpoint = self._get_dependency_package_route()
        result = self.get(endpoint)
        result.raise_for_status()
        return result.data

    def create_dependency_package(
        self,
        filename: str,
        python_modules: Dict[str, str],
        source_addons: Dict[str, str],
        installer_version: str,
        checksum: str,
        checksum_algorithm: str,
        file_size: int,
        sources: Optional[List[Dict[str, Any]]] = None,
        platform_name: Optional[str] = None,
    ):
        """Create dependency package on server.

        The package will be created on a server, it is also required to upload
        the package archive file (using :meth:`upload_dependency_package`).

        Args:
            filename (str): Filename of dependency package.
            python_modules (dict[str, str]): Python modules in dependency
                package::

                    {"<module name>": "<module version>", ...}

            source_addons (dict[str, str]): Name of addons for which is
                dependency package created::

                    {"<addon name>": "<addon version>", ...}

            installer_version (str): Version of installer for which was
                package created.
            checksum (str): Checksum of archive file where dependencies are.
            checksum_algorithm (str): Algorithm used to calculate checksum.
            file_size (Optional[int]): Size of file.
            sources (Optional[list[dict[str, Any]]]): Information about
                sources from where it is possible to get file.
            platform_name (Optional[str]): Name of platform for which is
                dependency package targeted. Default value is
                current platform.

        """
        post_body = {
            "filename": filename,
            "pythonModules": python_modules,
            "sourceAddons": source_addons,
            "installerVersion": installer_version,
            "checksum": checksum,
            "checksumAlgorithm": checksum_algorithm,
            "size": file_size,
            "platform": platform_name or platform.system().lower(),
        }
        if sources:
            post_body["sources"] = sources

        route = self._get_dependency_package_route()
        response = self.post(route, **post_body)
        response.raise_for_status()

    def update_dependency_package(
        self, filename: str, sources: List[Dict[str, Any]]
    ):
        """Update dependency package metadata on server.

        Args:
            filename (str): Filename of dependency package.
            sources (list[dict[str, Any]]): Information about
                sources from where it is possible to get file. Fully replaces
                existing sources.

        """
        response = self.patch(
            self._get_dependency_package_route(filename),
            sources=sources
        )
        response.raise_for_status()

    def delete_dependency_package(
        self, filename: str, platform_name: Optional[str] = None
    ):
        """Remove dependency package for specific platform.

        Args:
            filename (str): Filename of dependency package.
            platform_name (Optional[str]): Deprecated.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'delete_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )

        route = self._get_dependency_package_route(filename)
        response = self.delete(route)
        response.raise_for_status("Failed to delete dependency file")
        return response.data

    def download_dependency_package(
        self,
        src_filename: str,
        dst_directory: str,
        dst_filename: str,
        platform_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> str:
        """Download dependency package from server.

        This method requires to have authorized token available. The package
        is only downloaded.

        Args:
            src_filename (str): Filename of dependency pacakge.
                For server version 0.2.0 and lower it is name of package
                to download.
            dst_directory (str): Where the file should be downloaded.
            dst_filename (str): Name of destination filename.
            platform_name (Optional[str]): Deprecated.
            chunk_size (Optional[int]): Download chunk size.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        Returns:
            str: Filepath to downloaded file.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'download_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )
        route = self._get_dependency_package_route(src_filename)
        package_filepath = os.path.join(dst_directory, dst_filename)
        self.download_file(
            route,
            package_filepath,
            chunk_size=chunk_size,
            progress=progress
        )
        return package_filepath

    def upload_dependency_package(
        self,
        src_filepath: str,
        dst_filename: str,
        platform_name: Optional[str] = None,
        progress: Optional[TransferProgress] = None,
    ):
        """Upload dependency package to server.

        Args:
            src_filepath (str): Path to a package file.
            dst_filename (str): Dependency package filename or name of package
                for server version 0.2.0 or lower. Must be unique.
            platform_name (Optional[str]): Deprecated.
            progress (Optional[TransferProgress]): Object to keep track about
                upload state.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'upload_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )

        route = self._get_dependency_package_route(dst_filename)
        self.upload_file(route, src_filepath, progress=progress)

    def get_bundles(self) -> "BundlesInfoDict":
        """Server bundles with basic information.

        This is example output::

            {
                "bundles": [
                    {
                        "name": "my_bundle",
                        "createdAt": "2023-06-12T15:37:02.420260",
                        "installerVersion": "1.0.0",
                        "addons": {
                            "core": "1.2.3"
                        },
                        "dependencyPackages": {
                            "windows": "a_windows_package123.zip",
                            "linux": "a_linux_package123.zip",
                            "darwin": "a_mac_package123.zip"
                        },
                        "isProduction": False,
                        "isStaging": False
                    }
                ],
                "productionBundle": "my_bundle",
                "stagingBundle": "test_bundle"
            }

        Returns:
            dict[str, Any]: Server bundles with basic information.

        """
        response = self.get("bundles")
        response.raise_for_status()
        return response.data

    def create_bundle(
        self,
        name: str,
        addon_versions: Dict[str, str],
        installer_version: str,
        dependency_packages: Optional[Dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            Dict[str, "DevBundleAddonInfoDict"]] = None,
    ):
        """Create bundle on server.

        Bundle cannot be changed once is created. Only isProduction, isStaging
        and dependency packages can change after creation. In case dev bundle
        is created, it is possible to change anything, but it is not possible
        to mark bundle as dev and production or staging at the same time.

        Development addon config can define custom path to client code. It is
        used only for dev bundles.

        Example of 'dev_addons_config'::

            ```json
            {
                "core": {
                    "enabled": true,
                    "path": "/path/to/ayon-core/client"
                }
            }
            ```

        Args:
            name (str): Name of bundle.
            addon_versions (dict[str, str]): Addon versions.
            installer_version (Union[str, None]): Installer version.
            dependency_packages (Optional[dict[str, str]]): Dependency
                package names. Keys are platform names and values are name of
                packages.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only if 'is_dev' is set to 'True'.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only if 'is_dev' is set to 'True'.

        """
        body = {
            "name": name,
            "installerVersion": installer_version,
            "addons": addon_versions,
        }

        for key, value in (
            ("dependencyPackages", dependency_packages),
            ("isProduction", is_production),
            ("isStaging", is_staging),
            ("isDev", is_dev),
            ("activeUser", dev_active_user),
            ("addonDevelopment", dev_addons_config),
        ):
            if value is not None:
                body[key] = value

        response = self.post("bundles", **body)
        response.raise_for_status()

    def update_bundle(
        self,
        bundle_name: str,
        addon_versions: Optional[Dict[str, str]] = None,
        installer_version: Optional[str] = None,
        dependency_packages: Optional[Dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            Dict[str, "DevBundleAddonInfoDict"]] = None,
    ):
        """Update bundle on server.

        Dependency packages can be update only for single platform. Others
        will be left untouched. Use 'None' value to unset dependency package
        from bundle.

        Args:
            bundle_name (str): Name of bundle.
            addon_versions (Optional[dict[str, str]]): Addon versions,
                possible only for dev bundles.
            installer_version (Optional[str]): Installer version, possible
                only for dev bundles.
            dependency_packages (Optional[dict[str, str]]): Dependency pacakge
                names that should be used with the bundle.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only for dev bundles.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only for dev bundles.

        """
        body = {
            key: value
            for key, value in (
                ("installerVersion", installer_version),
                ("addons", addon_versions),
                ("dependencyPackages", dependency_packages),
                ("isProduction", is_production),
                ("isStaging", is_staging),
                ("isDev", is_dev),
                ("activeUser", dev_active_user),
                ("addonDevelopment", dev_addons_config),
            )
            if value is not None
        }

        response = self.patch(
            f"bundles/{bundle_name}",
            **body
        )
        response.raise_for_status()

    def check_bundle_compatibility(
        self,
        name: str,
        addon_versions: Dict[str, str],
        installer_version: str,
        dependency_packages: Optional[Dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            Dict[str, "DevBundleAddonInfoDict"]] = None,
    ) -> Dict[str, Any]:
        """Check bundle compatibility.

        Can be used as per-flight validation before creating bundle.

        Args:
            name (str): Name of bundle.
            addon_versions (dict[str, str]): Addon versions.
            installer_version (Union[str, None]): Installer version.
            dependency_packages (Optional[dict[str, str]]): Dependency
                package names. Keys are platform names and values are name of
                packages.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only if 'is_dev' is set to 'True'.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only if 'is_dev' is set to 'True'.

        Returns:
            Dict[str, Any]: Server response, with 'success' and 'issues'.

        """
        body = {
            "name": name,
            "installerVersion": installer_version,
            "addons": addon_versions,
        }

        for key, value in (
            ("dependencyPackages", dependency_packages),
            ("isProduction", is_production),
            ("isStaging", is_staging),
            ("isDev", is_dev),
            ("activeUser", dev_active_user),
            ("addonDevelopment", dev_addons_config),
        ):
            if value is not None:
                body[key] = value

        response = self.post("bundles/check", **body)
        response.raise_for_status()
        return response.data

    def delete_bundle(self, bundle_name: str):
        """Delete bundle from server.

        Args:
            bundle_name (str): Name of bundle to delete.

        """
        response = self.delete(f"bundles/{bundle_name}")
        response.raise_for_status()

    # Anatomy presets
    def get_project_anatomy_presets(self) -> List["AnatomyPresetDict"]:
        """Anatomy presets available on server.

        Content has basic information about presets. Example output::

            [
                {
                    "name": "netflix_VFX",
                    "primary": false,
                    "version": "1.0.0"
                },
                {
                    ...
                },
                ...
            ]

        Returns:
            list[dict[str, str]]: Anatomy presets available on server.

        """
        result = self.get("anatomy/presets")
        result.raise_for_status()
        return result.data.get("presets") or []

    def get_default_anatomy_preset_name(self) -> str:
        """Name of default anatomy preset.

        Primary preset is used as default preset. But when primary preset is
        not set a built-in is used instead. Built-in preset is named '_'.

        Returns:
            str: Name of preset that can be used by
                'get_project_anatomy_preset'.

        """
        for preset in self.get_project_anatomy_presets():
            if preset.get("primary"):
                return preset["name"]
        return "_"

    def get_project_anatomy_preset(
        self, preset_name: Optional[str] = None
    ) -> "AnatomyPresetDict":
        """Anatomy preset values by name.

        Get anatomy preset values by preset name. Primary preset is returned
        if preset name is set to 'None'.

        Args:
            preset_name (Optional[str]): Preset name.

        Returns:
            AnatomyPresetDict: Anatomy preset values.

        """
        if preset_name is None:
            preset_name = "__primary__"
            major, minor, patch, _, _ = self.server_version_tuple
            if (major, minor, patch) < (1, 0, 8):
                preset_name = self.get_default_anatomy_preset_name()

        result = self.get(f"anatomy/presets/{preset_name}")
        result.raise_for_status()
        return result.data

    def get_built_in_anatomy_preset(self) -> "AnatomyPresetDict":
        """Get built-in anatomy preset.

        Returns:
            AnatomyPresetDict: Built-in anatomy preset.

        """
        preset_name = "__builtin__"
        major, minor, patch, _, _ = self.server_version_tuple
        if (major, minor, patch) < (1, 0, 8):
            preset_name = "_"
        return self.get_project_anatomy_preset(preset_name)

    def get_build_in_anatomy_preset(self) -> "AnatomyPresetDict":
        warnings.warn(
            (
                "Used deprecated 'get_build_in_anatomy_preset' use"
                " 'get_built_in_anatomy_preset' instead."
            ),
            DeprecationWarning
        )
        return self.get_built_in_anatomy_preset()

    def get_project_root_overrides(
        self, project_name: str
    ) -> Dict[str, Dict[str, str]]:
        """Root overrides per site name.

        Method is based on logged user and can't be received for any other
            user on server.

        Output will contain only roots per site id used by logged user.

        Args:
            project_name (str): Name of project.

        Returns:
             dict[str, dict[str, str]]: Root values by root name by site id.

        """
        result = self.get(f"projects/{project_name}/roots")
        result.raise_for_status()
        return result.data

    def get_project_roots_by_site(
        self, project_name: str
    ) -> Dict[str, Dict[str, str]]:
        """Root overrides per site name.

        Method is based on logged user and can't be received for any other
        user on server.

        Output will contain only roots per site id used by logged user.

        Deprecated:
            Use 'get_project_root_overrides' instead. Function
                deprecated since 1.0.6

        Args:
            project_name (str): Name of project.

        Returns:
             dict[str, dict[str, str]]: Root values by root name by site id.

        """
        warnings.warn(
            (
                "Method 'get_project_roots_by_site' is deprecated."
                " Please use 'get_project_root_overrides' instead."
            ),
            DeprecationWarning
        )
        return self.get_project_root_overrides(project_name)

    def get_project_root_overrides_by_site_id(
        self, project_name: str, site_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Root overrides for site.

        If site id is not passed a site set in current api object is used
        instead.

        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.

        Returns:
            dict[str, str]: Root values by root name or None if
                site does not have overrides.

        """
        if site_id is None:
            site_id = self.site_id

        if site_id is None:
            return {}
        roots = self.get_project_root_overrides(project_name)
        return roots.get(site_id, {})

    def get_project_roots_for_site(
        self, project_name: str, site_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Root overrides for site.

        If site id is not passed a site set in current api object is used
        instead.

        Deprecated:
            Use 'get_project_root_overrides_by_site_id' instead. Function
                deprecated since 1.0.6
        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.

        Returns:
            dict[str, str]: Root values by root name, root name is not
                available if it does not have overrides.

        """
        warnings.warn(
            (
                "Method 'get_project_roots_for_site' is deprecated."
                " Please use 'get_project_root_overrides_by_site_id' instead."
            ),
            DeprecationWarning
        )
        return self.get_project_root_overrides_by_site_id(project_name)

    def _get_project_roots_values(
        self,
        project_name: str,
        site_id: Optional[str] = None,
        platform_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """Root values for site or platform.

        Helper function that treats 'siteRoots' endpoint. The endpoint
            requires to pass exactly one query value of site id
            or platform name.

        When using platform name, it does return default project roots without
            any site overrides.

        Output should contain all project roots with all filled values. If
            value does not have override on a site, it should be filled with
            project default value.

        Args:
            project_name (str): Project name.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            platform_name (Optional[str]): Platform for which want to receive
                roots.

        Returns:
            dict[str, str]: Root values.

        """
        query_data = {}
        if site_id is not None:
            query_data["site_id"] = site_id
        else:
            if platform_name is None:
                platform_name = platform.system()
            query_data["platform"] = platform_name.lower()

        query = prepare_query_string(query_data)
        response = self.get(
            f"projects/{project_name}/siteRoots{query}"
        )
        response.raise_for_status()
        return response.data

    def get_project_roots_by_site_id(
        self, project_name: str, site_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Root values for a site.

        If site id is not passed a site set in current api object is used
        instead. If site id is not available, default roots are returned
        for current platform.

        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                root values.

        Returns:
            dict[str, str]: Root values.

        """
        if site_id is None:
            site_id = self.site_id

        return self._get_project_roots_values(project_name, site_id=site_id)

    def get_project_roots_by_platform(
        self, project_name: str, platform_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Root values for a site.

        If platform name is not passed current platform name is used instead.

        This function does return root values without site overrides. It is
            possible to use the function to receive default root values.

        Args:
            project_name (str): Name of project.
            platform_name (Optional[Literal["windows", "linux", "darwin"]]):
                Platform name for which want to receive root values. Current
                platform name is used if not passed.

        Returns:
            dict[str, str]: Root values.

        """
        return self._get_project_roots_values(
            project_name, platform_name=platform_name
        )

    def get_addon_settings_schema(
        self,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sudio/Project settings schema of an addon.

        Project schema may look differently as some enums are based on project
        values.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (Optional[str]): Schema for specific project or
                default studio schemas.

        Returns:
            dict[str, Any]: Schema of studio/project settings.

        """
        args = tuple()
        if project_name:
            args = (project_name, )

        endpoint = self.get_addon_endpoint(
            addon_name, addon_version, "schema", *args
        )
        result = self.get(endpoint)
        result.raise_for_status()
        return result.data

    def get_addon_site_settings_schema(
        self, addon_name: str, addon_version: str
    ) -> Dict[str, Any]:
        """Site settings schema of an addon.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.

        Returns:
            dict[str, Any]: Schema of site settings.

        """
        result = self.get(
            f"addons/{addon_name}/{addon_version}/siteSettings/schema"
        )
        result.raise_for_status()
        return result.data

    def get_addon_studio_settings(
        self,
        addon_name: str,
        addon_version: str,
        variant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Addon studio settings.

        Receive studio settings for specific version of an addon.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.

        Returns:
           dict[str, Any]: Addon settings.

        """
        if variant is None:
            variant = self.default_settings_variant

        query = prepare_query_string({"variant": variant or None})

        result = self.get(
            f"addons/{addon_name}/{addon_version}/settings{query}"
        )
        result.raise_for_status()
        return result.data

    def get_addon_project_settings(
        self,
        addon_name: str,
        addon_version: str,
        project_name: str,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True
    ) -> Dict[str, Any]:
        """Addon project settings.

        Receive project settings for specific version of an addon. The settings
        may be with site overrides when enabled.

        Site id is filled with current connection site id if not passed. To
        make sure any site id is used set 'use_site' to 'False'.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (str): Name of project for which the settings are
                received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Name of site which is used for site
                overrides. Is filled with connection 'site_id' attribute
                if not passed.
            use_site (Optional[bool]): To force disable option of using site
                overrides set to 'False'. In that case won't be applied
                any site overrides.

        Returns:
            dict[str, Any]: Addon settings.

        """
        if not use_site:
            site_id = None
        elif not site_id:
            site_id = self.site_id

        if variant is None:
            variant = self.default_settings_variant

        query = prepare_query_string({
            "site": site_id or None,
            "variant": variant or None,
        })
        result = self.get(
            f"addons/{addon_name}/{addon_version}"
            f"/settings/{project_name}{query}"
        )
        result.raise_for_status()
        return result.data

    def get_addon_settings(
        self,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True
    ) -> Dict[str, Any]:
        """Receive addon settings.

        Receive addon settings based on project name value. Some arguments may
        be ignored if 'project_name' is set to 'None'.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (Optional[str]): Name of project for which the
                settings are received. A studio settings values are received
                if is 'None'.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Name of site which is used for site
                overrides. Is filled with connection 'site_id' attribute
                if not passed.
            use_site (Optional[bool]): To force disable option of using
                site overrides set to 'False'. In that case won't be applied
                any site overrides.

        Returns:
            dict[str, Any]: Addon settings.

        """
        if project_name is None:
            return self.get_addon_studio_settings(
                addon_name, addon_version, variant
            )
        return self.get_addon_project_settings(
            addon_name, addon_version, project_name, variant, site_id, use_site
        )

    def get_addon_site_settings(
        self,
        addon_name: str,
        addon_version: str,
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Site settings of an addon.

        If site id is not available an empty dictionary is returned.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            site_id (Optional[str]): Name of site for which should be settings
                returned. using 'site_id' attribute if not passed.

        Returns:
            dict[str, Any]: Site settings.

        """
        if site_id is None:
            site_id = self.site_id

        if not site_id:
            return {}

        query = prepare_query_string({"site": site_id})
        result = self.get(
            f"addons/{addon_name}/{addon_version}/siteSettings{query}"
        )
        result.raise_for_status()
        return result.data

    def get_bundle_settings(
        self,
        bundle_name: Optional[str] = None,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
    ) -> Dict[str, Any]:
        """Get complete set of settings for given data.

        If project is not passed then studio settings are returned. If variant
        is not passed 'default_settings_variant' is used. If bundle name is
        not passed then current production/staging bundle is used, based on
        variant value.

        Output contains addon settings and site settings in single dictionary.

        Todos:
            - test how it behaves if there is not any bundle.
            - test how it behaves if there is not any production/staging
                bundle.

        Example output::

            {
                "addons": [
                    {
                        "name": "addon-name",
                        "version": "addon-version",
                        "settings": {...},
                        "siteSettings": {...}
                    }
                ]
            }

        Returns:
            dict[str, Any]: All settings for single bundle.

        """
        if not use_site:
            site_id = None
        elif not site_id:
            site_id = self.site_id

        query = prepare_query_string({
            "project_name": project_name or None,
            "bundle_name": bundle_name or None,
            "variant": variant or self.default_settings_variant or None,
            "site_id": site_id,
        })
        response = self.get(f"settings{query}")
        response.raise_for_status()
        return response.data

    def get_addons_studio_settings(
        self,
        bundle_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> Dict[str, Any]:
        """All addons settings in one bulk.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            use_site (bool): To force disable option of using site overrides
                set to 'False'. In that case won't be applied any site
                overrides.
            only_values (Optional[bool]): Output will contain only settings
                values without metadata about addons.

        Returns:
            dict[str, Any]: Settings of all addons on server.

        """
        output = self.get_bundle_settings(
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site
        )
        if only_values:
            output = {
                addon["name"]: addon["settings"]
                for addon in output["addons"]
            }
        return output

    def get_addons_project_settings(
        self,
        project_name: str,
        bundle_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> Dict[str, Any]:
        """Project settings of all addons.

        Server returns information about used addon versions, so full output
        looks like:

        ```json
            {
                "settings": {...},
                "addons": {...}
            }
        ```

        The output can be limited to only values. To do so is 'only_values'
        argument which is by default set to 'True'. In that case output
        contains only value of 'settings' key.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            project_name (str): Name of project for which are settings
                received.
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            use_site (bool): To force disable option of using site overrides
                set to 'False'. In that case won't be applied any site
                overrides.
            only_values (Optional[bool]): Output will contain only settings
                values without metadata about addons.

        Returns:
            dict[str, Any]: Settings of all addons on server for passed
                project.

        """
        if not project_name:
            raise ValueError("Project name must be passed.")

        output = self.get_bundle_settings(
            project_name=project_name,
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site
        )
        if only_values:
            output = {
                addon["name"]: addon["settings"]
                for addon in output["addons"]
            }
        return output

    def get_addons_settings(
        self,
        bundle_name: Optional[str] = None,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> Dict[str, Any]:
        """Universal function to receive all addon settings.

        Based on 'project_name' will receive studio settings or project
        settings. In case project is not passed is 'site_id' ignored.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            project_name (Optional[str]): Name of project for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Id of site for which want to receive
                site overrides.
            use_site (Optional[bool]): To force disable option of using site
                overrides set to 'False'. In that case won't be applied
                any site overrides.
            only_values (Optional[bool]): Only settings values will be
                returned. By default, is set to 'True'.

        """
        if project_name is None:
            return self.get_addons_studio_settings(
                bundle_name=bundle_name,
                variant=variant,
                site_id=site_id,
                use_site=use_site,
                only_values=only_values
            )

        return self.get_addons_project_settings(
            project_name=project_name,
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site,
            only_values=only_values
        )

    def get_secrets(self) -> List["SecretDict"]:
        """Get all secrets.

        Example output::

            [
                {
                    "name": "secret_1",
                    "value": "secret_value_1",
                },
                {
                    "name": "secret_2",
                    "value": "secret_value_2",
                }
            ]

        Returns:
            list[SecretDict]: List of secret entities.

        """
        response = self.get("secrets")
        response.raise_for_status()
        return response.data

    def get_secret(self, secret_name: str) -> "SecretDict":
        """Get secret by name.

        Example output::

            {
                "name": "secret_name",
                "value": "secret_value",
            }

        Args:
            secret_name (str): Name of secret.

        Returns:
            dict[str, str]: Secret entity data.

        """
        response = self.get(f"secrets/{secret_name}")
        response.raise_for_status()
        return response.data

    def save_secret(self, secret_name: str, secret_value: str):
        """Save secret.

        This endpoint can create and update secret.

        Args:
            secret_name (str): Name of secret.
            secret_value (str): Value of secret.

        """
        response = self.put(
            f"secrets/{secret_name}",
            name=secret_name,
            value=secret_value,
        )
        response.raise_for_status()
        return response.data

    def delete_secret(self, secret_name: str):
        """Delete secret by name.

        Args:
            secret_name (str): Name of secret to delete.

        """
        response = self.delete(f"secrets/{secret_name}")
        response.raise_for_status()
        return response.data

    # Entity getters

    def get_rest_entity_by_id(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
    ) -> Optional["AnyEntityDict"]:
        """Get entity using REST on a project by its id.

        Args:
            project_name (str): Name of project where entity is.
            entity_type (Literal["folder", "task", "product", "version"]): The
                entity type which should be received.
            entity_id (str): Id of entity.

        Returns:
            Optional[AnyEntityDict]: Received entity data.

        """
        if not all((project_name, entity_type, entity_id)):
            return None

        response = self.get(
            f"projects/{project_name}/{entity_type}s/{entity_id}"
        )
        if response.status == 200:
            return response.data
        return None

    def get_rest_task(
        self, project_name: str, task_id: str
    ) -> Optional["TaskDict"]:
        return self.get_rest_entity_by_id(project_name, "task", task_id)

    def get_rest_product(
        self, project_name: str, product_id: str
    ) -> Optional["ProductDict"]:
        return self.get_rest_entity_by_id(project_name, "product", product_id)

    def get_rest_version(
        self, project_name: str, version_id: str
    ) -> Optional["VersionDict"]:
        return self.get_rest_entity_by_id(project_name, "version", version_id)

    def get_rest_representation(
        self, project_name: str, representation_id: str
    ) -> Optional["RepresentationDict"]:
        return self.get_rest_entity_by_id(
            project_name, "representation", representation_id
        )

    def get_tasks(
        self,
        project_name: str,
        task_ids: Optional[Iterable[str]] = None,
        task_names: Optional[Iterable[str]] = None,
        task_types: Optional[Iterable[str]] = None,
        folder_ids: Optional[Iterable[str]] = None,
        assignees: Optional[Iterable[str]] = None,
        assignees_all: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Generator["TaskDict", None, None]:
        """Query task entities from server.

        Args:
            project_name (str): Name of project.
            task_ids (Iterable[str]): Task ids to filter.
            task_names (Iterable[str]): Task names used for filtering.
            task_types (Iterable[str]): Task types used for filtering.
            folder_ids (Iterable[str]): Ids of task parents. Use 'None'
                if folder is direct child of project.
            assignees (Optional[Iterable[str]]): Task assignees used for
                filtering. All tasks with any of passed assignees are
                returned.
            assignees_all (Optional[Iterable[str]]): Task assignees used
                for filtering. Task must have all of passed assignees to be
                returned.
            statuses (Optional[Iterable[str]]): Task statuses used for
                filtering.
            tags (Optional[Iterable[str]]): Task tags used for
                filtering.
            active (Optional[bool]): Filter active/inactive tasks.
                Both are returned if is set to None.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Generator[TaskDict, None, None]: Queried task entities.

        """
        if not project_name:
            return

        filters = {
            "projectName": project_name
        }
        if not prepare_list_filters(
            filters,
            ("taskIds", task_ids),
            ("taskNames", task_names),
            ("taskTypes", task_types),
            ("folderIds", folder_ids),
            ("taskAssigneesAny", assignees),
            ("taskAssigneesAll", assignees_all),
            ("taskStatuses", statuses),
            ("taskTags", tags),
        ):
            return

        if not fields:
            fields = self.get_default_fields_for_type("task")
        else:
            fields = set(fields)
            self._prepare_fields("task", fields, own_attributes)

        if active is not None:
            fields.add("active")

        query = tasks_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for task in parsed_data["project"]["tasks"]:
                if active is not None and active is not task["active"]:
                    continue

                self._convert_entity_data(task)

                if own_attributes:
                    fill_own_attribs(task)
                yield task

    def get_task_by_name(
        self,
        project_name: str,
        folder_id: str,
        task_name: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional["TaskDict"]:
        """Query task entity by name and folder id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            folder_id (str): Folder id.
            task_name (str): Task name
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Optional[TaskDict]: Task entity data or None if was not found.

        """
        for task in self.get_tasks(
            project_name,
            folder_ids=[folder_id],
            task_names=[task_name],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        ):
            return task
        return None

    def get_task_by_id(
        self,
        project_name: str,
        task_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Optional["TaskDict"]:
        """Query task entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            task_id (str): Task id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Optional[TaskDict]: Task entity data or None if was not found.

        """
        for task in self.get_tasks(
            project_name,
            task_ids=[task_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        ):
            return task
        return None

    def get_tasks_by_folder_paths(
        self,
        project_name: str,
        folder_paths: Iterable[str],
        task_names: Optional[Iterable[str]] = None,
        task_types: Optional[Iterable[str]] = None,
        assignees: Optional[Iterable[str]] = None,
        assignees_all: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Dict[str, List["TaskDict"]]:
        """Query task entities from server by folder paths.

        Args:
            project_name (str): Name of project.
            folder_paths (list[str]): Folder paths.
            task_names (Iterable[str]): Task names used for filtering.
            task_types (Iterable[str]): Task types used for filtering.
            assignees (Optional[Iterable[str]]): Task assignees used for
                filtering. All tasks with any of passed assignees are
                returned.
            assignees_all (Optional[Iterable[str]]): Task assignees used
                for filtering. Task must have all of passed assignees to be
                returned.
            statuses (Optional[Iterable[str]]): Task statuses used for
                filtering.
            tags (Optional[Iterable[str]]): Task tags used for
                filtering.
            active (Optional[bool]): Filter active/inactive tasks.
                Both are returned if is set to None.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Dict[str, List[TaskDict]]: Task entities by
                folder path.

        """
        folder_paths = set(folder_paths)
        if not project_name or not folder_paths:
            return {}

        filters = {
            "projectName": project_name,
            "folderPaths": list(folder_paths),
        }
        if not prepare_list_filters(
            filters,
            ("taskNames", task_names),
            ("taskTypes", task_types),
            ("taskAssigneesAny", assignees),
            ("taskAssigneesAll", assignees_all),
            ("taskStatuses", statuses),
            ("taskTags", tags),
        ):
            return {}

        if not fields:
            fields = self.get_default_fields_for_type("task")
        else:
            fields = set(fields)
            self._prepare_fields("task", fields, own_attributes)

        if active is not None:
            fields.add("active")

        query = tasks_by_folder_paths_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        output = {
            folder_path: []
            for folder_path in folder_paths
        }
        for parsed_data in query.continuous_query(self):
            for folder in parsed_data["project"]["folders"]:
                folder_path = folder["path"]
                for task in folder["tasks"]:
                    if active is not None and active is not task["active"]:
                        continue

                    self._convert_entity_data(task)

                    if own_attributes:
                        fill_own_attribs(task)
                    output[folder_path].append(task)
        return output

    def get_tasks_by_folder_path(
        self,
        project_name: str,
        folder_path: str,
        task_names: Optional[Iterable[str]] = None,
        task_types: Optional[Iterable[str]] = None,
        assignees: Optional[Iterable[str]] = None,
        assignees_all: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> List["TaskDict"]:
        """Query task entities from server by folder path.

        Args:
            project_name (str): Name of project.
            folder_path (str): Folder path.
            task_names (Iterable[str]): Task names used for filtering.
            task_types (Iterable[str]): Task types used for filtering.
            assignees (Optional[Iterable[str]]): Task assignees used for
                filtering. All tasks with any of passed assignees are
                returned.
            assignees_all (Optional[Iterable[str]]): Task assignees used
                for filtering. Task must have all of passed assignees to be
                returned.
            statuses (Optional[Iterable[str]]): Task statuses used for
                filtering.
            tags (Optional[Iterable[str]]): Task tags used for
                filtering.
            active (Optional[bool]): Filter active/inactive tasks.
                Both are returned if is set to None.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        """
        return self.get_tasks_by_folder_paths(
            project_name,
            [folder_path],
            task_names,
            task_types=task_types,
            assignees=assignees,
            assignees_all=assignees_all,
            statuses=statuses,
            tags=tags,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )[folder_path]

    def get_task_by_folder_path(
        self,
        project_name: str,
        folder_path: str,
        task_name: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Optional["TaskDict"]:
        """Query task entity by folder path and task name.

        Args:
            project_name (str): Project name.
            folder_path (str): Folder path.
            task_name (str): Task name.
            fields (Optional[Iterable[str]]): Task fields that should
                be returned.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Optional[TaskDict]: Task entity data or None if was not found.

        """
        for task in self.get_tasks_by_folder_path(
            project_name,
            folder_path,
            active=None,
            task_names=[task_name],
            fields=fields,
            own_attributes=own_attributes,
        ):
            return task
        return None

    def create_task(
        self,
        project_name: str,
        name: str,
        task_type: str,
        folder_id: str,
        label: Optional[str] = None,
        assignees: Optional[Iterable[str]] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Create new task.

        Args:
            project_name (str): Project name.
            name (str): Folder name.
            task_type (str): Task type.
            folder_id (str): Parent folder id.
            label (Optional[str]): Label of folder.
            assignees (Optional[Iterable[str]]): Task assignees.
            attrib (Optional[dict[str, Any]]): Task attributes.
            data (Optional[dict[str, Any]]): Task data.
            tags (Optional[Iterable[str]]): Task tags.
            status (Optional[str]): Task status.
            active (Optional[bool]): Task active state.
            thumbnail_id (Optional[str]): Task thumbnail id.
            task_id (Optional[str]): Task id. If not passed new id is
                generated.

        Returns:
            str: Task id.

        """
        if not task_id:
            task_id = create_entity_id()
        create_data = {
            "id": task_id,
            "name": name,
            "taskType": task_type,
            "folderId": folder_id,
        }
        for key, value in (
            ("label", label),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("assignees", assignees),
            ("active", active),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/tasks",
            **create_data
        )
        response.raise_for_status()
        return task_id

    def update_task(
        self,
        project_name: str,
        task_id: str,
        name: Optional[str] = None,
        task_type: Optional[str] = None,
        folder_id: Optional[str] = None,
        label: Optional[str] = NOT_SET,
        assignees: Optional[List[str]] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ):
        """Update task entity on server.

        Do not pass ``label`` amd ``thumbnail_id`` if you don't
            want to change their values. Value ``None`` would unset
            their value.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            task_id (str): Task id.
            name (Optional[str]): New name.
            task_type (Optional[str]): New task type.
            folder_id (Optional[str]): New folder id.
            label (Optional[Union[str, None]]): New label.
            assignees (Optional[str]): New assignees.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[Union[str, None]]): New thumbnail id.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("taskType", task_type),
            ("folderId", folder_id),
            ("assignees", assignees),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("label", label),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/tasks/{task_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_task(self, project_name: str, task_id: str):
        """Delete task.

        Args:
            project_name (str): Project name.
            task_id (str): Task id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/tasks/{task_id}"
        )
        response.raise_for_status()

    def _filter_product(
        self,
        project_name: str,
        product: "ProductDict",
        active: "Union[bool, None]",
    ) -> Optional["ProductDict"]:
        if active is not None and product["active"] is not active:
            return None

        self._convert_entity_data(product)

        return product

    def get_products(
        self,
        project_name: str,
        product_ids: Optional[Iterable[str]] = None,
        product_names: Optional[Iterable[str]]=None,
        folder_ids: Optional[Iterable[str]]=None,
        product_types: Optional[Iterable[str]]=None,
        product_name_regex: Optional[str] = None,
        product_path_regex: Optional[str] = None,
        names_by_folder_ids: Optional[Dict[str, Iterable[str]]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Generator["ProductDict", None, None]:
        """Query products from server.

        Todos:
            Separate 'name_by_folder_ids' filtering to separated method. It
                cannot be combined with some other filters.

        Args:
            project_name (str): Name of project.
            product_ids (Optional[Iterable[str]]): Task ids to filter.
            product_names (Optional[Iterable[str]]): Task names used for
                filtering.
            folder_ids (Optional[Iterable[str]]): Ids of task parents.
                Use 'None' if folder is direct child of project.
            product_types (Optional[Iterable[str]]): Product types used for
                filtering.
            product_name_regex (Optional[str]): Filter products by name regex.
            product_path_regex (Optional[str]): Filter products by path regex.
                Path starts with folder path and ends with product name.
            names_by_folder_ids (Optional[dict[str, Iterable[str]]]): Product
                name filtering by folder id.
            statuses (Optional[Iterable[str]]): Product statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Product tags used
                for filtering.
            active (Optional[bool]): Filter active/inactive products.
                Both are returned if is set to None.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Generator[ProductDict, None, None]: Queried product entities.

        """
        if not project_name:
            return

        # Prepare these filters before 'name_by_filter_ids' filter
        filter_product_names = None
        if product_names is not None:
            filter_product_names = set(product_names)
            if not filter_product_names:
                return

        filter_folder_ids = None
        if folder_ids is not None:
            filter_folder_ids = set(folder_ids)
            if not filter_folder_ids:
                return

        # This will disable 'folder_ids' and 'product_names' filters
        #   - maybe could be enhanced in future?
        if names_by_folder_ids is not None:
            filter_product_names = set()
            filter_folder_ids = set()

            for folder_id, names in names_by_folder_ids.items():
                if folder_id and names:
                    filter_folder_ids.add(folder_id)
                    filter_product_names |= set(names)

            if not filter_product_names or not filter_folder_ids:
                return

        # Convert fields and add minimum required fields
        if fields:
            fields = set(fields) | {"id"}
            self._prepare_fields("product", fields)
        else:
            fields = self.get_default_fields_for_type("product")

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for products. The"
                    " argument will be removed from function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        # Add 'name' and 'folderId' if 'names_by_folder_ids' filter is entered
        if names_by_folder_ids:
            fields.add("name")
            fields.add("folderId")

        # Prepare filters for query
        filters = {
            "projectName": project_name
        }

        if filter_folder_ids:
            filters["folderIds"] = list(filter_folder_ids)

        if filter_product_names:
            filters["productNames"] = list(filter_product_names)

        if not prepare_list_filters(
            filters,
            ("productIds", product_ids),
            ("productTypes", product_types),
            ("productStatuses", statuses),
            ("productTags", tags),
        ):
            return

        for filter_key, filter_value in (
            ("productNameRegex", product_name_regex),
            ("productPathRegex", product_path_regex),
        ):
            if filter_value:
                filters[filter_key] = filter_value

        query = products_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        parsed_data = query.query(self)

        products = parsed_data.get("project", {}).get("products", [])
        # Filter products by 'names_by_folder_ids'
        if names_by_folder_ids:
            products_by_folder_id = collections.defaultdict(list)
            for product in products:
                filtered_product = self._filter_product(
                    project_name, product, active
                )
                if filtered_product is not None:
                    folder_id = filtered_product["folderId"]
                    products_by_folder_id[folder_id].append(filtered_product)

            for folder_id, names in names_by_folder_ids.items():
                for folder_product in products_by_folder_id[folder_id]:
                    if folder_product["name"] in names:
                        yield folder_product

        else:
            for product in products:
                filtered_product = self._filter_product(
                    project_name, product, active
                )
                if filtered_product is not None:
                    yield filtered_product

    def get_product_by_id(
        self,
        project_name: str,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["ProductDict"]:
        """Query product entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_id (str): Product id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Optional[ProductDict]: Product entity data or None
                if was not found.

        """
        products = self.get_products(
            project_name,
            product_ids=[product_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for product in products:
            return product
        return None

    def get_product_by_name(
        self,
        project_name: str,
        product_name: str,
        folder_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["ProductDict"]:
        """Query product entity by name and folder id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_name (str): Product name.
            folder_id (str): Folder id (Folder is a parent of products).
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                products.

        Returns:
            Optional[ProductDict]: Product entity data or None
                if was not found.

        """
        products = self.get_products(
            project_name,
            product_names=[product_name],
            folder_ids=[folder_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for product in products:
            return product
        return None

    def get_product_types(
        self, fields: Optional[Iterable[str]] = None
    ) -> List["ProductTypeDict"]:
        """Types of products.

        This is server wide information. Product types have 'name', 'icon' and
            'color'.

        Args:
            fields (Optional[Iterable[str]]): Product types fields to query.

        Returns:
            list[ProductTypeDict]: Product types information.

        """
        if not fields:
            fields = self.get_default_fields_for_type("productType")

        query = product_types_query(fields)

        parsed_data = query.query(self)

        return parsed_data.get("productTypes", [])

    def get_project_product_types(
        self, project_name: str, fields: Optional[Iterable[str]] = None
    ) -> List["ProductTypeDict"]:
        """DEPRECATED Types of products available in a project.

        Filter only product types available in a project.

        Args:
            project_name (str): Name of the project where to look for
                product types.
            fields (Optional[Iterable[str]]): Product types fields to query.

        Returns:
            List[ProductTypeDict]: Product types information.

        """
        warnings.warn(
            "Used deprecated function 'get_project_product_types'."
            " Use 'get_project' with 'productTypes' in 'fields' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if fields is None:
            fields = {"productTypes"}
        else:
            fields = {
                f"productTypes.{key}"
                for key in fields
            }

        project = self.get_project(project_name, fields=fields)
        return project["productTypes"]

    def get_product_type_names(
        self,
        project_name: Optional[str] = None,
        product_ids: Optional[Iterable[str]] = None,
    ) -> Set[str]:
        """DEPRECATED Product type names.

        Warnings:
            This function will be probably removed. Matters if 'products_id'
                filter has real use-case.

        Args:
            project_name (Optional[str]): Name of project where to look for
                queried entities.
            product_ids (Optional[Iterable[str]]): Product ids filter. Can be
                used only with 'project_name'.

        Returns:
            set[str]: Product type names.

        """
        warnings.warn(
            "Used deprecated function 'get_product_type_names'."
            " Use 'get_product_types' or 'get_products' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if project_name:
            if not product_ids:
                return set()
            products = self.get_products(
                project_name,
                product_ids=product_ids,
                fields=["productType"],
                active=None,
            )
            return {
                product["productType"]
                for product in products
            }

        return {
            product_info["name"]
            for product_info in self.get_product_types(project_name)
        }

    def create_product(
        self,
        project_name: str,
        name: str,
        product_type: str,
        folder_id: str,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] =None,
        status: Optional[str] = None,
        active: "Union[bool, None]" = None,
        product_id: Optional[str] = None,
    ) -> str:
        """Create new product.

        Args:
            project_name (str): Project name.
            name (str): Product name.
            product_type (str): Product type.
            folder_id (str): Parent folder id.
            attrib (Optional[dict[str, Any]]): Product attributes.
            data (Optional[dict[str, Any]]): Product data.
            tags (Optional[Iterable[str]]): Product tags.
            status (Optional[str]): Product status.
            active (Optional[bool]): Product active state.
            product_id (Optional[str]): Product id. If not passed new id is
                generated.

        Returns:
            str: Product id.

        """
        if not product_id:
            product_id = create_entity_id()
        create_data = {
            "id": product_id,
            "name": name,
            "productType": product_type,
            "folderId": folder_id,
        }
        for key, value in (
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/products",
            **create_data
        )
        response.raise_for_status()
        return product_id

    def update_product(
        self,
        project_name: str,
        product_id: str,
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
        product_type: Optional[str] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ):
        """Update product entity on server.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            product_id (str): Product id.
            name (Optional[str]): New product name.
            folder_id (Optional[str]): New product id.
            product_type (Optional[str]): New product type.
            attrib (Optional[dict[str, Any]]): New product attributes.
            data (Optional[dict[str, Any]]): New product data.
            tags (Optional[Iterable[str]]): New product tags.
            status (Optional[str]): New product status.
            active (Optional[bool]): New product active state.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("productType", product_type),
            ("folderId", folder_id),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/products/{product_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_product(self, project_name: str, product_id: str):
        """Delete product.

        Args:
            project_name (str): Project name.
            product_id (str): Product id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/products/{product_id}"
        )
        response.raise_for_status()

    def get_versions(
        self,
        project_name: str,
        version_ids: Optional[Iterable[str]] = None,
        product_ids: Optional[Iterable[str]] = None,
        task_ids: Optional[Iterable[str]] = None,
        versions: Optional[Iterable[str]] = None,
        hero: bool = True,
        standard: bool = True,
        latest: Optional[bool] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Generator["VersionDict", None, None]:
        """Get version entities based on passed filters from server.

        Args:
            project_name (str): Name of project where to look for versions.
            version_ids (Optional[Iterable[str]]): Version ids used for
                version filtering.
            product_ids (Optional[Iterable[str]]): Product ids used for
                version filtering.
            task_ids (Optional[Iterable[str]]): Task ids used for
                version filtering.
            versions (Optional[Iterable[int]]): Versions we're interested in.
            hero (Optional[bool]): Skip hero versions when set to False.
            standard (Optional[bool]): Skip standard (non-hero) when
                set to False.
            latest (Optional[bool]): Return only latest version of standard
                versions. This can be combined only with 'standard' attribute
                set to True.
            statuses (Optional[Iterable[str]]): Representation statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Representation tags used
                for filtering.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): Fields to be queried
                for version. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Generator[VersionDict, None, None]: Queried version entities.

        """
        if not fields:
            fields = self.get_default_fields_for_type("version")
        else:
            fields = set(fields)
            self._prepare_fields("version", fields)

        # Make sure fields have minimum required fields
        fields |= {"id", "version"}

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for versions. The"
                    " argument will be removed form function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        if not hero and not standard:
            return

        filters = {
            "projectName": project_name
        }
        if not prepare_list_filters(
            filters,
            ("taskIds", task_ids),
            ("versionIds", version_ids),
            ("productIds", product_ids),
            ("taskIds", task_ids),
            ("versions", versions),
            ("versionStatuses", statuses),
            ("versionTags", tags),
        ):
            return

        queries = []
        # Add filters based on 'hero' and 'standard'
        # NOTE: There is not a filter to "ignore" hero versions or to get
        #   latest and hero version
        # - if latest and hero versions should be returned it must be done in
        #       2 graphql queries
        if standard and not latest:
            # This query all versions standard + hero
            # - hero must be filtered out if is not enabled during loop
            query = versions_graphql_query(fields)
            for attr, filter_value in filters.items():
                query.set_variable_value(attr, filter_value)
            queries.append(query)
        else:
            if hero:
                # Add hero query if hero is enabled
                hero_query = versions_graphql_query(fields)
                for attr, filter_value in filters.items():
                    hero_query.set_variable_value(attr, filter_value)

                hero_query.set_variable_value("heroOnly", True)
                queries.append(hero_query)

            if standard:
                standard_query = versions_graphql_query(fields)
                for attr, filter_value in filters.items():
                    standard_query.set_variable_value(attr, filter_value)

                if latest:
                    standard_query.set_variable_value("latestOnly", True)
                queries.append(standard_query)

        for query in queries:
            for parsed_data in query.continuous_query(self):
                for version in parsed_data["project"]["versions"]:
                    if active is not None and version["active"] is not active:
                        continue

                    if not hero and version["version"] < 0:
                        continue

                    self._convert_entity_data(version)

                    yield version

    def get_version_by_id(
        self,
        project_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["VersionDict"]:
        """Query version entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version_id (str): Version id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_versions(
            project_name,
            version_ids=[version_id],
            active=None,
            hero=True,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_version_by_name(
        self,
        project_name: str,
        version: int,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["VersionDict"]:
        """Query version entity by version and product id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version (int): Version of version entity.
            product_id (str): Product id. Product is a parent of version.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_versions(
            project_name,
            product_ids=[product_id],
            versions=[version],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_version_by_id(
        self,
        project_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["VersionDict"]:
        """Query hero version entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version_id (int): Hero version id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_hero_versions(
            project_name,
            version_ids=[version_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_version_by_product_id(
        self,
        project_name: str,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional["VersionDict"]:
        """Query hero version entity by product id.

        Only one hero version is available on a product.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_id (int): Product id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_hero_versions(
            project_name,
            product_ids=[product_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_versions(
        self,
        project_name: str,
        product_ids: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator["VersionDict", None, None]:
        """Query hero versions by multiple filters.

        Only one hero version is available on a product.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_ids (Optional[Iterable[str]]): Product ids.
            version_ids (Optional[Iterable[str]]): Version ids.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        return self.get_versions(
            project_name,
            version_ids=version_ids,
            product_ids=product_ids,
            hero=True,
            standard=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def get_last_versions(
        self,
        project_name: str,
        product_ids: Iterable[str],
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Dict[str, Optional["VersionDict"]]:
        """Query last version entities by product ids.

        Args:
            project_name (str): Project where to look for representation.
            product_ids (Iterable[str]): Product ids.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            dict[str, Optional[VersionDict]]: Last versions by product id.

        """
        if fields:
            fields = set(fields)
            fields.add("productId")
        product_ids = set(product_ids)
        versions = self.get_versions(
            project_name,
            product_ids=product_ids,
            latest=True,
            hero=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        output = {
            version["productId"]: version
            for version in versions
        }
        for product_id in product_ids:
            output.setdefault(product_id, None)
        return output

    def get_last_version_by_product_id(
        self,
        project_name: str,
        product_id: str,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["VersionDict"]:
        """Query last version entity by product id.

        Args:
            project_name (str): Project where to look for representation.
            product_id (str): Product id.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Queried version entity or None.

        """
        versions = self.get_versions(
            project_name,
            product_ids=[product_id],
            latest=True,
            hero=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_last_version_by_product_name(
        self,
        project_name: str,
        product_name: str,
        folder_id: str,
        active: "Union[bool, None]" = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["VersionDict"]:
        """Query last version entity by product name and folder id.

        Args:
            project_name (str): Project where to look for representation.
            product_name (str): Product name.
            folder_id (str): Folder id.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[VersionDict]: Queried version entity or None.

        """
        if not folder_id:
            return None

        product = self.get_product_by_name(
            project_name, product_name, folder_id, fields={"id"}
        )
        if not product:
            return None
        return self.get_last_version_by_product_id(
            project_name,
            product["id"],
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def version_is_latest(self, project_name: str, version_id: str) -> bool:
        """Is version latest from a product.

        Args:
            project_name (str): Project where to look for representation.
            version_id (str): Version id.

        Returns:
            bool: Version is latest or not.

        """
        query = GraphQlQuery("VersionIsLatest")
        project_name_var = query.add_variable(
            "projectName", "String!", project_name
        )
        version_id_var = query.add_variable(
            "versionId", "String!", version_id
        )
        project_query = query.add_field("project")
        project_query.set_filter("name", project_name_var)
        version_query = project_query.add_field("version")
        version_query.set_filter("id", version_id_var)
        product_query = version_query.add_field("product")
        latest_version_query = product_query.add_field("latestVersion")
        latest_version_query.add_field("id")

        parsed_data = query.query(self)
        latest_version = (
            parsed_data["project"]["version"]["product"]["latestVersion"]
        )
        return latest_version["id"] == version_id

    def create_version(
        self,
        project_name: str,
        version: int,
        product_id: str,
        task_id: Optional[str] = None,
        author: Optional[str] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> str:
        """Create new version.

        Args:
            project_name (str): Project name.
            version (int): Version.
            product_id (str): Parent product id.
            task_id (Optional[str]): Parent task id.
            author (Optional[str]): Version author.
            attrib (Optional[dict[str, Any]]): Version attributes.
            data (Optional[dict[str, Any]]): Version data.
            tags (Optional[Iterable[str]]): Version tags.
            status (Optional[str]): Version status.
            active (Optional[bool]): Version active state.
            thumbnail_id (Optional[str]): Version thumbnail id.
            version_id (Optional[str]): Version id. If not passed new id is
                generated.

        Returns:
            str: Version id.

        """
        if not version_id:
            version_id = create_entity_id()
        create_data = {
            "id": version_id,
            "version": version,
            "productId": product_id,
        }
        for key, value in (
            ("taskId", task_id),
            ("author", author),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/versions",
            **create_data
        )
        response.raise_for_status()
        return version_id

    def update_version(
        self,
        project_name: str,
        version_id: str,
        version: Optional[int] = None,
        product_id: Optional[str] = None,
        task_id: Optional[str] = NOT_SET,
        author: Optional[str] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ):
        """Update version entity on server.

        Do not pass ``task_id`` amd ``thumbnail_id`` if you don't
            want to change their values. Value ``None`` would unset
            their value.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            version (Optional[int]): New version.
            product_id (Optional[str]): New product id.
            task_id (Optional[Union[str, None]]): New task id.
            author (Optional[str]): New author username.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[Union[str, None]]): New thumbnail id.

        """
        update_data = {}
        for key, value in (
            ("version", version),
            ("productId", product_id),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
            ("author", author),
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("taskId", task_id),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/versions/{version_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_version(self, project_name: str, version_id: str):
        """Delete version.

        Args:
            project_name (str): Project name.
            version_id (str): Version id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/versions/{version_id}"
        )
        response.raise_for_status()

    def _representation_conversion(
        self, representation: "RepresentationDict"
    ):
        if "context" in representation:
            orig_context = representation["context"]
            context = {}
            if orig_context and orig_context != "null":
                context = json.loads(orig_context)
            representation["context"] = context

        repre_files = representation.get("files")
        if not repre_files:
            return

        for repre_file in repre_files:
            repre_file_size = repre_file.get("size")
            if repre_file_size is not None:
                repre_file["size"] = int(repre_file["size"])

    def get_representations(
        self,
        project_name: str,
        representation_ids: Optional[Iterable[str]] = None,
        representation_names: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
        names_by_version_ids: Optional[Dict[str, Iterable[str]]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: "Union[bool, None]" = True,
        has_links: Optional[str] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator["RepresentationDict", None, None]:
        """Get representation entities based on passed filters from server.

        .. todo::

            Add separated function for 'names_by_version_ids' filtering.
            Because can't be combined with others.

        Args:
            project_name (str): Name of project where to look for versions.
            representation_ids (Optional[Iterable[str]]): Representation ids
                used for representation filtering.
            representation_names (Optional[Iterable[str]]): Representation
                names used for representation filtering.
            version_ids (Optional[Iterable[str]]): Version ids used for
                representation filtering. Versions are parents of
                representations.
            names_by_version_ids (Optional[Dict[str, Iterable[str]]]): Find
                representations by names and version ids. This filter
                discards all other filters.
            statuses (Optional[Iterable[str]]): Representation statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Representation tags used
                for filtering.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            has_links (Optional[Literal[IN, OUT, ANY]]): Filter
                representations with IN/OUT/ANY links.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Generator[RepresentationDict, None, None]: Queried
                representation entities.

        """
        if not fields:
            fields = self.get_default_fields_for_type("representation")
        else:
            fields = set(fields)
            self._prepare_fields("representation", fields)

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for representations. "
                    "The argument will be removed form function signature in "
                    "future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        if "files" in fields:
            fields.discard("files")
            fields |= REPRESENTATION_FILES_FIELDS

        filters = {
            "projectName": project_name
        }

        if representation_ids is not None:
            representation_ids = set(representation_ids)
            if not representation_ids:
                return
            filters["representationIds"] = list(representation_ids)

        version_ids_filter = None
        representation_names_filter = None
        if names_by_version_ids is not None:
            version_ids_filter = set()
            representation_names_filter = set()
            for version_id, names in names_by_version_ids.items():
                version_ids_filter.add(version_id)
                representation_names_filter |= set(names)

            if not version_ids_filter or not representation_names_filter:
                return

        else:
            if representation_names is not None:
                representation_names_filter = set(representation_names)
                if not representation_names_filter:
                    return

            if version_ids is not None:
                version_ids_filter = set(version_ids)
                if not version_ids_filter:
                    return

        if version_ids_filter:
            filters["versionIds"] = list(version_ids_filter)

        if representation_names_filter:
            filters["representationNames"] = list(representation_names_filter)

        if statuses is not None:
            statuses = set(statuses)
            if not statuses:
                return
            filters["representationStatuses"] = list(statuses)

        if tags is not None:
            tags = set(tags)
            if not tags:
                return
            filters["representationTags"] = list(tags)

        if has_links is not None:
            filters["representationHasLinks"] = has_links.upper()

        query = representations_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for repre in parsed_data["project"]["representations"]:
                if active is not None and active is not repre["active"]:
                    continue

                self._convert_entity_data(repre)

                self._representation_conversion(repre)

                yield repre

    def get_representation_by_id(
        self,
        project_name: str,
        representation_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["RepresentationDict"]:
        """Query representation entity from server based on id filter.

        Args:
            project_name (str): Project where to look for representation.
            representation_id (str): Id of representation.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[RepresentationDict]: Queried representation
                entity or None.

        """
        representations = self.get_representations(
            project_name,
            representation_ids=[representation_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for representation in representations:
            return representation
        return None

    def get_representation_by_name(
        self,
        project_name: str,
        representation_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["RepresentationDict"]:
        """Query representation entity by name and version id.

        Args:
            project_name (str): Project where to look for representation.
            representation_name (str): Representation name.
            version_id (str): Version id.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[RepresentationDict]: Queried representation entity
                or None.

        """
        representations = self.get_representations(
            project_name,
            representation_names=[representation_name],
            version_ids=[version_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for representation in representations:
            return representation
        return None

    def get_representations_hierarchy(
        self,
        project_name: str,
        representation_ids: Iterable[str],
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        task_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
        representation_fields: Optional[Iterable[str]] = None,
    ) -> Dict[str, RepresentationHierarchy]:
        """Find representation with parents by representation id.

        Representation entity with parent entities up to project.

        Default fields are used when any fields are set to `None`. But it is
            possible to pass in empty iterable (list, set, tuple) to skip
            entity.

        Args:
            project_name (str): Project where to look for entities.
            representation_ids (Iterable[str]): Representation ids.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            task_fields (Optional[Iterable[str]]): Task fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.
            representation_fields (Optional[Iterable[str]]): Representation
                fields.

        Returns:
            dict[str, RepresentationHierarchy]: Parent entities by
                representation id.

        """
        if not representation_ids:
            return {}

        if project_fields is not None:
            project_fields = set(project_fields)
            self._prepare_fields("project", project_fields)

        project = {}
        if project_fields is None:
            project = self.get_project(project_name)

        elif project_fields:
            # Keep project as empty dictionary if does not have
            #   filled any fields
            project = self.get_project(
                project_name, fields=project_fields
            )

        repre_ids = set(representation_ids)
        output = {
            repre_id: RepresentationHierarchy(
                project, None, None, None, None, None
            )
            for repre_id in representation_ids
        }

        if folder_fields is None:
            folder_fields = self.get_default_fields_for_type("folder")
        else:
            folder_fields = set(folder_fields)

        if task_fields is None:
            task_fields = self.get_default_fields_for_type("task")
        else:
            task_fields = set(task_fields)

        if product_fields is None:
            product_fields = self.get_default_fields_for_type("product")
        else:
            product_fields = set(product_fields)

        if version_fields is None:
            version_fields = self.get_default_fields_for_type("version")
        else:
            version_fields = set(version_fields)

        if representation_fields is None:
            representation_fields = self.get_default_fields_for_type(
                "representation"
            )
        else:
            representation_fields = set(representation_fields)

        for (entity_type, fields) in (
            ("folder", folder_fields),
            ("task", task_fields),
            ("product", product_fields),
            ("version", version_fields),
            ("representation", representation_fields),
        ):
            self._prepare_fields(entity_type, fields)

        representation_fields.add("id")

        query = representations_hierarchy_qraphql_query(
            folder_fields,
            task_fields,
            product_fields,
            version_fields,
            representation_fields,
        )
        query.set_variable_value("projectName", project_name)
        query.set_variable_value("representationIds", list(repre_ids))

        parsed_data = query.query(self)
        for repre in parsed_data["project"]["representations"]:
            repre_id = repre["id"]
            version = repre.pop("version", {})
            product = version.pop("product", {})
            task = version.pop("task", None)
            folder = product.pop("folder", {})
            self._convert_entity_data(repre)
            self._representation_conversion(repre)
            self._convert_entity_data(version)
            self._convert_entity_data(product)
            self._convert_entity_data(folder)
            if task:
                self._convert_entity_data(task)

            output[repre_id] = RepresentationHierarchy(
                project, folder, task, product, version, repre
            )

        return output

    def get_representation_hierarchy(
        self,
        project_name: str,
        representation_id: str,
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        task_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
        representation_fields: Optional[Iterable[str]] = None,
    ) -> Optional[RepresentationHierarchy]:
        """Find representation parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_id (str): Representation id.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            task_fields (Optional[Iterable[str]]): Task fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.
            representation_fields (Optional[Iterable[str]]): Representation
                fields.

        Returns:
            RepresentationHierarchy: Representation hierarchy entities.

        """
        if not representation_id:
            return None

        parents_by_repre_id = self.get_representations_hierarchy(
            project_name,
            [representation_id],
            project_fields=project_fields,
            folder_fields=folder_fields,
            task_fields=task_fields,
            product_fields=product_fields,
            version_fields=version_fields,
            representation_fields=representation_fields,
        )
        return parents_by_repre_id[representation_id]

    def get_representations_parents(
        self,
        project_name: str,
        representation_ids: Iterable[str],
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
    ) -> Dict[str, RepresentationParents]:
        """Find representations parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_ids (Iterable[str]): Representation ids.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.

        Returns:
            dict[str, RepresentationParents]: Parent entities by
                representation id.

        """
        hierarchy_by_repre_id = self.get_representations_hierarchy(
            project_name,
            representation_ids,
            project_fields=project_fields,
            folder_fields=folder_fields,
            task_fields=set(),
            product_fields=product_fields,
            version_fields=version_fields,
            representation_fields={"id"},
        )
        return {
            repre_id: RepresentationParents(
                hierarchy.version,
                hierarchy.product,
                hierarchy.folder,
                hierarchy.project,
            )
            for repre_id, hierarchy in hierarchy_by_repre_id.items()
        }

    def get_representation_parents(
        self,
        project_name: str,
        representation_id: str,
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
    ) -> Optional["RepresentationParents"]:
        """Find representation parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_id (str): Representation id.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.

        Returns:
            RepresentationParents: Representation parent entities.

        """
        if not representation_id:
            return None

        parents_by_repre_id = self.get_representations_parents(
            project_name,
            [representation_id],
            project_fields=project_fields,
            folder_fields=folder_fields,
            product_fields=product_fields,
            version_fields=version_fields,
        )
        return parents_by_repre_id[representation_id]

    def get_repre_ids_by_context_filters(
        self,
        project_name: str,
        context_filters: Optional[Dict[str, Iterable[str]]],
        representation_names: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """Find representation ids which match passed context filters.

        Each representation has context integrated on representation entity in
        database. The context may contain project, folder, task name or
        product name, product type and many more. This implementation gives
        option to quickly filter representation based on representation data
        in database.

        Context filters have defined structure. To define filter of nested
            subfield use dot '.' as delimiter (For example 'task.name').
        Filter values can be regex filters. String or ``re.Pattern`` can
            be used.

        Args:
            project_name (str): Project where to look for representations.
            context_filters (dict[str, list[str]]): Filters of context fields.
            representation_names (Optional[Iterable[str]]): Representation
                names, can be used as additional filter for representations
                by their names.
            version_ids (Optional[Iterable[str]]): Version ids, can be used
                as additional filter for representations by their parent ids.

        Returns:
            list[str]: Representation ids that match passed filters.

        Example:
            The function returns just representation ids so if entities are
                required for funtionality they must be queried afterwards by
                their ids.
            >>> project_name = "testProject"
            >>> filters = {
            ...     "task.name": ["[aA]nimation"],
            ...     "product": [".*[Mm]ain"]
            ... }
            >>> repre_ids = get_repre_ids_by_context_filters(
            ...     project_name, filters)
            >>> repres = get_representations(project_name, repre_ids)

        """
        if not isinstance(context_filters, dict):
            raise TypeError(
                f"Expected 'dict' got {str(type(context_filters))}"
            )

        filter_body = {}
        if representation_names is not None:
            if not representation_names:
                return []
            filter_body["names"] = list(set(representation_names))

        if version_ids is not None:
            if not version_ids:
                return []
            filter_body["versionIds"] = list(set(version_ids))

        body_context_filters = []
        for key, filters in context_filters.items():
            if not isinstance(filters, (set, list, tuple)):
                raise TypeError(
                    "Expected 'set', 'list', 'tuple' got {}".format(
                        str(type(filters))))

            new_filters = set()
            for filter_value in filters:
                if isinstance(filter_value, PatternType):
                    filter_value = filter_value.pattern
                new_filters.add(filter_value)

            body_context_filters.append({
                "key": key,
                "values": list(new_filters)
            })

        response = self.post(
            f"projects/{project_name}/repreContextFilter",
            context=body_context_filters,
            **filter_body
        )
        response.raise_for_status()
        return response.data["ids"]

    def create_representation(
        self,
        project_name: str,
        name: str,
        version_id: str,
        files: Optional[List[Dict[str, Any]]] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        traits: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]]=None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        representation_id: Optional[str] = None,
    ) -> str:
        """Create new representation.

        Args:
            project_name (str): Project name.
            name (str): Representation name.
            version_id (str): Parent version id.
            files (Optional[list[dict]]): Representation files information.
            attrib (Optional[dict[str, Any]]): Representation attributes.
            data (Optional[dict[str, Any]]): Representation data.
            traits (Optional[dict[str, Any]]): Representation traits
                serialized data as dict.
            tags (Optional[Iterable[str]]): Representation tags.
            status (Optional[str]): Representation status.
            active (Optional[bool]): Representation active state.
            representation_id (Optional[str]): Representation id. If not
                passed new id is generated.

        Returns:
            str: Representation id.

        """
        if not representation_id:
            representation_id = create_entity_id()
        create_data = {
            "id": representation_id,
            "name": name,
            "versionId": version_id,
        }
        for key, value in (
            ("files", files),
            ("attrib", attrib),
            ("data", data),
            ("traits", traits),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/representations",
            **create_data
        )
        response.raise_for_status()
        return representation_id

    def update_representation(
        self,
        project_name: str,
        representation_id: str,
        name: Optional[str] = None,
        version_id: Optional[str] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        attrib: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        traits: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ):
        """Update representation entity on server.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            representation_id (str): Representation id.
            name (Optional[str]): New name.
            version_id (Optional[str]): New version id.
            files (Optional[list[dict]]): New files
                information.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            traits (Optional[dict[str, Any]]): New traits.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("versionId", version_id),
            ("files", files),
            ("attrib", attrib),
            ("data", data),
            ("traits", traits),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/representations/{representation_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_representation(
        self, project_name: str, representation_id: str
    ):
        """Delete representation.

        Args:
            project_name (str): Project name.
            representation_id (str): Representation id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/representations/{representation_id}"
        )
        response.raise_for_status()

    def get_workfiles_info(
        self,
        project_name: str,
        workfile_ids: Optional[Iterable[str]] = None,
        task_ids: Optional[Iterable[str]] =None,
        paths: Optional[Iterable[str]] =None,
        path_regex: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        has_links: Optional[str]=None,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator["WorkfileInfoDict", None, None]:
        """Workfile info entities by passed filters.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_ids (Optional[Iterable[str]]): Workfile ids.
            task_ids (Optional[Iterable[str]]): Task ids.
            paths (Optional[Iterable[str]]): Rootless workfiles paths.
            path_regex (Optional[str]): Regex filter for workfile path.
            statuses (Optional[Iterable[str]]): Workfile info statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Workfile info tags used
                for filtering.
            has_links (Optional[Literal[IN, OUT, ANY]]): Filter
                representations with IN/OUT/ANY links.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Generator[WorkfileInfoDict, None, None]: Queried workfile info
                entites.

        """
        filters = {"projectName": project_name}
        if task_ids is not None:
            task_ids = set(task_ids)
            if not task_ids:
                return
            filters["taskIds"] = list(task_ids)

        if paths is not None:
            paths = set(paths)
            if not paths:
                return
            filters["paths"] = list(paths)

        if path_regex is not None:
            filters["workfilePathRegex"] = path_regex

        if workfile_ids is not None:
            workfile_ids = set(workfile_ids)
            if not workfile_ids:
                return
            filters["workfileIds"] = list(workfile_ids)

        if statuses is not None:
            statuses = set(statuses)
            if not statuses:
                return
            filters["workfileStatuses"] = list(statuses)

        if tags is not None:
            tags = set(tags)
            if not tags:
                return
            filters["workfileTags"] = list(tags)

        if has_links is not None:
            filters["workfilehasLinks"] = has_links.upper()

        if not fields:
            fields = self.get_default_fields_for_type("workfile")
        else:
            fields = set(fields)
            self._prepare_fields("workfile", fields)

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for workfiles. The"
                    " argument will be removed form function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        query = workfiles_info_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for workfile_info in parsed_data["project"]["workfiles"]:
                self._convert_entity_data(workfile_info)
                yield workfile_info

    def get_workfile_info(
        self,
        project_name: str,
        task_id: str,
        path: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["WorkfileInfoDict"]:
        """Workfile info entity by task id and workfile path.

        Args:
            project_name (str): Project under which the entity is located.
            task_id (str): Task id.
            path (str): Rootless workfile path.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Optional[WorkfileInfoDict]: Workfile info entity or None.

        """
        if not task_id or not path:
            return None

        for workfile_info in self.get_workfiles_info(
            project_name,
            task_ids=[task_id],
            paths=[path],
            fields=fields,
            own_attributes=own_attributes
        ):
            return workfile_info
        return None

    def get_workfile_info_by_id(
        self,
        project_name: str,
        workfile_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional["WorkfileInfoDict"]:
        """Workfile info entity by id.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_id (str): Workfile info id.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Optional[WorkfileInfoDict]: Workfile info entity or None.

        """
        if not workfile_id:
            return None

        for workfile_info in self.get_workfiles_info(
            project_name,
            workfile_ids=[workfile_id],
            fields=fields,
            own_attributes=own_attributes
        ):
            return workfile_info
        return None

    # --- Batch operations processing ---
    def send_batch_operations(
        self,
        project_name: str,
        operations: List[Dict[str, Any]],
        can_fail: bool = False,
        raise_on_fail: bool = True
    ) -> List[Dict[str, Any]]:
        """Post multiple CRUD operations to server.

        When multiple changes should be made on server side this is the best
        way to go. It is possible to pass multiple operations to process on a
        server side and do the changes in a transaction.

        Args:
            project_name (str): On which project should be operations
                processed.
            operations (list[dict[str, Any]]): Operations to be processed.
            can_fail (Optional[bool]): Server will try to process all
                operations even if one of them fails.
            raise_on_fail (Optional[bool]): Raise exception if an operation
                fails. You can handle failed operations on your own
                when set to 'False'.

        Raises:
            ValueError: Operations can't be converted to json string.
            FailedOperations: When output does not contain server operations
                or 'raise_on_fail' is enabled and any operation fails.

        Returns:
            list[dict[str, Any]]: Operations result with process details.

        """
        return self._send_batch_operations(
            f"projects/{project_name}/operations",
            operations,
            can_fail,
            raise_on_fail,
        )

    def _send_batch_operations(
        self,
        uri: str,
        operations: List[Dict[str, Any]],
        can_fail: bool,
        raise_on_fail: bool
    ) -> List[Dict[str, Any]]:
        if not operations:
            return []

        body_by_id = {}
        operations_body = []
        for operation in operations:
            if not operation:
                continue

            op_id = operation.get("id")
            if not op_id:
                op_id = create_entity_id()
                operation["id"] = op_id

            try:
                body = json.loads(
                    json.dumps(operation, default=entity_data_json_default)
                )
            except (TypeError, ValueError):
                raise ValueError("Couldn't json parse body: {}".format(
                    json.dumps(
                        operation, indent=4, default=failed_json_default
                    )
                ))

            body_by_id[op_id] = body
            operations_body.append(body)

        if not operations_body:
            return []

        result = self.post(
            uri,
            operations=operations_body,
            canFail=can_fail
        )

        op_results = result.get("operations")
        if op_results is None:
            detail = result.get("detail")
            if detail:
                raise FailedOperations(f"Operation failed. Detail: {detail}")
            raise FailedOperations(
                f"Operation failed. Content: {result.text}"
            )

        if result.get("success") or not raise_on_fail:
            return op_results

        for op_result in op_results:
            if not op_result["success"]:
                operation_id = op_result["id"]
                raise FailedOperations((
                    "Operation \"{}\" failed with data:\n{}\nDetail: {}."
                ).format(
                    operation_id,
                    json.dumps(body_by_id[operation_id], indent=4),
                    op_result["detail"],
                ))
        return op_results

    def _prepare_fields(
        self, entity_type: str, fields: Set[str], own_attributes: bool = False
    ):
        if not fields:
            return

        if "attrib" in fields:
            fields.remove("attrib")
            fields |= self.get_attributes_fields_for_type(entity_type)

        if own_attributes and entity_type in {"project", "folder", "task"}:
            fields.add("ownAttrib")

        if entity_type != "project":
            return

        # Use 'data' to fill 'bundle' data
        if "bundle" in fields:
            fields.remove("bundle")
            fields.add("data")

        maj_v, min_v, patch_v, _, _ = self.server_version_tuple
        if "folderTypes" in fields:
            fields.remove("folderTypes")
            folder_types_fields = set(DEFAULT_FOLDER_TYPE_FIELDS)
            if (maj_v, min_v, patch_v) > (1, 10, 0):
                folder_types_fields |= {"shortName"}
            fields |= {f"folderTypes.{name}" for name in folder_types_fields}

        if "taskTypes" in fields:
            fields.remove("taskTypes")
            task_types_fields = set(DEFAULT_TASK_TYPE_FIELDS)
            if (maj_v, min_v, patch_v) > (1, 10, 0):
                task_types_fields |= {"color", "icon", "shortName"}
            fields |= {f"taskTypes.{name}" for name in task_types_fields}

        for field, default_fields in (
            ("statuses", DEFAULT_PROJECT_STATUSES_FIELDS),
            ("tags", DEFAULT_PROJECT_TAGS_FIELDS),
            ("linkTypes", DEFAULT_PROJECT_TAGS_FIELDS),
        ):
            if (maj_v, min_v, patch_v) <= (1, 10, 0):
                break
            if field in fields:
                fields.remove(field)
                fields |= {f"{field}.{name}" for name in default_fields}

        if "productTypes" in fields:
            fields.remove("productTypes")
            fields |= {
                f"productTypes.{name}"
                for name in self.get_default_fields_for_type(
                    "productType"
                )
            }

    def _convert_entity_data(self, entity: "AnyEntityDict"):
        if not entity or "data" not in entity:
            return

        entity_data = entity["data"] or {}
        if isinstance(entity_data, str):
            entity_data = json.loads(entity_data)

        entity["data"] = entity_data
