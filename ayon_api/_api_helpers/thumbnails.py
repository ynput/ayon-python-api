from __future__ import annotations

import os
import warnings
from typing import Optional

from ayon_api.utils import (
    get_media_mime_type,
    ThumbnailContent,
    RequestTypes,
    RestApiResponse,
)

from .base import BaseServerAPI


class ThumbnailsAPI(BaseServerAPI):
    def get_thumbnail_by_id(
        self, project_name: str, thumbnail_id: str
    ) -> ThumbnailContent:
        """Get thumbnail from server by id.

        Warnings:
            Please keep in mind that used endpoint is allowed only for admins
                and managers. Use 'get_thumbnail' with entity type and id
                to allow access for artists.

        Notes:
            It is recommended to use one of prepared entity type specific
                methods 'get_folder_thumbnail', 'get_version_thumbnail' or
                'get_workfile_thumbnail'.
            We do recommend pass thumbnail id if you have access to it. Each
                entity that allows thumbnails has 'thumbnailId' field, so it
                can be queried.

        Args:
            project_name (str): Project under which the entity is located.
            thumbnail_id (Optional[str]): DEPRECATED Use
                'get_thumbnail_by_id'.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        response = self.raw_get(
            f"projects/{project_name}/thumbnails/{thumbnail_id}"
        )
        return self._prepare_thumbnail_content(project_name, response)

    def get_thumbnail(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        thumbnail_id: Optional[str] = None,
    ) -> ThumbnailContent:
        """Get thumbnail from server.

        Permissions of thumbnails are related to entities so thumbnails must
        be queried per entity. So an entity type and entity id is required
        to be passed.

        Notes:
            It is recommended to use one of prepared entity type specific
                methods 'get_folder_thumbnail', 'get_version_thumbnail' or
                'get_workfile_thumbnail'.
            We do recommend pass thumbnail id if you have access to it. Each
                entity that allows thumbnails has 'thumbnailId' field, so it
                can be queried.

        Args:
            project_name (str): Project under which the entity is located.
            entity_type (str): Entity type which passed entity id represents.
            entity_id (str): Entity id for which thumbnail should be returned.
            thumbnail_id (Optional[str]): DEPRECATED Use
                'get_thumbnail_by_id'.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        if thumbnail_id:
            warnings.warn(
                (
                    "Function 'get_thumbnail' got 'thumbnail_id' which"
                    " is deprecated and will be removed in future version."
                ),
                DeprecationWarning
            )

        if entity_type in (
            "folder",
            "task",
            "version",
            "workfile",
        ):
            entity_type += "s"

        response = self.raw_get(
            f"projects/{project_name}/{entity_type}/{entity_id}/thumbnail"
        )
        return self._prepare_thumbnail_content(project_name, response)

    def get_folder_thumbnail(
        self,
        project_name: str,
        folder_id: str,
        thumbnail_id: Optional[str] = None,
    ) -> ThumbnailContent:
        """Prepared method to receive thumbnail for folder entity.

        Args:
            project_name (str): Project under which the entity is located.
            folder_id (str): Folder id for which thumbnail should be returned.
            thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
                Used only to check if thumbnail was already cached.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        if thumbnail_id:
            warnings.warn(
                (
                    "Function 'get_folder_thumbnail' got 'thumbnail_id' which"
                    " is deprecated and will be removed in future version."
                ),
                DeprecationWarning
            )
        return self.get_thumbnail(
            project_name, "folder", folder_id
        )

    def get_task_thumbnail(
        self,
        project_name: str,
        task_id: str,
    ) -> ThumbnailContent:
        """Prepared method to receive thumbnail for task entity.

        Args:
            project_name (str): Project under which the entity is located.
            task_id (str): Folder id for which thumbnail should be returned.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        return self.get_thumbnail(project_name, "task", task_id)

    def get_version_thumbnail(
        self,
        project_name: str,
        version_id: str,
        thumbnail_id: Optional[str] = None,
    ) -> ThumbnailContent:
        """Prepared method to receive thumbnail for version entity.

        Args:
            project_name (str): Project under which the entity is located.
            version_id (str): Version id for which thumbnail should be
                returned.
            thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
                Used only to check if thumbnail was already cached.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        if thumbnail_id:
            warnings.warn(
                (
                    "Function 'get_version_thumbnail' got 'thumbnail_id' which"
                    " is deprecated and will be removed in future version."
                ),
                DeprecationWarning
            )
        return self.get_thumbnail(
            project_name, "version", version_id
        )

    def get_workfile_thumbnail(
        self,
        project_name: str,
        workfile_id: str,
        thumbnail_id: Optional[str] = None,
    ) -> ThumbnailContent:
        """Prepared method to receive thumbnail for workfile entity.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_id (str): Worfile id for which thumbnail should be
                returned.
            thumbnail_id (Optional[str]): Prepared thumbnail id from entity.
                Used only to check if thumbnail was already cached.

        Returns:
            ThumbnailContent: Thumbnail content wrapper. Does not have to be
                valid.

        """
        if thumbnail_id:
            warnings.warn(
                (
                    "Function 'get_workfile_thumbnail' got 'thumbnail_id'"
                    " which is deprecated and will be removed in future"
                    " version."
                ),
                DeprecationWarning
            )
        return self.get_thumbnail(
            project_name, "workfile", workfile_id
        )

    def create_thumbnail(
        self,
        project_name: str,
        src_filepath: str,
        thumbnail_id: Optional[str] = None,
    ) -> str:
        """Create new thumbnail on server from passed path.

        Args:
            project_name (str): Project where the thumbnail will be created
                and can be used.
            src_filepath (str): Filepath to thumbnail which should be uploaded.
            thumbnail_id (Optional[str]): Prepared if of thumbnail.

        Returns:
            str: Created thumbnail id.

        Raises:
            ValueError: When thumbnail source cannot be processed.

        """
        if not os.path.exists(src_filepath):
            raise ValueError("Entered filepath does not exist.")

        if thumbnail_id:
            self.update_thumbnail(
                project_name,
                thumbnail_id,
                src_filepath
            )
            return thumbnail_id

        mime_type = get_media_mime_type(src_filepath)
        response = self.upload_file(
            f"projects/{project_name}/thumbnails",
            src_filepath,
            request_type=RequestTypes.post,
            headers={"Content-Type": mime_type},
        )
        response.raise_for_status()
        return response.json()["id"]

    def update_thumbnail(
        self, project_name: str, thumbnail_id: str, src_filepath: str
    ):
        """Change thumbnail content by id.

        Update can be also used to create new thumbnail.

        Args:
            project_name (str): Project where the thumbnail will be created
                and can be used.
            thumbnail_id (str): Thumbnail id to update.
            src_filepath (str): Filepath to thumbnail which should be uploaded.

        Raises:
            ValueError: When thumbnail source cannot be processed.

        """
        if not os.path.exists(src_filepath):
            raise ValueError("Entered filepath does not exist.")

        mime_type = get_media_mime_type(src_filepath)
        response = self.upload_file(
            f"projects/{project_name}/thumbnails/{thumbnail_id}",
            src_filepath,
            request_type=RequestTypes.put,
            headers={"Content-Type": mime_type},
        )
        response.raise_for_status()

    def _prepare_thumbnail_content(
        self,
        project_name: str,
        response: RestApiResponse,
    ) -> ThumbnailContent:
        content = None
        content_type = response.content_type

        # It is expected the response contains thumbnail id otherwise the
        #   content cannot be cached and filepath returned
        thumbnail_id = response.headers.get("X-Thumbnail-Id")
        if thumbnail_id is not None:
            content = response.content

        return ThumbnailContent(
            project_name, thumbnail_id, content, content_type
        )
