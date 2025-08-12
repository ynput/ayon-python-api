import os
import typing
from typing import Optional

from .utils import (
    RequestTypes,
    prepare_query_string,
    TransferProgress,
)
from ._base import _BaseServerAPI

if typing.TYPE_CHECKING:
    from .typing import AddonsInfoDict


class _AddonsAPI(_BaseServerAPI):
    def get_addon_endpoint(
        self,
        addon_name: str,
        addon_version: str,
        *subpaths: str,
    ) -> str:
        """Calculate endpoint to addon route.

        Examples:
            >>> from ayon_api import ServerAPI
            >>> api = ServerAPI("https://your.url.com")
            >>> api.get_addon_url(
            ...     "example", "1.0.0", "private", "my.zip")
            'addons/example/1.0.0/private/my.zip'

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            *subpaths (str): Any amount of subpaths that are added to
                addon url.

        Returns:
            str: Final url.

        """
        ending = ""
        if subpaths:
            ending = f"/{'/'.join(subpaths)}"
        return f"addons/{addon_name}/{addon_version}{ending}"

    def get_addons_info(self, details: bool = True) -> "AddonsInfoDict":
        """Get information about addons available on server.

        Args:
            details (Optional[bool]): Detailed data with information how
                to get client code.

        """
        endpoint = "addons"
        if details:
            endpoint += "?details=1"
        response = self.get(endpoint)
        response.raise_for_status()
        return response.data

    def get_addon_url(
        self,
        addon_name: str,
        addon_version: str,
        *subpaths: str,
        use_rest: bool = True,
    ) -> str:
        """Calculate url to addon route.

        Examples:

            >>> api = ServerAPI("https://your.url.com")
            >>> api.get_addon_url(
            ...     "example", "1.0.0", "private", "my.zip")
            'https://your.url.com/api/addons/example/1.0.0/private/my.zip'

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            *subpaths (str): Any amount of subpaths that are added to
                addon url.
            use_rest (Optional[bool]): Use rest endpoint.

        Returns:
            str: Final url.

        """
        endpoint = self.get_addon_endpoint(
            addon_name, addon_version, *subpaths
        )
        url_base = self.get_base_url() if use_rest else self.get_rest_url()
        return f"{url_base}/{endpoint}"

    def delete_addon(
        self,
        addon_name: str,
        purge: Optional[bool] = None,
    ) -> None:
        """Delete addon from server.

        Delete all versions of addon from server.

        Args:
            addon_name (str): Addon name.
            purge (Optional[bool]): Purge all data related to the addon.

        """
        if purge is not None:
            purge = "true" if purge else "false"
        query = prepare_query_string({"purge": purge})

        response = self.delete(f"addons/{addon_name}{query}")
        response.raise_for_status()

    def delete_addon_version(
        self,
        addon_name: str,
        addon_version: str,
        purge: Optional[bool] = None,
    ) -> None:
        """Delete addon version from server.

        Delete all versions of addon from server.

        Args:
            addon_name (str): Addon name.
            addon_version (str): Addon version.
            purge (Optional[bool]): Purge all data related to the addon.

        """
        if purge is not None:
            purge = "true" if purge else "false"
        query = prepare_query_string({"purge": purge})
        response = self.delete(f"addons/{addon_name}/{addon_version}{query}")
        response.raise_for_status()

    def upload_addon_zip(
        self,
        src_filepath: str,
        progress: Optional[TransferProgress] = None,
    ):
        """Upload addon zip file to server.

        File is validated on server. If it is valid, it is installed. It will
            create an event job which can be tracked (tracking part is not
            implemented yet).

        Example output::

            {'eventId': 'a1bfbdee27c611eea7580242ac120003'}

        Args:
            src_filepath (str): Path to a zip file.
            progress (Optional[TransferProgress]): Object to keep track about
                upload state.

        Returns:
            dict[str, Any]: Response data from server.

        """
        response = self.upload_file(
            "addons/install",
            src_filepath,
            progress=progress,
            request_type=RequestTypes.post,
        )
        return response.json()

    def download_addon_private_file(
        self,
        addon_name: str,
        addon_version: str,
        filename: str,
        destination_dir: str,
        destination_filename: Optional[str] = None,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> str:
        """Download a file from addon private files.

        This method requires to have authorized token available. Private files
        are not under '/api' restpoint.

        Args:
            addon_name (str): Addon name.
            addon_version (str): Addon version.
            filename (str): Filename in private folder on server.
            destination_dir (str): Where the file should be downloaded.
            destination_filename (Optional[str]): Name of destination
                filename. Source filename is used if not passed.
            chunk_size (Optional[int]): Download chunk size.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        Returns:
            str: Filepath to downloaded file.

        """
        if not destination_filename:
            destination_filename = filename
        dst_filepath = os.path.join(destination_dir, destination_filename)
        # Filename can contain "subfolders"
        dst_dirpath = os.path.dirname(dst_filepath)
        os.makedirs(dst_dirpath, exist_ok=True)

        endpoint = self.get_addon_endpoint(
            addon_name,
            addon_version,
            "private",
            filename
        )
        url = f"{self.get_base_url()}/{endpoint}"
        self.download_file(
            url, dst_filepath, chunk_size=chunk_size, progress=progress
        )
        return dst_filepath
