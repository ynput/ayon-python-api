from __future__ import annotations

import typing
from typing import Optional, Iterable, Generator, Any

from ayon_api.utils import (
    prepare_list_filters,
    fill_own_attribs,
    create_entity_id,
    NOT_SET,
)
from ayon_api.graphql_queries import (
    tasks_graphql_query,
    tasks_by_folder_paths_graphql_query,
)

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import TaskDict, AdvancedFilterDict


class TasksAPI(BaseServerAPI):
    def get_rest_task(
        self, project_name: str, task_id: str
    ) -> Optional[TaskDict]:
        return self.get_rest_entity_by_id(project_name, "task", task_id)

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
        active: Optional[bool] = True,
        filters: Optional[AdvancedFilterDict] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> Generator[TaskDict, None, None]:
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
            filters (Optional[AdvancedFilterDict]): Advanced filtering options.
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

        graphql_filters = {
            "projectName": project_name
        }
        if not prepare_list_filters(
            graphql_filters,
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

        filters = self._prepare_advanced_filters(filters)
        if filters:
            graphql_filters["filter"] = filters

        if not fields:
            fields = self.get_default_fields_for_type("task")
        else:
            fields = set(fields)
            self._prepare_fields("task", fields, own_attributes)

        if active is not None:
            fields.add("active")

        query = tasks_graphql_query(fields)
        for attr, filter_value in graphql_filters.items():
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
    ) -> Optional[TaskDict]:
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
    ) -> Optional[TaskDict]:
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
        active: Optional[bool] = True,
        filters: Optional[AdvancedFilterDict] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> dict[str, list[TaskDict]]:
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
            filters (Optional[AdvancedFilterDict]): Advanced filtering options.
            fields (Optional[Iterable[str]]): Fields to be queried for
                folder. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            dict[str, list[TaskDict]]: Task entities by
                folder path.

        """
        folder_paths = set(folder_paths)
        if not project_name or not folder_paths:
            return {}

        graphql_filters = {
            "projectName": project_name,
            "folderPaths": list(folder_paths),
        }

        if not prepare_list_filters(
            graphql_filters,
            ("taskNames", task_names),
            ("taskTypes", task_types),
            ("taskAssigneesAny", assignees),
            ("taskAssigneesAll", assignees_all),
            ("taskStatuses", statuses),
            ("taskTags", tags),
        ):
            return {}

        filters = self._prepare_advanced_filters(filters)
        if filters:
            graphql_filters["filter"] = filters

        if not fields:
            fields = self.get_default_fields_for_type("task")
        else:
            fields = set(fields)
            self._prepare_fields("task", fields, own_attributes)

        if active is not None:
            fields.add("active")

        query = tasks_by_folder_paths_graphql_query(fields)
        for attr, filter_value in graphql_filters.items():
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
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False
    ) -> list[TaskDict]:
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
    ) -> Optional[TaskDict]:
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
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
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
        assignees: Optional[list[str]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ) -> None:
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
            label (Optional[Optional[str]]): New label.
            assignees (Optional[str]): New assignees.
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

    def delete_task(self, project_name: str, task_id: str) -> None:
        """Delete task.

        Args:
            project_name (str): Project name.
            task_id (str): Task id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/tasks/{task_id}"
        )
        response.raise_for_status()
