import os
import re
import io
import json
import logging
import collections
import platform
import copy
from http import HTTPStatus

import requests

from .constants import (
    DEFAULT_PROJECT_FIELDS,
    DEFAULT_FOLDER_FIELDS,
    DEFAULT_TASK_FIELDS,
    DEFAULT_SUBSET_FIELDS,
    DEFAULT_VERSION_FIELDS,
    DEFAULT_REPRESENTATION_FIELDS,
    REPRESENTATION_FILES_FIELDS,
    DEFAULT_WORKFILE_INFO_FIELDS,
)
from .thumbnails import ThumbnailCache
from .graphql import GraphQlQuery, INTROSPECTION_QUERY
from .graphql_queries import (
    project_graphql_query,
    projects_graphql_query,
    folders_graphql_query,
    tasks_graphql_query,
    subsets_graphql_query,
    versions_graphql_query,
    representations_graphql_query,
    representations_parents_qraphql_query,
    workfiles_info_graphql_query,
)
from .exceptions import (
    FailedOperations,
    UnauthorizedError,
    AuthenticationError,
    ServerNotReached,
    ServerError,
)
from .utils import (
    logout_from_server,
    create_entity_id,
    entity_data_json_default,
    failed_json_default,
    TransferProgress,
)

JSONDecodeError = getattr(json, "JSONDecodeError", ValueError)
# This should be collected from server schema
PROJECT_NAME_ALLOWED_SYMBOLS = "a-zA-Z0-9_"
PROJECT_NAME_REGEX = re.compile(
    "^[{}]+$".format(PROJECT_NAME_ALLOWED_SYMBOLS)
)


class RequestType:
    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return self.name.__hash__()


class RequestTypes:
    get = RequestType("GET")
    post = RequestType("POST")
    put = RequestType("PUT")
    patch = RequestType("PATCH")
    delete = RequestType("DELETE")


class RestApiResponse(object):
    """API Response."""

    def __init__(self, response, data=None):
        if response is None:
            status_code = 500
        else:
            status_code = response.status_code
        self._response = response
        self.status = status_code
        self._data = data

    @property
    def orig_response(self):
        return self._response

    @property
    def headers(self):
        return self._response.headers

    @property
    def data(self):
        if self._data is None:
            if self.status != 204:
                self._data = self.orig_response.json()
            else:
                self._data = {}
        return self._data

    @property
    def content(self):
        return self._response.content

    @property
    def content_type(self):
        return self.headers.get("Content-Type")

    @property
    def detail(self):
        return self.get("detail", HTTPStatus(self.status).description)

    @property
    def status_code(self):
        return self.status

    def raise_for_status(self):
        self._response.raise_for_status()

    def __enter__(self, *args, **kwargs):
        return self._response.__enter__(*args, **kwargs)

    def __contains__(self, key):
        return key in self.data

    def __repr__(self):
        return "<{}: {} ({})>".format(
            self.__class__.__name__, self.status, self.detail
        )

    def __len__(self):
        return 200 <= self.status < 400

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)


class GraphQlResponse:
    def __init__(self, data):
        self.data = data
        self.errors = data.get("errors")

    def __len__(self):
        if self.errors:
            return 0
        return 1

    def __repr__(self):
        if self.errors:
            return "<{} errors={}>".format(
                self.__class__.__name__, self.errors[0]['message']
            )
        return "<{}>".format(self.__class__.__name__)


def fill_own_attribs(entity):
    if not entity or not entity.get("attrib"):
        return

    attributes = set(entity["ownAttrib"])

    own_attrib = {}
    entity["ownAttrib"] = own_attrib

    for key, value in entity["attrib"].items():
        if key not in attributes:
            own_attrib[key] = None
        else:
            own_attrib[key] = copy.deepcopy(value)


