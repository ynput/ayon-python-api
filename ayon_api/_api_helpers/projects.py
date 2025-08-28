from __future__ import annotations

import json
import platform
import warnings
import typing
from typing import Optional, Generator, Iterable, Any

from ayon_api.constants import PROJECT_NAME_REGEX
from ayon_api.utils import prepare_query_string, fill_own_attribs
from ayon_api.graphql_queries import projects_graphql_query

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from ayon_api.typing import ProjectDict, AnatomyPresetDict


class ProjectsAPI(BaseServerAPI):
    def get_project_anatomy_presets(self) -> list[AnatomyPresetDict]:
        """Anatomy presets available on server.

        Content has basic information about presets. Example output::

            [
                {
                    "name": "netflix_VFX",
                    "primary": false,
                    "version": "1.0.0"
                },
                {
                    ...
                },
                ...
            ]

        Returns:
            list[dict[str, str]]: Anatomy presets available on server.

        """
        result = self.get("anatomy/presets")
        result.raise_for_status()
        return result.data.get("presets") or []

    def get_default_anatomy_preset_name(self) -> str:
        """Name of default anatomy preset.

        Primary preset is used as default preset. But when primary preset is
        not set a built-in is used instead. Built-in preset is named '_'.

        Returns:
            str: Name of preset that can be used by
                'get_project_anatomy_preset'.

        """
        for preset in self.get_project_anatomy_presets():
            if preset.get("primary"):
                return preset["name"]
        return "_"

    def get_project_anatomy_preset(
        self, preset_name: Optional[str] = None
    ) -> AnatomyPresetDict:
        """Anatomy preset values by name.

        Get anatomy preset values by preset name. Primary preset is returned
        if preset name is set to 'None'.

        Args:
            preset_name (Optional[str]): Preset name.

        Returns:
            AnatomyPresetDict: Anatomy preset values.

        """
        if preset_name is None:
            preset_name = "__primary__"
            major, minor, patch, _, _ = self.get_server_version_tuple()
            if (major, minor, patch) < (1, 0, 8):
                preset_name = self.get_default_anatomy_preset_name()

        result = self.get(f"anatomy/presets/{preset_name}")
        result.raise_for_status()
        return result.data

    def get_built_in_anatomy_preset(self) -> AnatomyPresetDict:
        """Get built-in anatomy preset.

        Returns:
            AnatomyPresetDict: Built-in anatomy preset.

        """
        preset_name = "__builtin__"
        major, minor, patch, _, _ = self.get_server_version_tuple()
        if (major, minor, patch) < (1, 0, 8):
            preset_name = "_"
        return self.get_project_anatomy_preset(preset_name)

    def get_build_in_anatomy_preset(self) -> AnatomyPresetDict:
        warnings.warn(
            (
                "Used deprecated 'get_build_in_anatomy_preset' use"
                " 'get_built_in_anatomy_preset' instead."
            ),
            DeprecationWarning
        )
        return self.get_built_in_anatomy_preset()

    def get_rest_project(
        self, project_name: str
    ) -> Optional[ProjectDict]:
        """Query project by name.

        This call returns project with anatomy data.

        Args:
            project_name (str): Name of project.

        Returns:
            Optional[ProjectDict]: Project entity data or 'None' if
                project was not found.

        """
        if not project_name:
            return None

        response = self.get(f"projects/{project_name}")
        # TODO ignore only error about not existing project
        if response.status != 200:
            return None
        project = response.data
        self._fill_project_entity_data(project)
        return project

    def get_rest_projects(
        self,
        active: Optional[bool] = True,
        library: Optional[bool] = None,
    ) -> Generator[ProjectDict, None, None]:
        """Query available project entities.

        User must be logged in.

        Args:
            active (Optional[bool]): Filter active/inactive projects. Both
                are returned if 'None' is passed.
            library (Optional[bool]): Filter standard/library projects. Both
                are returned if 'None' is passed.

        Returns:
            Generator[ProjectDict, None, None]: Available projects.

        """
        for project_name in self.get_project_names(active, library):
            project = self.get_rest_project(project_name)
            if project:
                yield project

    def get_project_names(
        self,
        active: Optional[bool] = True,
        library: Optional[bool] = None,
    ) -> list[str]:
        """Receive available project names.

        User must be logged in.

        Args:
            active (Optional[bool]): Filter active/inactive projects. Both
                are returned if 'None' is passed.
            library (Optional[bool]): Filter standard/library projects. Both
                are returned if 'None' is passed.

        Returns:
            list[str]: List of available project names.

        """
        if active is not None:
            active = "true" if active else "false"

        if library is not None:
            library = "true" if library else "false"

        query = prepare_query_string({"active": active, "library": library})

        response = self.get(f"projects{query}")
        response.raise_for_status()
        data = response.data
        project_names = []
        if data:
            for project in data["projects"]:
                project_names.append(project["name"])
        return project_names

    def get_projects(
        self,
        active: Optional[bool] = True,
        library: Optional[bool] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Generator[ProjectDict, None, None]:
        """Get projects.

        Args:
            active (Optional[bool]): Filter active or inactive projects.
                Filter is disabled when 'None' is passed.
            library (Optional[bool]): Filter library projects. Filter is
                disabled when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for project.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Generator[ProjectDict, None, None]: Queried projects.

        """
        if fields is not None:
            fields = set(fields)

        graphql_fields, use_rest = self._get_project_graphql_fields(fields)
        projects_by_name = {}
        if graphql_fields:
            projects = list(self._get_graphql_projects(
                active,
                library,
                fields=graphql_fields,
                own_attributes=own_attributes,
            ))
            if not use_rest:
                yield from projects
                return
            projects_by_name = {p["name"]: p for p in projects}

        for project in self.get_rest_projects(active, library):
            name = project["name"]
            graphql_p = projects_by_name.get(name)
            if graphql_p:
                project["productTypes"] = graphql_p["productTypes"]
            yield project

    def get_project(
        self,
        project_name: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional[ProjectDict]:
        """Get project.

        Args:
            project_name (str): Name of project.
            fields (Optional[Iterable[str]]): fields to be queried
                for project.
            own_attributes (Optional[bool]): Attribute values that are
                not explicitly set on entity will have 'None' value.

        Returns:
            Optional[ProjectDict]: Project entity data or None
                if project was not found.

        """
        if fields is not None:
            fields = set(fields)

        graphql_fields, use_rest = self._get_project_graphql_fields(fields)
        graphql_project = None
        if graphql_fields:
            graphql_project = next(self._get_graphql_projects(
                None,
                None,
                fields=graphql_fields,
                own_attributes=own_attributes,
            ), None)
            if not graphql_project or not use_rest:
                return graphql_project

        project = self.get_rest_project(project_name)
        if own_attributes:
            fill_own_attribs(project)
        if graphql_project:
            project["productTypes"] = graphql_project["productTypes"]
        return project

    def create_project(
        self,
        project_name: str,
        project_code: str,
        library_project: bool = False,
        preset_name: Optional[str] = None,
    ) -> ProjectDict:
        """Create project using AYON settings.

        This project creation function is not validating project entity on
        creation. It is because project entity is created blindly with only
        minimum required information about project which is name and code.

        Entered project name must be unique and project must not exist yet.

        Note:
            This function is here to be OP v4 ready but in v3 has more logic
                to do. That's why inner imports are in the body.

        Args:
            project_name (str): New project name. Should be unique.
            project_code (str): Project's code should be unique too.
            library_project (Optional[bool]): Project is library project.
            preset_name (Optional[str]): Name of anatomy preset. Default is
                used if not passed.

        Raises:
            ValueError: When project name already exists.

        Returns:
            ProjectDict: Created project entity.

        """
        if self.get_project(project_name):
            raise ValueError(
                f"Project with name \"{project_name}\" already exists"
            )

        if not PROJECT_NAME_REGEX.match(project_name):
            raise ValueError(
                f"Project name \"{project_name}\" contain invalid characters"
            )

        preset = self.get_project_anatomy_preset(preset_name)

        result = self.post(
            "projects",
            name=project_name,
            code=project_code,
            anatomy=preset,
            library=library_project
        )

        if result.status != 201:
            details = f"Unknown details ({result.status})"
            if result.data:
                details = result.data.get("detail") or details
            raise ValueError(
                f"Failed to create project \"{project_name}\": {details}"
            )

        return self.get_project(project_name)

    def update_project(
        self,
        project_name: str,
        library: Optional[bool] = None,
        folder_types: Optional[list[dict[str, Any]]] = None,
        task_types: Optional[list[dict[str, Any]]] = None,
        link_types: Optional[list[dict[str, Any]]] = None,
        statuses: Optional[list[dict[str, Any]]] = None,
        tags: Optional[list[dict[str, Any]]] = None,
        config: Optional[dict[str, Any]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        active: Optional[bool] = None,
        project_code: Optional[str] = None,
        **changes
    ) -> None:
        """Update project entity on server.

        Args:
            project_name (str): Name of project.
            library (Optional[bool]): Change library state.
            folder_types (Optional[list[dict[str, Any]]]): Folder type
                definitions.
            task_types (Optional[list[dict[str, Any]]]): Task type
                definitions.
            link_types (Optional[list[dict[str, Any]]]): Link type
                definitions.
            statuses (Optional[list[dict[str, Any]]]): Status definitions.
            tags (Optional[list[dict[str, Any]]]): List of tags available to
                set on entities.
            config (Optional[dict[str, Any]]): Project anatomy config
                with templates and roots.
            attrib (Optional[dict[str, Any]]): Project attributes to change.
            data (Optional[dict[str, Any]]): Custom data of a project. This
                value will 100% override project data.
            active (Optional[bool]): Change active state of a project.
            project_code (Optional[str]): Change project code. Not recommended
                during production.
            **changes: Other changed keys based on Rest API documentation.

        """
        changes.update({
            key: value
            for key, value in (
                ("library", library),
                ("folderTypes", folder_types),
                ("taskTypes", task_types),
                ("linkTypes", link_types),
                ("statuses", statuses),
                ("tags", tags),
                ("config", config),
                ("attrib", attrib),
                ("data", data),
                ("active", active),
                ("code", project_code),
            )
            if value is not None
        })
        response = self.patch(
            f"projects/{project_name}",
            **changes
        )
        response.raise_for_status()

    def delete_project(self, project_name: str):
        """Delete project from server.

        This will completely remove project from server without any step back.

        Args:
            project_name (str): Project name that will be removed.

        """
        if not self.get_project(project_name):
            raise ValueError(
                f"Project with name \"{project_name}\" was not found"
            )

        result = self.delete(f"projects/{project_name}")
        if result.status_code != 204:
            detail = result.data["detail"]
            raise ValueError(
                f"Failed to delete project \"{project_name}\". {detail}"
            )

    def get_project_root_overrides(
        self, project_name: str
    ) -> dict[str, dict[str, str]]:
        """Root overrides per site name.

        Method is based on logged user and can't be received for any other
            user on server.

        Output will contain only roots per site id used by logged user.

        Args:
            project_name (str): Name of project.

        Returns:
             dict[str, dict[str, str]]: Root values by root name by site id.

        """
        result = self.get(f"projects/{project_name}/roots")
        result.raise_for_status()
        return result.data

    def get_project_roots_by_site(
        self, project_name: str
    ) -> dict[str, dict[str, str]]:
        """Root overrides per site name.

        Method is based on logged user and can't be received for any other
        user on server.

        Output will contain only roots per site id used by logged user.

        Deprecated:
            Use 'get_project_root_overrides' instead. Function
                deprecated since 1.0.6

        Args:
            project_name (str): Name of project.

        Returns:
             dict[str, dict[str, str]]: Root values by root name by site id.

        """
        warnings.warn(
            (
                "Method 'get_project_roots_by_site' is deprecated."
                " Please use 'get_project_root_overrides' instead."
            ),
            DeprecationWarning
        )
        return self.get_project_root_overrides(project_name)

    def get_project_root_overrides_by_site_id(
        self, project_name: str, site_id: Optional[str] = None
    ) -> dict[str, str]:
        """Root overrides for site.

        If site id is not passed a site set in current api object is used
        instead.

        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.

        Returns:
            dict[str, str]: Root values by root name or None if
                site does not have overrides.

        """
        if site_id is None:
            site_id = self.get_site_id()

        if site_id is None:
            return {}
        roots = self.get_project_root_overrides(project_name)
        return roots.get(site_id, {})

    def get_project_roots_for_site(
        self, project_name: str, site_id: Optional[str] = None
    ) -> dict[str, str]:
        """Root overrides for site.

        If site id is not passed a site set in current api object is used
        instead.

        Deprecated:
            Use 'get_project_root_overrides_by_site_id' instead. Function
                deprecated since 1.0.6
        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.

        Returns:
            dict[str, str]: Root values by root name, root name is not
                available if it does not have overrides.

        """
        warnings.warn(
            (
                "Method 'get_project_roots_for_site' is deprecated."
                " Please use 'get_project_root_overrides_by_site_id' instead."
            ),
            DeprecationWarning
        )
        return self.get_project_root_overrides_by_site_id(project_name)

    def get_project_roots_by_site_id(
        self, project_name: str, site_id: Optional[str] = None
    ) -> dict[str, str]:
        """Root values for a site.

        If site id is not passed a site set in current api object is used
        instead. If site id is not available, default roots are returned
        for current platform.

        Args:
            project_name (str): Name of project.
            site_id (Optional[str]): Site id for which want to receive
                root values.

        Returns:
            dict[str, str]: Root values.

        """
        if site_id is None:
            site_id = self.get_site_id()

        return self._get_project_roots_values(project_name, site_id=site_id)

    def get_project_roots_by_platform(
        self, project_name: str, platform_name: Optional[str] = None
    ) -> dict[str, str]:
        """Root values for a site.

        If platform name is not passed current platform name is used instead.

        This function does return root values without site overrides. It is
            possible to use the function to receive default root values.

        Args:
            project_name (str): Name of project.
            platform_name (Optional[Literal["windows", "linux", "darwin"]]):
                Platform name for which want to receive root values. Current
                platform name is used if not passed.

        Returns:
            dict[str, str]: Root values.

        """
        return self._get_project_roots_values(
            project_name, platform_name=platform_name
        )

    def _get_project_graphql_fields(
        self, fields: Optional[set[str]]
    ) -> tuple[set[str], bool]:
        """Fetch of project must be done using REST endpoint.

        Returns:
            set[str]: GraphQl fields.

        """
        if fields is None:
            return set(), True

        has_product_types = False
        graphql_fields = set()
        for field in fields:
            # Product types are available only in GraphQl
            if field.startswith("productTypes"):
                has_product_types = True
                graphql_fields.add(field)

        if not has_product_types:
            return set(), True

        inters = fields & {"name", "code", "active", "library"}
        remainders = fields - (inters | graphql_fields)
        if remainders:
            graphql_fields.add("name")
            return graphql_fields, True
        graphql_fields |= inters
        return graphql_fields, False

    def _fill_project_entity_data(self, project: dict[str, Any]) -> None:
        # Add fake scope to statuses if not available
        if "statuses" in project:
            for status in project["statuses"]:
                scope = status.get("scope")
                if scope is None:
                    status["scope"] = [
                        "folder",
                        "task",
                        "product",
                        "version",
                        "representation",
                        "workfile"
                    ]

        # Convert 'data' from string to dict if needed
        if "data" in project:
            project_data = project["data"]
            if isinstance(project_data, str):
                project_data = json.loads(project_data)
                project["data"] = project_data

            # Fill 'bundle' from data if is not filled
            if "bundle" not in project:
                bundle_data = project["data"].get("bundle", {})
                prod_bundle = bundle_data.get("production")
                staging_bundle = bundle_data.get("staging")
                project["bundle"] = {
                    "production": prod_bundle,
                    "staging": staging_bundle,
                }

        # Convert 'config' from string to dict if needed
        config = project.get("config")
        if isinstance(config, str):
            project["config"] = json.loads(config)

        # Unifiy 'linkTypes' data structure from REST and GraphQL
        if "linkTypes" in project:
            for link_type in project["linkTypes"]:
                if "data" in link_type:
                    link_data = link_type.pop("data")
                    link_type.update(link_data)
                    if "style" not in link_type:
                        link_type["style"] = None
                    if "color" not in link_type:
                        link_type["color"] = None

    def _get_graphql_projects(
        self,
        active: Optional[bool],
        library: Optional[bool],
        fields: set[str],
        own_attributes: bool,
        project_name: Optional[str] = None
    ) -> Generator[ProjectDict, None, None]:
        if active is not None:
            fields.add("active")

        if library is not None:
            fields.add("library")

        self._prepare_fields("project", fields, own_attributes)

        query = projects_graphql_query(fields)
        if project_name is not None:
            query.set_variable_value("projectName", project_name)

        for parsed_data in query.continuous_query(self):
            for project in parsed_data["projects"]:
                if active is not None and active is not project["active"]:
                    continue
                if own_attributes:
                    fill_own_attribs(project)
                self._fill_project_entity_data(project)
                yield project

    def _get_project_roots_values(
        self,
        project_name: str,
        site_id: Optional[str] = None,
        platform_name: Optional[str] = None,
    ) -> dict[str, str]:
        """Root values for site or platform.

        Helper function that treats 'siteRoots' endpoint. The endpoint
            requires to pass exactly one query value of site id
            or platform name.

        When using platform name, it does return default project roots without
            any site overrides.

        Output should contain all project roots with all filled values. If
            value does not have override on a site, it should be filled with
            project default value.

        Args:
            project_name (str): Project name.
            site_id (Optional[str]): Site id for which want to receive
                site overrides.
            platform_name (Optional[str]): Platform for which want to receive
                roots.

        Returns:
            dict[str, str]: Root values.

        """
        query_data = {}
        if site_id is not None:
            query_data["site_id"] = site_id
        else:
            if platform_name is None:
                platform_name = platform.system()
            query_data["platform"] = platform_name.lower()

        query = prepare_query_string(query_data)
        response = self.get(
            f"projects/{project_name}/siteRoots{query}"
        )
        response.raise_for_status()
        return response.data
