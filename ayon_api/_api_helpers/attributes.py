from __future__ import annotations

import copy
import time
import typing
from typing import Optional

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        AttributeSchemaDict,
        AttributeSchemaDataDict,
        AttributesSchemaDict,
        AttributeScope,
    )

class _AttributesCache:
    _schema = None
    _last_fetch = 0
    _timeout = 60
    _attributes_by_type = {}

    def reset_schema(self) -> None:
        self._schema = None
        self._last_fetch = 0
        self._attributes_by_type = {}

    def set_timeout(self, timeout: int) -> None:
        self._timeout = timeout

    def get_schema(self) -> AttributesSchemaDict:
        return copy.deepcopy(self._schema)

    def set_schema(self, schema: AttributesSchemaDict) -> None:
        self._schema = schema
        self._last_fetch = time.time()

    def is_valid(self) -> bool:
        if self._schema is None:
            return False
        return time.time() - self._last_fetch < self._timeout

    def invalidate(self) -> None:
        if not self.is_valid():
            self.reset_schema()

    def get_attributes_for_type(
        self, entity_type: AttributeScope
    ) -> list[AttributeSchemaDict]:
        attributes = self._attributes_by_type.get(entity_type)
        if attributes is not None:
            return attributes

        attributes_schema = self.get_schema()
        if attributes_schema is None:
            raise ValueError("Attributes schema is not cached.")

        attributes = []
        for attr in attributes_schema["attributes"]:
            if entity_type not in attr["scope"]:
                continue
            attributes.append(attr)

        self._attributes_by_type[entity_type] = attributes
        return attributes



class AttributesAPI(BaseServerAPI):
    _attributes_cache = _AttributesCache()

    def get_attributes_schema(
        self, use_cache: bool = True
    ) -> AttributesSchemaDict:
        if not use_cache:
            self._attributes_cache.reset_schema()
        else:
            self._attributes_cache.invalidate()

        if not self._attributes_cache.is_valid():
            result = self.get("attributes")
            result.raise_for_status()
            self._attributes_cache.set_schema(result.data)
        return self._attributes_cache.get_schema()

    def reset_attributes_schema(self) -> None:
        """Reset attributes schema cache.

        DEPRECATED:
            Use 'reset_attributes_cache' instead.

        """
        self.log.warning(
            "Used deprecated function 'reset_attributes_schema'."
            " Please use 'reset_attributes_cache' instead."
        )
        self.reset_attributes_cache()

    def reset_attributes_cache(self) -> None:
        self._attributes_cache.reset_schema()

    def set_attributes_cache_timeout(self, timeout: int) -> None:
        self._attributes_cache.set_timeout(timeout)

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
        response.raise_for_status(
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
    ) -> dict[str, AttributeSchemaDataDict]:
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
        # Make sure attributes are cached
        self.get_attributes_schema()
        return {
            attr["name"]: attr["data"]
            for attr in self._attributes_cache.get_attributes_for_type(
                entity_type
            )
        }

    def get_attributes_fields_for_type(
        self, entity_type: AttributeScope
    ) -> set[str]:
        """Prepare attribute fields for entity type.

        DEPRECATED: Field 'attrib' is marked as deprecated and should not be
            used for GraphQL queries.

        Returns:
            set[str]: Attributes fields for entity type.

        """
        self.log.warning(
            "Method 'get_attributes_fields_for_type' is deprecated and should"
            " not be used for GraphQL queries. Use 'allAttrib' field instead"
            " of 'attrib'."
        )
        attributes = self.get_attributes_for_type(entity_type)
        return {
            f"attrib.{attr}"
            for attr in attributes
        }
