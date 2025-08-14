from __future__ import annotations

import os
import warnings
import platform
import typing
from typing import Optional, Any

from ayon_api.utils import TransferProgress

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import DependencyPackagesDict


class DependencyPackagesAPI(BaseServerAPI):
    def get_dependency_packages(self) -> "DependencyPackagesDict":
        """Information about dependency packages on server.

        To download dependency package, use 'download_dependency_package'
        method and pass in 'filename'.

        Example data structure::

            {
                "packages": [
                    {
                        "filename": str,
                        "platform": str,
                        "checksum": str,
                        "checksumAlgorithm": str,
                        "size": int,
                        "sources": list[dict[str, Any]],
                        "supportedAddons": dict[str, str],
                        "pythonModules": dict[str, str]
                    }
                ]
            }

        Returns:
            DependencyPackagesDict: Information about dependency packages
                known for server.

        """
        endpoint = self._get_dependency_package_route()
        result = self.get(endpoint)
        result.raise_for_status()
        return result.data

    def create_dependency_package(
        self,
        filename: str,
        python_modules: dict[str, str],
        source_addons: dict[str, str],
        installer_version: str,
        checksum: str,
        checksum_algorithm: str,
        file_size: int,
        sources: Optional[list[dict[str, Any]]] = None,
        platform_name: Optional[str] = None,
    ):
        """Create dependency package on server.

        The package will be created on a server, it is also required to upload
        the package archive file (using :meth:`upload_dependency_package`).

        Args:
            filename (str): Filename of dependency package.
            python_modules (dict[str, str]): Python modules in dependency
                package::

                    {"<module name>": "<module version>", ...}

            source_addons (dict[str, str]): Name of addons for which is
                dependency package created::

                    {"<addon name>": "<addon version>", ...}

            installer_version (str): Version of installer for which was
                package created.
            checksum (str): Checksum of archive file where dependencies are.
            checksum_algorithm (str): Algorithm used to calculate checksum.
            file_size (Optional[int]): Size of file.
            sources (Optional[list[dict[str, Any]]]): Information about
                sources from where it is possible to get file.
            platform_name (Optional[str]): Name of platform for which is
                dependency package targeted. Default value is
                current platform.

        """
        post_body = {
            "filename": filename,
            "pythonModules": python_modules,
            "sourceAddons": source_addons,
            "installerVersion": installer_version,
            "checksum": checksum,
            "checksumAlgorithm": checksum_algorithm,
            "size": file_size,
            "platform": platform_name or platform.system().lower(),
        }
        if sources:
            post_body["sources"] = sources

        route = self._get_dependency_package_route()
        response = self.post(route, **post_body)
        response.raise_for_status()

    def update_dependency_package(
        self, filename: str, sources: list[dict[str, Any]]
    ):
        """Update dependency package metadata on server.

        Args:
            filename (str): Filename of dependency package.
            sources (list[dict[str, Any]]): Information about
                sources from where it is possible to get file. Fully replaces
                existing sources.

        """
        response = self.patch(
            self._get_dependency_package_route(filename),
            sources=sources
        )
        response.raise_for_status()

    def delete_dependency_package(
        self, filename: str, platform_name: Optional[str] = None
    ):
        """Remove dependency package for specific platform.

        Args:
            filename (str): Filename of dependency package.
            platform_name (Optional[str]): Deprecated.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'delete_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )

        route = self._get_dependency_package_route(filename)
        response = self.delete(route)
        response.raise_for_status("Failed to delete dependency file")
        return response.data

    def download_dependency_package(
        self,
        src_filename: str,
        dst_directory: str,
        dst_filename: str,
        platform_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> str:
        """Download dependency package from server.

        This method requires to have authorized token available. The package
        is only downloaded.

        Args:
            src_filename (str): Filename of dependency pacakge.
                For server version 0.2.0 and lower it is name of package
                to download.
            dst_directory (str): Where the file should be downloaded.
            dst_filename (str): Name of destination filename.
            platform_name (Optional[str]): Deprecated.
            chunk_size (Optional[int]): Download chunk size.
            progress (Optional[TransferProgress]): Object that gives ability
                to track download progress.

        Returns:
            str: Filepath to downloaded file.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'download_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )
        route = self._get_dependency_package_route(src_filename)
        package_filepath = os.path.join(dst_directory, dst_filename)
        self.download_file(
            route,
            package_filepath,
            chunk_size=chunk_size,
            progress=progress
        )
        return package_filepath

    def upload_dependency_package(
        self,
        src_filepath: str,
        dst_filename: str,
        platform_name: Optional[str] = None,
        progress: Optional[TransferProgress] = None,
    ):
        """Upload dependency package to server.

        Args:
            src_filepath (str): Path to a package file.
            dst_filename (str): Dependency package filename or name of package
                for server version 0.2.0 or lower. Must be unique.
            platform_name (Optional[str]): Deprecated.
            progress (Optional[TransferProgress]): Object to keep track about
                upload state.

        """
        if platform_name is not None:
            warnings.warn(
                (
                    "Argument 'platform_name' is deprecated in"
                    " 'upload_dependency_package'. The argument will be"
                    " removed, please modify your code accordingly."
                ),
                DeprecationWarning
            )

        route = self._get_dependency_package_route(dst_filename)
        self.upload_file(route, src_filepath, progress=progress)

    def _get_dependency_package_route(
        self, filename: Optional[str] = None
    ) -> str:
        endpoint = "desktop/dependencyPackages"
        if filename:
            return f"{endpoint}/{filename}"
        return endpoint
