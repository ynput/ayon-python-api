import os
from .constants import (
    SERVER_URL_ENV_KEY,
    SERVER_TOKEN_ENV_KEY,
)
from .server import ServerAPIBase


class ServerAPI(ServerAPIBase):
    """Extended server api which also handles storing tokens and url.

    Created object expect to have set environment variables
    'OPENPYPE_SERVER_URL'. Also is expecting filled 'OPENPYPE_TOKEN'
    but that can be filled afterwards with calling 'login' method.
    """

    def __init__(self):
        url = self.get_url()
        token = self.get_token()

        super(ServerAPI, self).__init__(url, token)

        self.validate_server_availability()
        self.create_session()

    def login(self, username, password):
        """Login to the server or change user.

        If user is the same as current user and token is available the
        login is skipped.
        """

        previous_token = self._access_token
        super(ServerAPI, self).login(username, password)
        if self.has_valid_token and previous_token != self._access_token:
            os.environ[SERVER_TOKEN_ENV_KEY] = self._access_token

    @staticmethod
    def get_url():
        return os.environ.get(SERVER_URL_ENV_KEY)

    @staticmethod
    def get_token():
        return os.environ.get(SERVER_TOKEN_ENV_KEY)

    @staticmethod
    def set_environments(url, token):
        """Change url and token environemnts in currently running process.

        Args:
            url (str): New server url.
            token (str): User's token.
        """

        os.environ[SERVER_URL_ENV_KEY] = url or ""
        os.environ[SERVER_TOKEN_ENV_KEY] = token or ""


class GlobalContext:
    """Singleton connection holder.

    Goal is to avoid create connection on import which can be dangerous in
    some cases.
    """

    _connection = None

    @classmethod
    def get_server_api_connection(cls):
        if cls._connection is None:
            cls._connection = ServerAPI()
        return cls._connection


def get_server_api_connection():
    """Access to global scope object of ServerAPI.

    This access expect to have set environment variables 'OPENPYPE_SERVER_URL'
    and 'OPENPYPE_TOKEN'.

    Returns:
        ServerAPI: Object of connection to server.
    """

    return GlobalContext.get_server_api_connection()


def get(*args, **kwargs):
    con = get_server_api_connection()
    return con.get(*args, **kwargs)


def post(*args, **kwargs):
    con = get_server_api_connection()
    return con.post(*args, **kwargs)


def put(*args, **kwargs):
    con = get_server_api_connection()
    return con.put(*args, **kwargs)


def patch(*args, **kwargs):
    con = get_server_api_connection()
    return con.patch(*args, **kwargs)


def delete(*args, **kwargs):
    con = get_server_api_connection()
    return con.delete(*args, **kwargs)


def get_project(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_project(*args, **kwargs)


def get_projects(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_projects(*args, **kwargs)


def get_folders(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_folders(*args, **kwargs)


def get_tasks(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_tasks(*args, **kwargs)


def get_folder_by_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_folder_by_id(*args, **kwargs)


def get_folder_by_path(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_folder_by_path(*args, **kwargs)


def get_folder_by_name(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_folder_by_name(*args, **kwargs)


def get_folder_ids_with_subsets(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_folder_ids_with_subsets(*args, **kwargs)


def get_subsets(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_subsets(*args, **kwargs)


def get_subset_by_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_subset_by_id(*args, **kwargs)


def get_subset_by_name(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_subset_by_name(*args, **kwargs)


def get_subset_families(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_subset_families(*args, **kwargs)


def get_versions(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_versions(*args, **kwargs)


def get_version_by_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_version_by_id(*args, **kwargs)


def get_version_by_name(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_version_by_name(*args, **kwargs)


def get_hero_version_by_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_hero_version_by_id(*args, **kwargs)


def get_hero_version_by_subset_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_hero_version_by_subset_id(*args, **kwargs)


def get_hero_versions(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_hero_versions(*args, **kwargs)


def get_last_versions(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_last_versions(*args, **kwargs)


def get_last_version_by_subset_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_last_version_by_subset_id(*args, **kwargs)


def get_last_version_by_subset_name(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_last_version_by_subset_name(*args, **kwargs)


def version_is_latest(*args, **kwargs):
    con = get_server_api_connection()
    return con.version_is_latest(*args, **kwargs)


def get_representations(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_representations(*args, **kwargs)


def get_representation_by_id(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_representation_by_id(*args, **kwargs)


def get_representation_by_name(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_representation_by_name(*args, **kwargs)


def get_representation_parents(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_representation_parents(*args, **kwargs)


def get_representations_parents(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_representations_parents(*args, **kwargs)


def get_project_settings(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_project_settings(*args, **kwargs)


def get_addon_settings(*args, **kwargs):
    con = get_server_api_connection()
    return con.get_addon_settings(*args, **kwargs)


def create_project(
    project_name,
    project_code,
    library_project=False,
    preset_name=None
):
    con = get_server_api_connection()
    return con.create_project(
        project_name,
        project_code,
        library_project,
        preset_name
    )


def delete_project(project_name):
    con = get_server_api_connection()
    return con.delete_project(project_name)


def create_thumbnail(project_name, src_filepath):
    con = get_server_api_connection()
    return con.create_thumbnail(project_name, src_filepath)


def get_thumbnail(project_name, entity_type, entity_id, thumbnail_id=None):
    con = get_server_api_connection()
    con.get_thumbnail(project_name, entity_type, entity_id, thumbnail_id)


def get_folder_thumbnail(project_name, folder_id, thumbnail_id=None):
    con = get_server_api_connection()
    return con.get_folder_thumbnail(project_name, folder_id, thumbnail_id)


def get_version_thumbnail(project_name, version_id, thumbnail_id=None):
    con = get_server_api_connection()
    return con.get_version_thumbnail(project_name, version_id, thumbnail_id)


def get_workfile_thumbnail(project_name, workfile_id, thumbnail_id=None):
    con = get_server_api_connection()
    return con.get_workfile_thumbnail(project_name, workfile_id, thumbnail_id)


def create_thumbnail(project_name, src_filepath):
    con = get_server_api_connection()
    return con.create_thumbnail(project_name, src_filepath)


def get_default_fields_for_type(entity_type):
    con = get_server_api_connection()
    return con.get_default_fields_for_type(entity_type)