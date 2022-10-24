import collections

from .constants import (
    DEFAULT_FOLDER_FIELDS,
    DEFAULT_TASK_FIELDS,
    DEFAULT_SUBSET_FIELDS,
    DEFAULT_VERSION_FIELDS,
    DEFAULT_REPRESENTATION_FIELDS,
)
from .graphql import GraphQlQuery
from .graphql_queries import (
    project_graphql_query,
    projects_graphql_query,
    folders_graphql_query,
    tasks_graphql_query,
    subsets_graphql_query,
    versions_graphql_query,
    representations_graphql_query,
    reprersentations_parents_qraphql_query,
)
from .server import get_server_api_connection


def get_projects(active=None, library=None, fields=None, con=None):
    """Get projects.

    Args:
        active (Union[bool, None]): Filter active or inactive projects. Filter
            is disabled when 'None' is passed.
        library (Union[bool, None]): Filter library projects. Filter is
            disabled when 'None' is passed.
        fields (Union[Iterable[str], None]): fields to be queried for project.

    Returns:
        List[Dict[str, Any]]: List of queried projects.
    """

    if fields is None:
        use_rest = True
    else:
        use_rest = False
        fields = set(fields)
        for field in fields:
            if field.startswith("config"):
                use_rest = True
                break

    if con is None:
        con = get_server_api_connection()
    if use_rest:
        for project in con.get_rest_projects(active, library):
            yield project

    else:
        query = projects_graphql_query(fields)
        for parsed_data in query.continuous_query(con):
            for project in parsed_data["projects"]:
                yield project


def get_project(project_name, fields=None, con=None):
    """Get project.

    Args:
        project_name (str): Name of project.
        fields (Union[Iterable(str), None]): fields to be queried for project.

    Returns:
        Union[Dict[str, Any], None]: Project entity data or None if project was
            not found.
    """

    if fields is not None:
        fields = set(fields)

    # Skip if both are disabled
    if con is None:
        con = get_server_api_connection()
    if not fields:
        return con.get_rest_project(project_name)

    query = project_graphql_query(fields)
    query.set_variable_value("projectName", project_name)

    parsed_data = query.query(con)

    data = parsed_data["project"]
    data["name"] = project_name
    return data


