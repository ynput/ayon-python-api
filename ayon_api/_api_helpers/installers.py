from __future__ import annotations


import typing
from typing import Optional, Any

from ayon_api.utils import prepare_query_string, TransferProgress

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import InstallersInfoDict


class InstallersAPI(BaseServerAPI):
    def get_installers(
        self,
        version: Optional[str] = None,
        platform_name: Optional[str] = None,
    ) -> "InstallersInfoDict":
        """Information about desktop application installers on server.

        Desktop application installers are helpers to download/update AYON
        desktop application for artists.

        Args:
            version (Optional[str]): Filter installers by version.
            platform_name (Optional[str]): Filter installers by platform name.

        Returns:
            InstallersInfoDict: Information about installers known for server.

        """
        query = prepare_query_string({
            "version": version or None,
            "platform": platform_name or None,
        })
        response = self.get(f"desktop/installers{query}")
        response.raise_for_status()
        return response.data

    def create_installer(
        self,
        filename: str,
        version: str,
        python_version: str,
        platform_name: str,
        python_modules: dict[str, str],
        runtime_python_modules: dict[str, str],
        checksum: str,
        checksum_algorithm: str,
        file_size: int,
        sources: Optional[list[dict[str, Any]]] = None,
    ):
        """Create new installer information on server.

        This step will create only metadata. Make sure to upload installer
            to the server using 'upload_installer' method.

        Runtime python modules are modules that are required to run AYON
            desktop application, but are not added to PYTHONPATH for any
            subprocess.

        Args:
            filename (str): Installer filename.
            version (str): Version of installer.
            python_version (str): Version of Python.
            platform_name (str): Name of platform.
            python_modules (dict[str, str]): Python modules that are available
                in installer.
            runtime_python_modules (dict[str, str]): Runtime python modules
                that are available in installer.
            checksum (str): Installer file checksum.
            checksum_algorithm (str): Type of checksum used to create checksum.
            file_size (int): File size.
            sources (Optional[list[dict[str, Any]]]): List of sources that
                can be used to download file.

        """
        body = {
            "filename": filename,
            "version": version,
            "pythonVersion": python_version,
            "platform": platform_name,
            "pythonModules": python_modules,
            "runtimePythonModules": runtime_python_modules,
            "checksum": checksum,
            "checksumAlgorithm": checksum_algorithm,
            "size": file_size,
        }
        if sources:
            body["sources"] = sources

        response = self.post("desktop/installers", **body)
        response.raise_for_status()

    def update_installer(self, filename: str, sources: list[dict[str, Any]]):
        """Update installer information on server.

        Args:
            filename (str): Installer filename.
            sources (list[dict[str, Any]]): List of sources that
                can be used to download file. Fully replaces existing sources.

        """
        response = self.patch(
            f"desktop/installers/{filename}",
            sources=sources
        )
        response.raise_for_status()

    def delete_installer(self, filename: str):
        """Delete installer from server.

        Args:
            filename (str): Installer filename.

        """
        response = self.delete(f"desktop/installers/{filename}")
        response.raise_for_status()

    def download_installer(
        self,
        filename: str,
        dst_filepath: str,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None
    ):
        """Download installer file from server.

        Args:
            filename (str): Installer filename.
            dst_filepath (str): Destination filepath.
            chunk_size (Optional[int]): Download chunk size.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        """
        self.download_file(
            f"desktop/installers/{filename}",
            dst_filepath,
            chunk_size=chunk_size,
            progress=progress
        )

    def upload_installer(
        self,
        src_filepath: str,
        dst_filename: str,
        progress: Optional[TransferProgress] = None,
    ):
        """Upload installer file to server.

        Args:
            src_filepath (str): Source filepath.
            dst_filename (str): Destination filename.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        Returns:
            requests.Response: Response object.

        """
        return self.upload_file(
            f"desktop/installers/{dst_filename}",
            src_filepath,
            progress=progress
        )
