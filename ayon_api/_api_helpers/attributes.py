from __future__ import annotations

import typing
from typing import Optional
import copy

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        AttributeSchemaDataDict,
        AttributeSchemaDict,
        AttributesSchemaDict,
        AttributeScope,
    )


class AttributesAPI(BaseServerAPI):
    _attributes_schema = None
    _entity_type_attributes_cache = {}

    def get_attributes_schema(
        self, use_cache: bool = True
    ) -> AttributesSchemaDict:
        if not use_cache:
            self.reset_attributes_schema()

        if self._attributes_schema is None:
            result = self.get("attributes")
            result.raise_for_status()
            self._attributes_schema = result.data
        return copy.deepcopy(self._attributes_schema)

    def reset_attributes_schema(self) -> None:
        self._attributes_schema = None
        self._entity_type_attributes_cache = {}

    def set_attribute_config(
        self,
        attribute_name: str,
        data: AttributeSchemaDataDict,
        scope: list[AttributeScope],
        position: Optional[int] = None,
        builtin: bool = False,
    ) -> None:
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
            f"attributes/{attribute_name}",
            data=data,
            scope=scope,
            position=position,
            builtin=builtin
        )
        if response.status_code != 204:
            # TODO raise different exception
            raise ValueError(
                f"Attribute \"{attribute_name}\" was not created/updated."
                f" {response.detail}"
            )

        self.reset_attributes_schema()

    def remove_attribute_config(self, attribute_name: str) -> None:
        """Remove attribute from server.

        This can't be un-done, please use carefully.

        Args:
            attribute_name (str): Name of attribute to remove.

        """
        response = self.delete(f"attributes/{attribute_name}")
        response.raise_for_status(
            f"Attribute \"{attribute_name}\" was not created/updated."
            f" {response.detail}"
        )

        self.reset_attributes_schema()

    def get_attributes_for_type(
        self, entity_type: AttributeScope
    ) -> dict[str, AttributeSchemaDict]:
        """Get attribute schemas available for an entity type.

        Example::

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
            dict[str, dict[str, Any]]: Attribute schemas that are available
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

    def get_attributes_fields_for_type(
        self, entity_type: AttributeScope
    ) -> set[str]:
        """Prepare attribute fields for entity type.

        Returns:
            set[str]: Attributes fields for entity type.

        """
        attributes = self.get_attributes_for_type(entity_type)
        return {
            f"attrib.{attr}"
            for attr in attributes
        }
