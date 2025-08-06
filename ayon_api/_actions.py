import typing
from typing import Optional, Dict, List, Any

from .utils import prepare_query_string
from ._base import _BaseServerAPI

if typing.TYPE_CHECKING:
    from .typing import (
        ActionEntityTypes,
        ActionManifestDict,
        ActionTriggerResponse,
        ActionTakeResponse,
        ActionConfigResponse,
        ActionModeType,
    )


class _ActionsAPI(_BaseServerAPI):
    """Implementation of actions API for ServerAPI."""
    def get_actions(
        self,
        project_name: Optional[str] = None,
        entity_type: Optional["ActionEntityTypes"] = None,
        entity_ids: Optional[List[str]] = None,
        entity_subtypes: Optional[List[str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        *,
        variant: Optional[str] = None,
        mode: Optional["ActionModeType"] = None,
    ) -> List["ActionManifestDict"]:
        """Get actions for a context.

        Args:
            project_name (Optional[str]): Name of the project. None for global
                actions.
            entity_type (Optional[ActionEntityTypes]): Entity type where the
                action is triggered. None for global actions.
            entity_ids (Optional[List[str]]): List of entity ids where the
                action is triggered. None for global actions.
            entity_subtypes (Optional[List[str]]): List of entity subtypes
                folder types for folder ids, task types for tasks ids.
            form_data (Optional[Dict[str, Any]]): Form data of the action.
            variant (Optional[str]): Settings variant.
            mode (Optional[ActionModeType]): Action modes.

        Returns:
            List[ActionManifestDict]: List of action manifests.

        """
        if variant is None:
            variant = self.get_default_settings_variant()
        query_data = {"variant": variant}
        if mode:
            query_data["mode"] = mode
        query = prepare_query_string(query_data)
        kwargs = {
            key: value
            for key, value in (
                ("projectName", project_name),
                ("entityType", entity_type),
                ("entityIds", entity_ids),
                ("entitySubtypes", entity_subtypes),
                ("formData", form_data),
            )
            if value is not None
        }
        response = self.post(f"actions/list{query}", **kwargs)
        response.raise_for_status()
        return response.data["actions"]

    def trigger_action(
        self,
        identifier: str,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None,
        entity_type: Optional["ActionEntityTypes"] = None,
        entity_ids: Optional[List[str]] = None,
        entity_subtypes: Optional[List[str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        *,
        variant: Optional[str] = None,
    ) -> "ActionTriggerResponse":
        """Trigger action.

        Args:
            identifier (str): Identifier of the action.
            addon_name (str): Name of the addon.
            addon_version (str): Version of the addon.
            project_name (Optional[str]): Name of the project. None for global
                actions.
            entity_type (Optional[ActionEntityTypes]): Entity type where the
                action is triggered. None for global actions.
            entity_ids (Optional[List[str]]): List of entity ids where the
                action is triggered. None for global actions.
            entity_subtypes (Optional[List[str]]): List of entity subtypes
                folder types for folder ids, task types for tasks ids.
            form_data (Optional[Dict[str, Any]]): Form data of the action.
            variant (Optional[str]): Settings variant.

        """
        if variant is None:
            variant = self.get_default_settings_variant()
        query_data = {
            "addonName": addon_name,
            "addonVersion": addon_version,
            "identifier": identifier,
            "variant": variant,
        }
        query = prepare_query_string(query_data)

        kwargs = {
            key: value
            for key, value in (
                ("projectName", project_name),
                ("entityType", entity_type),
                ("entityIds", entity_ids),
                ("entitySubtypes", entity_subtypes),
                ("formData", form_data),
            )
            if value is not None
        }

        response = self.post(f"actions/execute{query}", **kwargs)
        response.raise_for_status()
        return response.data

    def get_action_config(
        self,
        identifier: str,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None,
        entity_type: Optional["ActionEntityTypes"] = None,
        entity_ids: Optional[List[str]] = None,
        entity_subtypes: Optional[List[str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        *,
        variant: Optional[str] = None,
    ) -> "ActionConfigResponse":
        """Get action configuration.

        Args:
            identifier (str): Identifier of the action.
            addon_name (str): Name of the addon.
            addon_version (str): Version of the addon.
            project_name (Optional[str]): Name of the project. None for global
                actions.
            entity_type (Optional[ActionEntityTypes]): Entity type where the
                action is triggered. None for global actions.
            entity_ids (Optional[List[str]]): List of entity ids where the
                action is triggered. None for global actions.
            entity_subtypes (Optional[List[str]]): List of entity subtypes
                folder types for folder ids, task types for tasks ids.
            form_data (Optional[Dict[str, Any]]): Form data of the action.
            variant (Optional[str]): Settings variant.

        Returns:
            ActionConfigResponse: Action configuration data.

        """
        return self._send_config_request(
            identifier,
            addon_name,
            addon_version,
            None,
            project_name,
            entity_type,
            entity_ids,
            entity_subtypes,
            form_data,
            variant,
        )

    def set_action_config(
        self,
        identifier: str,
        addon_name: str,
        addon_version: str,
        value: Dict[str, Any],
        project_name: Optional[str] = None,
        entity_type: Optional["ActionEntityTypes"] = None,
        entity_ids: Optional[List[str]] = None,
        entity_subtypes: Optional[List[str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        *,
        variant: Optional[str] = None,
    ) -> "ActionConfigResponse":
        """Set action configuration.

        Args:
            identifier (str): Identifier of the action.
            addon_name (str): Name of the addon.
            addon_version (str): Version of the addon.
            value (Optional[Dict[str, Any]]): Value of the action
                configuration.
            project_name (Optional[str]): Name of the project. None for global
                actions.
            entity_type (Optional[ActionEntityTypes]): Entity type where the
                action is triggered. None for global actions.
            entity_ids (Optional[List[str]]): List of entity ids where the
                action is triggered. None for global actions.
            entity_subtypes (Optional[List[str]]): List of entity subtypes
                folder types for folder ids, task types for tasks ids.
            form_data (Optional[Dict[str, Any]]): Form data of the action.
            variant (Optional[str]): Settings variant.

        Returns:
            ActionConfigResponse: New action configuration data.

        """
        return self._send_config_request(
            identifier,
            addon_name,
            addon_version,
            value,
            project_name,
            entity_type,
            entity_ids,
            entity_subtypes,
            form_data,
            variant,
        )

    def take_action(self, action_token: str) -> "ActionTakeResponse":
        """Take action metadata using an action token.

        Args:
            action_token (str): AYON launcher action token.

        Returns:
            ActionTakeResponse: Action metadata describing how to launch
                action.

        """
        response = self.get(f"actions/abort/{action_token}")
        response.raise_for_status()
        return response.data

    def abort_action(
        self,
        action_token: str,
        message: Optional[str] = None,
    ) -> None:
        """Abort action using an action token.

        Args:
            action_token (str): AYON launcher action token.
            message (Optional[str]): Message to display in the UI.

        """
        if message is None:
            message = "Action aborted"
        response = self.post(
            f"actions/abort/{action_token}",
            message=message,
        )
        response.raise_for_status()

    def _send_config_request(
        self,
        identifier: str,
        addon_name: str,
        addon_version: str,
        value: Optional[Dict[str, Any]],
        project_name: Optional[str],
        entity_type: Optional["ActionEntityTypes"],
        entity_ids: Optional[List[str]],
        entity_subtypes: Optional[List[str]],
        form_data: Optional[Dict[str, Any]],
        variant: Optional[str],
    ) -> "ActionConfigResponse":
        """Set and get action configuration."""
        if variant is None:
            variant = self.get_default_settings_variant()
        query_data = {
            "addonName": addon_name,
            "addonVersion": addon_version,
            "identifier": identifier,
            "variant": variant,
        }
        query = prepare_query_string(query_data)

        kwargs = {
            query_key: query_value
            for query_key, query_value in (
                ("projectName", project_name),
                ("entityType", entity_type),
                ("entityIds", entity_ids),
                ("entitySubtypes", entity_subtypes),
                ("formData", form_data),
            )
            if query_value is not None
        }
        if value is not None:
            kwargs["value"] = value

        response = self.post(f"actions/config{query}", **kwargs)
        response.raise_for_status()
        return response.data
