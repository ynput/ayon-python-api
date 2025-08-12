from __future__ import annotations

import warnings
import typing
from typing import Optional, Iterable, Generator, Any

from ._base import _BaseServerAPI
from .exceptions import UnsupportedServerVersion
from .utils import (
    prepare_query_string,
    prepare_list_filters,
    fill_own_attribs,
    create_entity_id,
    NOT_SET,
)
from .graphql_queries import folders_graphql_query

if typing.TYPE_CHECKING:
    from .typing import (
        FolderDict,
        FlatFolderDict,
        ProjectHierarchyDict,
    )


class _FoldersAPI(_BaseServerAPI):
    def get_rest_folder(
        self, project_name: str, folder_id: str
    ) -> Optional["FolderDict"]:
        return self.get_rest_entity_by_id(
            project_name, "folder", folder_id
        )

    def get_rest_folders(
        self, project_name: str, include_attrib: bool = False
    ) -> list["FlatFolderDict"]:
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
            List[FlatFolderDict]: List of folder entities.

        """
        major, minor, patch, _, _ = self.get_server_version_tuple()
        if (major, minor, patch) < (1, 0, 8):
            raise UnsupportedServerVersion(
                "Function 'get_folders_rest' is supported"
                " for AYON server 1.0.8 and above."
            )
        query = prepare_query_string({
            "attrib": "true" if include_attrib else "false"
        })
        response = self.get(
            f"projects/{project_name}/folders{query}"
        )
        response.raise_for_status()
        return response.data["folders"]

    def get_folders_hierarchy(
        self,
        project_name: str,
        search_string: Optional[str] = None,
        folder_types: Optional[Iterable[str]] = None
    ) -> "ProjectHierarchyDict":
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
        if folder_types:
            folder_types = ",".join(folder_types)

        query = prepare_query_string({
            "search": search_string or None,
            "types": folder_types or None,
        })
        response = self.get(
            f"projects/{project_name}/hierarchy{query}"
        )
        response.raise_for_status()
        return response.data

    def get_folders_rest(
        self, project_name: str, include_attrib: bool = False
    ) -> list["FlatFolderDict"]:
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
            List[FlatFolderDict]: List of folder entities.

        """
        warnings.warn(
            (
                "DEPRECATION: Used deprecated 'get_folders_rest',"
                " use 'get_rest_folders' instead."
            ),
            DeprecationWarning
        )
        return self.get_rest_folders(project_name, include_attrib)

    def get_folders(
        self,
        project_name: str,
        folder_ids: Optional[Iterable[str]] = None,
        folder_paths: Optional[Iterable[str]] = None,
        folder_names: Optional[Iterable[str]] = None,
        folder_types: Optional[Iterable[str]] = None,
        parent_ids: Optional[Iterable[str]] = None,
        folder_path_regex: Optional[str] = None,
        has_products: Optional[bool] = None,
        has_tasks: Optional[bool] = None,
        has_children: Optional[bool] = None,
        statuses: Optional[Iterable[str]] = None,
        assignees_all: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: Optional[bool] = True,
        has_links: Optional[bool] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Generator["FolderDict", None, None]:
        """Query folders from server.

        Todos:
            Folder name won't be unique identifier, so we should add
                folder path filtering.

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
            Generator[FolderDict, None, None]: Queried folder entities.

        """
        if not project_name:
            return

        filters = {
            "projectName": project_name
        }
        if not prepare_list_filters(
            filters,
            ("folderIds", folder_ids),
            ("folderPaths", folder_paths),
            ("folderNames", folder_names),
            ("folderTypes", folder_types),
            ("folderStatuses", statuses),
            ("folderTags", tags),
            ("folderAssigneesAll", assignees_all),
        ):
            return

        for filter_key, filter_value in (
            ("folderPathRegex", folder_path_regex),
            ("folderHasProducts", has_products),
            ("folderHasTasks", has_tasks),
            ("folderHasLinks", has_links),
            ("folderHasChildren", has_children),
        ):
            if filter_value is not None:
                filters[filter_key] = filter_value

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

        if not fields:
            fields = self.get_default_fields_for_type("folder")
        else:
            fields = set(fields)
            self._prepare_fields("folder", fields)

        if active is not None:
            fields.add("active")

        if own_attributes:
            fields.add("ownAttrib")

        query = folders_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for folder in parsed_data["project"]["folders"]:
                if active is not None and active is not folder["active"]:
                    continue

                self._convert_entity_data(folder)

                if own_attributes:
                    fill_own_attribs(folder)
                yield folder

    def get_folder_by_id(
        self,
        project_name: str,
        folder_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional["FolderDict"]:
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
            Optional[FolderDict]: Folder entity data or None
                if was not found.

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
        project_name: str,
        folder_path: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional["FolderDict"]:
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
            Optional[FolderDict]: Folder entity data or None
                if was not found.

        """
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
        project_name: str,
        folder_name: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional["FolderDict"]:
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
            Optional[FolderDict]: Folder entity data or None
                if was not found.

        """
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

    def get_folder_ids_with_products(
        self, project_name: str, folder_ids: Optional[Iterable[str]] = None
    ) -> set[str]:
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
        if folder_ids is not None:
            folder_ids = set(folder_ids)
            if not folder_ids:
                return set()

        query = folders_graphql_query({"id"})
        query.set_variable_value("projectName", project_name)
        query.set_variable_value("folderHasProducts", True)
        if folder_ids:
            query.set_variable_value("folderIds", list(folder_ids))

        parsed_data = query.query(self)
        folders = parsed_data["project"]["folders"]
        return {
            folder["id"]
            for folder in folders
        }

    def create_folder(
        self,
        project_name: str,
        name: str,
        folder_type: Optional[str] = None,
        parent_id: Optional[str] = None,
        label: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> str:
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
        if not folder_id:
            folder_id = create_entity_id()
        create_data = {
            "id": folder_id,
            "name": name,
        }
        for key, value in (
            ("folderType", folder_type),
            ("parentId", parent_id),
            ("label", label),
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
            f"projects/{project_name}/folders",
            **create_data
        )
        response.raise_for_status()
        return folder_id

    def update_folder(
        self,
        project_name: str,
        folder_id: str,
        name: Optional[str] = None,
        folder_type: Optional[str] = None,
        parent_id: Optional[str] = NOT_SET,
        label: Optional[str] = NOT_SET,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ):
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
            parent_id (Optional[str]): New parent folder id.
            label (Optional[str]): New label.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[str]): New thumbnail id.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("folderType", folder_type),
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
            ("parentId", parent_id),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/folders/{folder_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_folder(
        self, project_name: str, folder_id: str, force: bool = False
    ):
        """Delete folder.

        Args:
            project_name (str): Project name.
            folder_id (str): Folder id to delete.
            force (Optional[bool]): Folder delete folder with all children
                folder, products, versions and representations.

        """
        url = f"projects/{project_name}/folders/{folder_id}"
        if force:
            url += "?force=true"
        response = self.delete(url)
        response.raise_for_status()