from __future__ import annotations

from typing import Optional, Any

from ayon_api.exceptions import UnsupportedServerVersion
from ayon_api.utils import prepare_query_string

from .base import BaseServerAPI


class SystemAPI(BaseServerAPI):
    def get_sites(
        self,
        platform_name: Optional[str] = None,
        hostname: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get sites registered on server.

        Non-manager users receive only sites they have used.

        Example output::

            [
                {
                    "id": "site-id",
                    "platform": "windows",
                    "hostname": "my-machine",
                    "version": "1.0.0",
                    "users": ["admin"],
                }
            ]

        Args:
            platform_name (Optional[str]): Filter sites by platform name.
                Possible values are 'windows', 'linux' and 'darwin'.
            hostname (Optional[str]): Filter sites by machine hostname.

        Returns:
            list[dict[str, Any]]: List of sites.

        """
        query = prepare_query_string({
            "platform": platform_name or None,
            "hostname": hostname or None,
        })
        response = self.get(f"system/sites{query}")
        response.raise_for_status()
        return response.data

    def delete_site(self, site_id: str) -> None:
        """Unregister site from server.

        Requires administrator privileges.

        Args:
            site_id (str): Site id.

        """
        response = self.delete(f"system/sites/{site_id}")
        response.raise_for_status()

    def get_restart_required(self) -> dict[str, Any]:
        """Get information whether server requires restart.

        Example output::

            {
                "required": True,
                "reason": "Server restart is required",
            }

        Returns:
            dict[str, Any]: Restart required information with keys
                'required' and 'reason'.

        """
        response = self.get("system/restartRequired")
        response.raise_for_status()
        return response.data

    def set_restart_required(
        self,
        required: bool,
        reason: Optional[str] = None,
    ) -> None:
        """Set or clear the server restart required flag.

        This notifies administrators that the server needs to be restarted.
            Use 'trigger_server_restart' to actually restart the server.

        Args:
            required (bool): Server requires restart.
            reason (Optional[str]): Human-readable reason for the restart.

        """
        body: dict[str, Any] = {"required": required}
        if reason is not None:
            body["reason"] = reason
        response = self.post("system/restartRequired", **body)
        response.raise_for_status()

    def get_server_config_schema(self) -> dict[str, Any]:
        """Get JSON schema of server configuration.

        Returns:
            dict[str, Any]: Server configuration schema.

        """
        response = self.get("config/schema")
        response.raise_for_status()
        return response.data

    def update_server_config(self, config: dict[str, Any]) -> None:
        """Partially update server configuration.

        Values are recursively merged into current server configuration.
            Keys that are not passed remain unchanged. Use the same
            structure as 'get_server_config' returns, e.g.
            '{"studio_name": "My Studio"}'.

        Requires administrator privileges.

        Args:
            config (dict[str, Any]): Server configuration values to change.

        Raises:
            UnsupportedServerVersion: Server version is lower than 1.15.9.

        """
        if self.get_server_version_tuple() < (1, 15, 9):
            raise UnsupportedServerVersion(
                "Function 'update_server_config' is supported"
                " for AYON server 1.15.9 and above."
            )
        response = self.raw_patch("config", json=config)
        response.raise_for_status()

    def get_enums(self) -> list[dict[str, Any]]:
        """Get available enum resolvers.

        Example output::

            [
                {
                    "name": "statuses",
                    "label": "Statuses",
                    ...
                }
            ]

        Returns:
            list[dict[str, Any]]: List of enum resolvers information.

        Raises:
            UnsupportedServerVersion: Server version is lower than 1.16.4.

        """
        if self.get_server_version_tuple() < (1, 16, 4):
            raise UnsupportedServerVersion(
                "Function 'get_enums' is supported"
                " for AYON server 1.16.4 and above."
            )
        response = self.get("enum")
        response.raise_for_status()
        return response.data

    def get_enum(
        self,
        enum_name: str,
        project_name: Optional[str] = None,
        user_name: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Get enum items resolved by server.

        Accepted context values depend on the enum resolver, use 'get_enums'
            to find out which parameters a resolver accepts.

        Example output::

            [
                {
                    "value": "in_progress",
                    "label": "In progress",
                    ...
                }
            ]

        Args:
            enum_name (str): Name of the enum e.g. 'statuses'.
            project_name (Optional[str]): Project name for project context.
            user_name (Optional[str]): Resolve enum for different user.
                Only administrators can use this.
            context (Optional[dict[str, Any]]): Additional context
                parameters for the resolver. Lists are joined with comma.

        Returns:
            list[dict[str, Any]]: List of enum items.

        """
        query_data: dict[str, Any] = {}
        if context:
            for key, value in context.items():
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, (list, tuple, set)):
                    value = ",".join(str(item) for item in value)
                query_data[key] = value

        if project_name is not None:
            query_data["project_name"] = project_name
        if user_name is not None:
            query_data["user"] = user_name

        query = prepare_query_string(query_data)
        response = self.get(f"enum/{enum_name}{query}")
        response.raise_for_status()
        return response.data
