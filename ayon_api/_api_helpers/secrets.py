from __future__ import annotations

import typing

from .base import BaseServerAPI
if typing.TYPE_CHECKING:
    from ayon_api.typing import SecretDict


class SecretsAPI(BaseServerAPI):
    def get_secrets(self) -> list[SecretDict]:
        """Get all secrets.

        Example output::

            [
                {
                    "name": "secret_1",
                    "value": "secret_value_1",
                },
                {
                    "name": "secret_2",
                    "value": "secret_value_2",
                }
            ]

        Returns:
            list[SecretDict]: List of secret entities.

        """
        response = self.get("secrets")
        response.raise_for_status()
        return response.data

    def get_secret(self, secret_name: str) -> SecretDict:
        """Get secret by name.

        Example output::

            {
                "name": "secret_name",
                "value": "secret_value",
            }

        Args:
            secret_name (str): Name of secret.

        Returns:
            dict[str, str]: Secret entity data.

        """
        response = self.get(f"secrets/{secret_name}")
        response.raise_for_status()
        return response.data

    def save_secret(self, secret_name: str, secret_value: str) -> None:
        """Save secret.

        This endpoint can create and update secret.

        Args:
            secret_name (str): Name of secret.
            secret_value (str): Value of secret.

        """
        response = self.put(
            f"secrets/{secret_name}",
            name=secret_name,
            value=secret_value,
        )
        response.raise_for_status()

    def delete_secret(self, secret_name: str) -> None:
        """Delete secret by name.

        Args:
            secret_name (str): Name of secret to delete.

        """
        response = self.delete(f"secrets/{secret_name}")
        response.raise_for_status()