class ServerAPIBase(object):
    """Base handler of connection to server.

    Requires url to server which is used as base for api and graphql calls.

    Login cause that a session is used

    Args:
        base_url (str): Example: http://localhost:5000
        token (str): Access token (api key) to server.
        site_id (str): Unique name of site. Should be the same when
            connection is created from the same machine under same user.
        client_version (str): Version of client application (used in
            desktop client application).
    """

    def __init__(
        self,
        base_url,
        token=None,
        site_id=None,
        client_version=None
    ):
        if not base_url:
            raise ValueError("Invalid server URL {}".format(str(base_url)))

        base_url = base_url.rstrip("/")
        self._base_url = base_url
        self._rest_url = "{}/api".format(base_url)
        self._graphl_url = "{}/graphql".format(base_url)
        self._log = None
        self._access_token = token
        self._site_id = site_id
        self._client_version = client_version
        self._access_token_is_service = None
        self._token_is_valid = None
        self._server_available = None

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

        self._thumbnail_cache = ThumbnailCache(True)

    def get_base_url(self):
        return self._base_url

    def get_rest_url(self):
        return self._rest_url

    base_url = property(get_base_url)
    rest_url = property(get_rest_url)

    @property
    def access_token(self):
        return self._access_token

    def get_site_id(self):
        return self._site_id

    def set_site_id(self, site_id):
        if self._site_id == site_id:
            return
        self._site_id = site_id
        # Recreate session on machine id change
        if self._session is not None:
            self.close_session()
            self.create_session()

    site_id = property(get_site_id, set_site_id)

    @property
    def is_server_available(self):
        if self._server_available is None:
            response = requests.get(self._base_url)
            self._server_available = response.status_code == 200
        return self._server_available

    @property
    def has_valid_token(self):
        if self._access_token is None:
            return False

        if self._token_is_valid is None:
            self.validate_token()
        return self._token_is_valid

    def validate_server_availability(self):
        if not self.is_server_available:
            raise ServerNotReached("Server \"{}\" can't be reached".format(
                self._base_url
            ))

    def validate_token(self):
        try:
            # TODO add other possible validations
            # - existence of 'user' key in info
            # - validate that 'site_id' is in 'sites' in info
            self.get_info()
            self.get_user()
            self._token_is_valid = True

        except UnauthorizedError:
            self._token_is_valid = False
        return self._token_is_valid

    def set_token(self, token):
        self.reset_token()
        self._access_token = token
        self.get_user()

    def reset_token(self):
        self._access_token = None
        self._token_is_valid = None
        self.close_session()

    def create_session(self):
        if self._session is not None:
            raise ValueError("Session is already created.")

        # Validate token before session creation
        self.validate_token()

        session = requests.Session()
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

    def get_info(self):
        """Get information about current used api key.

        By default, the 'info' contains only 'uptime' and 'version'. With
        logged user info also contains information about user and machines on
        which was logged in.

        Todos:
            Use this method for validation of token instead of 'get_user'.

        Returns:
            Dict[str, Any]: Information from server.
        """

        response = self.get("info")
        return response.data

    def _get_user_info(self):
        if self._access_token is None:
            return None

        if self._access_token_is_service is not None:
            response = self.get("users/me")
            return response.data

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

    def get_users(self):
        # TODO how to find out if user have permission?
        users = self.get("users")
        return users.data

    def get_user(self, username=None):
        output = None
        if username is None:
            output = self._get_user_info()
        else:
            response = self.get("users/{}".format(username))
            if response.status == 200:
                output = response.data

        if output is None:
            raise UnauthorizedError("User is not authorized.")
        return output

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    def get_headers(self, content_type=None):
        if content_type is None:
            content_type = "application/json"

        headers = {
            "Content-Type": content_type,
            "x-ayon-platform": platform.system().lower(),
            "x-ayon-hostname": platform.node(),
        }
        if self._site_id is not None:
            headers["x-ayon-site-id"] = self._site_id

        if self._client_version is not None:
            headers["x-ayon-version"] = self._client_version

        if self._access_token:
            if self._access_token_is_service:
                headers["X-Api-Key"] = self._access_token
            else:
                headers["Authorization"] = "Bearer {}".format(
                    self._access_token)
        return headers

    def login(self, username, password):
        if self.has_valid_token:
            try:
                user_info = self.get_user()
            except UnauthorizedError:
                user_info = {}

            current_username = user_info.get("name")
            if current_username == username:
                self.close_session()
                self.create_session()
                return

        self.reset_token()

        self.validate_server_availability()

        response = self.post(
            "auth/login",
            name=username,
            password=password
        )
        if response.status_code != 200:
            _detail = response.data.get("detail")
            details = ""
            if _detail:
                details = " {}".format(_detail)

            raise AuthenticationError("Login failed {}".format(details))

        self._access_token = response["token"]

        if not self.has_valid_token:
            raise AuthenticationError("Invalid credentials")
        self.create_session()

    def logout(self, soft=False):
        if self._access_token:
            if not soft:
                self._logout()
            self.reset_token()

    def _logout(self):
        logout_from_server(self._base_url, self._access_token)

    def _do_rest_request(self, function, url, **kwargs):
        if self._session is None:
            if "headers" not in kwargs:
                kwargs["headers"] = self.get_headers()

            if isinstance(function, RequestType):
                function = self._base_functions_mapping[function]

        elif isinstance(function, RequestType):
            function = self._session_functions_mapping[function]

        try:
            response = function(url, **kwargs)

        except ConnectionRefusedError:
            new_response = RestApiResponse(
                None,
                {"detail": "Unable to connect the server. Connection refused"}
            )
        except requests.exceptions.ConnectionError:
            new_response = RestApiResponse(
                None,
                {"detail": "Unable to connect the server. Connection error"}
            )
        else:
            content_type = response.headers.get("Content-Type")
            if content_type == "application/json":
                try:
                    new_response = RestApiResponse(response)
                except JSONDecodeError:
                    new_response = RestApiResponse(
                        None,
                        {
                            "detail": "The response is not a JSON: {}".format(
                                response.text)
                        }
                    )

            elif content_type in ("image/jpeg", "image/png"):
                new_response = RestApiResponse(response)

            else:
                new_response = RestApiResponse(response)

        self.log.debug("Response {}".format(str(new_response)))
        return new_response

    def raw_post(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [POST] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            RequestTypes.post,
            url,
            **kwargs
        )

    def raw_put(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [PUT] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            RequestTypes.put,
            url,
            **kwargs
        )

    def raw_patch(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [PATCH] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            RequestTypes.patch,
            url,
            **kwargs
        )

    def raw_get(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [GET] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            RequestTypes.get,
            url,
            **kwargs
        )

    def raw_delete(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [DELETE] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            RequestTypes.delete,
            url,
            **kwargs
        )

    def post(self, entrypoint, **kwargs):
        return self.raw_post(entrypoint, json=kwargs)

    def put(self, entrypoint, **kwargs):
        return self.raw_put(entrypoint, json=kwargs)

    def patch(self, entrypoint, **kwargs):
        return self.raw_patch(entrypoint, json=kwargs)

    def get(self, entrypoint, **kwargs):
        return self.raw_get(entrypoint, params=kwargs)

    def delete(self, entrypoint, **kwargs):
        return self.raw_delete(entrypoint, params=kwargs)

    def get_event(self, event_id):
        """Receive full event data by id.

        Events received using event server do not contain full information. To
        get the full event information is required to receive it explicitly.

        Args:
            event_id (str): Id of event.

        Returns:
            Dict[str, Any]: Full event data.
        """

        response = self.get("events/{}".format(event_id))
        response.raise_for_status()
        return response.data

    def update_event(
        self,
        event_id,
        sender=None,
        project_name=None,
        status=None,
        description=None,
        summary=None,
        payload=None
    ):
        kwargs = {}
        for key, value in (
            ("sender", sender),
            ("projectName", project_name),
            ("status", status),
            ("description", description),
            ("summary", summary),
            ("payload", payload),
        ):
            if value is not None:
                kwargs[key] = value
        response = self.patch(
            "events/{}".format(event_id),
            **kwargs
        )
        response.raise_for_status()

    def dispatch_event(
        self,
        topic,
        sender=None,
        event_hash=None,
        project_name=None,
        username=None,
        dependencies=None,
        description=None,
        summary=None,
        payload=None,
        finished=True,
        store=True,
    ):
        if summary is None:
            summary = {}
        if payload is None:
            payload = {}
        event_data = {
            "topic": topic,
            "sender": sender,
            "hash": event_hash,
            "project": project_name,
            "user": username,
            "dependencies": dependencies,
            "description": description,
            "summary": summary,
            "payload": payload,
            "finished": finished,
            "store": store,
        }
        if self.post("events", **event_data):
            self.log.debug("Dispatched event {}".format(topic))
            return True
        self.log.error("Unable to dispatch event {}".format(topic))
        return False

    def enroll_event_job(
        self,
        source_topic,
        target_topic,
        sender,
        description=None,
        sequential=None
    ):
        """Enroll job based on events.

        Args:
            source_topic (str): Topic
        """

        kwargs = {
            "sourceTopic": source_topic,
            "targetTopic": target_topic,
            "sender": sender,
        }
        if sequential is not None:
            kwargs["sequential"] = sequential
        if description is not None:
            kwargs["description"] = description
        response = self.post("enroll", **kwargs)
        if response.status_code == 204:
            return None
        elif response.status_code >= 400:
            self.log.error(response.text)
            return None

        return response.data

    def _download_file(self, url, filepath, chunk_size, progress):
        dst_directory = os.path.dirname(filepath)
        if not os.path.exists(dst_directory):
            os.makedirs(dst_directory)

        kwargs = {"stream": True}
        if self._session is None:
            kwargs["headers"] = self.get_headers()
            get_func = self._base_functions_mapping[RequestTypes.get]
        else:
            get_func = self._session_functions_mapping[RequestTypes.get]

        with open(filepath, "wb") as f_stream:
            with get_func(url, **kwargs) as response:
                response.raise_for_status()
                progress.set_content_size(response.headers["Content-length"])
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f_stream.write(chunk)
                    progress.add_transferred_chunk(len(chunk))

    def download_file(self, endpoint, filepath, chunk_size=None, progress=None):
        """Download file from AYON server.

        Endpoint can be full url (must start with 'base_url' of api object).

        Progress object can be used to track download. Can be used when
        download happens in thread and other thread want to catch changes over
        time.

        Args:
            endpoint (str): Endpoint or URL to file that should be downloaded.
            filepath (str): Path where file will be downloaded.
            chunk_size (int): Size of chunks that are received in single loop.
            progress (TransferProgress): Object that gives ability to track
                download progress.
        """

        if not chunk_size:
            # 1 MB chunk by default
            chunk_size = 1024 * 1024

        if endpoint.startswith(self._base_url):
            url = endpoint
        else:
            endpoint = endpoint.lstrip("/").rstrip("/")
            url = "{}/{}".format(self._rest_url, endpoint)

        # Create dummy object so the function does not have to check
        #   'progress' variable everywhere
        if progress is None:
            progress = TransferProgress()

        progress.set_source_url(url)
        progress.set_destination_url(filepath)
        progress.set_started()
        try:
            self._download_file(url, filepath, chunk_size, progress)

        except Exception as exc:
            progress.set_failed(str(exc))
            raise

        finally:
            progress.set_transfer_done()

    def _upload_file(self, url, filepath, progress):
        kwargs = {}
        if self._session is None:
            kwargs["headers"] = self.get_headers()
            post_func = self._base_functions_mapping[RequestTypes.post]
        else:
            post_func = self._session_functions_mapping[RequestTypes.post]

        with open(filepath, "rb") as stream:
            stream.seek(0, io.SEEK_END)
            size = stream.tell()
            stream.seek(0)
            progress.set_content_size(size)
            response = post_func(url, data=stream, **kwargs)
        response.raise_for_status()
        progress.set_transferred_size(size)

    def upload_file(self, endpoint, filepath, progress=None):
        """Upload file to server.

        Todos:
            Uploading with more detailed progress.

        Args:
            endpoint (str): Endpoint or url where file will be uploaded.
            filepath (str): Source filepath.
            progress (TransferProgress): Object that gives ability to track
                upload progress.
        """

        if endpoint.startswith(self._base_url):
            url = endpoint
        else:
            endpoint = endpoint.lstrip("/").rstrip("/")
            url = "{}/{}".format(self._rest_url, endpoint)

        # Create dummy object so the function does not have to check
        #   'progress' variable everywhere
        if progress is None:
            progress = TransferProgress()

        progress.set_source_url(filepath)
        progress.set_destination_url(url)
        progress.set_started()

        try:
            self._upload_file(url, filepath, progress)

        except Exception as exc:
            progress.set_failed(str(exc))
            raise

        finally:
            progress.set_transfer_done()

    def trigger_server_restart(self):
        result = self.post("system/restart")
        if result.status_code != 204:
            # TODO add better exception
            raise ValueError("Failed to restart server")

    def query_graphql(self, query, variables=None):
        data = {"query": query, "variables": variables or {}}
        response = self._do_rest_request(
            RequestTypes.post,
            self._graphl_url,
            json=data
        )
        return GraphQlResponse(response)

    def get_graphql_schema(self):
        return self.query_graphql(INTROSPECTION_QUERY).data

    def get_server_schema(self):
        """Get server schema with info, url paths, components etc.

        Todo:
            Cache schema - How to find out it is outdated?

        Returns:
            Dict[str, Any]: Full server schema.
        """

        url = "{}/openapi.json".format(self._base_url)
        response = self._do_rest_request(RequestTypes.get, url)
        if response:
            return response.data
        return None

    def get_schemas(self):
        """Get components schema.

        Name of components does not match entity type names e.g. 'project' is
        under 'ProjectModel'. We should find out some mapping. Also there
        are properties which don't have information about reference to object
        e.g. 'config' has just object definition without reference schema.

        Returns:
            Dict[str, Any]: Component schemas.
        """

        server_schema = self.get_server_schema()
        return server_schema["components"]["schemas"]

    def get_attributes_schema(self, use_cache=True):
        if not use_cache:
            self.reset_attributes_schema()

        if self._attributes_schema is None:
            result = self.get("attributes")
            if result.status_code != 200:
                raise UnauthorizedError(
                    "User must be authorized to receive attributes"
                )
            self._attributes_schema = result.data
        return copy.deepcopy(self._attributes_schema)

    def reset_attributes_schema(self):
        self._attributes_schema = None
        self._entity_type_attributes_cache = {}

    def set_attribute_config(
        self, attribute_name, data, scope, position=None, builtin=False
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
            "attributes/{}".format(attribute_name),
            data=data,
            scope=scope,
            position=position,
            builtin=builtin
        )
        if response.status_code != 204:
            # TODO raise different exception
            raise ValueError(
                "Attribute \"{}\" was not created/updated. {}".format(
                    attribute_name, response.detail
                )
            )

        self.reset_attributes_schema()

    def remove_attribute_config(self, attribute_name):
        response = self.delete("attributes/{}".format(attribute_name))
        if response.status_code != 204:
            # TODO raise different exception
            raise ValueError(
                "Attribute \"{}\" was not created/updated. {}".format(
                    attribute_name, response.detail
                )
            )

        self.reset_attributes_schema()

    def get_attributes_for_type(self, entity_type):
        """Get attribute schemas available for an entity type.

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
            Dict[str, Dict[str, Any]]: Attribute schemas that are available
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

    def get_default_fields_for_type(self, entity_type):
        attributes = self.get_attributes_for_type(entity_type)
        if entity_type == "project":
            return DEFAULT_PROJECT_FIELDS | {
                "attrib.{}".format(attr)
                for attr in attributes
            }

        if entity_type == "folder":
            return DEFAULT_FOLDER_FIELDS | {
                "attrib.{}".format(attr)
                for attr in attributes
            }

        if entity_type == "task":
            return DEFAULT_TASK_FIELDS | {
                "attrib.{}".format(attr)
                for attr in attributes
            }

        if entity_type == "subset":
            return DEFAULT_SUBSET_FIELDS | {
                "attrib.{}".format(attr)
                for attr in attributes
            }

        if entity_type == "version":
            return DEFAULT_VERSION_FIELDS | {
                "attrib.{}".format(attr)
                for attr in attributes
            }

        if entity_type == "representation":
            return (
                DEFAULT_REPRESENTATION_FIELDS
                | REPRESENTATION_FILES_FIELDS
                | {
                    "attrib.{}".format(attr)
                    for attr in attributes
                }
            )

    def get_addons_info(self, details=True):
        """Get information about addons available on server.

        Args:
            details (bool): Detailed data with information how to get client
                code.
        """

        endpoint = "addons"
        if details:
            endpoint += "?details=1"
        response = self.get(endpoint)
        response.raise_for_status()
        return response.data

    def download_addon_private_file(
        self,
        addon_name,
        addon_version,
        filename,
        destination_dir,
        destination_filename=None,
        chunk_size=None,
        progress=None,
    ):
        """Download a file from addon private files.

        This method requires to have authorized token available. Private files
        are not under '/api' restpoint.

        Args:
            addon_name (str): Addon name.
            addon_version (str): Addon version.
            filename (str): Filename in private folder on server.
            destination_dir (str): Where the file should be downloaded.
            destination_filename (str): Name of destination filename. Source
                filename is used if not passed.
            chunk_size (int): Download chunk size.
            progress (TransferProgress): Object that gives ability to track
                download progress.

        Returns:
            str: Filepath to downloaded file.
        """

        if not destination_filename:
            destination_filename = filename
        dst_filepath = os.path.join(destination_dir, destination_filename)
        # Filename can contain "subfolders"
        dst_dirpath = os.path.dirname(dst_filepath)
        if not os.path.exists(dst_dirpath):
            os.makedirs(dst_dirpath)

        url = "{}/addons/{}/{}/private/{}".format(
            self._base_url,
            addon_name,
            addon_version,
            filename
        )
        self.download_file(
            url, dst_filepath, chunk_size=chunk_size, progress=progress
        )
        return dst_filepath

    def get_dependencies_info(self):
        result = self.get("dependencies")
        return result.data

    def update_dependency_info(
        self,
        name,
        platform_name,
        size,
        checksum,
        checksum_algorithm=None,
        supported_addons=None,
        python_modules=None,
        sources=None
    ):
        """Update or create dependency package infor by it's identifiers.

        The endpoint can be used to create or update dependency package.

        Args:
            name (str): Name of dependency package.
            platform_name (Literal["windows", "linux", "darwin"]): Platform for
                which is dependency package targeted.
            size (int): Size of dependency package in bytes.
            checksum (str): Checksum of archive file where dependecies are.
            checksum_algorithm (str): Algorithm used to calculate checksum.
                By default, is used 'md5' (defined by server).
            supported_addons (Dict[str, str]): Name of addons for which was the
                package created ('{"<addon name>": "<addon version>", ...}').
            python_modules (Dict[str, str]): Python modules in dependencies
                package ('{"<module name>": "<module version>", ...}').
            sources (List[Dict[str, Any]]): Information about sources where
                dependency package is available.
        """

        kwargs = {
            key: value
            for key, value in (
                ("checksumAlgorithm", checksum_algorithm),
                ("supportedAddons", supported_addons),
                ("pythonModules", python_modules),
                ("sources", sources),
            )
            if value
        }

        response = self.put(
            "dependencies",
            name=name,
            platform=platform_name,
            size=size,
            checksum=checksum,
            **kwargs
        )
        if response.status not in (200, 201):
            raise ServerError("Failed to create/update dependency")
        return response.data

    def download_dependency_package(
        self,
        package_name,
        dst_directory,
        filename,
        platform_name=None,
        chunk_size=None,
        progress=None,
    ):
        """Download dependency package from server.

        This method requires to have authorized token available. The package is
        only downloaded.

        Args:
            package_name (str): Name of package to download.
            dst_directory (str): Where the file should be downloaded.
            filename (str): Name of destination filename.
            platform_name (str): Name of platform for which the dependency
                package is targetter. Default value is current platform.
            chunk_size (int): Download chunk size.
            progress (TransferProgress): Object that gives ability to track
                download progress.

        Returns:
            str: Filepath to downloaded file.
       """
        if platform_name is None:
            platform_name = platform.system().lower()

        package_filepath = os.path.join(dst_directory, filename)
        self.download_file(
            "dependencies/{}/{}".format(package_name, platform_name),
            package_filepath,
            chunk_size=chunk_size,
            progress=progress
        )
        return package_filepath

    def upload_dependency_package(
        self, filepath, package_name, platform_name=None, progress=None
    ):
        if platform_name is None:
            platform_name = platform.system().lower()

        self.upload_file(
            "dependencies/{}/{}".format(package_name, platform_name),
            filepath,
            progress=progress
        )

    def delete_dependency_package(self, package_name, platform_name=None):
        if platform_name is None:
            platform_name = platform.system().lower()

        response = self.delete(
            "dependencies/{}/{}".format(package_name, platform_name),
        )
        if response.status != 200:
            raise ServerError("Failed to delete dependency file")
        return response.data

    # Anatomy presets
    def get_project_anatomy_presets(self, add_default=True):
        result = self.get("anatomy/presets")
        presets = result.data
        if add_default:
            presets.append(self.get_project_anatomy_preset())
        return presets

    def get_project_anatomy_preset(self, preset_name=None):
        if preset_name is None:
            preset_name = "_"
        result = self.get("anatomy/presets/{}".format(preset_name))
        return result.data

    def get_full_production_settings(self):
        # TODO raise error if status is not 200
        response = self.get("settings/production")
        if response.status == 200:
            return response.data
        return None

    def get_production_settings(self):
        return self.get_full_production_settings()["settings"]

    # Settings getters
    def get_full_project_settings(self, project_name):
        result = self.get("projects/{}/settings".format(project_name))
        if result.status == 200:
            return result.data
        return None

    def get_project_settings(self, project_name=None):
        if project_name is None:
            return self.get_production_settings()

        full_settings = self.get_full_project_settings(project_name)
        if full_settings is None:
            return full_settings
        return full_settings["settings"]

    def get_addon_studio_settings(self, addon_name, addon_version):
        result = self.get(
            "addons/{}/{}/settings".format(addon_name, addon_version)
        )
        result.raise_for_status()
        return result.data

    def get_addon_project_settings(
        self, addon_name, addon_version, project_name
    ):
        result = self.get(
            "addons/{}/{}/settings/{}".format(
                addon_name, addon_version, project_name
            )
        )
        result.raise_for_status()
        return result.data

    def get_addon_settings(self, addon_name, addon_version, project_name=None):
        if project_name is None:
            return self.get_addon_studio_settings(addon_name, addon_version)
        return self.get_addon_project_settings(
            addon_name, addon_version, project_name
        )

    # Entity getters
    def get_rest_project(self, project_name):
        """Receive project by name.

        This call returns project with anatomy data.

        Args:
            project_name (str): Name of project.

        Returns:
            Union[Dict[str, Any], None]: Project entity data or 'None' if
                project was not found.
        """

        response = self.get("projects/{}".format(project_name))
        if response.status == 200:
            return response.data
        return None

    def get_rest_projects(self, active=True, library=None):
        """Receive available project entity data.

        User must be logged in.

        Args:
            active (bool): Filter active/inactive projects. Both are returned
                if 'None' is passed.
            library (bool): Filter standard/library projects. Both are
                returned if 'None' is passed.

        Returns:
            Generator[Dict[str, Any]]: Available projects.
        """

        for project_name in self.get_project_names(active, library):
            project = self.get_rest_project(project_name)
            if project:
                yield project

    def get_rest_entity_by_id(self, project_name, entity_type, entity_id):
        entity_endpoint = "{}s".format(entity_type)
        response = self.get("projects/{}/{}/{}".format(
            project_name, entity_endpoint, entity_id
        ))
        if response.status == 200:
            return response.data
        return None

    def get_rest_folder(self, project_name, folder_id):
        return self.get_rest_entity_by_id(project_name, "folder", folder_id)

    def get_rest_task(self, project_name, task_id):
        return self.get_rest_entity_by_id(project_name, "task", task_id)

    def get_rest_subset(self, project_name, subset_id):
        return self.get_rest_entity_by_id(project_name, "subset", subset_id)

    def get_rest_version(self, project_name, version_id):
        return self.get_rest_entity_by_id(project_name, "version", version_id)

    def get_rest_representation(self, project_name, representation_id):
        return self.get_rest_entity_by_id(
            project_name, "representation", representation_id
        )

    def get_project_names(self, active=True, library=None):
        """Receive available project names.

        User must be logged in.

        Args:
            active (bool): Filter active/inactive projects. Both are returned
                if 'None' is passed.
            library (bool): Filter standard/library projects. Both are
                returned if 'None' is passed.

        Returns:
            List[str]: List of available project names.
        """

        query_keys = {}
        if active is not None:
            query_keys["active"] = "true" if active else "false"

        if library is not None:
            query_keys["library"] = "true" if active else "false"
        query = ""
        if query_keys:
            query = "?{}".format(",".join([
                "{}={}".format(key, value)
                for key, value in query_keys.items()
            ]))

        response = self.get("projects{}".format(query), **query_keys)
        response.raise_for_status()
        data = response.data
        project_names = []
        if data:
            for project in data["projects"]:
                project_names.append(project["name"])
        return project_names

    def get_projects(
        self, active=True, library=None, fields=None, own_attributes=False
    ):
        """Get projects.

        Args:
            active (Union[bool, None]): Filter active or inactive projects.
                Filter is disabled when 'None' is passed.
            library (Union[bool, None]): Filter library projects. Filter is
                disabled when 'None' is passed.
            fields (Union[Iterable[str], None]): fields to be queried
                for project.
            own_attributes (bool): Attribute values that are not explicitly set
                on entity will have 'None' value.

        Returns:
            Generator[Dict[str, Any]]: Queried projects.
        """

        if fields is None:
            use_rest = True
        else:
            use_rest = False
            fields = set(fields)
            if own_attributes:
                fields.add("ownAttrib")
            for field in fields:
                if field.startswith("config"):
                    use_rest = True
                    break

        if use_rest:
            for project in self.get_rest_projects(active, library):
                if own_attributes:
                    fill_own_attribs(project)
                yield project

        else:
            query = projects_graphql_query(fields)
            for parsed_data in query.continuous_query(self):
                for project in parsed_data["projects"]:
                    if own_attributes:
                        fill_own_attribs(project)
                    yield project

    def get_project(self, project_name, fields=None, own_attributes=False):
        """Get project.

        Args:
            project_name (str): Name of project.
            fields (Union[Iterable[str], None]): fields to be queried
                for project.
            own_attributes (bool): Attribute values that are not explicitly set
                on entity will have 'None' value.

        Returns:
            Union[Dict[str, Any], None]: Project entity data or None
                if project was not found.
        """

        use_rest = True
        if fields is not None:
            use_rest = False
            _fields = set()
            for field in fields:
                if field.startswith("config") or field == "data":
                    use_rest = True
                    break
                _fields.add(field)

            fields = _fields

        if use_rest:
            project = self.get_rest_project(project_name)
            if own_attributes:
                fill_own_attribs(project)
            return project

        if own_attributes:
            field.add("ownAttrib")
        query = project_graphql_query(fields)
        query.set_variable_value("projectName", project_name)

        parsed_data = query.query(self)

        project = parsed_data["project"]
        if project is not None:
            project["name"] = project_name
            if own_attributes:
                fill_own_attribs(project)
        return project

    def get_folders(
        self,
        project_name,
        folder_ids=None,
        folder_paths=None,
        folder_names=None,
        parent_ids=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        """Query folders from server.

        Todos:
            Folder name won't be unique identifier so we should add folder path
                filtering.

        Notes:
            Filter 'active' don't have direct filter in GraphQl.

        Args:
            folder_ids (Iterable[str]): Folder ids to filter.
            folder_paths (Iterable[str]): Folder paths used for filtering.
            folder_names (Iterable[str]): Folder names used for filtering.
            parent_ids (Iterable[str]): Ids of folder parents. Use 'None'
                if folder is direct child of project.
            active (Union[bool, None]): Filter active/inactive folders.
                Both are returned if is set to None.
            fields (Union[Iterable[str], None]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.

        Returns:
            Generator[dict[str, Any]]: Queried folder entities.
        """

        if not project_name:
            return

        filters = {
            "projectName": project_name
        }
        if folder_ids is not None:
            folder_ids = set(folder_ids)
            if not folder_ids:
                return
            filters["folderIds"] = list(folder_ids)

        if folder_paths is not None:
            folder_paths = set(folder_paths)
            if not folder_paths:
                return
            filters["folderPaths"] = list(folder_paths)

        if folder_names is not None:
            folder_names = set(folder_names)
            if not folder_names:
                return
            filters["folderNames"] = list(folder_names)

        if parent_ids is not None:
            parent_ids = set(parent_ids)
            if not parent_ids:
                return
            if None in parent_ids:
                # Replace 'None' with '"root"' which is used during GraphQl
                #   query for parent ids filter for folders without folder
                #   parent
                parent_ids.remove(None)
                parent_ids.add("root")

            if project_name in parent_ids:
                # Replace project name with '"root"' which is used during
                #   GraphQl query for parent ids filter for folders without
                #   folder parent
                parent_ids.remove(project_name)
                parent_ids.add("root")

            filters["parentFolderIds"] = list(parent_ids)

        if fields:
            fields = set(fields)
        else:
            fields = self.get_default_fields_for_type("folder")

        use_rest = False
        if "data" in fields:
            use_rest = True
            fields = {"id"}

        if active is not None:
            fields.add("active")

        if own_attributes and not use_rest:
            fields.add("ownAttrib")

        query = folders_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for folder in parsed_data["project"]["folders"]:
                if active is not None and active is not folder["active"]:
                    continue

                if use_rest:
                    folder = self.get_rest_folder(project_name, folder["id"])

                if own_attributes:
                    fill_own_attribs(folder)
                yield folder

    def get_tasks(
        self,
        project_name,
        task_ids=None,
        task_names=None,
        task_types=None,
        folder_ids=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        if not project_name:
            return

        filters = {
            "projectName": project_name
        }

        if task_ids is not None:
            task_ids = set(task_ids)
            if not task_ids:
                return
            filters["taskIds"] = list(task_ids)

        if task_names is not None:
            task_names = set(task_names)
            if not task_names:
                return
            filters["taskNames"] = list(task_names)

        if task_types is not None:
            task_types = set(task_types)
            if not task_types:
                return
            filters["taskTypes"] = list(task_types)

        if folder_ids is not None:
            folder_ids = set(folder_ids)
            if not folder_ids:
                return
            filters["folderIds"] = list(folder_ids)

        if not fields:
            fields = self.get_default_fields_for_type("task")

        fields = set(fields)

        use_rest = False
        if "data" in fields:
            use_rest = True
            fields = {"id"}

        if active is not None:
            fields.add("active")

        if own_attributes:
            fields.add("ownAttrib")

        query = tasks_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for task in parsed_data["project"]["tasks"]:
                if active is not None and active is not task["active"]:
                    continue

                if use_rest:
                    task = self.get_rest_task(project_name, task["id"])

                if own_attributes:
                    fill_own_attribs(task)
                yield task

    def get_task_by_name(
        self,
        project_name,
        folder_id,
        task_name,
        fields=None,
        own_attributes=False
    ):
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
        project_name,
        task_id,
        fields=None,
        own_attributes=False
    ):
        for task in self.get_tasks(
            project_name,
            task_ids=[task_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        ):
            return task
        return None


    def get_folder_by_id(
        self,
        project_name,
        folder_id,
        fields=None,
        own_attributes=False
    ):
        """Receive folder data by it's id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            folder_id (str): Folder's id.
            fields (Iterable[str]): Fields that should be returned. All fields
                are returned if 'None' is passed.

        Returns:
            Union[dict, None]: Folder entity data or None if was not found.
        """

        folders = self.get_folders(
            project_name,
            folder_ids=[folder_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for folder in folders:
            return folder
        return None

    def get_folder_by_path(
        self,
        project_name,
        folder_path,
        fields=None,
        own_attributes=False
    ):
        folders = self.get_folders(
            project_name,
            folder_paths=[folder_path],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for folder in folders:
            return folder
        return None

    def get_folder_by_name(
        self,
        project_name,
        folder_name,
        fields=None,
        own_attributes=False
    ):
        folders = self.get_folders(
            project_name,
            folder_names=[folder_name],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for folder in folders:
            return folder
        return None

    def get_folder_ids_with_subsets(self, project_name, folder_ids=None):
        if folder_ids is not None:
            folder_ids = set(folder_ids)
            if not folder_ids:
                return set()

        query = folders_graphql_query({"id"})
        query.set_variable_value("projectName", project_name)
        query.set_variable_value("folderHasSubsets", True)
        if folder_ids:
            query.set_variable_value("folderIds", list(folder_ids))

        parsed_data = query.query(self)
        folders = parsed_data["project"]["folders"]
        return {
            folder["id"]
            for folder in folders
        }

    def _filter_subset(
        self, project_name, subset, active, own_attributes, use_rest
    ):
        if active is not None and subset["active"] is not active:
            return None

        if use_rest:
            subset = self.get_rest_subset(project_name, subset["id"])

        if own_attributes:
            fill_own_attribs(subset)

        return subset

    def get_subsets(
        self,
        project_name,
        subset_ids=None,
        subset_names=None,
        folder_ids=None,
        names_by_folder_ids=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        if not project_name:
            return

        if subset_ids is not None:
            subset_ids = set(subset_ids)
            if not subset_ids:
                return

        filter_subset_names = None
        if subset_names is not None:
            filter_subset_names = set(subset_names)
            if not filter_subset_names:
                return

        filter_folder_ids = None
        if folder_ids is not None:
            filter_folder_ids = set(folder_ids)
            if not filter_folder_ids:
                return

        # This will disable 'folder_ids' and 'subset_names' filters
        #   - maybe could be enhanced in future?
        if names_by_folder_ids is not None:
            filter_subset_names = set()
            filter_folder_ids = set()

            for folder_id, names in names_by_folder_ids.items():
                if folder_id and names:
                    filter_folder_ids.add(folder_id)
                    filter_subset_names |= set(names)

            if not filter_subset_names or not filter_folder_ids:
                return

        # Convert fields and add minimum required fields
        if fields:
            fields = set(fields) | {"id"}
        else:
            fields = self.get_default_fields_for_type("subset")

        use_rest = False
        if "data" in fields:
            use_rest = True
            fields = {"id"}

        if active is not None:
            fields.add("active")

        if own_attributes:
            fields.add("ownAttrib")

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

        if subset_ids:
            filters["subsetIds"] = list(subset_ids)

        if filter_subset_names:
            filters["subsetNames"] = list(filter_subset_names)

        query = subsets_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        parsed_data = query.query(self)

        subsets = parsed_data.get("project", {}).get("subsets", [])
        # Filter subsets by 'names_by_folder_ids'
        if names_by_folder_ids:
            subsets_by_folder_id = collections.defaultdict(list)
            for subset in subsets:
                filtered_subset = self._filter_subset(
                    project_name, subset, active, own_attributes, use_rest
                )
                if filtered_subset is not None:
                    folder_id = filtered_subset["folderId"]
                    subsets_by_folder_id[folder_id].append(filtered_subset)

            for folder_id, names in names_by_folder_ids.items():
                for folder_subset in subsets_by_folder_id[folder_id]:
                    if folder_subset["name"] in names:
                        yield folder_subset

        else:
            for subset in subsets:
                filtered_subset = self._filter_subset(
                    project_name, subset, active, own_attributes, use_rest
                )
                if filtered_subset is not None:
                    yield filtered_subset


    def get_subset_by_id(
        self,
        project_name,
        subset_id,
        fields=None,
        own_attributes=False
    ):
        subsets = self.get_subsets(
            project_name,
            subset_ids=[subset_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for subset in subsets:
            return subset
        return None

    def get_subset_by_name(
        self,
        project_name,
        subset_name,
        folder_id,
        fields=None,
        own_attributes=False
    ):
        subsets = self.get_subsets(
            project_name,
            subset_names=[subset_name],
            folder_ids=[folder_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for subset in subsets:
            return subset
        return None

    def get_subset_families(self, project_name, subset_ids=None):
        if subset_ids is not None:
            subsets = self.get_subsets(
                project_name,
                subset_ids=subset_ids,
                fields=["data.family"],
                active=None,
            )
            return {
                subset["data"]["family"]
                for subset in subsets
            }

        query = GraphQlQuery("SubsetFamilies")
        project_name_var = query.add_variable(
            "projectName", "String!", project_name
        )
        project_query = query.add_field("project")
        project_query.set_filter("name", project_name_var)
        project_query.add_field("subsetFamilies")

        parsed_data = query.query(self)

        return set(parsed_data.get("project", {}).get("subsetFamilies", []))

    def get_versions(
        self,
        project_name,
        version_ids=None,
        subset_ids=None,
        versions=None,
        hero=True,
        standard=True,
        latest=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        """Get version entities based on passed filters from server.

        Args:
            project_name (str): Name of project where to look for versions.
            version_ids (Iterable[str]): Version ids used for version
                filtering.
            subset_ids (Iterable[str]): Subset ids used for version filtering.
            versions (Iterable[int]): Versions we're interested in.
            hero (bool): Receive also hero versions when set to true.
            standard (bool): Receive versions which are not hero when
                set to true.
            latest (bool): Return only latest version of standard versions.
                This can be combined only with 'standard' attribute
                set to True.
            fields (Union[Iterable[str], None]): Fields to be queried
                for version. All possible folder fields are returned
                if 'None' is passed.

        Returns:
            Generator[Dict[str, Any]]: Queried version entities.
        """

        if not fields:
            fields = self.get_default_fields_for_type("version")
        fields = set(fields)

        if active is not None:
            fields.add("active")

        # Make sure fields have minimum required fields
        fields |= {"id", "version"}

        use_rest = False
        if "data" in fields:
            use_rest = True
            fields = {"id"}

        if own_attributes:
            fields.add("ownAttrib")

        filters = {
            "projectName": project_name
        }
        if version_ids is not None:
            version_ids = set(version_ids)
            if not version_ids:
                return
            filters["versionIds"] = list(version_ids)

        if subset_ids is not None:
            subset_ids = set(subset_ids)
            if not subset_ids:
                return
            filters["subsetIds"] = list(subset_ids)

        # TODO versions can't be used as fitler at this moment!
        if versions is not None:
            versions = set(versions)
            if not versions:
                return
            filters["versions"] = list(versions)

        if not hero and not standard:
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

                    if use_rest:
                        version = self.get_rest_version(
                            project_name, version["id"]
                        )

                    if own_attributes:
                        fill_own_attribs(version)

                    yield version

    def get_version_by_id(
        self,
        project_name,
        version_id,
        fields=None,
        own_attributes=False
    ):
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
        project_name,
        version,
        subset_id,
        fields=None,
        own_attributes=False
    ):
        versions = self.get_versions(
            project_name,
            subset_ids=[subset_id],
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
        project_name,
        version_id,
        fields=None,
        own_attributes=False
    ):
        versions = self.get_hero_versions(
            project_name,
            version_ids=[version_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_version_by_subset_id(
        self,
        project_name,
        subset_id,
        fields=None,
        own_attributes=False
    ):
        versions = self.get_hero_versions(
            project_name,
            subset_ids=[subset_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_versions(
        self,
        project_name,
        subset_ids=None,
        version_ids=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        return self.get_versions(
            project_name,
            version_ids=version_ids,
            subset_ids=subset_ids,
            hero=True,
            standard=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def get_last_versions(
        self,
        project_name,
        subset_ids,
        active=True,
        fields=None,
        own_attributes=False
    ):
        versions = self.get_versions(
            project_name,
            subset_ids=subset_ids,
            latest=True,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        return {
            version["parent"]: version
            for version in versions
        }

    def get_last_version_by_subset_id(
        self,
        project_name,
        subset_id,
        active=True,
        fields=None,
        own_attributes=False
    ):
        versions = self.get_versions(
            project_name,
            subset_ids=[subset_id],
            latest=True,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_last_version_by_subset_name(
        self,
        project_name,
        subset_name,
        folder_id,
        active=True,
        fields=None,
        own_attributes=False
    ):
        if not folder_id:
            return None

        subset = self.get_subset_by_name(
            project_name, subset_name, folder_id, fields=["_id"]
        )
        if not subset:
            return None
        return self.get_last_version_by_subset_id(
            project_name,
            subset["id"],
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def version_is_latest(self, project_name, version_id):
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
        subset_query = version_query.add_field("subset")
        latest_version_query = subset_query.add_field("latestVersion")
        latest_version_query.add_field("id")

        parsed_data = query.query(self)
        latest_version = (
            parsed_data["project"]["version"]["subset"]["latestVersion"]
        )
        return latest_version["id"] == version_id

    def get_representations(
        self,
        project_name,
        representation_ids=None,
        representation_names=None,
        version_ids=None,
        names_by_version_ids=None,
        active=True,
        fields=None,
        own_attributes=False
    ):
        """Get version entities based on passed filters from server.

        Todo:
            Add separated function for 'names_by_version_ids' filtering.
                Because can't be combined with others.

        Args:
            project_name (str): Name of project where to look for versions.
            representation_ids (Iterable[str]): Representaion ids used for
                representation filtering.
            representation_names (Iterable[str]): Representation names used for
                representation filtering.
            version_ids (Iterable[str]): Version ids used for
                representation filtering. Versions are parents of
                    representations.
            names_by_version_ids (bool): Find representations by names and
                version ids. This filter discard all other filters.
            active (bool): Receive active/inactive representaions. All are
                returned when 'None' is passed.
            fields (Union[Iterable[str], None]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.

        Returns:
            Generator[Dict[str, Any]]: Queried representation entities.
        """

        if not fields:
            fields = self.get_default_fields_for_type("representation")
        fields = set(fields)

        use_rest = False
        if "data" in fields:
            use_rest = True
            fields = {"id"}

        if active is not None:
            fields.add("active")

        if own_attributes:
            fields.add("ownAttrib")

        filters = {
            "projectName": project_name
        }

        if representation_ids is not None:
            representation_ids = set(representation_ids)
            if not representation_ids:
                return
            filters["representationIds"] = list(representation_ids)

        version_ids_filter = None
        representaion_names_filter = None
        if names_by_version_ids is not None:
            version_ids_filter = set()
            representaion_names_filter = set()
            for version_id, names in names_by_version_ids.items():
                version_ids_filter.add(version_id)
                representaion_names_filter |= set(names)

            if not version_ids_filter or not representaion_names_filter:
                return

        else:
            if representation_names is not None:
                representaion_names_filter = set(representation_names)
                if not representaion_names_filter:
                    return

            if version_ids is not None:
                version_ids_filter = set(version_ids)
                if not version_ids_filter:
                    return

        if version_ids_filter:
            filters["versionIds"] = list(version_ids_filter)

        if representaion_names_filter:
            filters["representationNames"] = list(representaion_names_filter)

        query = representations_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for repre in parsed_data["project"]["representations"]:
                if active is not None and active is not repre["active"]:
                    continue

                if use_rest:
                    repre = self.get_rest_representation(
                        project_name, repre["id"]
                    )

                if "context" in repre:
                    orig_context = repre["context"]
                    context = {}
                    if orig_context and orig_context != "null":
                        context = json.loads(orig_context)
                    repre["context"] = context

                if own_attributes:
                    fill_own_attribs(repre)
                yield repre

    def get_representation_by_id(
        self,
        project_name,
        representation_id,
        fields=None,
        own_attributes=False
    ):
        representations = self.get_representations(
            project_name,
            representation_ids=[representation_id],
            active=None,
            fields=fields,
        )
        for representation in representations:
            return representation
        return None

    def get_representation_by_name(
        self,
        project_name,
        representation_name,
        version_id,
        fields=None,
        own_attributes=False
    ):
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

    def get_representation_parents(self, project_name, representation):
        if not representation:
            return None

        repre_id = representation["_id"]
        parents_by_repre_id = self.get_representations_parents(
            project_name, [representation]
        )
        return parents_by_repre_id[repre_id]

    def get_representations_parents(self, project_name, representation_ids):
        if not representation_ids:
            return {}

        project = self.get_project(project_name)
        repre_ids = set(representation_ids)
        output = {
            repre_id: (None, None, None, None)
            for repre_id in representation_ids
        }

        version_fields = self.get_default_fields_for_type("version")
        subset_fields = self.get_default_fields_for_type("subset")
        folder_fields = self.get_default_fields_for_type("folder")

        query = representations_parents_qraphql_query(
            version_fields, subset_fields, folder_fields
        )
        query.set_variable_value("projectName", project_name)
        query.set_variable_value("representationIds", list(repre_ids))

        parsed_data = query.query(self)
        for repre in parsed_data["project"]["representations"]:
            repre_id = repre["id"]
            version = repre.pop("version")
            subset = version.pop("subset")
            folder = subset.pop("folder")
            output[repre_id] = (version, subset, folder, project)

        return output

    def get_workfiles_info(
        self,
        project_name,
        workfile_ids=None,
        task_ids=None,
        paths=None,
        fields=None,
        own_attributes=False
    ):
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

        if workfile_ids is not None:
            workfile_ids = set(workfile_ids)
            if not workfile_ids:
                return
            filters["workfileIds"] = list(workfile_ids)

        if not fields:
            fields = DEFAULT_WORKFILE_INFO_FIELDS
        fields = set(fields)
        if own_attributes:
            fields.add("ownAttrib")

        query = workfiles_info_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for workfile_info in parsed_data["project"]["workfiles"]:
                if own_attributes:
                    fill_own_attribs(workfile_info)
                yield workfile_info

    def get_workfile_info(
        self, project_name, task_id, path, fields=None, own_attributes=False
    ):
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
        self, project_name, workfile_id, fields=None, own_attributes=False
    ):
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

    def get_thumbnail(
        self, project_name, entity_type, entity_id, thumbnail_id=None
    ):
        """Get thumbnail from server.

        Permissions of thumbnails are related to entities so thumbnails must be
        queried per entity. Thus an entity type and entity type is required to
        be passed.

        If thumbnail id is passed logic can look into locally cached thumbnails
        before calling server which can enhance loading time. If thumbnail id
        is not passed the thumbnail is always downloaded even if is available.

        Notes:
            It is recommended to use one of prepared entity type specific
                methods 'get_folder_thumbnail', 'get_version_thumbnail' or
                'get_workfile_thumbnail'.
            We do recommend pass thumbnail id if you have access to it. Each
                entity that allows thumbnails has 'thumbnailId' field so it can
                be queried.

        Args:
            project_name (str): Project under which the entity is located.
            entity_type (str): Entity type which passed entity id represents.
            entity_id (str): Entity id for which thumbnail should be returned.
            thumbnail_id (str): Prepared thumbnail id from entity. Used only
                to check if thumbnail was already cached.

        Returns:
            Union[str, None]: Path to downlaoded thumbnail or none if entity
                does not have any (or if user does not have permissions).
        """

        # Look for thumbnail into cache and return the path if was found
        filepath = self._thumbnail_cache.get_thumbnail_filepath(
            project_name, thumbnail_id
        )
        if filepath:
            return filepath

        if entity_type in (
            "folder",
            "version",
            "workfile",
        ):
            entity_type += "s"

        # Receive thumbnail content from server
        result = self.raw_get("projects/{}/{}/{}/thumbnail".format(
            project_name,
            entity_type,
            entity_id
        ))

        if result.content_type is None:
            return None

        # It is expected the response contains thumbnail id otherwise the
        #   content cannot be cached and filepath returned
        thumbnail_id = result.headers.get("X-Thumbnail-Id")
        if thumbnail_id is None:
            return None

        # Cache thumbnail and return it's path
        return self._thumbnail_cache.store_thumbnail(
            project_name,
            thumbnail_id,
            result.content,
            result.content_type
        )

    def get_folder_thumbnail(
        self, project_name, folder_id, thumbnail_id=None
    ):
        """Prepared method to receive thumbnail for folder entity.

        Args:
            project_name (str): Project under which the entity is located.
            folder_id (str): Folder id for which thumbnail should be returned.
            thumbnail_id (str): Prepared thumbnail id from entity. Used only
                to check if thumbnail was already cached.

        Returns:
            Union[str, None]: Path to downlaoded thumbnail or none if entity
                does not have any (or if user does not have permissions).
        """

        return self.get_thumbnail(
            project_name, "folder", folder_id, thumbnail_id
        )

    def get_version_thumbnail(
        self, project_name, version_id, thumbnail_id=None
    ):
        """Prepared method to receive thumbnail for version entity.

        Args:
            project_name (str): Project under which the entity is located.
            version_id (str): Version id for which thumbnail should be
                returned.
            thumbnail_id (str): Prepared thumbnail id from entity. Used only
                to check if thumbnail was already cached.

        Returns:
            Union[str, None]: Path to downlaoded thumbnail or none if entity
                does not have any (or if user does not have permissions).
        """

        return self.get_thumbnail(
            project_name, "version", version_id, thumbnail_id
        )

    def get_workfile_thumbnail(
        self, project_name, workfile_id, thumbnail_id=None
    ):
        """Prepared method to receive thumbnail for workfile entity.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_id (str): Worfile id for which thumbnail should be
                returned.
            thumbnail_id (str): Prepared thumbnail id from entity. Used only
                to check if thumbnail was already cached.

        Returns:
            Union[str, None]: Path to downlaoded thumbnail or none if entity
                does not have any (or if user does not have permissions).
        """

        return self.get_thumbnail(
            project_name, "workfile", workfile_id, thumbnail_id
        )

    def create_project(
        self,
        project_name,
        project_code,
        library_project=False,
        preset_name=None
    ):
        """Create project using Ayon settings.

        This project creation function is not validating project entity on
        creation. It is because project entity is created blindly with only
        minimum required information about project which is it's name, code.

        Entered project name must be unique and project must not exist yet.

        Note:
            This function is here to be OP v4 ready but in v3 has more logic
                to do. That's why inner imports are in the body.

        Args:
            project_name (str): New project name. Should be unique.
            project_code (str): Project's code should be unique too.
            library_project (bool): Project is library project.
            preset_name (str): Name of anatomy preset. Default is used if not
                passed.
            con (ServerAPI): Connection to server with logged user.

        Raises:
            ValueError: When project name already exists.

        Returns:
            Dict[str, Any]: Created project entity.
        """

        if self.get_project(project_name, fields=["name"]):
            raise ValueError("Project with name \"{}\" already exists".format(
                project_name
            ))

        if not PROJECT_NAME_REGEX.match(project_name):
            raise ValueError((
                "Project name \"{}\" contain invalid characters"
            ).format(project_name))

        preset = self.get_project_anatomy_preset(preset_name)

        result = self.post(
            "projects",
            name=project_name,
            code=project_code,
            anatomy=preset,
            library=library_project
        )

        if result.status != 201:
            details = "Unknown details ({})".format(result.status)
            if result.data:
                details = result.data.get("detail") or details
            raise ValueError("Failed to create project \"{}\": {}".format(
                project_name, details
            ))

        return self.get_project(project_name)

    def delete_project(self, project_name):
        """Delete project from server.

        This will completely remove project from server without any step back.

        Args:
            project_name (str): Project name that will be removed.
        """

        if not self.get_project(project_name, fields=["name"]):
            raise ValueError("Project with name \"{}\" was not found".format(
                project_name
            ))

        result = self.delete("projects/{}".format(project_name))
        if result.status_code != 204:
            raise ValueError(
                "Failed to delete project \"{}\". {}".format(
                    project_name, result.data["detail"]
                )
            )

    def create_thumbnail(self, project_name, src_filepath):
        """Create new thumbnail on server from passed path.

        Args:
            project_name (str): Project where the thumbnail will be created
                and can be used.
            src_filepath (str): Filepath to thumbnail which should be uploaded.

        Returns:
            str: Created thumbnail id.

        Todos:
            Define more specific exceptions for thumbnail creation.

        Raises:
            ValueError: When thumbnail creation fails (due to many reasons).
        """

        if not os.path.exists(src_filepath):
            raise ValueError("Entered filepath does not exist.")

        ext = os.path.splitext(src_filepath)[-1].lower()
        if ext == ".png":
            mime_type = "image/png"

        elif ext in (".jpeg", ".jpg"):
            mime_type = "image/jpeg"

        else:
            raise ValueError(
                "Thumbnail source file has unknown extensions {}".format(ext))

        with open(src_filepath, "rb") as stream:
            content = stream.read()

        response = self.raw_post(
            "projects/{}/thumbnails".format(project_name),
            headers={"Content-Type": mime_type},
            data=content
        )
        if response.status_code != 200:
            _detail = response.data.get("detail")
            details = ""
            if _detail:
                details = " {}".format(_detail)
            raise ValueError(
                "Failed to create thumbnail.{}".format(details))
        return response.data["id"]

    def send_batch_operations(self, project_name, operations, can_fail=False):
        if not operations:
            return

        body_by_id = {}
        for operation in operations:
            if not operation:
                continue
            op_id = operation.get("id")
            if not op_id:
                op_id = create_entity_id()
                operation["id"] = op_id
            body_by_id[op_id] = operation

        operations_body = []
        for operation in operations:
            if not operation:
                continue

            try:
                body = json.loads(
                    json.dumps(operation, default=entity_data_json_default)
                )
            except:
                raise ValueError("Couldn't json parse body: {}".format(
                    json.dumps(
                        operation, indent=4, default=failed_json_default
                    )
                ))

            body_by_id[operation["id"]] = body
            operations_body.append(body)

        if not operations_body:
            return

        result = self.post(
            "projects/{}/operations".format(project_name),
            operations=operations_body,
            canFail=can_fail
        )

        if result.get("success"):
            return

        if "operations" not in result:
            raise FailedOperations(
                "Operation failed. Content: {}".format(str(result))
            )

        for op_result in result["operations"]:
            if not op_result["success"]:
                operation_id = op_result["id"]
                raise FailedOperations((
                    "Operation \"{}\" failed with data:\n{}\nError: {}."
                ).format(
                    operation_id,
                    json.dumps(body_by_id[operation_id], indent=4),
                    op_result["error"],
                ))

