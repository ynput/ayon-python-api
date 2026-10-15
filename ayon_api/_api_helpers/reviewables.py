from __future__ import annotations

import typing
from typing import Any, Iterable, Optional

from ayon_api.utils import prepare_query_string

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import ReviewablesEntityType


class ReviewablesAPI(BaseServerAPI):
    def get_reviewables(
        self,
        project_name: str,
        entity_type: ReviewablesEntityType,
        entity_ids: Iterable[str],
        *,
        latest: bool = False,
        latest_done: bool = False,
    ) -> list[dict[str, Any]]:
        """Get reviewables for multiple entities of one entity type.

        Each item in output represents a version with its reviewables.

        Args:
            project_name (str): Project name.
            entity_type (ReviewablesEntityType): Entity type of passed
                entity ids. Supported types are 'folder', 'product',
                'version' and 'task'.
            entity_ids (Iterable[str]): Entity ids for which reviewables
                should be returned.
            latest (bool): Return only reviewables of the latest version.
            latest_done (bool): Return only reviewables of the latest
                approved versions.

        Returns:
            list[dict[str, Any]]: Versions with reviewables.

        """
        query = self._prepare_reviewables_query(latest, latest_done)
        response = self.post(
            f"projects/{project_name}/{entity_type}s/reviewables/list{query}",
            entityIds=list(entity_ids),
        )
        response.raise_for_status()
        return response.data

    def get_version_reviewables(
        self,
        project_name: str,
        version_id: str,
        *,
        latest: bool = False,
        latest_done: bool = False,
    ) -> dict[str, Any]:
        """Get reviewables of a version.

        Notes:
            Server responds with an error if version does not have
                any reviewables.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            latest (bool): Return only reviewables of the latest version.
            latest_done (bool): Return only reviewables of the latest
                approved versions.

        Returns:
            dict[str, Any]: Version information with reviewables.

        """
        return self._get_entity_reviewables(
            project_name, "versions", version_id, latest, latest_done
        )

    def get_product_reviewables(
        self,
        project_name: str,
        product_id: str,
        *,
        latest: bool = False,
        latest_done: bool = False,
    ) -> list[dict[str, Any]]:
        """Get reviewables of all versions of a product.

        Args:
            project_name (str): Project name.
            product_id (str): Product id.
            latest (bool): Return only reviewables of the latest version.
            latest_done (bool): Return only reviewables of the latest
                approved versions.

        Returns:
            list[dict[str, Any]]: Versions with reviewables.

        """
        return self._get_entity_reviewables(
            project_name, "products", product_id, latest, latest_done
        )

    def get_folder_reviewables(
        self,
        project_name: str,
        folder_id: str,
        *,
        latest: bool = False,
        latest_done: bool = False,
    ) -> list[dict[str, Any]]:
        """Get reviewables of all versions under a folder.

        Args:
            project_name (str): Project name.
            folder_id (str): Folder id.
            latest (bool): Return only reviewables of the latest versions.
            latest_done (bool): Return only reviewables of the latest
                approved versions.

        Returns:
            list[dict[str, Any]]: Versions with reviewables.

        """
        return self._get_entity_reviewables(
            project_name, "folders", folder_id, latest, latest_done
        )

    def get_task_reviewables(
        self,
        project_name: str,
        task_id: str,
        *,
        latest: bool = False,
        latest_done: bool = False,
    ) -> list[dict[str, Any]]:
        """Get reviewables of all versions linked to a task.

        Args:
            project_name (str): Project name.
            task_id (str): Task id.
            latest (bool): Return only reviewables of the latest versions.
            latest_done (bool): Return only reviewables of the latest
                approved versions.

        Returns:
            list[dict[str, Any]]: Versions with reviewables.

        """
        return self._get_entity_reviewables(
            project_name, "tasks", task_id, latest, latest_done
        )

    def sort_version_reviewables(
        self,
        project_name: str,
        version_id: str,
        reviewable_ids: list[str],
    ) -> None:
        """Change order of reviewables of a version.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            reviewable_ids (list[str]): Reviewable (activity) ids in
                the desired order. Must contain all reviewables of
                the version.

        """
        response = self.patch(
            f"projects/{project_name}/versions/{version_id}/reviewables",
            sort=reviewable_ids,
        )
        response.raise_for_status()

    def update_reviewable(
        self,
        project_name: str,
        version_id: str,
        reviewable_id: str,
        *,
        label: Optional[str] = None,
    ) -> None:
        """Update reviewable of a version.

        At this moment only label of reviewable can be changed.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            reviewable_id (str): Reviewable (activity) id.
            label (Optional[str]): New label of reviewable.

        """
        kwargs = {}
        if label is not None:
            kwargs["label"] = label

        response = self.patch(
            f"projects/{project_name}/versions/{version_id}"
            f"/reviewables/{reviewable_id}",
            **kwargs
        )
        response.raise_for_status()

    def _prepare_reviewables_query(
        self, latest: bool, latest_done: bool
    ) -> str:
        return prepare_query_string({
            "latest": "true" if latest else None,
            "latest_done": "true" if latest_done else None,
        })

    def _get_entity_reviewables(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        latest: bool,
        latest_done: bool,
    ) -> Any:
        query = self._prepare_reviewables_query(latest, latest_done)
        response = self.get(
            f"projects/{project_name}/{entity_type}/{entity_id}"
            f"/reviewables{query}"
        )
        response.raise_for_status()
        return response.data
