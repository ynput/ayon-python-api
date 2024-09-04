"""Singleton based server api for direct access.

This implementation will be probably the most used part of package. Gives
option to have singleton connection to Server URL based on environment variable
values. All public functions and classes are imported in '__init__.py' so
they're available directly in top module import.

Function that are just wrappers for ServerAPI object are generated
automatically, and changing them manually can cause issues.
"""

import os
import socket

from .constants import (
    SERVER_URL_ENV_KEY,
    SERVER_API_ENV_KEY,
)
from .server_api import ServerAPI
from .exceptions import FailedServiceInit
from .utils import (
    get_default_settings_variant as _get_default_settings_variant
)


class GlobalServerAPI(ServerAPI):
    """Extended server api which also handles storing tokens and url.

    Created object expect to have set environment variables
    'AYON_SERVER_URL'. Also is expecting filled 'AYON_API_KEY'
    but that can be filled afterwards with calling 'login' method.
    """

    def __init__(
        self,
        site_id=None,
        client_version=None,
        default_settings_variant=None,
        ssl_verify=None,
        cert=None,
    ):
        url = self.get_url()
        token = self.get_token()

        super(GlobalServerAPI, self).__init__(
            url,
            token,
            site_id,
            client_version,
            default_settings_variant,
            ssl_verify,
            cert,
            # We want to make sure that server and api key validation
            #   happens all the time in 'GlobalServerAPI'.
            create_session=False,
        )
        self.validate_server_availability()
        self.create_session()

    def login(self, username, password):
        """Login to the server or change user.

        If user is the same as current user and token is available the
        login is skipped.

        """
        previous_token = self._access_token
        super(GlobalServerAPI, self).login(username, password)
        if self.has_valid_token and previous_token != self._access_token:
            os.environ[SERVER_API_ENV_KEY] = self._access_token

    @staticmethod
    def get_url():
        return os.environ.get(SERVER_URL_ENV_KEY)

    @staticmethod
    def get_token():
        return os.environ.get(SERVER_API_ENV_KEY)

    @staticmethod
    def set_environments(url, token):
        """Change url and token environemnts in currently running process.

        Args:
            url (str): New server url.
            token (str): User's token.

        """
        os.environ[SERVER_URL_ENV_KEY] = url or ""
        os.environ[SERVER_API_ENV_KEY] = token or ""


class GlobalContext:
    """Singleton connection holder.

    Goal is to avoid create connection on import which can be dangerous in
    some cases.

    """
    _connection = None

    @classmethod
    def is_connection_created(cls):
        return cls._connection is not None

    @classmethod
    def change_token(cls, url, token):
        GlobalServerAPI.set_environments(url, token)
        if cls._connection is None:
            return

        if cls._connection.get_base_url() == url:
            cls._connection.set_token(token)
        else:
            cls.close_connection()

    @classmethod
    def close_connection(cls):
        if cls._connection is not None:
            cls._connection.close_session()
        cls._connection = None

    @classmethod
    def create_connection(cls, *args, **kwargs):
        if cls._connection is not None:
            cls.close_connection()
        cls._connection = GlobalServerAPI(*args, **kwargs)
        return cls._connection

    @classmethod
    def get_server_api_connection(cls):
        if cls._connection is None:
            cls.create_connection()
        return cls._connection


class ServiceContext:
    """Helper for services running under server.

    When service is running from server the process receives information about
    connection from environment variables. This class helps to initialize the
    values without knowing environment variables (that may change over time).

    All what must be done is to call 'init_service' function/method. The
    arguments are for cases when the service is running in specific environment
    and their values are e.g. loaded from private file or for testing purposes.

    """
    token = None
    server_url = None
    addon_name = None
    addon_version = None
    service_name = None

    @classmethod
    def init_service(
        cls,
        token=None,
        server_url=None,
        addon_name=None,
        addon_version=None,
        service_name=None,
        connect=True
    ):
        token = token or os.environ.get("AYON_API_KEY")
        server_url = server_url or os.environ.get("AYON_SERVER_URL")
        if not server_url:
            raise FailedServiceInit("URL to server is not set")

        if not token:
            raise FailedServiceInit(
                "Token to server {} is not set".format(server_url)
            )

        addon_name = addon_name or os.environ.get("AYON_ADDON_NAME")
        addon_version = addon_version or os.environ.get("AYON_ADDON_VERSION")
        service_name = service_name or os.environ.get("AYON_SERVICE_NAME")

        cls.token = token
        cls.server_url = server_url
        cls.addon_name = addon_name
        cls.addon_version = addon_version
        cls.service_name = service_name or socket.gethostname()

        # Make sure required environments for GlobalServerAPI are set
        GlobalServerAPI.set_environments(cls.server_url, cls.token)

        if connect:
            print("Connecting to server \"{}\"".format(server_url))
            con = GlobalContext.get_server_api_connection()
            user = con.get_user()
            print("Logged in as user \"{}\"".format(user["name"]))


def init_service(*args, **kwargs):
    """Initialize current connection from service.

    The service expect specific environment variables. The variables must all
    be set to make the connection work as a service.

    """
    ServiceContext.init_service(*args, **kwargs)


def get_service_addon_name():
    """Name of addon which initialized service connection.

    Service context must be initialized to be able to use this function. Call
    'init_service' on you service start to do so.

    Returns:
        Union[str, None]: Name of addon or None.

    """
    return ServiceContext.addon_name


def get_service_addon_version():
    """Version of addon which initialized service connection.

    Service context must be initialized to be able to use this function. Call
    'init_service' on you service start to do so.

    Returns:
        Union[str, None]: Version of addon or None.

    """
    return ServiceContext.addon_version


def get_service_name():
    """Name of service.

    Service context must be initialized to be able to use this function. Call
    'init_service' on you service start to do so.

    Returns:
        Union[str, None]: Name of service if service was registered.

    """
    return ServiceContext.service_name


def get_service_addon_settings(project_name=None):
    """Addon settings of service which initialized service.

    Service context must be initialized to be able to use this function. Call
    'init_service' on you service start to do so.

    Args:
        project_name (Optional[str]): Project name.

    Returns:
        Dict[str, Any]: Addon settings.

    Raises:
        ValueError: When service was not initialized.

    """
    addon_name = get_service_addon_name()
    addon_version = get_service_addon_version()
    if addon_name is None or addon_version is None:
        raise ValueError("Service is not initialized")
    return get_addon_settings(
        addon_name, addon_version, project_name=project_name
    )


def is_connection_created():
    """Is global connection created.

    Returns:
        bool: True if connection was connected.

    """
    return GlobalContext.is_connection_created()


def create_connection(site_id=None, client_version=None):
    """Create global connection.

    Args:
        site_id (str): Machine site id/name.
        client_version (str): Desktop app version.

    Returns:
        GlobalServerAPI: Created connection.

    """
    return GlobalContext.create_connection(site_id, client_version)


def close_connection():
    """Close global connection if is connected."""
    GlobalContext.close_connection()


def change_token(url, token):
    """Change connection token for url.

    This function can be also used to change url.

    Args:
        url (str): Server url.
        token (str): API key token.

    """
    GlobalContext.change_token(url, token)


def set_environments(url, token):
    """Set global environments for global connection.

    Args:
        url (Union[str, None]): Url to server or None to unset environments.
        token (Union[str, None]): API key token to be used for connection.

    """
    GlobalServerAPI.set_environments(url, token)


def get_server_api_connection():
    """Access to global scope object of GlobalServerAPI.

    This access expect to have set environment variables 'AYON_SERVER_URL'
    and 'AYON_API_KEY'.

    Returns:
        GlobalServerAPI: Object of connection to server.

    """
    return GlobalContext.get_server_api_connection()

# ------------------------------------------------
#     This content is generated automatically.
# ------------------------------------------------
def get_base_url():
    con = get_server_api_connection()
    return con.get_base_url()


def get_rest_url():
    con = get_server_api_connection()
    return con.get_rest_url()


def get_ssl_verify():
    """Enable ssl verification.

    Returns:
        bool: Current state of ssl verification.

    """
    con = get_server_api_connection()
    return con.get_ssl_verify()


def set_ssl_verify(*args, **kwargs):
    """Change ssl verification state.

    Args:
        ssl_verify (Union[bool, str, None]): Enabled/disable
            ssl verification, can be a path to file.

    """
    con = get_server_api_connection()
    return con.set_ssl_verify(*args, **kwargs)


def get_cert():
    """Current cert file used for connection to server.

    Returns:
        Union[str, None]: Path to cert file.

    """
    con = get_server_api_connection()
    return con.get_cert()


