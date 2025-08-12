from __future__ import annotations

import json
import typing
from typing import Optional, Generator, Iterable, Any

from ._base import _BaseServerAPI
from .utils import prepare_query_string, fill_own_attribs
from .graphql_queries import projects_graphql_query

if typing.TYPE_CHECKING:
    from .typing import ProjectDict


class _ProjectsAPI(_BaseServerAPI):
    def get_rest_project(
        self, project_name: str
    ) -> Optional["ProjectDict"]:
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
    ) -> Generator["ProjectDict", None, None]:
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
    ) -> Generator["ProjectDict", None, None]:
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
    ) -> Optional["ProjectDict"]:
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
    ):
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
