import os
import typing
from typing import Optional, Any

from ayon_api.utils import (
    RequestTypes,
    prepare_query_string,
    TransferProgress,
)

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        AddonsInfoDict,
        BundlesInfoDict,
        DevBundleAddonInfoDict,
    )


class BundlesAddonsAPI(BaseServerAPI):
    def get_bundles(self) -> "BundlesInfoDict":
        """Server bundles with basic information.

        This is example output::

            {
                "bundles": [
                    {
                        "name": "my_bundle",
                        "createdAt": "2023-06-12T15:37:02.420260",
                        "installerVersion": "1.0.0",
                        "addons": {
                            "core": "1.2.3"
                        },
                        "dependencyPackages": {
                            "windows": "a_windows_package123.zip",
                            "linux": "a_linux_package123.zip",
                            "darwin": "a_mac_package123.zip"
                        },
                        "isProduction": False,
                        "isStaging": False
                    }
                ],
                "productionBundle": "my_bundle",
                "stagingBundle": "test_bundle"
            }

        Returns:
            dict[str, Any]: Server bundles with basic information.

        """
        response = self.get("bundles")
        response.raise_for_status()
        return response.data

    def create_bundle(
        self,
        name: str,
        addon_versions: dict[str, str],
        installer_version: str,
        dependency_packages: Optional[dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            dict[str, "DevBundleAddonInfoDict"]] = None,
    ):
        """Create bundle on server.

        Bundle cannot be changed once is created. Only isProduction, isStaging
        and dependency packages can change after creation. In case dev bundle
        is created, it is possible to change anything, but it is not possible
        to mark bundle as dev and production or staging at the same time.

        Development addon config can define custom path to client code. It is
        used only for dev bundles.

        Example of 'dev_addons_config'::

            ```json
            {
                "core": {
                    "enabled": true,
                    "path": "/path/to/ayon-core/client"
                }
            }
            ```

        Args:
            name (str): Name of bundle.
            addon_versions (dict[str, str]): Addon versions.
            installer_version (Union[str, None]): Installer version.
            dependency_packages (Optional[dict[str, str]]): Dependency
                package names. Keys are platform names and values are name of
                packages.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only if 'is_dev' is set to 'True'.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only if 'is_dev' is set to 'True'.

        """
        body = {
            "name": name,
            "installerVersion": installer_version,
            "addons": addon_versions,
        }

        for key, value in (
            ("dependencyPackages", dependency_packages),
            ("isProduction", is_production),
            ("isStaging", is_staging),
            ("isDev", is_dev),
            ("activeUser", dev_active_user),
            ("addonDevelopment", dev_addons_config),
        ):
            if value is not None:
                body[key] = value

        response = self.post("bundles", **body)
        response.raise_for_status()

    def update_bundle(
        self,
        bundle_name: str,
        addon_versions: Optional[dict[str, str]] = None,
        installer_version: Optional[str] = None,
        dependency_packages: Optional[dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            dict[str, "DevBundleAddonInfoDict"]] = None,
    ):
        """Update bundle on server.

        Dependency packages can be update only for single platform. Others
        will be left untouched. Use 'None' value to unset dependency package
        from bundle.

        Args:
            bundle_name (str): Name of bundle.
            addon_versions (Optional[dict[str, str]]): Addon versions,
                possible only for dev bundles.
            installer_version (Optional[str]): Installer version, possible
                only for dev bundles.
            dependency_packages (Optional[dict[str, str]]): Dependency pacakge
                names that should be used with the bundle.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only for dev bundles.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only for dev bundles.

        """
        body = {
            key: value
            for key, value in (
                ("installerVersion", installer_version),
                ("addons", addon_versions),
                ("dependencyPackages", dependency_packages),
                ("isProduction", is_production),
                ("isStaging", is_staging),
                ("isDev", is_dev),
                ("activeUser", dev_active_user),
                ("addonDevelopment", dev_addons_config),
            )
            if value is not None
        }

        response = self.patch(
            f"bundles/{bundle_name}",
            **body
        )
        response.raise_for_status()

    def check_bundle_compatibility(
        self,
        name: str,
        addon_versions: dict[str, str],
        installer_version: str,
        dependency_packages: Optional[dict[str, str]] = None,
        is_production: Optional[bool] = None,
        is_staging: Optional[bool] = None,
        is_dev: Optional[bool] = None,
        dev_active_user: Optional[str] = None,
        dev_addons_config: Optional[
            dict[str, "DevBundleAddonInfoDict"]] = None,
    ) -> dict[str, Any]:
        """Check bundle compatibility.

        Can be used as per-flight validation before creating bundle.

        Args:
            name (str): Name of bundle.
            addon_versions (dict[str, str]): Addon versions.
            installer_version (Union[str, None]): Installer version.
            dependency_packages (Optional[dict[str, str]]): Dependency
                package names. Keys are platform names and values are name of
                packages.
            is_production (Optional[bool]): Bundle will be marked as
                production.
            is_staging (Optional[bool]): Bundle will be marked as staging.
            is_dev (Optional[bool]): Bundle will be marked as dev.
            dev_active_user (Optional[str]): Username that will be assigned
                to dev bundle. Can be used only if 'is_dev' is set to 'True'.
            dev_addons_config (Optional[dict[str, Any]]): Configuration for
                dev addons. Can be used only if 'is_dev' is set to 'True'.

        Returns:
            dict[str, Any]: Server response, with 'success' and 'issues'.

        """
        body = {
            "name": name,
            "installerVersion": installer_version,
            "addons": addon_versions,
        }

        for key, value in (
            ("dependencyPackages", dependency_packages),
            ("isProduction", is_production),
            ("isStaging", is_staging),
            ("isDev", is_dev),
            ("activeUser", dev_active_user),
            ("addonDevelopment", dev_addons_config),
        ):
            if value is not None:
                body[key] = value

        response = self.post("bundles/check", **body)
        response.raise_for_status()
        return response.data

    def delete_bundle(self, bundle_name: str):
        """Delete bundle from server.

        Args:
            bundle_name (str): Name of bundle to delete.

        """
        response = self.delete(f"bundles/{bundle_name}")
        response.raise_for_status()

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
            >>> from ayon_api import ServerAPI
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


    def get_addon_settings_schema(
        self,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Sudio/Project settings schema of an addon.

        Project schema may look differently as some enums are based on project
        values.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (Optional[str]): Schema for specific project or
                default studio schemas.

        Returns:
            dict[str, Any]: Schema of studio/project settings.

        """
        args = tuple()
        if project_name:
            args = (project_name, )

        endpoint = self.get_addon_endpoint(
            addon_name, addon_version, "schema", *args
        )
        result = self.get(endpoint)
        result.raise_for_status()
        return result.data

    def get_addon_site_settings_schema(
        self, addon_name: str, addon_version: str
    ) -> dict[str, Any]:
        """Site settings schema of an addon.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.

        Returns:
            dict[str, Any]: Schema of site settings.

        """
        result = self.get(
            f"addons/{addon_name}/{addon_version}/siteSettings/schema"
        )
        result.raise_for_status()
        return result.data

    def get_addon_studio_settings(
        self,
        addon_name: str,
        addon_version: str,
        variant: Optional[str] = None,
    ) -> dict[str, Any]:
        """Addon studio settings.

        Receive studio settings for specific version of an addon.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.

        Returns:
           dict[str, Any]: Addon settings.

        """
        if variant is None:
            variant = self.get_default_settings_variant()

        query = prepare_query_string({"variant": variant or None})

        result = self.get(
            f"addons/{addon_name}/{addon_version}/settings{query}"
        )
        result.raise_for_status()
        return result.data

    def get_addon_project_settings(
        self,
        addon_name: str,
        addon_version: str,
        project_name: str,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True
    ) -> dict[str, Any]:
        """Addon project settings.

        Receive project settings for specific version of an addon. The settings
        may be with site overrides when enabled.

        Site id is filled with current connection site id if not passed. To
        make sure any site id is used set 'use_site' to 'False'.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (str): Name of project for which the settings are
                received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Name of site which is used for site
                overrides. Is filled with connection 'site_id' attribute
                if not passed.
            use_site (Optional[bool]): To force disable option of using site
                overrides set to 'False'. In that case won't be applied
                any site overrides.

        Returns:
            dict[str, Any]: Addon settings.

        """
        if not use_site:
            site_id = None
        elif not site_id:
            site_id = self.get_site_id()

        if variant is None:
            variant = self.get_default_settings_variant()

        query = prepare_query_string({
            "site": site_id or None,
            "variant": variant or None,
        })
        result = self.get(
            f"addons/{addon_name}/{addon_version}"
            f"/settings/{project_name}{query}"
        )
        result.raise_for_status()
        return result.data

    def get_addon_settings(
        self,
        addon_name: str,
        addon_version: str,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True
    ) -> dict[str, Any]:
        """Receive addon settings.

        Receive addon settings based on project name value. Some arguments may
        be ignored if 'project_name' is set to 'None'.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            project_name (Optional[str]): Name of project for which the
                settings are received. A studio settings values are received
                if is 'None'.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Name of site which is used for site
                overrides. Is filled with connection 'site_id' attribute
                if not passed.
            use_site (Optional[bool]): To force disable option of using
                site overrides set to 'False'. In that case won't be applied
                any site overrides.

        Returns:
            dict[str, Any]: Addon settings.

        """
        if project_name is None:
            return self.get_addon_studio_settings(
                addon_name, addon_version, variant
            )
        return self.get_addon_project_settings(
            addon_name, addon_version, project_name, variant, site_id, use_site
        )

    def get_addon_site_settings(
        self,
        addon_name: str,
        addon_version: str,
        site_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Site settings of an addon.

        If site id is not available an empty dictionary is returned.

        Args:
            addon_name (str): Name of addon.
            addon_version (str): Version of addon.
            site_id (Optional[str]): Name of site for which should be settings
                returned. using 'site_id' attribute if not passed.

        Returns:
            dict[str, Any]: Site settings.

        """
        if site_id is None:
            site_id = self.get_site_id()

        if not site_id:
            return {}

        query = prepare_query_string({"site": site_id})
        result = self.get(
            f"addons/{addon_name}/{addon_version}/siteSettings{query}"
        )
        result.raise_for_status()
        return result.data

    def get_bundle_settings(
        self,
        bundle_name: Optional[str] = None,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
    ) -> dict[str, Any]:
        """Get complete set of settings for given data.

        If project is not passed then studio settings are returned. If variant
        is not passed 'default_settings_variant' is used. If bundle name is
        not passed then current production/staging bundle is used, based on
        variant value.

        Output contains addon settings and site settings in single dictionary.

        Todos:
            - test how it behaves if there is not any bundle.
            - test how it behaves if there is not any production/staging
                bundle.

        Example output::

            {
                "addons": [
                    {
                        "name": "addon-name",
                        "version": "addon-version",
                        "settings": {...},
                        "siteSettings": {...}
                    }
                ]
            }

        Returns:
            dict[str, Any]: All settings for single bundle.

        """
        if not use_site:
            site_id = None
        elif not site_id:
            site_id = self.get_site_id()

        query = prepare_query_string({
            "project_name": project_name or None,
            "bundle_name": bundle_name or None,
            "variant": variant or self.get_default_settings_variant() or None,
            "site_id": site_id,
        })
        response = self.get(f"settings{query}")
        response.raise_for_status()
        return response.data

    def get_addons_studio_settings(
        self,
        bundle_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> dict[str, Any]:
        """All addons settings in one bulk.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            use_site (bool): To force disable option of using site overrides
                set to 'False'. In that case won't be applied any site
                overrides.
            only_values (Optional[bool]): Output will contain only settings
                values without metadata about addons.

        Returns:
            dict[str, Any]: Settings of all addons on server.

        """
        output = self.get_bundle_settings(
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site
        )
        if only_values:
            output = {
                addon["name"]: addon["settings"]
                for addon in output["addons"]
            }
        return output

    def get_addons_project_settings(
        self,
        project_name: str,
        bundle_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> dict[str, Any]:
        """Project settings of all addons.

        Server returns information about used addon versions, so full output
        looks like:

        ```json
            {
                "settings": {...},
                "addons": {...}
            }
        ```

        The output can be limited to only values. To do so is 'only_values'
        argument which is by default set to 'True'. In that case output
        contains only value of 'settings' key.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            project_name (str): Name of project for which are settings
                received.
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            use_site (bool): To force disable option of using site overrides
                set to 'False'. In that case won't be applied any site
                overrides.
            only_values (Optional[bool]): Output will contain only settings
                values without metadata about addons.

        Returns:
            dict[str, Any]: Settings of all addons on server for passed
                project.

        """
        if not project_name:
            raise ValueError("Project name must be passed.")

        output = self.get_bundle_settings(
            project_name=project_name,
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site
        )
        if only_values:
            output = {
                addon["name"]: addon["settings"]
                for addon in output["addons"]
            }
        return output

    def get_addons_settings(
        self,
        bundle_name: Optional[str] = None,
        project_name: Optional[str] = None,
        variant: Optional[str] = None,
        site_id: Optional[str] = None,
        use_site: bool = True,
        only_values: bool = True,
    ) -> dict[str, Any]:
        """Universal function to receive all addon settings.

        Based on 'project_name' will receive studio settings or project
        settings. In case project is not passed is 'site_id' ignored.

        Warnings:
            Behavior of this function changed with AYON server version 0.3.0.
                Structure of output from server changed. If using
                'only_values=True' then output should be same as before.

        Args:
            bundle_name (Optional[str]): Name of bundle for which should be
                settings received.
            project_name (Optional[str]): Name of project for which should be
                settings received.
            variant (Optional[Literal['production', 'staging']]): Name of
                settings variant. Used 'default_settings_variant' by default.
            site_id (Optional[str]): Id of site for which want to receive
                site overrides.
            use_site (Optional[bool]): To force disable option of using site
                overrides set to 'False'. In that case won't be applied
                any site overrides.
            only_values (Optional[bool]): Only settings values will be
                returned. By default, is set to 'True'.

        """
        if project_name is None:
            return self.get_addons_studio_settings(
                bundle_name=bundle_name,
                variant=variant,
                site_id=site_id,
                use_site=use_site,
                only_values=only_values
            )

        return self.get_addons_project_settings(
            project_name=project_name,
            bundle_name=bundle_name,
            variant=variant,
            site_id=site_id,
            use_site=use_site,
            only_values=only_values
        )
