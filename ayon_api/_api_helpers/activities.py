from __future__ import annotations

import json
import typing
from typing import Optional, Iterable, Generator, Any

from ayon_api.utils import (
    SortOrder,
    prepare_list_filters,
)
from ayon_api.graphql_queries import activities_graphql_query

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        ActivityType,
        ActivityReferenceType,
    )


class ActivitiesAPI(BaseServerAPI):
    def get_activities(
        self,
        project_name: str,
        activity_ids: Optional[Iterable[str]] = None,
        activity_types: Optional[Iterable["ActivityType"]] = None,
        entity_ids: Optional[Iterable[str]] = None,
        entity_names: Optional[Iterable[str]] = None,
        entity_type: Optional[str] = None,
        changed_after: Optional[str] = None,
        changed_before: Optional[str] = None,
        reference_types: Optional[Iterable["ActivityReferenceType"]] = None,
        fields: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        order: Optional[SortOrder] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Get activities from server with filtering options.

        Args:
            project_name (str): Project on which activities happened.
            activity_ids (Optional[Iterable[str]]): Activity ids.
            activity_types (Optional[Iterable[ActivityType]]): Activity types.
            entity_ids (Optional[Iterable[str]]): Entity ids.
            entity_names (Optional[Iterable[str]]): Entity names.
            entity_type (Optional[str]): Entity type.
            changed_after (Optional[str]): Return only activities changed
                after given iso datetime string.
            changed_before (Optional[str]): Return only activities changed
                before given iso datetime string.
            reference_types (Optional[Iterable[ActivityReferenceType]]):
                Reference types filter. Defaults to `['origin']`.
            fields (Optional[Iterable[str]]): Fields that should be received
                for each activity.
            limit (Optional[int]): Limit number of activities to be fetched.
            order (Optional[SortOrder]): Order activities in ascending
                or descending order. It is recommended to set 'limit'
                when used descending.

        Returns:
            Generator[dict[str, Any]]: Available activities matching filters.

        """
        if not project_name:
            return
        filters = {
            "projectName": project_name,
        }
        if reference_types is None:
            reference_types = {"origin"}

        if not prepare_list_filters(
            filters,
            ("activityIds", activity_ids),
            ("activityTypes", activity_types),
            ("entityIds", entity_ids),
            ("entityNames", entity_names),
            ("referenceTypes", reference_types),
        ):
            return

        for filter_key, filter_value in (
            ("entityType", entity_type),
            ("changedAfter", changed_after),
            ("changedBefore", changed_before),
        ):
            if filter_value is not None:
                filters[filter_key] = filter_value

        if not fields:
            fields = self.get_default_fields_for_type("activity")

        query = activities_graphql_query(set(fields), order)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        if limit:
            activities_field = query.get_field_by_path("activities")
            activities_field.set_limit(limit)

        for parsed_data in query.continuous_query(self):
            for activity in parsed_data["project"]["activities"]:
                activity_data = activity.get("activityData")
                if isinstance(activity_data, str):
                    activity["activityData"] = json.loads(activity_data)
                yield activity

    def get_activity_by_id(
        self,
        project_name: str,
        activity_id: str,
        reference_types: Optional[Iterable["ActivityReferenceType"]] = None,
        fields: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Get activity by id.

        Args:
            project_name (str): Project on which activity happened.
            activity_id (str): Activity id.
            reference_types: Optional[Iterable[ActivityReferenceType]]: Filter
                by reference types.
            fields (Optional[Iterable[str]]): Fields that should be received
                for each activity.

        Returns:
            Optional[dict[str, Any]]: Activity data or None if activity is not
                found.

        """
        for activity in self.get_activities(
            project_name=project_name,
            activity_ids={activity_id},
            reference_types=reference_types,
            fields=fields,
        ):
            return activity
        return None

    def create_activity(
        self,
        project_name: str,
        entity_id: str,
        entity_type: str,
        activity_type: "ActivityType",
        activity_id: Optional[str] = None,
        body: Optional[str] = None,
        file_ids: Optional[list[str]] = None,
        timestamp: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create activity on a project.

        Args:
            project_name (str): Project on which activity happened.
            entity_id (str): Entity id.
            entity_type (str): Entity type.
            activity_type (ActivityType): Activity type.
            activity_id (Optional[str]): Activity id.
            body (Optional[str]): Activity body.
            file_ids (Optional[list[str]]): List of file ids attached
                to activity.
            timestamp (Optional[str]): Activity timestamp.
            data (Optional[dict[str, Any]]): Additional data.

        Returns:
            str: Activity id.

        """
        post_data = {
            "activityType": activity_type,
        }
        for key, value in (
            ("id", activity_id),
            ("body", body),
            ("files", file_ids),
            ("timestamp", timestamp),
            ("data", data),
        ):
            if value is not None:
                post_data[key] = value

        response = self.post(
            f"projects/{project_name}/{entity_type}/{entity_id}/activities",
            **post_data
        )
        response.raise_for_status()
        return response.data["id"]

    def update_activity(
        self,
        project_name: str,
        activity_id: str,
        body: Optional[str] = None,
        file_ids: Optional[list[str]] = None,
        append_file_ids: Optional[bool] = False,
        data: Optional[dict[str, Any]] = None,
    ):
        """Update activity by id.

        Args:
            project_name (str): Project on which activity happened.
            activity_id (str): Activity id.
            body (str): Activity body.
            file_ids (Optional[list[str]]): List of file ids attached
                to activity.
            append_file_ids (Optional[bool]): Append file ids to existing
                list of file ids.
            data (Optional[dict[str, Any]]): Update data in activity.

        """
        update_data = {}
        major, minor, patch, _, _ = self.get_server_version_tuple()
        new_patch_model = (major, minor, patch) > (1, 5, 6)
        if body is None and not new_patch_model:
            raise ValueError(
                "Update without 'body' is supported"
                " after server version 1.5.6."
            )

        if body is not None:
            update_data["body"] = body

        if file_ids is not None:
            update_data["files"] = file_ids
            if new_patch_model:
                update_data["appendFiles"] = append_file_ids
            elif append_file_ids:
                raise ValueError(
                    "Append file ids is supported after server version 1.5.6."
                )

        if data is not None:
            if not new_patch_model:
                raise ValueError(
                    "Update of data is supported after server version 1.5.6."
                )
            update_data["data"] = data

        response = self.patch(
            f"projects/{project_name}/activities/{activity_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_activity(self, project_name: str, activity_id: str):
        """Delete activity by id.

        Args:
            project_name (str): Project on which activity happened.
            activity_id (str): Activity id to remove.

        """
        response = self.delete(
            f"projects/{project_name}/activities/{activity_id}"
        )
        response.raise_for_status()

    def send_activities_batch_operations(
        self,
        project_name: str,
        operations: list[dict[str, Any]],
        can_fail: bool = False,
        raise_on_fail: bool = True
    ) -> list[dict[str, Any]]:
        """Post multiple CRUD activities operations to server.

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
            f"projects/{project_name}/operations/activities",
            operations,
            can_fail,
            raise_on_fail,
        )
