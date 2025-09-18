from __future__ import annotations

import warnings
import typing
from typing import Optional, Iterable, Generator, Any

from ayon_api.utils import (
    NOT_SET,
    create_entity_id,
    prepare_list_filters,
)
from ayon_api.graphql import GraphQlQuery
from ayon_api.graphql_queries import versions_graphql_query

from .base import BaseServerAPI, _PLACEHOLDER

if typing.TYPE_CHECKING:
    from ayon_api.typing import VersionDict


class VersionsAPI(BaseServerAPI):
    def get_rest_version(
        self, project_name: str, version_id: str
    ) -> Optional[VersionDict]:
        return self.get_rest_entity_by_id(project_name, "version", version_id)

    def get_versions(
        self,
        project_name: str,
        version_ids: Optional[Iterable[str]] = None,
        product_ids: Optional[Iterable[str]] = None,
        task_ids: Optional[Iterable[str]] = None,
        versions: Optional[Iterable[str]] = None,
        hero: bool = True,
        standard: bool = True,
        latest: Optional[bool] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Generator[VersionDict, None, None]:
        """Get version entities based on passed filters from server.

        Args:
            project_name (str): Name of project where to look for versions.
            version_ids (Optional[Iterable[str]]): Version ids used for
                version filtering.
            product_ids (Optional[Iterable[str]]): Product ids used for
                version filtering.
            task_ids (Optional[Iterable[str]]): Task ids used for
                version filtering.
            versions (Optional[Iterable[int]]): Versions we're interested in.
            hero (Optional[bool]): Skip hero versions when set to False.
            standard (Optional[bool]): Skip standard (non-hero) when
                set to False.
            latest (Optional[bool]): Return only latest version of standard
                versions. This can be combined only with 'standard' attribute
                set to True.
            statuses (Optional[Iterable[str]]): Representation statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Representation tags used
                for filtering.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): Fields to be queried
                for version. All possible folder fields are returned
                if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Generator[VersionDict, None, None]: Queried version entities.

        """
        if not fields:
            fields = self.get_default_fields_for_type("version")
        else:
            fields = set(fields)
            self._prepare_fields("version", fields)

        # Make sure fields have minimum required fields
        fields |= {"id", "version"}

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for versions. The"
                    " argument will be removed form function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        if not hero and not standard:
            return

        filters = {
            "projectName": project_name
        }
        if not prepare_list_filters(
            filters,
            ("taskIds", task_ids),
            ("versionIds", version_ids),
            ("productIds", product_ids),
            ("taskIds", task_ids),
            ("versions", versions),
            ("versionStatuses", statuses),
            ("versionTags", tags),
        ):
            return

        queries = []
        # Add filters based on 'hero' and 'standard'
        # NOTE: There is not a filter to "ignore" hero versions or to get
        #   latest and hero version
        # - if latest and hero versions should be returned it must be done in
        #       2 graphql queries
        if standard and not latest:
            # This query all versions standard + hero
            # - hero must be filtered out if is not enabled during loop
            query = versions_graphql_query(fields)
            for attr, filter_value in filters.items():
                query.set_variable_value(attr, filter_value)
            queries.append(query)
        else:
            if hero:
                # Add hero query if hero is enabled
                hero_query = versions_graphql_query(fields)
                for attr, filter_value in filters.items():
                    hero_query.set_variable_value(attr, filter_value)

                hero_query.set_variable_value("heroOnly", True)
                queries.append(hero_query)

            if standard:
                standard_query = versions_graphql_query(fields)
                for attr, filter_value in filters.items():
                    standard_query.set_variable_value(attr, filter_value)

                if latest:
                    standard_query.set_variable_value("latestOnly", True)
                queries.append(standard_query)

        for query in queries:
            for parsed_data in query.continuous_query(self):
                for version in parsed_data["project"]["versions"]:
                    if active is not None and version["active"] is not active:
                        continue

                    if not hero and version["version"] < 0:
                        continue

                    self._convert_entity_data(version)

                    yield version

    def get_version_by_id(
        self,
        project_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional[VersionDict]:
        """Query version entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version_id (str): Version id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_versions(
            project_name,
            version_ids={version_id},
            active=None,
            hero=True,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_version_by_name(
        self,
        project_name: str,
        version: int,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional[VersionDict]:
        """Query version entity by version and product id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version (int): Version of version entity.
            product_id (str): Product id. Product is a parent of version.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_versions(
            project_name,
            product_ids={product_id},
            versions={version},
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_version_by_id(
        self,
        project_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional[VersionDict]:
        """Query hero version entity by id.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            version_id (int): Hero version id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_hero_versions(
            project_name,
            version_ids=[version_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_version_by_product_id(
        self,
        project_name: str,
        product_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER
    ) -> Optional[VersionDict]:
        """Query hero version entity by product id.

        Only one hero version is available on a product.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_id (int): Product id.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        versions = self.get_hero_versions(
            project_name,
            product_ids=[product_id],
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_hero_versions(
        self,
        project_name: str,
        product_ids: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator[VersionDict, None, None]:
        """Query hero versions by multiple filters.

        Only one hero version is available on a product.

        Args:
            project_name (str): Name of project where to look for queried
                entities.
            product_ids (Optional[Iterable[str]]): Product ids.
            version_ids (Optional[Iterable[str]]): Version ids.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): Fields that should be returned.
                All fields are returned if 'None' is passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Version entity data or None
                if was not found.

        """
        return self.get_versions(
            project_name,
            version_ids=version_ids,
            product_ids=product_ids,
            hero=True,
            standard=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def get_last_versions(
        self,
        project_name: str,
        product_ids: Iterable[str],
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> dict[str, Optional[VersionDict]]:
        """Query last version entities by product ids.

        Args:
            project_name (str): Project where to look for representation.
            product_ids (Iterable[str]): Product ids.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            dict[str, Optional[VersionDict]]: Last versions by product id.

        """
        if fields:
            fields = set(fields)
            fields.add("productId")
        product_ids = set(product_ids)
        versions = self.get_versions(
            project_name,
            product_ids=product_ids,
            latest=True,
            hero=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        output = {
            version["productId"]: version
            for version in versions
        }
        for product_id in product_ids:
            output.setdefault(product_id, None)
        return output

    def get_last_version_by_product_id(
        self,
        project_name: str,
        product_id: str,
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[VersionDict]:
        """Query last version entity by product id.

        Args:
            project_name (str): Project where to look for representation.
            product_id (str): Product id.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                versions.

        Returns:
            Optional[VersionDict]: Queried version entity or None.

        """
        versions = self.get_versions(
            project_name,
            product_ids=[product_id],
            latest=True,
            hero=False,
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )
        for version in versions:
            return version
        return None

    def get_last_version_by_product_name(
        self,
        project_name: str,
        product_name: str,
        folder_id: str,
        active: Optional[bool] = True,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[VersionDict]:
        """Query last version entity by product name and folder id.

        Args:
            project_name (str): Project where to look for representation.
            product_name (str): Product name.
            folder_id (str): Folder id.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[VersionDict]: Queried version entity or None.

        """
        if not folder_id:
            return None

        product = self.get_product_by_name(
            project_name, product_name, folder_id, fields={"id"}
        )
        if not product:
            return None
        return self.get_last_version_by_product_id(
            project_name,
            product["id"],
            active=active,
            fields=fields,
            own_attributes=own_attributes
        )

    def version_is_latest(self, project_name: str, version_id: str) -> bool:
        """Is version latest from a product.

        Args:
            project_name (str): Project where to look for representation.
            version_id (str): Version id.

        Returns:
            bool: Version is latest or not.

        """
        query = GraphQlQuery("VersionIsLatest")
        project_name_var = query.add_variable(
            "projectName", "String!", project_name
        )
        version_id_var = query.add_variable(
            "versionId", "String!", version_id
        )
        project_query = query.add_field("project")
        project_query.set_filter("name", project_name_var)
        version_query = project_query.add_field("version")
        version_query.set_filter("id", version_id_var)
        product_query = version_query.add_field("product")
        latest_version_query = product_query.add_field("latestVersion")
        latest_version_query.add_field("id")

        parsed_data = query.query(self)
        latest_version = (
            parsed_data["project"]["version"]["product"]["latestVersion"]
        )
        return latest_version["id"] == version_id

    def create_version(
        self,
        project_name: str,
        version: int,
        product_id: str,
        task_id: Optional[str] = None,
        author: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> str:
        """Create new version.

        Args:
            project_name (str): Project name.
            version (int): Version.
            product_id (str): Parent product id.
            task_id (Optional[str]): Parent task id.
            author (Optional[str]): Version author.
            attrib (Optional[dict[str, Any]]): Version attributes.
            data (Optional[dict[str, Any]]): Version data.
            tags (Optional[Iterable[str]]): Version tags.
            status (Optional[str]): Version status.
            active (Optional[bool]): Version active state.
            thumbnail_id (Optional[str]): Version thumbnail id.
            version_id (Optional[str]): Version id. If not passed new id is
                generated.

        Returns:
            str: Version id.

        """
        if not version_id:
            version_id = create_entity_id()
        create_data = {
            "id": version_id,
            "version": version,
            "productId": product_id,
        }
        for key, value in (
            ("taskId", task_id),
            ("author", author),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/versions",
            **create_data
        )
        response.raise_for_status()
        return version_id

    def update_version(
        self,
        project_name: str,
        version_id: str,
        version: Optional[int] = None,
        product_id: Optional[str] = None,
        task_id: Optional[str] = NOT_SET,
        author: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ) -> None:
        """Update version entity on server.

        Do not pass ``task_id`` amd ``thumbnail_id`` if you don't
            want to change their values. Value ``None`` would unset
            their value.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            version_id (str): Version id.
            version (Optional[int]): New version.
            product_id (Optional[str]): New product id.
            task_id (Optional[str]): New task id.
            author (Optional[str]): New author username.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[str]): New thumbnail id.

        """
        update_data = {}
        for key, value in (
            ("version", version),
            ("productId", product_id),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
            ("author", author),
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("taskId", task_id),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/versions/{version_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_version(self, project_name: str, version_id: str) -> None:
        """Delete version.

        Args:
            project_name (str): Project name.
            version_id (str): Version id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/versions/{version_id}"
        )
        response.raise_for_status()
