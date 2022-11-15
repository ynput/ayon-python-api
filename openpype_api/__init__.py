from .server import (
    ServerAPIBase,
)

from .server_api import (
    ServerAPI,

    get_server_api_connection,

    get,
    post,
    put,
    patch,
    delete,

    get_projects,
    get_project,
    create_project,
    delete_project,

    get_folder_by_id,
    get_folder_by_name,
    get_folder_by_path,
    get_folders,

    get_tasks,

    get_folder_ids_with_subsets,
    get_subset_by_id,
    get_subset_by_name,
    get_subsets,
    get_subset_families,

    get_version_by_id,
    get_version_by_name,
    version_is_latest,
    get_versions,
    get_hero_version_by_subset_id,
    get_hero_version_by_id,
    get_hero_versions,
    get_last_versions,
    get_last_version_by_subset_id,
    get_last_version_by_subset_name,
    get_representation_by_id,
    get_representation_by_name,
    get_representations,
    get_representations_parents,
    get_representation_parents,
    get_thumbnail_id_from_source,

    get_project_settings,
    get_addon_settings,

    create_thumbnail,
    get_thumbnail,
    get_folder_thumbnail,
    get_version_thumbnail,
    get_workfile_thumbnail,
)


__all__ = (
    "ServerAPIBase",

    "ServerAPI",
    "get_server_api_connection",
    "get",
    "post",
    "put",
    "patch",
    "delete",

    "get_project_settings",
    "get_addon_settings",

    "get_projects",
    "get_project",

    "get_folder_by_id",
    "get_folder_by_name",
    "get_folder_by_path",
    "get_folders",

    "get_tasks",

    "get_folder_ids_with_subsets",
    "get_subset_by_id",
    "get_subset_by_name",
    "get_subsets",
    "get_subset_families",
    "get_version_by_id",
    "get_version_by_name",
    "version_is_latest",
    "get_versions",
    "get_hero_version_by_subset_id",
    "get_hero_version_by_id",
    "get_hero_versions",
    "get_last_versions",
    "get_last_version_by_subset_id",
    "get_last_version_by_subset_name",
    "get_representation_by_id",
    "get_representation_by_name",
    "get_representations",
    "get_representations_parents",
    "get_representation_parents",
    "get_thumbnail_id_from_source",
)
