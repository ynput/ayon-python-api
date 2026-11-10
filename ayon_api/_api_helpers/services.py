from __future__ import annotations

from typing import Optional, Any

from ayon_api.exceptions import UnsupportedServerVersion

from .base import BaseServerAPI


class ServicesAPI(BaseServerAPI):
    def get_services(self) -> list[dict[str, Any]]:
        """Get addon services registered on server.

        Only administrators receive the services, other users get an
            empty list.

        Returns:
            list[dict[str, Any]]: List of services.

        """
        response = self.get("services")
        response.raise_for_status()
        return response.data["services"]

    def spawn_service(
        self,
        service_name: str,
        addon_name: str,
        addon_version: str,
        service: str,
        hostname: str,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """Spawn (create) a new addon service.

        Requires administrator privileges.

        Args:
            service_name (str): Unique name of the service.
            addon_name (str): Name of addon that provides the service.
            addon_version (str): Version of addon.
            service (str): Name of service defined by the addon.
            hostname (str): Name of host (ASH) where service should run.
            config (Optional[dict[str, Any]]): Service configuration
                e.g. 'volumes', 'ports', 'memLimit', 'user', 'env',
                'storagePath' or 'registryAuth'.
                'registryAuth' is ignored by AYON server older than 1.16.7.

        """
        body: dict[str, Any] = {
            "addonName": addon_name,
            "addonVersion": addon_version,
            "service": service,
            "hostname": hostname,
        }
        if config is not None:
            body["config"] = config
        response = self.put(f"services/{service_name}", **body)
        response.raise_for_status()

    def update_service(
        self,
        service_name: str,
        should_run: Optional[bool] = None,
        hostname: Optional[str] = None,
        error: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update addon service.

        Requires administrator privileges.

        Args:
            service_name (str): Name of the service.
            should_run (Optional[bool]): Service should be running.
            hostname (Optional[str]): Name of host where service should run.
            error (Optional[str]): Error message. Ignored when service
                should be running.
            config (Optional[dict[str, Any]]): Service configuration
                values to change e.g. 'volumes', 'ports', 'memLimit',
                'user', 'env', 'storagePath' or 'registryAuth'.
                'registryAuth' is ignored by AYON server older than 1.16.7.

        Raises:
            UnsupportedServerVersion: 'error' is used with server version
                lower than 1.16.7.

        """
        if (
            error is not None
            and self.get_server_version_tuple() < (1, 16, 7)
        ):
            raise UnsupportedServerVersion(
                "Argument 'error' of 'update_service' is supported"
                " for AYON server 1.16.7 and above."
            )
        body: dict[str, Any] = {}
        if config:
            body.update(config)
        for key, value in (
            ("shouldRun", should_run),
            ("hostname", hostname),
            ("error", error),
        ):
            if value is not None:
                body[key] = value

        response = self.patch(f"services/{service_name}", **body)
        response.raise_for_status()

    def delete_service(self, service_name: str) -> None:
        """Delete addon service.

        Requires administrator privileges.

        Args:
            service_name (str): Name of the service.

        """
        response = self.delete(f"services/{service_name}")
        response.raise_for_status()

    def get_hosts(self) -> list[dict[str, Any]]:
        """Get AYON service hosts (ASH) registered on server.

        Host is registered automatically when it sends heartbeat to server.

        Example output::

            [
                {
                    "name": "my-host",
                    "lastSeen": "2025-01-01T00:00:00",
                    "health": {"cpu": 0.5, "mem": 42.0},
                }
            ]

        Returns:
            list[dict[str, Any]]: List of hosts.

        """
        response = self.get("hosts")
        response.raise_for_status()
        return response.data["hosts"]
