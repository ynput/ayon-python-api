from __future__ import annotations

import json
import typing
from typing import Optional, Iterable, Any, Generator

from ayon_api.utils import create_entity_id
from ayon_api.graphql_queries import entity_lists_graphql_query

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        EntityListEntityType,
        EntityListAttributeDefinitionDict,
        EntityListItemMode,
    )


class ListsAPI(BaseServerAPI):
    def get_entity_lists(
        self,
        project_name: str,
        *,
        list_ids: Optional[Iterable[str]] = None,
        active: Optional[bool] = None,
        fields: Optional[Iterable[str]] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch entity lists from AYON server.

        Warnings:
            You can't get list items for lists with different 'entityType' in
                one call.

        Notes:
            To get list items, you have to pass 'items' field or
                'items.{sub-fields you want}' to 'fields' argument.

        Args:
            project_name (str): Project name where entity lists are.
            list_ids (Optional[Iterable[str]]): List of entity list ids to
                fetch.
            active (Optional[bool]): Filter by active state of entity lists.
            fields (Optional[Iterable[str]]): Fields to fetch from server.

        Returns:
            Generator[dict[str, Any], None, None]: Entity list entities
                matching defined filters.

        """
        if fields is None:
            fields = self.get_default_fields_for_type("entityList")
        fields = set(fields)
        if "items" in fields:
            fields.discard("items")
            fields |= {
                "items.id",
                "items.entityId",
                "items.entityType",
                "items.position",
            }

        if active is not None:
            fields.add("active")

        filters: dict[str, Any] = {"projectName": project_name}
        if list_ids is not None:
            if not list_ids:
                return
            filters["listIds"] = list(set(list_ids))

        query = entity_lists_graphql_query(fields)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for entity_list in parsed_data["project"]["entityLists"]:
                if active is not None and entity_list["active"] != active:
                    continue

                attributes = entity_list.get("attributes")
                if isinstance(attributes, str):
                    entity_list["attributes"] = json.loads(attributes)

                self._convert_entity_data(entity_list)

                yield entity_list

    def get_entity_list_rest(
        self, project_name: str, list_id: str
    ) -> Optional[dict[str, Any]]:
        """Get entity list by id using REST API.

        Args:
            project_name (str): Project name.
            list_id (str): Entity list id.

        Returns:
            Optional[dict[str, Any]]: Entity list data or None if not found.

        """
        response = self.get(f"projects/{project_name}/lists/{list_id}")
        response.raise_for_status()
        return response.data

    def get_entity_list_by_id(
        self,
        project_name: str,
        list_id: str,
        fields: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Get entity list by id using GraphQl.

        Args:
            project_name (str): Project name.
            list_id (str): Entity list id.
            fields (Optional[Iterable[str]]): Fields to fetch from server.

        Returns:
            Optional[dict[str, Any]]: Entity list data or None if not found.

        """
        for entity_list in self.get_entity_lists(
            project_name, list_ids=[list_id], active=None, fields=fields
        ):
            return entity_list
        return None

    def create_entity_list(
        self,
        project_name: str,
        entity_type: EntityListEntityType,
        label: str,
        *,
        list_type: Optional[str] = None,
        access: Optional[dict[str, Any]] = None,
        attrib: Optional[list[dict[str, Any]]] = None,
        data: Optional[list[dict[str, Any]]] = None,
        tags: Optional[list[str]] = None,
        template: Optional[dict[str, Any]] = None,
        owner: Optional[str] = None,
        active: Optional[bool] = None,
        items: Optional[list[dict[str, Any]]] = None,
        list_id: Optional[str] = None,
    ) -> str:
        """Create entity list.

        Args:
            project_name (str): Project name where entity list lives.
            entity_type (EntityListEntityType): Which entity types can be
                used in list.
            label (str): Entity list label.
            list_type (Optional[str]): Entity list type.
            access (Optional[dict[str, Any]]): Access control for entity list.
            attrib (Optional[dict[str, Any]]): Attribute values of
                entity list.
            data (Optional[dict[str, Any]]): Custom data of entity list.
            tags (Optional[list[str]]): Entity list tags.
            template (Optional[dict[str, Any]]): Dynamic list template.
            owner (Optional[str]): New owner of the list.
            active (Optional[bool]): Change active state of entity list.
            items (Optional[list[dict[str, Any]]]): Initial items in
                entity list.
            list_id (Optional[str]): Entity list id.

        """
        if list_id is None:
            list_id = create_entity_id()
        kwargs = {
            "id": list_id,
            "entityType": entity_type,
            "label": label,
        }
        for key, value in (
            ("entityListType", list_type),
            ("access", access),
            ("attrib", attrib),
            ("template", template),
            ("tags", tags),
            ("owner", owner),
            ("data", data),
            ("active", active),
            ("items", items),
        ):
            if value is not None:
                kwargs[key] = value

        response = self.post(
            f"projects/{project_name}/lists/{list_id}/items",
            **kwargs

        )
        response.raise_for_status()
        return list_id

    def update_entity_list(
        self,
        project_name: str,
        list_id: str,
        *,
        label: Optional[str] = None,
        access: Optional[dict[str, Any]] = None,
        attrib: Optional[list[dict[str, Any]]] = None,
        data: Optional[list[dict[str, Any]]] = None,
        tags: Optional[list[str]] = None,
        owner: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Update entity list.

        Args:
            project_name (str): Project name where entity list lives.
            list_id (str): Entity list id that will be updated.
            label (Optional[str]): New label of entity list.
            access (Optional[dict[str, Any]]): Access control for entity list.
            attrib (Optional[dict[str, Any]]): Attribute values of
                entity list.
            data (Optional[dict[str, Any]]): Custom data of entity list.
            tags (Optional[list[str]]): Entity list tags.
            owner (Optional[str]): New owner of the list.
            active (Optional[bool]): Change active state of entity list.

        """
        kwargs = {
            key: value
            for key, value in (
                ("label", label),
                ("access", access),
                ("attrib", attrib),
                ("data", data),
                ("tags", tags),
                ("owner", owner),
                ("active", active),
            )
            if value is not None
        }
        response = self.patch(
            f"projects/{project_name}/lists/{list_id}",
            **kwargs
        )
        response.raise_for_status()

    def delete_entity_list(self, project_name: str, list_id: str) -> None:
        """Delete entity list from project.

        Args:
            project_name (str): Project name.
            list_id (str): Entity list id that will be removed.

        """
        response = self.delete(f"projects/{project_name}/lists/{list_id}")
        response.raise_for_status()

    def get_entity_list_attribute_definitions(
        self, project_name: str, list_id: str
    ) -> list[EntityListAttributeDefinitionDict]:
        """Get attribute definitioins on entity list.

        Args:
            project_name (str): Project name.
            list_id (str): Entity list id.

        Returns:
            list[EntityListAttributeDefinitionDict]: List of attribute
                definitions.

        """
        response = self.get(
            f"projects/{project_name}/lists/{list_id}/attributes"
        )
        response.raise_for_status()
        return response.data

    def set_entity_list_attribute_definitions(
        self,
        project_name: str,
        list_id: str,
        attribute_definitions: list[EntityListAttributeDefinitionDict],
    ) -> None:
        """Set attribute definitioins on entity list.

        Args:
            project_name (str): Project name.
            list_id (str): Entity list id.
            attribute_definitions (list[EntityListAttributeDefinitionDict]):
                List of attribute definitions.

        """
        response = self.raw_put(
            f"projects/{project_name}/lists/{list_id}/attributes",
            json=attribute_definitions,
        )
        response.raise_for_status()

    def create_entity_list_item(
        self,
        project_name: str,
        list_id: str,
        *,
        position: Optional[int] = None,
        label: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        item_id: Optional[str] = None,
    ) -> str:
        """Create entity list item.

        Args:
            project_name (str): Project name where entity list lives.
            list_id (str): Entity list id where item will be added.
            position (Optional[int]): Position of item in entity list.
            label (Optional[str]): Label of item in entity list.
            attrib (Optional[dict[str, Any]]): Item attribute values.
            data (Optional[dict[str, Any]]): Item data.
            tags (Optional[list[str]]): Tags of item in entity list.
            item_id (Optional[str]): Id of item that will be created.

        Returns:
            str: Item id.

        """
        if item_id is None:
            item_id = create_entity_id()
        kwargs = {
            "id": item_id,
            "entityId": list_id,
        }
        for key, value in (
            ("position", position),
            ("label", label),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
        ):
            if value is not None:
                kwargs[key] = value

        response = self.post(
            f"projects/{project_name}/lists/{list_id}/items",
            **kwargs
        )
        response.raise_for_status()
        return item_id

    def update_entity_list_items(
        self,
        project_name: str,
        list_id: str,
        items: list[dict[str, Any]],
        mode: EntityListItemMode,
    ) -> None:
        """Update items in entity list.

        Args:
            project_name (str): Project name where entity list live.
            list_id (str): Entity list id.
            items (list[dict[str, Any]]): Entity list items.
            mode (EntityListItemMode): Mode of items update.

        """
        response = self.post(
            f"projects/{project_name}/lists/{list_id}/items",
            items=items,
            mode=mode,
        )
        response.raise_for_status()

    def update_entity_list_item(
        self,
        project_name: str,
        list_id: str,
        item_id: str,
        *,
        new_list_id: Optional[str],
        position: Optional[int] = None,
        label: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Update item in entity list.

        Args:
            project_name (str): Project name where entity list live.
            list_id (str): Entity list id where item lives.
            item_id (str): Item id that will be removed from entity list.
            new_list_id (Optional[str]): New entity list id where item will be
                added.
            position (Optional[int]): Position of item in entity list.
            label (Optional[str]): Label of item in entity list.
            attrib (Optional[dict[str, Any]]): Attributes of item in entity
                list.
            data (Optional[dict[str, Any]]): Custom data of item in
                entity list.
            tags (Optional[list[str]]): Tags of item in entity list.

        """
        kwargs = {}
        for key, value in (
            ("entityId", new_list_id),
            ("position", position),
            ("label", label),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
        ):
            if value is not None:
                kwargs[key] = value
        response = self.patch(
            f"projects/{project_name}/lists/{list_id}/items/{item_id}",
            **kwargs,
        )
        response.raise_for_status()

    def delete_entity_list_item(
        self,
        project_name: str,
        list_id: str,
        item_id: str,
    ) -> None:
        """Delete item from entity list.

        Args:
            project_name (str): Project name where entity list live.
            list_id (str): Entity list id from which item will be removed.
            item_id (str): Item id that will be removed from entity list.

        """
        response = self.delete(
            f"projects/{project_name}/lists/{list_id}/items/{item_id}",
        )
        response.raise_for_status()
