from .server import get_server_api_connection


def get_full_project_settings(project_name):
    con = get_server_api_connection()
    result = con.get("projects/{}/settings".format(project_name))
    if result.status == 200:
        return result.data
    return None


def get_project_settings(project_name):
    full_settings = get_full_project_settings(project_name)
    if full_settings is None:
        return full_settings
    return full_settings["settings"]


def get_addon_settings(addon_name, addon_version, project_name):
    con = get_server_api_connection()
    result = con.get("addons/{}/{}/settings/{}".format(project_name))
    if result.status == 200:
        return result.data
    return None
