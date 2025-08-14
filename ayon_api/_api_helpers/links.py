from __future__ import annotations

import collections
import typing
from typing import Optional, Any, Iterable

from ayon_api.graphql_queries import (
    folders_graphql_query,
    tasks_graphql_query,
    products_graphql_query,
    versions_graphql_query,
    representations_graphql_query,
)

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import LinkDirection


class LinksAPI(BaseServerAPI):
    def get_full_link_type_name(
        self, link_type_name: str, input_type: str, output_type: str
    ) -> str:
        """Calculate full link type name used for query from server.

        Args:
            link_type_name (str): Type of link.
            input_type (str): Input entity type of link.
            output_type (str): Output entity type of link.

        Returns:
            str: Full name of link type used for query from server.

        """
        return "|".join([link_type_name, input_type, output_type])

    def get_link_types(self, project_name: str) -> list[dict[str, Any]]:
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
        response = self.get(f"projects/{project_name}/links/types")
        response.raise_for_status()
        return response.data["types"]

    def get_link_type(
        self,
        project_name: str,
        link_type_name: str,
        input_type: str,
        output_type: str,
    ) -> Optional[dict[str, Any]]:
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
            Optional[dict[str, Any]]: Link type information.

        """
        full_type_name = self.get_full_link_type_name(
            link_type_name, input_type, output_type
        )
        for link_type in self.get_link_types(project_name):
            if link_type["name"] == full_type_name:
                return link_type
        return None

    def create_link_type(
        self,
        project_name: str,
        link_type_name: str,
        input_type: str,
        output_type: str,
        data: Optional[dict[str, Any]] = None,
    ):
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
        if data is None:
            data = {}
        full_type_name = self.get_full_link_type_name(
            link_type_name, input_type, output_type
        )
        response = self.put(
            f"projects/{project_name}/links/types/{full_type_name}",
            **data
        )
        response.raise_for_status()

    def delete_link_type(
        self,
        project_name: str,
        link_type_name: str,
        input_type: str,
        output_type: str,
    ):
        """Remove link type from project.

        Args:
            project_name (str): Project where link type is created.
            link_type_name (str): Name of link type.
            input_type (str): Input entity type of link.
            output_type (str): Output entity type of link.

        Raises:
            HTTPRequestError: Server error happened.

        """
        full_type_name = self.get_full_link_type_name(
            link_type_name, input_type, output_type
        )
        response = self.delete(
            f"projects/{project_name}/links/types/{full_type_name}"
        )
        response.raise_for_status()

    def make_sure_link_type_exists(
        self,
        project_name: str,
        link_type_name: str,
        input_type: str,
        output_type: str,
        data: Optional[dict[str, Any]] = None,
    ):
        """Make sure link type exists on a project.

        Args:
            project_name (str): Name of project.
            link_type_name (str): Name of link type.
            input_type (str): Input entity type of link.
            output_type (str): Output entity type of link.
            data (Optional[dict[str, Any]]): Link type related data.

        """
        link_type = self.get_link_type(
            project_name, link_type_name, input_type, output_type)
        if (
            link_type
            and (data is None or data == link_type["data"])
        ):
            return
        self.create_link_type(
            project_name, link_type_name, input_type, output_type, data
        )

    def create_link(
        self,
        project_name: str,
        link_type_name: str,
        input_id: str,
        input_type: str,
        output_id: str,
        output_type: str,
        link_name: Optional[str] = None,
    ):
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
        full_link_type_name = self.get_full_link_type_name(
            link_type_name, input_type, output_type)

        kwargs = {
            "input": input_id,
            "output": output_id,
            "linkType": full_link_type_name,
        }
        if link_name:
            kwargs["name"] = link_name

        response = self.post(
            f"projects/{project_name}/links", **kwargs
        )
        response.raise_for_status()
        return response.data

    def delete_link(self, project_name: str, link_id: str):
        """Remove link by id.

        Args:
            project_name (str): Project where link exists.
            link_id (str): Id of link.

        Raises:
            HTTPRequestError: Server error happened.

        """
        response = self.delete(
            f"projects/{project_name}/links/{link_id}"
        )
        response.raise_for_status()

    def _prepare_link_filters(
        self,
        filters: dict[str, Any],
        link_types: Optional[Iterable[str], None],
        link_direction: Optional["LinkDirection"],
        link_names: Optional[Iterable[str]],
        link_name_regex: Optional[str],
    ) -> bool:
        """Add links filters for GraphQl queries.

        Args:
            filters (dict[str, Any]): Object where filters will be added.
            link_types (Optional[Iterable[str]]): Link types filters.
            link_direction (Optional[Literal["in", "out"]]): Direction of
                link "in", "out" or 'None' for both.
            link_names (Optional[Iterable[str]]): Link name filters.
            link_name_regex (Optional[str]): Regex filter for link name.

        Returns:
            bool: Links are valid, and query from server can happen.

        """
        if link_types is not None:
            link_types = set(link_types)
            if not link_types:
                return False
            filters["linkTypes"] = list(link_types)

        if link_names is not None:
            link_names = set(link_names)
            if not link_names:
                return False
            filters["linkNames"] = list(link_names)

        if link_direction is not None:
            if link_direction not in ("in", "out"):
                return False
            filters["linkDirection"] = link_direction

        if link_name_regex is not None:
            filters["linkNameRegex"] = link_name_regex
        return True

    def get_entities_links(
        self,
        project_name: str,
        entity_type: str,
        entity_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
        link_names: Optional[Iterable[str]] = None,
        link_name_regex: Optional[str] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
                "version", "representations"]): Entity type.
            entity_ids (Optional[Iterable[str]]): Ids of entities for which
                links should be received.
            link_types (Optional[Iterable[str]]): Link type filters.
            link_direction (Optional[Literal["in", "out"]]): Link direction
                filter.
            link_names (Optional[Iterable[str]]): Link name filters.
            link_name_regex (Optional[str]): Regex filter for link name.

        Returns:
            dict[str, list[dict[str, Any]]]: Link info by entity ids.

        """
        if entity_type == "folder":
            query_func = folders_graphql_query
            id_filter_key = "folderIds"
            project_sub_key = "folders"
        elif entity_type == "task":
            query_func = tasks_graphql_query
            id_filter_key = "taskIds"
            project_sub_key = "tasks"
        elif entity_type == "product":
            query_func = products_graphql_query
            id_filter_key = "productIds"
            project_sub_key = "products"
        elif entity_type == "version":
            query_func = versions_graphql_query
            id_filter_key = "versionIds"
            project_sub_key = "versions"
        elif entity_type == "representation":
            query_func = representations_graphql_query
            id_filter_key = "representationIds"
            project_sub_key = "representations"
        else:
            raise ValueError("Unknown type \"{}\". Expected {}".format(
                entity_type,
                ", ".join(
                    ("folder", "task", "product", "version", "representation")
                )
            ))

        output = collections.defaultdict(list)
        filters = {
            "projectName": project_name
        }
        if entity_ids is not None:
            entity_ids = set(entity_ids)
            if not entity_ids:
                return output
            filters[id_filter_key] = list(entity_ids)

        if not self._prepare_link_filters(
            filters, link_types, link_direction, link_names, link_name_regex
        ):
            return output

        link_fields = {"id", "links"}
        query = query_func(link_fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for entity in parsed_data["project"][project_sub_key]:
                entity_id = entity["id"]
                output[entity_id].extend(entity["links"])
        return output

    def get_folders_links(
        self,
        project_name: str,
        folder_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
        return self.get_entities_links(
            project_name, "folder", folder_ids, link_types, link_direction
        )

    def get_folder_links(
        self,
        project_name: str,
        folder_id: str,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> list[dict[str, Any]]:
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
        return self.get_folders_links(
            project_name, [folder_id], link_types, link_direction
        )[folder_id]

    def get_tasks_links(
        self,
        project_name: str,
        task_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
        return self.get_entities_links(
            project_name, "task", task_ids, link_types, link_direction
        )

    def get_task_links(
        self,
        project_name: str,
        task_id: str,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> list[dict[str, Any]]:
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
        return self.get_tasks_links(
            project_name, [task_id], link_types, link_direction
        )[task_id]

    def get_products_links(
        self,
        project_name: str,
        product_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
        return self.get_entities_links(
            project_name, "product", product_ids, link_types, link_direction
        )

    def get_product_links(
        self,
        project_name: str,
        product_id: str,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> list[dict[str, Any]]:
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
        return self.get_products_links(
            project_name, [product_id], link_types, link_direction
        )[product_id]

    def get_versions_links(
        self,
        project_name: str,
        version_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
        return self.get_entities_links(
            project_name, "version", version_ids, link_types, link_direction
        )

    def get_version_links(
        self,
        project_name: str,
        version_id: str,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> list[dict[str, Any]]:
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
        return self.get_versions_links(
            project_name, [version_id], link_types, link_direction
        )[version_id]

    def get_representations_links(
        self,
        project_name: str,
        representation_ids: Optional[Iterable[str]] = None,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None,
    ) -> dict[str, list[dict[str, Any]]]:
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
        return self.get_entities_links(
            project_name,
            "representation",
            representation_ids,
            link_types,
            link_direction
        )

    def get_representation_links(
        self,
        project_name: str,
        representation_id: str,
        link_types: Optional[Iterable[str]] = None,
        link_direction: Optional["LinkDirection"] = None
    ) -> list[dict[str, Any]]:
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
        return self.get_representations_links(
            project_name, [representation_id], link_types, link_direction
        )[representation_id]