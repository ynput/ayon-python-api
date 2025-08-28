from __future__ import annotations

import json
import warnings
import typing
from typing import Optional, Iterable, Generator, Any

from ayon_api.constants import REPRESENTATION_FILES_FIELDS
from ayon_api.utils import (
    RepresentationHierarchy,
    RepresentationParents,
    PatternType,
    create_entity_id,
)
from ayon_api.graphql_queries import (
    representations_graphql_query,
    representations_hierarchy_qraphql_query,
)

from .base import BaseServerAPI, _PLACEHOLDER

if typing.TYPE_CHECKING:
    from ayon_api.typing import RepresentationDict


class RepresentationsAPI(BaseServerAPI):
    def get_rest_representation(
        self, project_name: str, representation_id: str
    ) -> Optional[RepresentationDict]:
        return self.get_rest_entity_by_id(
            project_name, "representation", representation_id
        )

    def get_representations(
        self,
        project_name: str,
        representation_ids: Optional[Iterable[str]] = None,
        representation_names: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
        names_by_version_ids: Optional[dict[str, Iterable[str]]] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        active: Optional[bool] = True,
        has_links: Optional[str] = None,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator[RepresentationDict, None, None]:
        """Get representation entities based on passed filters from server.

        .. todo::

            Add separated function for 'names_by_version_ids' filtering.
            Because can't be combined with others.

        Args:
            project_name (str): Name of project where to look for versions.
            representation_ids (Optional[Iterable[str]]): Representation ids
                used for representation filtering.
            representation_names (Optional[Iterable[str]]): Representation
                names used for representation filtering.
            version_ids (Optional[Iterable[str]]): Version ids used for
                representation filtering. Versions are parents of
                representations.
            names_by_version_ids (Optional[dict[str, Iterable[str]]]): Find
                representations by names and version ids. This filter
                discards all other filters.
            statuses (Optional[Iterable[str]]): Representation statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Representation tags used
                for filtering.
            active (Optional[bool]): Receive active/inactive entities.
                Both are returned when 'None' is passed.
            has_links (Optional[Literal[IN, OUT, ANY]]): Filter
                representations with IN/OUT/ANY links.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Generator[RepresentationDict, None, None]: Queried
                representation entities.

        """
        if not fields:
            fields = self.get_default_fields_for_type("representation")
        else:
            fields = set(fields)
            self._prepare_fields("representation", fields)

        if active is not None:
            fields.add("active")

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for representations. "
                    "The argument will be removed form function signature in "
                    "future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        if "files" in fields:
            fields.discard("files")
            fields |= REPRESENTATION_FILES_FIELDS

        filters = {
            "projectName": project_name
        }

        if representation_ids is not None:
            representation_ids = set(representation_ids)
            if not representation_ids:
                return
            filters["representationIds"] = list(representation_ids)

        version_ids_filter = None
        representation_names_filter = None
        if names_by_version_ids is not None:
            version_ids_filter = set()
            representation_names_filter = set()
            for version_id, names in names_by_version_ids.items():
                version_ids_filter.add(version_id)
                representation_names_filter |= set(names)

            if not version_ids_filter or not representation_names_filter:
                return

        else:
            if representation_names is not None:
                representation_names_filter = set(representation_names)
                if not representation_names_filter:
                    return

            if version_ids is not None:
                version_ids_filter = set(version_ids)
                if not version_ids_filter:
                    return

        if version_ids_filter:
            filters["versionIds"] = list(version_ids_filter)

        if representation_names_filter:
            filters["representationNames"] = list(representation_names_filter)

        if statuses is not None:
            statuses = set(statuses)
            if not statuses:
                return
            filters["representationStatuses"] = list(statuses)

        if tags is not None:
            tags = set(tags)
            if not tags:
                return
            filters["representationTags"] = list(tags)

        if has_links is not None:
            filters["representationHasLinks"] = has_links.upper()

        query = representations_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for repre in parsed_data["project"]["representations"]:
                if active is not None and active is not repre["active"]:
                    continue

                self._convert_entity_data(repre)

                self._representation_conversion(repre)

                yield repre

    def get_representation_by_id(
        self,
        project_name: str,
        representation_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[RepresentationDict]:
        """Query representation entity from server based on id filter.

        Args:
            project_name (str): Project where to look for representation.
            representation_id (str): Id of representation.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[RepresentationDict]: Queried representation
                entity or None.

        """
        representations = self.get_representations(
            project_name,
            representation_ids=[representation_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for representation in representations:
            return representation
        return None

    def get_representation_by_name(
        self,
        project_name: str,
        representation_name: str,
        version_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[RepresentationDict]:
        """Query representation entity by name and version id.

        Args:
            project_name (str): Project where to look for representation.
            representation_name (str): Representation name.
            version_id (str): Version id.
            fields (Optional[Iterable[str]]): fields to be queried
                for representations.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                representations.

        Returns:
            Optional[RepresentationDict]: Queried representation entity
                or None.

        """
        representations = self.get_representations(
            project_name,
            representation_names=[representation_name],
            version_ids=[version_id],
            active=None,
            fields=fields,
            own_attributes=own_attributes
        )
        for representation in representations:
            return representation
        return None

    def get_representations_hierarchy(
        self,
        project_name: str,
        representation_ids: Iterable[str],
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        task_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
        representation_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, RepresentationHierarchy]:
        """Find representation with parents by representation id.

        Representation entity with parent entities up to project.

        Default fields are used when any fields are set to `None`. But it is
            possible to pass in empty iterable (list, set, tuple) to skip
            entity.

        Args:
            project_name (str): Project where to look for entities.
            representation_ids (Iterable[str]): Representation ids.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            task_fields (Optional[Iterable[str]]): Task fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.
            representation_fields (Optional[Iterable[str]]): Representation
                fields.

        Returns:
            dict[str, RepresentationHierarchy]: Parent entities by
                representation id.

        """
        if not representation_ids:
            return {}

        if project_fields is not None:
            project_fields = set(project_fields)
            self._prepare_fields("project", project_fields)

        project = {}
        if project_fields is None:
            project = self.get_project(project_name)

        elif project_fields:
            # Keep project as empty dictionary if does not have
            #   filled any fields
            project = self.get_project(
                project_name, fields=project_fields
            )

        repre_ids = set(representation_ids)
        output = {
            repre_id: RepresentationHierarchy(
                project, None, None, None, None, None
            )
            for repre_id in representation_ids
        }

        if folder_fields is None:
            folder_fields = self.get_default_fields_for_type("folder")
        else:
            folder_fields = set(folder_fields)

        if task_fields is None:
            task_fields = self.get_default_fields_for_type("task")
        else:
            task_fields = set(task_fields)

        if product_fields is None:
            product_fields = self.get_default_fields_for_type("product")
        else:
            product_fields = set(product_fields)

        if version_fields is None:
            version_fields = self.get_default_fields_for_type("version")
        else:
            version_fields = set(version_fields)

        if representation_fields is None:
            representation_fields = self.get_default_fields_for_type(
                "representation"
            )
        else:
            representation_fields = set(representation_fields)

        for (entity_type, fields) in (
            ("folder", folder_fields),
            ("task", task_fields),
            ("product", product_fields),
            ("version", version_fields),
            ("representation", representation_fields),
        ):
            self._prepare_fields(entity_type, fields)

        representation_fields.add("id")

        query = representations_hierarchy_qraphql_query(
            folder_fields,
            task_fields,
            product_fields,
            version_fields,
            representation_fields,
        )
        query.set_variable_value("projectName", project_name)
        query.set_variable_value("representationIds", list(repre_ids))

        parsed_data = query.query(self)
        for repre in parsed_data["project"]["representations"]:
            repre_id = repre["id"]
            version = repre.pop("version", {})
            product = version.pop("product", {})
            task = version.pop("task", None)
            folder = product.pop("folder", {})
            self._convert_entity_data(repre)
            self._representation_conversion(repre)
            self._convert_entity_data(version)
            self._convert_entity_data(product)
            self._convert_entity_data(folder)
            if task:
                self._convert_entity_data(task)

            output[repre_id] = RepresentationHierarchy(
                project, folder, task, product, version, repre
            )

        return output

    def get_representation_hierarchy(
        self,
        project_name: str,
        representation_id: str,
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        task_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
        representation_fields: Optional[Iterable[str]] = None,
    ) -> Optional[RepresentationHierarchy]:
        """Find representation parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_id (str): Representation id.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            task_fields (Optional[Iterable[str]]): Task fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.
            representation_fields (Optional[Iterable[str]]): Representation
                fields.

        Returns:
            RepresentationHierarchy: Representation hierarchy entities.

        """
        if not representation_id:
            return None

        parents_by_repre_id = self.get_representations_hierarchy(
            project_name,
            [representation_id],
            project_fields=project_fields,
            folder_fields=folder_fields,
            task_fields=task_fields,
            product_fields=product_fields,
            version_fields=version_fields,
            representation_fields=representation_fields,
        )
        return parents_by_repre_id[representation_id]

    def get_representations_parents(
        self,
        project_name: str,
        representation_ids: Iterable[str],
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, RepresentationParents]:
        """Find representations parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_ids (Iterable[str]): Representation ids.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.

        Returns:
            dict[str, RepresentationParents]: Parent entities by
                representation id.

        """
        hierarchy_by_repre_id = self.get_representations_hierarchy(
            project_name,
            representation_ids,
            project_fields=project_fields,
            folder_fields=folder_fields,
            task_fields=set(),
            product_fields=product_fields,
            version_fields=version_fields,
            representation_fields={"id"},
        )
        return {
            repre_id: RepresentationParents(
                hierarchy.version,
                hierarchy.product,
                hierarchy.folder,
                hierarchy.project,
            )
            for repre_id, hierarchy in hierarchy_by_repre_id.items()
        }

    def get_representation_parents(
        self,
        project_name: str,
        representation_id: str,
        project_fields: Optional[Iterable[str]] = None,
        folder_fields: Optional[Iterable[str]] = None,
        product_fields: Optional[Iterable[str]] = None,
        version_fields: Optional[Iterable[str]] = None,
    ) -> Optional[RepresentationParents]:
        """Find representation parents by representation id.

        Representation parent entities up to project.

        Args:
            project_name (str): Project where to look for entities.
            representation_id (str): Representation id.
            project_fields (Optional[Iterable[str]]): Project fields.
            folder_fields (Optional[Iterable[str]]): Folder fields.
            product_fields (Optional[Iterable[str]]): Product fields.
            version_fields (Optional[Iterable[str]]): Version fields.

        Returns:
            RepresentationParents: Representation parent entities.

        """
        if not representation_id:
            return None

        parents_by_repre_id = self.get_representations_parents(
            project_name,
            [representation_id],
            project_fields=project_fields,
            folder_fields=folder_fields,
            product_fields=product_fields,
            version_fields=version_fields,
        )
        return parents_by_repre_id[representation_id]

    def get_repre_ids_by_context_filters(
        self,
        project_name: str,
        context_filters: Optional[dict[str, Iterable[str]]],
        representation_names: Optional[Iterable[str]] = None,
        version_ids: Optional[Iterable[str]] = None,
    ) -> list[str]:
        """Find representation ids which match passed context filters.

        Each representation has context integrated on representation entity in
        database. The context may contain project, folder, task name or
        product name, product type and many more. This implementation gives
        option to quickly filter representation based on representation data
        in database.

        Context filters have defined structure. To define filter of nested
            subfield use dot '.' as delimiter (For example 'task.name').
        Filter values can be regex filters. String or ``re.Pattern`` can
            be used.

        Args:
            project_name (str): Project where to look for representations.
            context_filters (dict[str, list[str]]): Filters of context fields.
            representation_names (Optional[Iterable[str]]): Representation
                names, can be used as additional filter for representations
                by their names.
            version_ids (Optional[Iterable[str]]): Version ids, can be used
                as additional filter for representations by their parent ids.

        Returns:
            list[str]: Representation ids that match passed filters.

        Example:
            The function returns just representation ids so if entities are
                required for funtionality they must be queried afterwards by
                their ids.
            >>> from ayon_api import get_repre_ids_by_context_filters
            >>> from ayon_api import get_representations
            >>> project_name = "testProject"
            >>> filters = {
            ...     "task.name": ["[aA]nimation"],
            ...     "product": [".*[Mm]ain"]
            ... }
            >>> repre_ids = get_repre_ids_by_context_filters(
            ...     project_name, filters)
            >>> repres = get_representations(project_name, repre_ids)

        """
        if not isinstance(context_filters, dict):
            raise TypeError(
                f"Expected 'dict' got {str(type(context_filters))}"
            )

        filter_body = {}
        if representation_names is not None:
            if not representation_names:
                return []
            filter_body["names"] = list(set(representation_names))

        if version_ids is not None:
            if not version_ids:
                return []
            filter_body["versionIds"] = list(set(version_ids))

        body_context_filters = []
        for key, filters in context_filters.items():
            if not isinstance(filters, (set, list, tuple)):
                raise TypeError(
                    "Expected 'set', 'list', 'tuple' got {}".format(
                        str(type(filters))))

            new_filters = set()
            for filter_value in filters:
                if isinstance(filter_value, PatternType):
                    filter_value = filter_value.pattern
                new_filters.add(filter_value)

            body_context_filters.append({
                "key": key,
                "values": list(new_filters)
            })

        response = self.post(
            f"projects/{project_name}/repreContextFilter",
            context=body_context_filters,
            **filter_body
        )
        response.raise_for_status()
        return response.data["ids"]

    def create_representation(
        self,
        project_name: str,
        name: str,
        version_id: str,
        files: Optional[list[dict[str, Any]]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        traits: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]]=None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        representation_id: Optional[str] = None,
    ) -> str:
        """Create new representation.

        Args:
            project_name (str): Project name.
            name (str): Representation name.
            version_id (str): Parent version id.
            files (Optional[list[dict]]): Representation files information.
            attrib (Optional[dict[str, Any]]): Representation attributes.
            data (Optional[dict[str, Any]]): Representation data.
            traits (Optional[dict[str, Any]]): Representation traits
                serialized data as dict.
            tags (Optional[Iterable[str]]): Representation tags.
            status (Optional[str]): Representation status.
            active (Optional[bool]): Representation active state.
            representation_id (Optional[str]): Representation id. If not
                passed new id is generated.

        Returns:
            str: Representation id.

        """
        if not representation_id:
            representation_id = create_entity_id()
        create_data = {
            "id": representation_id,
            "name": name,
            "versionId": version_id,
        }
        for key, value in (
            ("files", files),
            ("attrib", attrib),
            ("data", data),
            ("traits", traits),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                create_data[key] = value

        response = self.post(
            f"projects/{project_name}/representations",
            **create_data
        )
        response.raise_for_status()
        return representation_id

    def update_representation(
        self,
        project_name: str,
        representation_id: str,
        name: Optional[str] = None,
        version_id: Optional[str] = None,
        files: Optional[list[dict[str, Any]]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        traits: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Update representation entity on server.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            representation_id (str): Representation id.
            name (Optional[str]): New name.
            version_id (Optional[str]): New version id.
            files (Optional[list[dict]]): New files
                information.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            traits (Optional[dict[str, Any]]): New traits.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("versionId", version_id),
            ("files", files),
            ("attrib", attrib),
            ("data", data),
            ("traits", traits),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        response = self.patch(
            f"projects/{project_name}/representations/{representation_id}",
            **update_data
        )
        response.raise_for_status()

    def delete_representation(
        self, project_name: str, representation_id: str
    ) -> None:
        """Delete representation.

        Args:
            project_name (str): Project name.
            representation_id (str): Representation id to delete.

        """
        response = self.delete(
            f"projects/{project_name}/representations/{representation_id}"
        )
        response.raise_for_status()

    def _representation_conversion(
        self, representation: RepresentationDict
    ) -> None:
        if "context" in representation:
            orig_context = representation["context"]
            context = {}
            if orig_context and orig_context != "null":
                context = json.loads(orig_context)
            representation["context"] = context

        repre_files = representation.get("files")
        if not repre_files:
            return

        for repre_file in repre_files:
            repre_file_size = repre_file.get("size")
            if repre_file_size is not None:
                repre_file["size"] = int(repre_file["size"])