def set_cert(*args, **kwargs):
    """Change cert file used for connection to server.

    Args:
        cert (Union[str, None]): Path to cert file.

    """
    con = get_server_api_connection()
    return con.set_cert(*args, **kwargs)


def get_timeout():
    """Current value for requests timeout.

    Returns:
        float: Timeout value in seconds.

    """
    con = get_server_api_connection()
    return con.get_timeout()


def set_timeout(*args, **kwargs):
    """Change timeout value for requests.

    Args:
        timeout (Union[float, None]): Timeout value in seconds.

    """
    con = get_server_api_connection()
    return con.set_timeout(*args, **kwargs)


def get_max_retries():
    """Current value for requests max retries.

    Returns:
        int: Max retries value.

    """
    con = get_server_api_connection()
    return con.get_max_retries()


def set_max_retries(*args, **kwargs):
    """Change max retries value for requests.

    Args:
        max_retries (Union[int, None]): Max retries value.

    """
    con = get_server_api_connection()
    return con.set_max_retries(*args, **kwargs)


def is_service_user():
    """Check if connection is using service API key.

    Returns:
        bool: Used api key belongs to service user.

    """
    con = get_server_api_connection()
    return con.is_service_user()


def get_site_id():
    """Site id used for connection.

    Site id tells server from which machine/site is connection created and
    is used for default site overrides when settings are received.

    Returns:
        Union[str, None]: Site id value or None if not filled.

    """
    con = get_server_api_connection()
    return con.get_site_id()


def set_site_id(*args, **kwargs):
    """Change site id of connection.

    Behave as specific site for server. It affects default behavior of
    settings getter methods.

    Args:
        site_id (Union[str, None]): Site id value, or 'None' to unset.

    """
    con = get_server_api_connection()
    return con.set_site_id(*args, **kwargs)


def get_client_version():
    """Version of client used to connect to server.

    Client version is AYON client build desktop application.

    Returns:
        str: Client version string used in connection.

    """
    con = get_server_api_connection()
    return con.get_client_version()


def set_client_version(*args, **kwargs):
    """Set version of client used to connect to server.

    Client version is AYON client build desktop application.

    Args:
        client_version (Union[str, None]): Client version string.

    """
    con = get_server_api_connection()
    return con.set_client_version(*args, **kwargs)


def get_default_settings_variant():
    """Default variant used for settings.

    Returns:
        Union[str, None]: name of variant or None.

    """
    if not GlobalContext.is_connection_created():
        return _get_default_settings_variant()
    con = get_server_api_connection()
    return con.get_default_settings_variant()


def set_default_settings_variant(*args, **kwargs):
    """Change default variant for addon settings.

    Note:
        It is recommended to set only 'production' or 'staging' variants
            as default variant.

    Args:
        variant (str): Settings variant name. It is possible to use
            'production', 'staging' or name of dev bundle.

    """
    con = get_server_api_connection()
    return con.set_default_settings_variant(*args, **kwargs)


def get_sender():
    """Sender used to send requests.

    Returns:
        Union[str, None]: Sender name or None.

    """
    con = get_server_api_connection()
    return con.get_sender()


def set_sender(*args, **kwargs):
    """Change sender used for requests.

    Args:
        sender (Union[str, None]): Sender name or None.

    """
    con = get_server_api_connection()
    return con.set_sender(*args, **kwargs)


def get_info():
    """Get information about current used api key.

    By default, the 'info' contains only 'uptime' and 'version'. With
    logged user info also contains information about user and machines on
    which was logged in.

    Todos:
        Use this method for validation of token instead of 'get_user'.

    Returns:
        dict[str, Any]: Information from server.

    """
    con = get_server_api_connection()
    return con.get_info()


def get_server_version():
    """Get server version.

    Version should match semantic version (https://semver.org/).

    Returns:
        str: Server version.

    """
    con = get_server_api_connection()
    return con.get_server_version()


def get_server_version_tuple():
    """Get server version as tuple.

    Version should match semantic version (https://semver.org/).

    This function only returns first three numbers of version.

    Returns:
        Tuple[int, int, int, Union[str, None], Union[str, None]]: Server
            version.

    """
    con = get_server_api_connection()
    return con.get_server_version_tuple()


def get_users(*args, **kwargs):
    """Get Users.

    Only administrators and managers can fetch all users. For other users
        it is required to pass in 'project_name' filter.

    Args:
        project_name (Optional[str]): Project name.
        usernames (Optional[Iterable[str]]): Filter by usernames.
        fields (Optional[Iterable[str]]): Fields to be queried
            for users.

    Returns:
        Generator[dict[str, Any]]: Queried users.

    """
    con = get_server_api_connection()
    return con.get_users(*args, **kwargs)