def get_folders(
    project_name,
    folder_ids=None,
    folder_paths=None,
    folder_names=None,
    parent_ids=None,
    active=None,
    fields=None,
    con=None
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
        parent_ids (Iterable[str]): Ids of folder parents. Use 'None' if folder
            is direct child of project.
        active (Union[bool, None]): Filter active/inactive folders. Both are
            returned if is set to None.
        fields (Union[Iterable[str], None]): Fields to be queried for folder.
            All possible folder fields are returned if 'None' is passed.

    Returns:
        Iterable[dict[str, Any]]: Queried folder entities.
    """

    if not project_name:
        return []

    filters = {
        "projectName": project_name
    }
    if folder_ids is not None:
        folder_ids = set(folder_ids)
        if not folder_ids:
            return []
        filters["folderIds"] = list(folder_ids)

    if folder_paths is not None:
        folder_paths = set(folder_paths)
        if not folder_paths:
            return []
        filters["folderPaths"] = list(folder_paths)

    if folder_names is not None:
        folder_names = set(folder_names)
        if not folder_names:
            return []
        filters["folderNames"] = list(folder_names)

    if parent_ids is not None:
        parent_ids = set(parent_ids)
        if not parent_ids:
            return []
        if None in parent_ids:
            # Replace 'None' with '"root"' which is used during GraphQl query
            #   for parent ids filter for folders without folder parent
            parent_ids.remove(None)
            parent_ids.add("root")

        if project_name in parent_ids:
            # Replace project name with '"root"' which is used during GraphQl
            #   query for parent ids filter for folders without folder parent
            parent_ids.remove(project_name)
            parent_ids.add("root")

        filters["parentFolderIds"] = list(parent_ids)

    if not fields:
        fields = DEFAULT_FOLDER_FIELDS
    fields = set(fields)
    if active is not None:
        fields.add("active")

    query = folders_graphql_query(fields)
    for attr, filter_value in filters.items():
        query.set_variable_value(attr, filter_value)

    if con is None:
        con = get_server_api_connection()
    for parsed_data in query.continuous_query(con):
        for folder in parsed_data["project"]["folders"]:
            if active is None or active is folder["active"]:
                yield folder


def get_tasks(
    project_name,
    task_ids=None,
    task_names=None,
    task_types=None,
    folder_ids=None,
    active=None,
    fields=None,
    con=None
):
    if not project_name:
        return []

    filters = {
        "projectName": project_name
    }

    if task_ids is not None:
        task_ids = set(task_ids)
        if not task_ids:
            return []
        filters["taskIds"] = list(task_ids)

    if task_names is not None:
        task_names = set(task_names)
        if not task_names:
            return []
        filters["taskNames"] = list(task_names)

    if task_types is not None:
        task_types = set(task_types)
        if not task_types:
            return []
        filters["taskTypes"] = list(task_types)

    if folder_ids is not None:
        folder_ids = set(folder_ids)
        if not folder_ids:
            return []
        filters["folderIds"] = list(folder_ids)

    if not fields:
        fields = DEFAULT_TASK_FIELDS
    fields = set(fields)
    if active is not None:
        fields.add("active")

    query = tasks_graphql_query(fields)
    for attr, filter_value in filters.items():
        query.set_variable_value(attr, filter_value)

    if con is None:
        con = get_server_api_connection()
    for parsed_data in query.continuous_query(con):
        for task in parsed_data["project"]["tasks"]:
            if active is None or active is task["active"]:
                yield task


def get_folder_by_id(project_name, folder_id, fields=None, con=None):
    """Receive folder data by it's id.

    Args:
        project_name (str): Name of project where to look for queried entities.
        folder_id (str): Folder's id.
        fields (Iterable[str]): Fields that should be returned. All fields are
            returned if 'None' is passed.

    Returns:
        Union[dict, None]: Folder entity data or None if was not found.
    """

    folders = get_folders(
        project_name, folder_ids=[folder_id], fields=fields, con=con
    )
    for folder in folders:
        return folder
    return None


def get_folder_by_path(project_name, folder_path, fields=None, con=None):
    folders = get_folders(
        project_name, folder_paths=[folder_path], fields=fields, con=con
    )
    for folder in folders:
        return folder
    return None


def get_folder_by_name(project_name, folder_name, fields=None, con=None):
    folders = get_folders(
        project_name, folder_names=[folder_name], fields=fields, con=con
    )
    for folder in folders:
        return folder
    return None


def get_folder_ids_with_subsets(project_name, folder_ids=None, con=None):
    if folder_ids is not None:
        folder_ids = set(folder_ids)
        if not folder_ids:
            return set()

    query = folders_graphql_query({"id"})
    query.set_variable_value("projectName", project_name)
    query.set_variable_value("folderHasSubsets", True)
    if folder_ids:
        query.set_variable_value("folderIds", list(folder_ids))

    if con is None:
        con = get_server_api_connection()
    parsed_data = query.query(con)
    folders = parsed_data["project"]["folders"]
    return {
        folder["id"]
        for folder in folders
    }


def get_subsets(
    project_name,
    subset_ids=None,
    subset_names=None,
    folder_ids=None,
    names_by_folder_ids=None,
    archived=False,
    fields=None,
    con=None
):
    if not project_name:
        return []

    if subset_ids is not None:
        subset_ids = set(subset_ids)
        if not subset_ids:
            return []

    filter_subset_names = None
    if subset_names is not None:
        filter_subset_names = set(subset_names)
        if not filter_subset_names:
            return []

    filter_folder_ids = None
    if folder_ids is not None:
        filter_folder_ids = set(folder_ids)
        if not filter_folder_ids:
            return []

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
            return []

    # Convert fields and add minimum required fields
    if fields is None:
        fields = set(DEFAULT_SUBSET_FIELDS)
    else:
        fields = set(fields) | {"id", "active"}

    # Add 'name' and 'folderId' if 'name_by_asset_ids' filter is entered
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

    if con is None:
        con = get_server_api_connection()
    parsed_data = query.query(con)

    subsets = parsed_data.get("project", {}).get("subsets", [])

    # Filter subsets by 'names_by_folder_ids'
    if names_by_folder_ids:
        subsets_by_folder_id = collections.defaultdict(list)
        for subset in subsets:
            folder_id = subset["folderId"]
            subsets_by_folder_id[folder_id].append(subset)

        filtered_subsets = []
        for folder_id, names in names_by_folder_ids.items():
            for folder_subset in subsets_by_folder_id[folder_id]:
                if folder_subset["name"] in names:
                    filtered_subsets.append(subset)
        subsets = filtered_subsets

    return list(subsets)


def get_subset_by_id(project_name, subset_id, fields=None, con=None):
    subsets = get_subsets(
        project_name, subset_ids=[subset_id], fields=fields, con=con
    )
    for subset in subsets:
        return subset
    return None


def get_subset_by_name(
    project_name, subset_name, folder_id, fields=None, con=None
):
    subsets = get_subsets(
        project_name,
        subset_names=[subset_name],
        folder_ids=[folder_id],
        fields=fields,
        con=con
    )
    for subset in subsets:
        return subset
    return None


def get_subset_families(project_name, subset_ids=None, con=None):
    if subset_ids is not None:
        subsets = get_subsets(
            project_name,
            subset_ids=subset_ids,
            fields=["data.family"],
            con=con
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

    if con is None:
        con = get_server_api_connection()
    parsed_data = query.query(con)

    return set(parsed_data.get("project", {}).get("subsetFamilies", []))


def get_versions(
    project_name,
    version_ids=None,
    subset_ids=None,
    versions=None,
    hero=True,
    standard=True,
    latest=None,
    fields=None,
    con=None
):
    """Get version entities based on passed filters from server.

    Args:
        project_name (str): Name of project where to look for versions.
        version_ids (Iterable[str]): Version ids used for version filtering.
        subset_ids (Iterable[str]): Subset ids used for version filtering.
        versions (Iterable[int]): Versions we're interested in.
        hero (bool): Receive also hero versions when set to true.
        standard (bool): Receive versions which are not hero when set to true.
        latest (bool): Return only latest version of standard versions.
            This can be combined only with 'standard' attribute set to True.
        fields (Union[Iterable(str), None]): Fields to be queried for version.
            All possible folder fields are returned if 'None' is passed.

    Returns:
        List[Dict[str, Any]]: Queried version entities.
    """

    if not fields:
        fields = DEFAULT_VERSION_FIELDS
    fields = set(fields)

    filters = {
        "projectName": project_name
    }
    if version_ids is not None:
        version_ids = set(version_ids)
        if not version_ids:
            return []
        filters["versionIds"] = list(version_ids)

    if subset_ids is not None:
        subset_ids = set(subset_ids)
        if not subset_ids:
            return []
        filters["subsetIds"] = list(subset_ids)

    # TODO versions can't be used as fitler at this moment!
    if versions is not None:
        versions = set(versions)
        if not versions:
            return []
        filters["versions"] = list(versions)

    if not hero and not standard:
        return []

    # Add filters based on 'hero' and 'stadard'
    if hero and not standard:
        filters["heroOnly"] = True
    elif hero and latest:
        filters["heroOrLatestOnly"] = True
    elif latest:
        filters["latestOnly"] = True

    # Make sure fields have minimum required fields
    fields |= {"id", "version"}

    query = versions_graphql_query(fields)

    for attr, filter_value in filters.items():
        query.set_variable_value(attr, filter_value)

    if con is None:
        con = get_server_api_connection()

    for parsed_data in query.continuous_query(con):
        for version in parsed_data["project"]["versions"]:
            yield version


def get_version_by_id(project_name, version_id, fields=None, con=None):
    versions = get_versions(
        project_name,
        version_ids=[version_id],
        fields=fields,
        hero=True,
        con=con
    )
    for version in versions:
        return version
    return None


def get_version_by_name(
    project_name, version, subset_id, fields=None, con=None
):
    versions = get_versions(
        project_name,
        subset_ids=[subset_id],
        versions=[version],
        fields=fields,
        con=con
    )
    if versions:
        return versions[0]
    return None


def get_hero_version_by_id(project_name, version_id, fields=None, con=None):
    versions = get_hero_versions(
        project_name,
        version_ids=[version_id],
        fields=fields,
        con=con
    )
    for version in versions:
        return version
    return None


def get_hero_version_by_subset_id(
    project_name, subset_id, fields=None, con=None
):
    versions = get_hero_versions(
        project_name,
        subset_ids=[subset_id],
        fields=fields,
        con=con
    )
    for version in versions:
        return version
    return None


def get_hero_versions(
    project_name,
    subset_ids=None,
    version_ids=None,
    fields=None,
    con=None
):
    return get_versions(
        project_name,
        version_ids=version_ids,
        subset_ids=subset_ids,
        hero=True,
        standard=False,
        fields=fields,
        con=con
    )


def get_last_versions(project_name, subset_ids, fields=None, con=None):
    versions = get_versions(
        project_name,
        subset_ids=subset_ids,
        latest=True,
        fields=fields,
        con=con
    )
    return {
        version["parent"]: version
        for version in versions
    }


def get_last_version_by_subset_id(
    project_name, subset_id, fields=None, con=None
):
    versions = get_versions(
        project_name,
        subset_ids=[subset_id],
        latest=True,
        fields=fields,
        con=con
    )
    if not versions:
        return versions[0]
    return None


def get_last_version_by_subset_name(
    project_name, subset_name, folder_id, fields=None, con=None
):
    if not folder_id:
        return None

    subset = get_subset_by_name(
        project_name, subset_name, folder_id, fields=["_id"], con=con
    )
    if not subset:
        return None
    return get_last_version_by_subset_id(
        project_name, subset["id"], fields=fields, con=con
    )


def version_is_latest(project_name, version_id, con=None):
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

    if con is None:
        con = get_server_api_connection()
    parsed_data = query.query(con)
    latest_version = (
        parsed_data["project"]["version"]["subset"]["latestVersion"]
    )
    return latest_version["id"] == version_id


def get_representations(
    project_name,
    representation_ids=None,
    representation_names=None,
    version_ids=None,
    names_by_version_ids=None,
    active=None,
    fields=None,
    con=None
):
    """Get version entities based on passed filters from server.

    Todo:
        Add separated function for 'names_by_version_ids' filtering. Because
            can't be combined with others.

    Args:
        project_name (str): Name of project where to look for versions.
        representation_ids (Iterable[str]): Representaion ids used for
            representation filtering.
        representation_names (Iterable[str]): Representation names used for
            representation filtering.
        version_ids (Iterable[str]): Version ids used for
            representation filtering. Versions are parents of representations.
        names_by_version_ids (bool): Find representations by names and
            version ids. This filter discard all other filters.
        active (bool): Receive active/inactive representaions. All are returned
            when 'None' is passed.
        fields (Union[Iterable(str), None]): Fields to be queried for
            representation. All possible fields are returned if 'None' is
            passed.

    Returns:
        List[Dict[str, Any]]: Queried representation entities.
    """

    if not fields:
        fields = DEFAULT_REPRESENTATION_FIELDS
    fields = set(fields)

    if active is not None:
        fields.add("active")

    filters = {
        "projectName": project_name
    }

    if representation_ids is not None:
        representation_ids = set(representation_ids)
        if not representation_ids:
            return []
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
            return []

    else:
        if representation_names is not None:
            representaion_names_filter = set(representation_names)
            if not representaion_names_filter:
                return []

        if version_ids is not None:
            version_ids_filter = set(version_ids)
            if not version_ids_filter:
                return []

    if version_ids_filter:
        filters["versionIds"] = list(version_ids_filter)

    if representaion_names_filter:
        filters["representationNames"] = list(representaion_names_filter)

    query = representations_graphql_query(fields)

    for attr, filter_value in filters.items():
        query.set_variable_value(attr, filter_value)

    if con is None:
        con = get_server_api_connection()
    parsed_data = query.query(con)

    representations = parsed_data.get("project", {}).get("representations", [])
    if active is None:
        representations = [
            repre
            for repre in representations
            if repre["active"] == active
        ]
    return representations


def get_representation_by_id(
    project_name, representation_id, fields=None, con=None
):
    representations = get_representations(
        project_name,
        representation_ids=[representation_id],
        fields=fields,
        con=con
    )
    for representation in representations:
        return representation
    return None


def get_representation_by_name(
    project_name, representation_name, version_id, fields=None, con=None
):
    representations = get_representations(
        project_name,
        representation_names=[representation_name],
        version_ids=[version_id],
        fields=fields,
        con=con
    )
    for representation in representations:
        return representation
    return None


def get_representation_parents(project_name, representation, con=None):
    if not representation:
        return None

    repre_id = representation["_id"]
    parents_by_repre_id = get_representations_parents(
        project_name, [representation], con=con
    )
    return parents_by_repre_id[repre_id]


def get_representations_parents(project_name, representation_ids, con=None):
    if not representation_ids:
        return {}

    project = get_project(project_name, con=con)
    repre_ids = set(representation_ids)
    output = {
        repre_id: (None, None, None, None)
        for repre_id in representation_ids
    }

    query = reprersentations_parents_qraphql_query()
    query.set_variable_value("projectName", project_name)
    query.set_variable_value("representationIds", list(repre_ids))

    if con is None:
        con = get_server_api_connection()

    parsed_data = query.query(con)
    for repre in parsed_data["project"]["representations"]:
        repre_id = repre["id"]
        version = repre.pop("version")
        subset = version.pop("subset")
        folder = subset.pop("folder")
        output[repre_id] = (version, subset, folder, project)

    return output


def get_thumbnail_id_from_source(project_name, src_type, src_id, con=None):
    """Receive thumbnail id from source entity.

    Args:
        project_name (str): Name of project where to look for queried entities.
        src_type (str): Type of source entity ('asset', 'version').
        src_id (Union[str, ObjectId]): Id of source entity.

    Returns:
        ObjectId: Thumbnail id assigned to entity.
        None: If Source entity does not have any thumbnail id assigned.
    """

    if not src_type or not src_id:
        return None

    if src_type == "subset":
        subset = get_subset_by_id(
            project_name, src_id, fields=["data.thumbnail_id"], con=con
        ) or {}
        return subset.get("data", {}).get("thumbnail_id")

    if src_type == "folder":
        subset = get_folder_by_id(
            project_name, src_id, fields=["data.thumbnail_id"], con=con
        ) or {}
        return subset.get("data", {}).get("thumbnail_id")

    return None
