from __future__ import annotations

import warnings
import typing
from typing import Optional, Iterable, Generator

from ayon_api.graphql_queries import workfiles_info_graphql_query

from .base import BaseServerAPI, _PLACEHOLDER

if typing.TYPE_CHECKING:
    from ayon_api.typing import WorkfileInfoDict


class WorkfilesAPI(BaseServerAPI):
    def get_workfiles_info(
        self,
        project_name: str,
        workfile_ids: Optional[Iterable[str]] = None,
        task_ids: Optional[Iterable[str]] =None,
        paths: Optional[Iterable[str]] =None,
        path_regex: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
        has_links: Optional[str]=None,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Generator[WorkfileInfoDict, None, None]:
        """Workfile info entities by passed filters.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_ids (Optional[Iterable[str]]): Workfile ids.
            task_ids (Optional[Iterable[str]]): Task ids.
            paths (Optional[Iterable[str]]): Rootless workfiles paths.
            path_regex (Optional[str]): Regex filter for workfile path.
            statuses (Optional[Iterable[str]]): Workfile info statuses used
                for filtering.
            tags (Optional[Iterable[str]]): Workfile info tags used
                for filtering.
            has_links (Optional[Literal[IN, OUT, ANY]]): Filter
                representations with IN/OUT/ANY links.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Generator[WorkfileInfoDict, None, None]: Queried workfile info
                entites.

        """
        filters = {"projectName": project_name}
        if task_ids is not None:
            task_ids = set(task_ids)
            if not task_ids:
                return
            filters["taskIds"] = list(task_ids)

        if paths is not None:
            paths = set(paths)
            if not paths:
                return
            filters["paths"] = list(paths)

        if path_regex is not None:
            filters["workfilePathRegex"] = path_regex

        if workfile_ids is not None:
            workfile_ids = set(workfile_ids)
            if not workfile_ids:
                return
            filters["workfileIds"] = list(workfile_ids)

        if statuses is not None:
            statuses = set(statuses)
            if not statuses:
                return
            filters["workfileStatuses"] = list(statuses)

        if tags is not None:
            tags = set(tags)
            if not tags:
                return
            filters["workfileTags"] = list(tags)

        if has_links is not None:
            filters["workfilehasLinks"] = has_links.upper()

        if not fields:
            fields = self.get_default_fields_for_type("workfile")
        else:
            fields = set(fields)
            self._prepare_fields("workfile", fields)

        if own_attributes is not _PLACEHOLDER:
            warnings.warn(
                (
                    "'own_attributes' is not supported for workfiles. The"
                    " argument will be removed form function signature in"
                    " future (apx. version 1.0.10 or 1.1.0)."
                ),
                DeprecationWarning
            )

        query = workfiles_info_graphql_query(fields)

        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        for parsed_data in query.continuous_query(self):
            for workfile_info in parsed_data["project"]["workfiles"]:
                self._convert_entity_data(workfile_info)
                yield workfile_info

    def get_workfile_info(
        self,
        project_name: str,
        task_id: str,
        path: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[WorkfileInfoDict]:
        """Workfile info entity by task id and workfile path.

        Args:
            project_name (str): Project under which the entity is located.
            task_id (str): Task id.
            path (str): Rootless workfile path.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Optional[WorkfileInfoDict]: Workfile info entity or None.

        """
        if not task_id or not path:
            return None

        for workfile_info in self.get_workfiles_info(
            project_name,
            task_ids=[task_id],
            paths=[path],
            fields=fields,
            own_attributes=own_attributes
        ):
            return workfile_info
        return None

    def get_workfile_info_by_id(
        self,
        project_name: str,
        workfile_id: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes=_PLACEHOLDER,
    ) -> Optional[WorkfileInfoDict]:
        """Workfile info entity by id.

        Args:
            project_name (str): Project under which the entity is located.
            workfile_id (str): Workfile info id.
            fields (Optional[Iterable[str]]): Fields to be queried for
                representation. All possible fields are returned if 'None' is
                passed.
            own_attributes (Optional[bool]): DEPRECATED: Not supported for
                workfiles.

        Returns:
            Optional[WorkfileInfoDict]: Workfile info entity or None.

        """
        if not workfile_id:
            return None

        for workfile_info in self.get_workfiles_info(
            project_name,
            workfile_ids=[workfile_id],
            fields=fields,
            own_attributes=own_attributes
        ):
            return workfile_info
        return None