def get_user_by_name(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_user_by_name(*args, **kwargs)


def get_user(*args, **kwargs):
    """Get user info using REST endpoit.

    Args:
        username (Optional[str]): Username.

    Returns:
        Union[dict[str, Any], None]: User info or None if user is not
            found.

    """
    con = get_server_api_connection()
    return con.get_user(*args, **kwargs)


def raw_post(*args, **kwargs):
    con = get_server_api_connection()
    return con.raw_post(*args, **kwargs)


def raw_put(*args, **kwargs):
    con = get_server_api_connection()
    return con.raw_put(*args, **kwargs)


def raw_patch(*args, **kwargs):
    con = get_server_api_connection()
    return con.raw_patch(*args, **kwargs)


def raw_get(*args, **kwargs):
    con = get_server_api_connection()
    return con.raw_get(*args, **kwargs)


def raw_delete(*args, **kwargs):
    con = get_server_api_connection()
    return con.raw_delete(*args, **kwargs)


def post(*args, **kwargs):
    con = get_server_api_connection()
    return con.post(*args, **kwargs)


def put(*args, **kwargs):
    con = get_server_api_connection()
    return con.put(*args, **kwargs)


def patch(*args, **kwargs):
    con = get_server_api_connection()
    return con.patch(*args, **kwargs)


def get(*args, **kwargs):
    con = get_server_api_connection()
    return con.get(*args, **kwargs)


def delete(*args, **kwargs):
    con = get_server_api_connection()
    return con.delete(*args, **kwargs)


def get_event(*args, **kwargs):
    """Query full event data by id.

    Events received using event server do not contain full information. To
    get the full event information is required to receive it explicitly.

    Args:
        event_id (str): Event id.

    Returns:
        dict[str, Any]: Full event data.

    """
    con = get_server_api_connection()
    return con.get_event(*args, **kwargs)


def get_events(*args, **kwargs):
    """Get events from server with filtering options.

    Notes:
        Not all event happen on a project.

    Args:
        topics (Optional[Iterable[str]]): Name of topics.
        event_ids (Optional[Iterable[str]]): Event ids.
        project_names (Optional[Iterable[str]]): Project on which
            event happened.
        states (Optional[Iterable[str]]): Filtering by states.
        users (Optional[Iterable[str]]): Filtering by users
            who created/triggered an event.
        include_logs (Optional[bool]): Query also log events.
        has_children (Optional[bool]): Event is with/without children
            events. If 'None' then all events are returned, default.
        newer_than (Optional[str]): Return only events newer than given
            iso datetime string.
        older_than (Optional[str]): Return only events older than given
            iso datetime string.
        fields (Optional[Iterable[str]]): Fields that should be received
            for each event.

    Returns:
        Generator[dict[str, Any]]: Available events matching filters.

    """
    con = get_server_api_connection()
    return con.get_events(*args, **kwargs)


def update_event(*args, **kwargs):
    """Update event data.

    Args:
        event_id (str): Event id.
        sender (Optional[str]): New sender of event.
        project_name (Optional[str]): New project name.
        username (Optional[str]): New username.
        status (Optional[str]): New event status. Enum: "pending",
            "in_progress", "finished", "failed", "aborted", "restarted"
        description (Optional[str]): New description.
        summary (Optional[dict[str, Any]]): New summary.
        payload (Optional[dict[str, Any]]): New payload.
        progress (Optional[int]): New progress. Range [0-100].
        retries (Optional[int]): New retries.

    """
    con = get_server_api_connection()
    return con.update_event(*args, **kwargs)


def dispatch_event(*args, **kwargs):
    """Dispatch event to server.

    Args:
        topic (str): Event topic used for filtering of listeners.
        sender (Optional[str]): Sender of event.
        event_hash (Optional[str]): Event hash.
        project_name (Optional[str]): Project name.
        username (Optional[str]): Username which triggered event.
        depends_on (Optional[str]): Add dependency to another event.
        description (Optional[str]): Description of event.
        summary (Optional[dict[str, Any]]): Summary of event that can be used
            for simple filtering on listeners.
        payload (Optional[dict[str, Any]]): Full payload of event data with
            all details.
        finished (Optional[bool]): Mark event as finished on dispatch.
        store (Optional[bool]): Store event in event queue for possible
            future processing otherwise is event send only
            to active listeners.
        dependencies (Optional[list[str]]): Deprecated.
            List of event id dependencies.

    Returns:
        RestApiResponse: Response from server.

    """
    con = get_server_api_connection()
    return con.dispatch_event(*args, **kwargs)


def enroll_event_job(*args, **kwargs):
    """Enroll job based on events.

    Enroll will find first unprocessed event with 'source_topic' and will
    create new event with 'target_topic' for it and return the new event
    data.

    Use 'sequential' to control that only single target event is created
    at same time. Creation of new target events is blocked while there is
    at least one unfinished event with target topic, when set to 'True'.
    This helps when order of events matter and more than one process using
    the same target is running at the same time.

    Make sure the new event has updated status to '"finished"' status
    when you're done with logic

    Target topic should not clash with other processes/services.

    Created target event have 'dependsOn' key where is id of source topic.

    Use-case:
        - Service 1 is creating events with topic 'my.leech'
        - Service 2 process 'my.leech' and uses target topic 'my.process'
            - this service can run on 1-n machines
            - all events must be processed in a sequence by their creation
                time and only one event can be processed at a time
            - in this case 'sequential' should be set to 'True' so only
                one machine is actually processing events, but if one goes
                down there are other that can take place
        - Service 3 process 'my.leech' and uses target topic 'my.discover'
            - this service can run on 1-n machines
            - order of events is not important
            - 'sequential' should be 'False'

    Args:
        source_topic (str): Source topic to enroll.
        target_topic (str): Topic of dependent event.
        sender (str): Identifier of sender (e.g. service name or username).
        description (Optional[str]): Human readable text shown
            in target event.
        sequential (Optional[bool]): The source topic must be processed
            in sequence.
        events_filter (Optional[dict[str, Any]]): Filtering conditions
            to filter the source event. For more technical specifications
            look to server backed 'ayon_server.sqlfilter.Filter'.
            TODO: Add example of filters.
        max_retries (Optional[int]): How many times can be event retried.
            Default value is based on server (3 at the time of this PR).

    Returns:
        Union[None, dict[str, Any]]: None if there is no event matching
            filters. Created event with 'target_topic'.

    """
    con = get_server_api_connection()
    return con.enroll_event_job(*args, **kwargs)


def download_file_to_stream(*args, **kwargs):
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
        stream (Union[io.BytesIO, BinaryIO]): Stream where output will be stored.
        chunk_size (Optional[int]): Size of chunks that are received
            in single loop.
        progress (Optional[TransferProgress]): Object that gives ability
            to track download progress.

    """
    con = get_server_api_connection()
    return con.download_file_to_stream(*args, **kwargs)


def download_file(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.download_file(*args, **kwargs)


def upload_file_from_stream(*args, **kwargs):
    """Upload file to server from bytes.

    Todos:
        Use retries and timeout.
        Return RestApiResponse.

    Args:
        endpoint (str): Endpoint or url where file will be uploaded.
        stream (Union[io.BytesIO, BinaryIO]): File content stream.
        progress (Optional[TransferProgress]): Object that gives ability
            to track upload progress.
        request_type (Optional[RequestType]): Type of request that will
            be used to upload file.
        **kwargs (Any): Additional arguments that will be passed
            to request function.

    Returns:
        requests.Response: Response object

    """
    con = get_server_api_connection()
    return con.upload_file_from_stream(*args, **kwargs)


def upload_file(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.upload_file(*args, **kwargs)


def upload_reviewable(*args, **kwargs):
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
        RestApiResponse: Server response.

    """
    con = get_server_api_connection()
    return con.upload_reviewable(*args, **kwargs)


def trigger_server_restart():
    """Trigger server restart.

    Restart may be required when a change of specific value happened on
    server.

    """
    con = get_server_api_connection()
    return con.trigger_server_restart()


def query_graphql(*args, **kwargs):
    """Execute GraphQl query.

    Args:
        query (str): GraphQl query string.
        variables (Optional[dict[str, Any]): Variables that can be
            used in query.

    Returns:
        GraphQlResponse: Response from server.

    """
    con = get_server_api_connection()
    return con.query_graphql(*args, **kwargs)


def get_graphql_schema():
    con = get_server_api_connection()
    return con.get_graphql_schema()


def get_server_schema():
    """Get server schema with info, url paths, components etc.

    Todos:
        Cache schema - How to find out it is outdated?

    Returns:
        dict[str, Any]: Full server schema.

    """
    con = get_server_api_connection()
    return con.get_server_schema()


def get_schemas():
    """Get components schema.

    Name of components does not match entity type names e.g. 'project' is
    under 'ProjectModel'. We should find out some mapping. Also, there
    are properties which don't have information about reference to object
    e.g. 'config' has just object definition without reference schema.

    Returns:
        dict[str, Any]: Component schemas.

    """
    con = get_server_api_connection()
    return con.get_schemas()


def get_attributes_schema(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_attributes_schema(*args, **kwargs)


def reset_attributes_schema():
    con = get_server_api_connection()
    return con.reset_attributes_schema()


def set_attribute_config(*args, **kwargs):
    con = get_server_api_connection()
    return con.set_attribute_config(*args, **kwargs)


def remove_attribute_config(*args, **kwargs):
    """Remove attribute from server.

    This can't be un-done, please use carefully.

    Args:
        attribute_name (str): Name of attribute to remove.

    """
    con = get_server_api_connection()
    return con.remove_attribute_config(*args, **kwargs)


def get_attributes_for_type(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_attributes_for_type(*args, **kwargs)


def get_attributes_fields_for_type(*args, **kwargs):
    """Prepare attribute fields for entity type.

    Returns:
        set[str]: Attributes fields for entity type.

    """
    con = get_server_api_connection()
    return con.get_attributes_fields_for_type(*args, **kwargs)


def get_default_fields_for_type(*args, **kwargs):
    """Default fields for entity type.

    Returns most of commonly used fields from server.

    Args:
        entity_type (str): Name of entity type.

    Returns:
        set[str]: Fields that should be queried from server.

    """
    con = get_server_api_connection()
    return con.get_default_fields_for_type(*args, **kwargs)


def get_addons_info(*args, **kwargs):
    """Get information about addons available on server.

    Args:
        details (Optional[bool]): Detailed data with information how
            to get client code.

    """
    con = get_server_api_connection()
    return con.get_addons_info(*args, **kwargs)


def get_addon_url(*args, **kwargs):
    """Calculate url to addon route.

    Examples:

        >>> api = ServerAPI("https://your.url.com")
        >>> api.get_addon_url(
        ...     "example", "1.0.0", "private", "my.zip")
        'https://your.url.com/addons/example/1.0.0/private/my.zip'

    Args:
        addon_name (str): Name of addon.
        addon_version (str): Version of addon.
        *subpaths (str): Any amount of subpaths that are added to
            addon url.

    Returns:
        str: Final url.

    """
    con = get_server_api_connection()
    return con.get_addon_url(*args, **kwargs)


def download_addon_private_file(*args, **kwargs):
    """Download a file from addon private files.

    This method requires to have authorized token available. Private files
    are not under '/api' restpoint.

    Args:
        addon_name (str): Addon name.
        addon_version (str): Addon version.
        filename (str): Filename in private folder on server.
        destination_dir (str): Where the file should be downloaded.
        destination_filename (Optional[str]): Name of destination
            filename. Source filename is used if not passed.
        chunk_size (Optional[int]): Download chunk size.
        progress (Optional[TransferProgress]): Object that gives ability
            to track download progress.

    Returns:
        str: Filepath to downloaded file.

    """
    con = get_server_api_connection()
    return con.download_addon_private_file(*args, **kwargs)


def get_installers(*args, **kwargs):
    """Information about desktop application installers on server.

    Desktop application installers are helpers to download/update AYON
    desktop application for artists.

    Args:
        version (Optional[str]): Filter installers by version.
        platform_name (Optional[str]): Filter installers by platform name.

    Returns:
        list[dict[str, Any]]:

    """
    con = get_server_api_connection()
    return con.get_installers(*args, **kwargs)


def create_installer(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.create_installer(*args, **kwargs)


def update_installer(*args, **kwargs):
    """Update installer information on server.

    Args:
        filename (str): Installer filename.
        sources (list[dict[str, Any]]): List of sources that
            can be used to download file. Fully replaces existing sources.

    """
    con = get_server_api_connection()
    return con.update_installer(*args, **kwargs)


def delete_installer(*args, **kwargs):
    """Delete installer from server.

    Args:
        filename (str): Installer filename.

    """
    con = get_server_api_connection()
    return con.delete_installer(*args, **kwargs)


def download_installer(*args, **kwargs):
    """Download installer file from server.

    Args:
        filename (str): Installer filename.
        dst_filepath (str): Destination filepath.
        chunk_size (Optional[int]): Download chunk size.
        progress (Optional[TransferProgress]): Object that gives ability
            to track download progress.

    """
    con = get_server_api_connection()
    return con.download_installer(*args, **kwargs)


def upload_installer(*args, **kwargs):
    """Upload installer file to server.

    Args:
        src_filepath (str): Source filepath.
        dst_filename (str): Destination filename.
        progress (Optional[TransferProgress]): Object that gives ability
            to track download progress.

    Returns:
        requests.Response: Response object.

    """
    con = get_server_api_connection()
    return con.upload_installer(*args, **kwargs)


def get_dependency_packages():
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
        dict[str, Any]: Information about dependency packages known for
            server.

    """
    con = get_server_api_connection()
    return con.get_dependency_packages()


def create_dependency_package(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.create_dependency_package(*args, **kwargs)


def update_dependency_package(*args, **kwargs):
    """Update dependency package metadata on server.

    Args:
        filename (str): Filename of dependency package.
        sources (list[dict[str, Any]]): Information about
            sources from where it is possible to get file. Fully replaces
            existing sources.

    """
    con = get_server_api_connection()
    return con.update_dependency_package(*args, **kwargs)


def delete_dependency_package(*args, **kwargs):
    """Remove dependency package for specific platform.

    Args:
        filename (str): Filename of dependency package.
        platform_name (Optional[str]): Deprecated.

    """
    con = get_server_api_connection()
    return con.delete_dependency_package(*args, **kwargs)


def download_dependency_package(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.download_dependency_package(*args, **kwargs)


def upload_dependency_package(*args, **kwargs):
    """Upload dependency package to server.

    Args:
        src_filepath (str): Path to a package file.
        dst_filename (str): Dependency package filename or name of package
            for server version 0.2.0 or lower. Must be unique.
        platform_name (Optional[str]): Deprecated.
        progress (Optional[TransferProgress]): Object to keep track about
            upload state.

    """
    con = get_server_api_connection()
    return con.upload_dependency_package(*args, **kwargs)


def upload_addon_zip(*args, **kwargs):
    """Upload addon zip file to server.

    File is validated on server. If it is valid, it is installed. It will
        create an event job which can be tracked (tracking part is not
        implemented yet).

    Example output::

        {'eventId': 'a1bfbdee27c611eea7580242ac120003'}

    Args:
        src_filepath (str): Path to a zip file.
        progress (Optional[TransferProgress]): Object to keep track about
            upload state.

    Returns:
        dict[str, Any]: Response data from server.

    """
    con = get_server_api_connection()
    return con.upload_addon_zip(*args, **kwargs)


def get_bundles():
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
    con = get_server_api_connection()
    return con.get_bundles()


def create_bundle(*args, **kwargs):
    """Create bundle on server.

    Bundle cannot be changed once is created. Only isProduction, isStaging
    and dependency packages can change after creation.

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

    """
    con = get_server_api_connection()
    return con.create_bundle(*args, **kwargs)


def update_bundle(*args, **kwargs):
    """Update bundle on server.

    Dependency packages can be update only for single platform. Others
    will be left untouched. Use 'None' value to unset dependency package
    from bundle.

    Args:
        bundle_name (str): Name of bundle.
        dependency_packages (Optional[dict[str, str]]): Dependency pacakge
            names that should be used with the bundle.
        is_production (Optional[bool]): Bundle will be marked as
            production.
        is_staging (Optional[bool]): Bundle will be marked as staging.

    """
    con = get_server_api_connection()
    return con.update_bundle(*args, **kwargs)


def delete_bundle(*args, **kwargs):
    """Delete bundle from server.

    Args:
        bundle_name (str): Name of bundle to delete.

    """
    con = get_server_api_connection()
    return con.delete_bundle(*args, **kwargs)


def get_project_anatomy_presets():
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
    con = get_server_api_connection()
    return con.get_project_anatomy_presets()


def get_default_anatomy_preset_name():
    """Name of default anatomy preset.

    Primary preset is used as default preset. But when primary preset is
    not set a built-in is used instead. Built-in preset is named '_'.

    Returns:
        str: Name of preset that can be used by
            'get_project_anatomy_preset'.

    """
    con = get_server_api_connection()
    return con.get_default_anatomy_preset_name()


def get_project_anatomy_preset(*args, **kwargs):
    """Anatomy preset values by name.

    Get anatomy preset values by preset name. Primary preset is returned
    if preset name is set to 'None'.

    Args:
        preset_name (Optional[str]): Preset name.

    Returns:
        dict[str, Any]: Anatomy preset values.

    """
    con = get_server_api_connection()
    return con.get_project_anatomy_preset(*args, **kwargs)


def get_build_in_anatomy_preset():
    """Get built-in anatomy preset.

    Returns:
        dict[str, Any]: Built-in anatomy preset.

    """
    con = get_server_api_connection()
    return con.get_build_in_anatomy_preset()


def get_project_root_overrides(*args, **kwargs):
    """Root overrides per site name.

    Method is based on logged user and can't be received for any other
        user on server.

    Output will contain only roots per site id used by logged user.

    Args:
        project_name (str): Name of project.

    Returns:
         dict[str, dict[str, str]]: Root values by root name by site id.

    """
    con = get_server_api_connection()
    return con.get_project_root_overrides(*args, **kwargs)


def get_project_roots_by_site(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_project_roots_by_site(*args, **kwargs)


def get_project_root_overrides_by_site_id(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_project_root_overrides_by_site_id(*args, **kwargs)


def get_project_roots_for_site(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_project_roots_for_site(*args, **kwargs)


def get_project_roots_by_site_id(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_project_roots_by_site_id(*args, **kwargs)


def get_project_roots_by_platform(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_project_roots_by_platform(*args, **kwargs)


def get_addon_settings_schema(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addon_settings_schema(*args, **kwargs)


def get_addon_site_settings_schema(*args, **kwargs):
    """Site settings schema of an addon.

    Args:
        addon_name (str): Name of addon.
        addon_version (str): Version of addon.

    Returns:
        dict[str, Any]: Schema of site settings.

    """
    con = get_server_api_connection()
    return con.get_addon_site_settings_schema(*args, **kwargs)


def get_addon_studio_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addon_studio_settings(*args, **kwargs)


def get_addon_project_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addon_project_settings(*args, **kwargs)


def get_addon_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addon_settings(*args, **kwargs)


def get_addon_site_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addon_site_settings(*args, **kwargs)


def get_bundle_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_bundle_settings(*args, **kwargs)


def get_addons_studio_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addons_studio_settings(*args, **kwargs)


def get_addons_project_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addons_project_settings(*args, **kwargs)


def get_addons_settings(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_addons_settings(*args, **kwargs)


def get_secrets():
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
        list[dict[str, str]]: List of secret entities.

    """
    con = get_server_api_connection()
    return con.get_secrets()


def get_secret(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_secret(*args, **kwargs)


def save_secret(*args, **kwargs):
    """Save secret.

    This endpoint can create and update secret.

    Args:
        secret_name (str): Name of secret.
        secret_value (str): Value of secret.

    """
    con = get_server_api_connection()
    return con.save_secret(*args, **kwargs)


def delete_secret(*args, **kwargs):
    """Delete secret by name.

    Args:
        secret_name (str): Name of secret to delete.

    """
    con = get_server_api_connection()
    return con.delete_secret(*args, **kwargs)


def get_rest_project(*args, **kwargs):
    """Query project by name.

    This call returns project with anatomy data.

    Args:
        project_name (str): Name of project.

    Returns:
        Union[dict[str, Any], None]: Project entity data or 'None' if
            project was not found.

    """
    con = get_server_api_connection()
    return con.get_rest_project(*args, **kwargs)


def get_rest_projects(*args, **kwargs):
    """Query available project entities.

    User must be logged in.

    Args:
        active (Optional[bool]): Filter active/inactive projects. Both
            are returned if 'None' is passed.
        library (Optional[bool]): Filter standard/library projects. Both
            are returned if 'None' is passed.

    Returns:
        Generator[dict[str, Any]]: Available projects.

    """
    con = get_server_api_connection()
    return con.get_rest_projects(*args, **kwargs)


def get_rest_entity_by_id(*args, **kwargs):
    """Get entity using REST on a project by its id.

    Args:
        project_name (str): Name of project where entity is.
        entity_type (Literal["folder", "task", "product", "version"]): The
            entity type which should be received.
        entity_id (str): Id of entity.

    Returns:
        dict[str, Any]: Received entity data.

    """
    con = get_server_api_connection()
    return con.get_rest_entity_by_id(*args, **kwargs)


def get_rest_folder(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_rest_folder(*args, **kwargs)


def get_rest_folders(*args, **kwargs):
    """Get simplified flat list of all project folders.

    Get all project folders in single REST call. This can be faster than
        using 'get_folders' method which is using GraphQl, but does not
        allow any filtering, and set of fields is defined
        by server backend.

    Example::

        [
            {
                "id": "112233445566",
                "parentId": "112233445567",
                "path": "/root/parent/child",
                "parents": ["root", "parent"],
                "name": "child",
                "label": "Child",
                "folderType": "Folder",
                "hasTasks": False,
                "hasChildren": False,
                "taskNames": [
                    "Compositing",
                ],
                "status": "In Progress",
                "attrib": {},
                "ownAttrib": [],
                "updatedAt": "2023-06-12T15:37:02.420260",
            },
            ...
        ]

    Args:
        project_name (str): Project name.
        include_attrib (Optional[bool]): Include attribute values
            in output. Slower to query.

    Returns:
        list[dict[str, Any]]: List of folder entities.

    """
    con = get_server_api_connection()
    return con.get_rest_folders(*args, **kwargs)


def get_rest_task(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_rest_task(*args, **kwargs)


def get_rest_product(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_rest_product(*args, **kwargs)


def get_rest_version(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_rest_version(*args, **kwargs)


def get_rest_representation(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_rest_representation(*args, **kwargs)


def get_project_names(*args, **kwargs):
    """Receive available project names.

    User must be logged in.

    Args:
        active (Optional[bool]): Filter active/inactive projects. Both
            are returned if 'None' is passed.
        library (Optional[bool]): Filter standard/library projects. Both
            are returned if 'None' is passed.

    Returns:
        list[str]: List of available project names.

    """
    con = get_server_api_connection()
    return con.get_project_names(*args, **kwargs)


def get_projects(*args, **kwargs):
    """Get projects.

    Args:
        active (Optional[bool]): Filter active or inactive projects.
            Filter is disabled when 'None' is passed.
        library (Optional[bool]): Filter library projects. Filter is
            disabled when 'None' is passed.
        fields (Optional[Iterable[str]]): fields to be queried
            for project.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Generator[dict[str, Any]]: Queried projects.

    """
    con = get_server_api_connection()
    return con.get_projects(*args, **kwargs)


def get_project(*args, **kwargs):
    """Get project.

    Args:
        project_name (str): Name of project.
        fields (Optional[Iterable[str]]): fields to be queried
            for project.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Union[dict[str, Any], None]: Project entity data or None
            if project was not found.

    """
    con = get_server_api_connection()
    return con.get_project(*args, **kwargs)


def get_folders_hierarchy(*args, **kwargs):
    """Get project hierarchy.

    All folders in project in hierarchy data structure.

    Example output:
        {
            "hierarchy": [
                {
                    "id": "...",
                    "name": "...",
                    "label": "...",
                    "status": "...",
                    "folderType": "...",
                    "hasTasks": False,
                    "taskNames": [],
                    "parents": [],
                    "parentId": None,
                    "children": [...children folders...]
                },
                ...
            ]
        }

    Args:
        project_name (str): Project where to look for folders.
        search_string (Optional[str]): Search string to filter folders.
        folder_types (Optional[Iterable[str]]): Folder types to filter.

    Returns:
        dict[str, Any]: Response data from server.

    """
    con = get_server_api_connection()
    return con.get_folders_hierarchy(*args, **kwargs)


def get_folders_rest(*args, **kwargs):
    """Get simplified flat list of all project folders.

    Get all project folders in single REST call. This can be faster than
        using 'get_folders' method which is using GraphQl, but does not
        allow any filtering, and set of fields is defined
        by server backend.

    Example::

        [
            {
                "id": "112233445566",
                "parentId": "112233445567",
                "path": "/root/parent/child",
                "parents": ["root", "parent"],
                "name": "child",
                "label": "Child",
                "folderType": "Folder",
                "hasTasks": False,
                "hasChildren": False,
                "taskNames": [
                    "Compositing",
                ],
                "status": "In Progress",
                "attrib": {},
                "ownAttrib": [],
                "updatedAt": "2023-06-12T15:37:02.420260",
            },
            ...
        ]

    Deprecated:
        Use 'get_rest_folders' instead. Function was renamed to match
            other rest functions, like 'get_rest_folder',
            'get_rest_project' etc. .
        Will be removed in '1.0.7' or '1.1.0'.

    Args:
        project_name (str): Project name.
        include_attrib (Optional[bool]): Include attribute values
            in output. Slower to query.

    Returns:
        list[dict[str, Any]]: List of folder entities.

    """
    con = get_server_api_connection()
    return con.get_folders_rest(*args, **kwargs)


def get_folders(*args, **kwargs):
    """Query folders from server.

    Todos:
        Folder name won't be unique identifier, so we should add folder path
            filtering.

    Notes:
        Filter 'active' don't have direct filter in GraphQl.

    Args:
        project_name (str): Name of project.
        folder_ids (Optional[Iterable[str]]): Folder ids to filter.
        folder_paths (Optional[Iterable[str]]): Folder paths used
            for filtering.
        folder_names (Optional[Iterable[str]]): Folder names used
            for filtering.
        folder_types (Optional[Iterable[str]]): Folder types used
            for filtering.
        parent_ids (Optional[Iterable[str]]): Ids of folder parents.
            Use 'None' if folder is direct child of project.
        folder_path_regex (Optional[str]): Folder path regex used
            for filtering.
        has_products (Optional[bool]): Filter folders with/without
            products. Ignored when None, default behavior.
        has_tasks (Optional[bool]): Filter folders with/without
            tasks. Ignored when None, default behavior.
        has_children (Optional[bool]): Filter folders with/without
            children. Ignored when None, default behavior.
        statuses (Optional[Iterable[str]]): Folder statuses used
            for filtering.
        assignees_all (Optional[Iterable[str]]): Filter by assigness
            on children tasks. Task must have all of passed assignees.
        tags (Optional[Iterable[str]]): Folder tags used
            for filtering.
        active (Optional[bool]): Filter active/inactive folders.
            Both are returned if is set to None.
        has_links (Optional[Literal[IN, OUT, ANY]]): Filter
            representations with IN/OUT/ANY links.
        fields (Optional[Iterable[str]]): Fields to be queried for
            folder. All possible folder fields are returned
            if 'None' is passed.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Generator[dict[str, Any]]: Queried folder entities.

    """
    con = get_server_api_connection()
    return con.get_folders(*args, **kwargs)


def get_folder_by_id(*args, **kwargs):
    """Query folder entity by id.

    Args:
        project_name (str): Name of project where to look for queried
            entities.
        folder_id (str): Folder id.
        fields (Optional[Iterable[str]]): Fields that should be returned.
            All fields are returned if 'None' is passed.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Union[dict, None]: Folder entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_folder_by_id(*args, **kwargs)


def get_folder_by_path(*args, **kwargs):
    """Query folder entity by path.

    Folder path is a path to folder with all parent names joined by slash.

    Args:
        project_name (str): Name of project where to look for queried
            entities.
        folder_path (str): Folder path.
        fields (Optional[Iterable[str]]): Fields that should be returned.
            All fields are returned if 'None' is passed.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Union[dict, None]: Folder entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_folder_by_path(*args, **kwargs)


def get_folder_by_name(*args, **kwargs):
    """Query folder entity by path.

    Warnings:
        Folder name is not a unique identifier of a folder. Function is
            kept for OpenPype 3 compatibility.

    Args:
        project_name (str): Name of project where to look for queried
            entities.
        folder_name (str): Folder name.
        fields (Optional[Iterable[str]]): Fields that should be returned.
            All fields are returned if 'None' is passed.
        own_attributes (Optional[bool]): Attribute values that are
            not explicitly set on entity will have 'None' value.

    Returns:
        Union[dict, None]: Folder entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_folder_by_name(*args, **kwargs)


def get_folder_ids_with_products(*args, **kwargs):
    """Find folders which have at least one product.

    Folders that have at least one product should be immutable, so they
    should not change path -> change of name or name of any parent
    is not possible.

    Args:
        project_name (str): Name of project.
        folder_ids (Optional[Iterable[str]]): Limit folder ids filtering
            to a set of folders. If set to None all folders on project are
            checked.

    Returns:
        set[str]: Folder ids that have at least one product.

    """
    con = get_server_api_connection()
    return con.get_folder_ids_with_products(*args, **kwargs)


def create_folder(*args, **kwargs):
    """Create new folder.

    Args:
        project_name (str): Project name.
        name (str): Folder name.
        folder_type (Optional[str]): Folder type.
        parent_id (Optional[str]): Parent folder id. Parent is project
            if is ``None``.
        label (Optional[str]): Label of folder.
        attrib (Optional[dict[str, Any]]): Folder attributes.
        data (Optional[dict[str, Any]]): Folder data.
        tags (Optional[Iterable[str]]): Folder tags.
        status (Optional[str]): Folder status.
        active (Optional[bool]): Folder active state.
        thumbnail_id (Optional[str]): Folder thumbnail id.
        folder_id (Optional[str]): Folder id. If not passed new id is
            generated.

    Returns:
        str: Entity id.

    """
    con = get_server_api_connection()
    return con.create_folder(*args, **kwargs)


def update_folder(*args, **kwargs):
    """Update folder entity on server.

    Do not pass ``parent_id``, ``label`` amd ``thumbnail_id`` if you don't
        want to change their values. Value ``None`` would unset
        their value.

    Update of ``data`` will override existing value on folder entity.

    Update of ``attrib`` does change only passed attributes. If you want
        to unset value, use ``None``.

    Args:
        project_name (str): Project name.
        folder_id (str): Folder id.
        name (Optional[str]): New name.
        folder_type (Optional[str]): New folder type.
        parent_id (Optional[Union[str, None]]): New parent folder id.
        label (Optional[Union[str, None]]): New label.
        attrib (Optional[dict[str, Any]]): New attributes.
        data (Optional[dict[str, Any]]): New data.
        tags (Optional[Iterable[str]]): New tags.
        status (Optional[str]): New status.
        active (Optional[bool]): New active state.
        thumbnail_id (Optional[Union[str, None]]): New thumbnail id.

    """
    con = get_server_api_connection()
    return con.update_folder(*args, **kwargs)


def delete_folder(*args, **kwargs):
    """Delete folder.

    Args:
        project_name (str): Project name.
        folder_id (str): Folder id to delete.
        force (Optional[bool]): Folder delete folder with all children
            folder, products, versions and representations.

    """
    con = get_server_api_connection()
    return con.delete_folder(*args, **kwargs)


def get_tasks(*args, **kwargs):
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
        Generator[dict[str, Any]]: Queried task entities.

    """
    con = get_server_api_connection()
    return con.get_tasks(*args, **kwargs)


def get_task_by_name(*args, **kwargs):
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
        Union[dict, None]: Task entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_task_by_name(*args, **kwargs)


def get_task_by_id(*args, **kwargs):
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
        Union[dict, None]: Task entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_task_by_id(*args, **kwargs)


def get_tasks_by_folder_paths(*args, **kwargs):
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
        dict[dict[str, list[dict[str, Any]]]: Task entities by
            folder path.

    """
    con = get_server_api_connection()
    return con.get_tasks_by_folder_paths(*args, **kwargs)


def get_tasks_by_folder_path(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_tasks_by_folder_path(*args, **kwargs)


def get_task_by_folder_path(*args, **kwargs):
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
        Union[dict[str, Any], None]: Task entity data or None if was
            not found.

    """
    con = get_server_api_connection()
    return con.get_task_by_folder_path(*args, **kwargs)


def create_task(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.create_task(*args, **kwargs)


def update_task(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.update_task(*args, **kwargs)


def delete_task(*args, **kwargs):
    """Delete task.

    Args:
        project_name (str): Project name.
        task_id (str): Task id to delete.

    """
    con = get_server_api_connection()
    return con.delete_task(*args, **kwargs)


def get_products(*args, **kwargs):
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
        Generator[dict[str, Any]]: Queried product entities.

    """
    con = get_server_api_connection()
    return con.get_products(*args, **kwargs)


def get_product_by_id(*args, **kwargs):
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
        Union[dict, None]: Product entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_product_by_id(*args, **kwargs)


def get_product_by_name(*args, **kwargs):
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
        Union[dict, None]: Product entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_product_by_name(*args, **kwargs)


def get_product_types(*args, **kwargs):
    """Types of products.

    This is server wide information. Product types have 'name', 'icon' and
        'color'.

    Args:
        fields (Optional[Iterable[str]]): Product types fields to query.

    Returns:
        list[dict[str, Any]]: Product types information.

    """
    con = get_server_api_connection()
    return con.get_product_types(*args, **kwargs)


def get_project_product_types(*args, **kwargs):
    """Types of products available on a project.

    Filter only product types available on project.

    Args:
        project_name (str): Name of project where to look for
            product types.
        fields (Optional[Iterable[str]]): Product types fields to query.

    Returns:
        list[dict[str, Any]]: Product types information.

    """
    con = get_server_api_connection()
    return con.get_project_product_types(*args, **kwargs)


def get_product_type_names(*args, **kwargs):
    """Product type names.

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
    con = get_server_api_connection()
    return con.get_product_type_names(*args, **kwargs)


def create_product(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.create_product(*args, **kwargs)


def update_product(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.update_product(*args, **kwargs)


def delete_product(*args, **kwargs):
    """Delete product.

    Args:
        project_name (str): Project name.
        product_id (str): Product id to delete.

    """
    con = get_server_api_connection()
    return con.delete_product(*args, **kwargs)


def get_versions(*args, **kwargs):
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
        Generator[dict[str, Any]]: Queried version entities.

    """
    con = get_server_api_connection()
    return con.get_versions(*args, **kwargs)


def get_version_by_id(*args, **kwargs):
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
        Union[dict, None]: Version entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_version_by_id(*args, **kwargs)


def get_version_by_name(*args, **kwargs):
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
        Union[dict, None]: Version entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_version_by_name(*args, **kwargs)


def get_hero_version_by_id(*args, **kwargs):
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
        Union[dict, None]: Version entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_hero_version_by_id(*args, **kwargs)


def get_hero_version_by_product_id(*args, **kwargs):
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
        Union[dict, None]: Version entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_hero_version_by_product_id(*args, **kwargs)


def get_hero_versions(*args, **kwargs):
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
        Union[dict, None]: Version entity data or None if was not found.

    """
    con = get_server_api_connection()
    return con.get_hero_versions(*args, **kwargs)


def get_last_versions(*args, **kwargs):
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
        dict[str, dict[str, Any]]: Last versions by product id.

    """
    con = get_server_api_connection()
    return con.get_last_versions(*args, **kwargs)


def get_last_version_by_product_id(*args, **kwargs):
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
        Union[dict[str, Any], None]: Queried version entity or None.

    """
    con = get_server_api_connection()
    return con.get_last_version_by_product_id(*args, **kwargs)


def get_last_version_by_product_name(*args, **kwargs):
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
        Union[dict[str, Any], None]: Queried version entity or None.

    """
    con = get_server_api_connection()
    return con.get_last_version_by_product_name(*args, **kwargs)


def version_is_latest(*args, **kwargs):
    """Is version latest from a product.

    Args:
        project_name (str): Project where to look for representation.
        version_id (str): Version id.

    Returns:
        bool: Version is latest or not.

    """
    con = get_server_api_connection()
    return con.version_is_latest(*args, **kwargs)


def create_version(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.create_version(*args, **kwargs)


def update_version(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.update_version(*args, **kwargs)


def delete_version(*args, **kwargs):
    """Delete version.

    Args:
        project_name (str): Project name.
        version_id (str): Version id to delete.

    """
    con = get_server_api_connection()
    return con.delete_version(*args, **kwargs)


def get_representations(*args, **kwargs):
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
        names_by_version_ids (Optional[bool]): Find representations
            by names and version ids. This filter discard all
            other filters.
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
        Generator[dict[str, Any]]: Queried representation entities.

    """
    con = get_server_api_connection()
    return con.get_representations(*args, **kwargs)


def get_representation_by_id(*args, **kwargs):
    """Query representation entity from server based on id filter.

    Args:
        project_name (str): Project where to look for representation.
        representation_id (str): Id of representation.
        fields (Optional[Iterable[str]]): fields to be queried
            for representations.
        own_attributes (Optional[bool]): DEPRECATED: Not supported for
            representations.

    Returns:
        Union[dict[str, Any], None]: Queried representation entity or None.

    """
    con = get_server_api_connection()
    return con.get_representation_by_id(*args, **kwargs)


def get_representation_by_name(*args, **kwargs):
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
        Union[dict[str, Any], None]: Queried representation entity or None.

    """
    con = get_server_api_connection()
    return con.get_representation_by_name(*args, **kwargs)


def get_representations_hierarchy(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_representations_hierarchy(*args, **kwargs)


def get_representation_hierarchy(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_representation_hierarchy(*args, **kwargs)


def get_representations_parents(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_representations_parents(*args, **kwargs)


def get_representation_parents(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_representation_parents(*args, **kwargs)


def get_repre_ids_by_context_filters(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.get_repre_ids_by_context_filters(*args, **kwargs)


def create_representation(*args, **kwargs):
    """Create new representation.

    Args:
        project_name (str): Project name.
        name (str): Representation name.
        version_id (str): Parent version id.
        files (Optional[list[dict]]): Representation files information.
        attrib (Optional[dict[str, Any]]): Representation attributes.
        data (Optional[dict[str, Any]]): Representation data.
        tags (Optional[Iterable[str]]): Representation tags.
        status (Optional[str]): Representation status.
        active (Optional[bool]): Representation active state.
        representation_id (Optional[str]): Representation id. If not
            passed new id is generated.

    Returns:
        str: Representation id.

    """
    con = get_server_api_connection()
    return con.create_representation(*args, **kwargs)


def update_representation(*args, **kwargs):
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
        tags (Optional[Iterable[str]]): New tags.
        status (Optional[str]): New status.
        active (Optional[bool]): New active state.

    """
    con = get_server_api_connection()
    return con.update_representation(*args, **kwargs)


def delete_representation(*args, **kwargs):
    """Delete representation.

    Args:
        project_name (str): Project name.
        representation_id (str): Representation id to delete.

    """
    con = get_server_api_connection()
    return con.delete_representation(*args, **kwargs)


def get_workfiles_info(*args, **kwargs):
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
        Generator[dict[str, Any]]: Queried workfile info entites.

    """
    con = get_server_api_connection()
    return con.get_workfiles_info(*args, **kwargs)


def get_workfile_info(*args, **kwargs):
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
        Union[dict[str, Any], None]: Workfile info entity or None.

    """
    con = get_server_api_connection()
    return con.get_workfile_info(*args, **kwargs)


def get_workfile_info_by_id(*args, **kwargs):
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
        Union[dict[str, Any], None]: Workfile info entity or None.

    """
    con = get_server_api_connection()
    return con.get_workfile_info_by_id(*args, **kwargs)


def get_thumbnail_by_id(*args, **kwargs):
    """Get thumbnail from server by id.

    Permissions of thumbnails are related to entities so thumbnails must
    be queried per entity. So an entity type and entity type is required
    to be passed.

    Notes:
        It is recommended to use one of prepared entity type specific
            methods 'get_folder_thumbnail', 'get_version_thumbnail' or
            'get_workfile_thumbnail'.
        We do recommend pass thumbnail id if you have access to it. Each
            entity that allows thumbnails has 'thumbnailId' field, so it
            can be queried.

    Args:
        project_name (str): Project under which the entity is located.
        thumbnail_id (Optional[str]): DEPRECATED Use
            'get_thumbnail_by_id'.

    Returns:
        ThumbnailContent: Thumbnail content wrapper. Does not have to be
            valid.

    """
    con = get_server_api_connection()
    return con.get_thumbnail_by_id(*args, **kwargs)


def get_thumbnail(*args, **kwargs):
    """Get thumbnail from server.

    Permissions of thumbnails are related to entities so thumbnails must
    be queried per entity. So an entity type and entity type is required
    to be passed.

    Notes:
        It is recommended to use one of prepared entity type specific
            methods 'get_folder_thumbnail', 'get_version_thumbnail' or
            'get_workfile_thumbnail'.
        We do recommend pass thumbnail id if you have access to it. Each
            entity that allows thumbnails has 'thumbnailId' field, so it
            can be queried.

    Args:
        project_name (str): Project under which the entity is located.
        entity_type (str): Entity type which passed entity id represents.
        entity_id (str): Entity id for which thumbnail should be returned.
        thumbnail_id (Optional[str]): DEPRECATED Use
            'get_thumbnail_by_id'.

    Returns:
        ThumbnailContent: Thumbnail content wrapper. Does not have to be
            valid.

    """
    con = get_server_api_connection()
    return con.get_thumbnail(*args, **kwargs)


def get_folder_thumbnail(*args, **kwargs):
    """Prepared method to receive thumbnail for folder entity.

    Args:
        project_name (str): Project under which the entity is located.
        folder_id (str): Folder id for which thumbnail should be returned.
        thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
            Used only to check if thumbnail was already cached.

    Returns:
        Union[str, None]: Path to downloaded thumbnail or none if entity
            does not have any (or if user does not have permissions).

    """
    con = get_server_api_connection()
    return con.get_folder_thumbnail(*args, **kwargs)


def get_version_thumbnail(*args, **kwargs):
    """Prepared method to receive thumbnail for version entity.

    Args:
        project_name (str): Project under which the entity is located.
        version_id (str): Version id for which thumbnail should be
            returned.
        thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
            Used only to check if thumbnail was already cached.

    Returns:
        Union[str, None]: Path to downloaded thumbnail or none if entity
            does not have any (or if user does not have permissions).

    """
    con = get_server_api_connection()
    return con.get_version_thumbnail(*args, **kwargs)


def get_workfile_thumbnail(*args, **kwargs):
    """Prepared method to receive thumbnail for workfile entity.

    Args:
        project_name (str): Project under which the entity is located.
        workfile_id (str): Worfile id for which thumbnail should be
            returned.
        thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
            Used only to check if thumbnail was already cached.

    Returns:
        Union[str, None]: Path to downloaded thumbnail or none if entity
            does not have any (or if user does not have permissions).

    """
    con = get_server_api_connection()
    return con.get_workfile_thumbnail(*args, **kwargs)


def create_thumbnail(*args, **kwargs):
    """Create new thumbnail on server from passed path.

    Args:
        project_name (str): Project where the thumbnail will be created
            and can be used.
        src_filepath (str): Filepath to thumbnail which should be uploaded.
        thumbnail_id (Optional[str]): Prepared if of thumbnail.

    Returns:
        str: Created thumbnail id.

    Raises:
        ValueError: When thumbnail source cannot be processed.

    """
    con = get_server_api_connection()
    return con.create_thumbnail(*args, **kwargs)


def update_thumbnail(*args, **kwargs):
    """Change thumbnail content by id.

    Update can be also used to create new thumbnail.

    Args:
        project_name (str): Project where the thumbnail will be created
            and can be used.
        thumbnail_id (str): Thumbnail id to update.
        src_filepath (str): Filepath to thumbnail which should be uploaded.

    Raises:
        ValueError: When thumbnail source cannot be processed.

    """
    con = get_server_api_connection()
    return con.update_thumbnail(*args, **kwargs)


def create_project(*args, **kwargs):
    """Create project using AYON settings.

    This project creation function is not validating project entity on
    creation. It is because project entity is created blindly with only
    minimum required information about project which is name and code.

    Entered project name must be unique and project must not exist yet.

    Note:
        This function is here to be OP v4 ready but in v3 has more logic
            to do. That's why inner imports are in the body.

    Args:
        project_name (str): New project name. Should be unique.
        project_code (str): Project's code should be unique too.
        library_project (Optional[bool]): Project is library project.
        preset_name (Optional[str]): Name of anatomy preset. Default is
            used if not passed.

    Raises:
        ValueError: When project name already exists.

    Returns:
        dict[str, Any]: Created project entity.

    """
    con = get_server_api_connection()
    return con.create_project(*args, **kwargs)


def update_project(*args, **kwargs):
    """Update project entity on server.

    Args:
        project_name (str): Name of project.
        library (Optional[bool]): Change library state.
        folder_types (Optional[list[dict[str, Any]]]): Folder type
            definitions.
        task_types (Optional[list[dict[str, Any]]]): Task type
            definitions.
        link_types (Optional[list[dict[str, Any]]]): Link type
            definitions.
        statuses (Optional[list[dict[str, Any]]]): Status definitions.
        tags (Optional[list[dict[str, Any]]]): List of tags available to
            set on entities.
        config (Optional[dict[dict[str, Any]]]): Project anatomy config
            with templates and roots.
        attrib (Optional[dict[str, Any]]): Project attributes to change.
        data (Optional[dict[str, Any]]): Custom data of a project. This
            value will 100% override project data.
        active (Optional[bool]): Change active state of a project.
        project_code (Optional[str]): Change project code. Not recommended
            during production.
        **changes: Other changed keys based on Rest API documentation.

    """
    con = get_server_api_connection()
    return con.update_project(*args, **kwargs)


def delete_project(*args, **kwargs):
    """Delete project from server.

    This will completely remove project from server without any step back.

    Args:
        project_name (str): Project name that will be removed.

    """
    con = get_server_api_connection()
    return con.delete_project(*args, **kwargs)


def get_full_link_type_name(*args, **kwargs):
    """Calculate full link type name used for query from server.

    Args:
        link_type_name (str): Type of link.
        input_type (str): Input entity type of link.
        output_type (str): Output entity type of link.

    Returns:
        str: Full name of link type used for query from server.

    """
    con = get_server_api_connection()
    return con.get_full_link_type_name(*args, **kwargs)


def get_link_types(*args, **kwargs):
    """All link types available on a project.

    Example output:
        [
            {
                "name": "reference|folder|folder",
                "link_type": "reference",
                "input_type": "folder",
                "output_type": "folder",
                "data": {}
            }
        ]

    Args:
        project_name (str): Name of project where to look for link types.

    Returns:
        list[dict[str, Any]]: Link types available on project.

    """
    con = get_server_api_connection()
    return con.get_link_types(*args, **kwargs)


def get_link_type(*args, **kwargs):
    """Get link type data.

    There is not dedicated REST endpoint to get single link type,
    so method 'get_link_types' is used.

    Example output:
        {
            "name": "reference|folder|folder",
            "link_type": "reference",
            "input_type": "folder",
            "output_type": "folder",
            "data": {}
        }

    Args:
        project_name (str): Project where link type is available.
        link_type_name (str): Name of link type.
        input_type (str): Input entity type of link.
        output_type (str): Output entity type of link.

    Returns:
        Union[None, dict[str, Any]]: Link type information.

    """
    con = get_server_api_connection()
    return con.get_link_type(*args, **kwargs)


def create_link_type(*args, **kwargs):
    """Create or update link type on server.

    Warning:
        Because PUT is used for creation it is also used for update.

    Args:
        project_name (str): Project where link type is created.
        link_type_name (str): Name of link type.
        input_type (str): Input entity type of link.
        output_type (str): Output entity type of link.
        data (Optional[dict[str, Any]]): Additional data related to link.

    Raises:
        HTTPRequestError: Server error happened.

    """
    con = get_server_api_connection()
    return con.create_link_type(*args, **kwargs)


def delete_link_type(*args, **kwargs):
    """Remove link type from project.

    Args:
        project_name (str): Project where link type is created.
        link_type_name (str): Name of link type.
        input_type (str): Input entity type of link.
        output_type (str): Output entity type of link.

    Raises:
        HTTPRequestError: Server error happened.

    """
    con = get_server_api_connection()
    return con.delete_link_type(*args, **kwargs)


def make_sure_link_type_exists(*args, **kwargs):
    """Make sure link type exists on a project.

    Args:
        project_name (str): Name of project.
        link_type_name (str): Name of link type.
        input_type (str): Input entity type of link.
        output_type (str): Output entity type of link.
        data (Optional[dict[str, Any]]): Link type related data.

    """
    con = get_server_api_connection()
    return con.make_sure_link_type_exists(*args, **kwargs)


def create_link(*args, **kwargs):
    """Create link between 2 entities.

    Link has a type which must already exists on a project.

    Example output::

        {
            "id": "59a212c0d2e211eda0e20242ac120002"
        }

    Args:
        project_name (str): Project where the link is created.
        link_type_name (str): Type of link.
        input_id (str): Input entity id.
        input_type (str): Entity type of input entity.
        output_id (str): Output entity id.
        output_type (str): Entity type of output entity.
        link_name (Optional[str]): Name of link.
            Available from server version '1.0.0-rc.6'.

    Returns:
        dict[str, str]: Information about link.

    Raises:
        HTTPRequestError: Server error happened.

    """
    con = get_server_api_connection()
    return con.create_link(*args, **kwargs)


def delete_link(*args, **kwargs):
    """Remove link by id.

    Args:
        project_name (str): Project where link exists.
        link_id (str): Id of link.

    Raises:
        HTTPRequestError: Server error happened.

    """
    con = get_server_api_connection()
    return con.delete_link(*args, **kwargs)


def get_entities_links(*args, **kwargs):
    """Helper method to get links from server for entity types.

    .. highlight:: text
    .. code-block:: text

        Example output:
        {
            "59a212c0d2e211eda0e20242ac120001": [
                {
                    "id": "59a212c0d2e211eda0e20242ac120002",
                    "linkType": "reference",
                    "description": "reference link between folders",
                    "projectName": "my_project",
                    "author": "frantadmin",
                    "entityId": "b1df109676db11ed8e8c6c9466b19aa8",
                    "entityType": "folder",
                    "direction": "out"
                },
                ...
            ],
            ...
        }

    Args:
        project_name (str): Project where links are.
        entity_type (Literal["folder", "task", "product",
        |    "version", "representations"]): Entity type.
        entity_ids (Optional[Iterable[str]]): Ids of entities for which
        |    links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
        |    filter.
        link_names (Optional[Iterable[str]]): Link name filters.
        link_name_regex (Optional[str]): Regex filter for link name.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by entity ids.

    """
    con = get_server_api_connection()
    return con.get_entities_links(*args, **kwargs)


def get_folders_links(*args, **kwargs):
    """Query folders links from server.

    Args:
        project_name (str): Project where links are.
        folder_ids (Optional[Iterable[str]]): Ids of folders for which
            links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by folder ids.

    """
    con = get_server_api_connection()
    return con.get_folders_links(*args, **kwargs)


def get_folder_links(*args, **kwargs):
    """Query folder links from server.

    Args:
        project_name (str): Project where links are.
        folder_id (str): Folder id for which links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        list[dict[str, Any]]: Link info of folder.

    """
    con = get_server_api_connection()
    return con.get_folder_links(*args, **kwargs)


def get_tasks_links(*args, **kwargs):
    """Query tasks links from server.

    Args:
        project_name (str): Project where links are.
        task_ids (Optional[Iterable[str]]): Ids of tasks for which
            links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by task ids.

    """
    con = get_server_api_connection()
    return con.get_tasks_links(*args, **kwargs)


def get_task_links(*args, **kwargs):
    """Query task links from server.

    Args:
        project_name (str): Project where links are.
        task_id (str): Task id for which links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        list[dict[str, Any]]: Link info of task.

    """
    con = get_server_api_connection()
    return con.get_task_links(*args, **kwargs)


def get_products_links(*args, **kwargs):
    """Query products links from server.

    Args:
        project_name (str): Project where links are.
        product_ids (Optional[Iterable[str]]): Ids of products for which
            links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by product ids.

    """
    con = get_server_api_connection()
    return con.get_products_links(*args, **kwargs)


def get_product_links(*args, **kwargs):
    """Query product links from server.

    Args:
        project_name (str): Project where links are.
        product_id (str): Product id for which links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        list[dict[str, Any]]: Link info of product.

    """
    con = get_server_api_connection()
    return con.get_product_links(*args, **kwargs)


def get_versions_links(*args, **kwargs):
    """Query versions links from server.

    Args:
        project_name (str): Project where links are.
        version_ids (Optional[Iterable[str]]): Ids of versions for which
            links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by version ids.

    """
    con = get_server_api_connection()
    return con.get_versions_links(*args, **kwargs)


def get_version_links(*args, **kwargs):
    """Query version links from server.

    Args:
        project_name (str): Project where links are.
        version_id (str): Version id for which links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        list[dict[str, Any]]: Link info of version.

    """
    con = get_server_api_connection()
    return con.get_version_links(*args, **kwargs)


def get_representations_links(*args, **kwargs):
    """Query representations links from server.

    Args:
        project_name (str): Project where links are.
        representation_ids (Optional[Iterable[str]]): Ids of
            representations for which links should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        dict[str, list[dict[str, Any]]]: Link info by representation ids.

    """
    con = get_server_api_connection()
    return con.get_representations_links(*args, **kwargs)


def get_representation_links(*args, **kwargs):
    """Query representation links from server.

    Args:
        project_name (str): Project where links are.
        representation_id (str): Representation id for which links
            should be received.
        link_types (Optional[Iterable[str]]): Link type filters.
        link_direction (Optional[Literal["in", "out"]]): Link direction
            filter.

    Returns:
        list[dict[str, Any]]: Link info of representation.

    """
    con = get_server_api_connection()
    return con.get_representation_links(*args, **kwargs)


def send_batch_operations(*args, **kwargs):
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
    con = get_server_api_connection()
    return con.send_batch_operations(*args, **kwargs)
