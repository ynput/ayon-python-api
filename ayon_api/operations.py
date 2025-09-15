from __future__ import annotations

import os
import copy
import collections
import uuid
from abc import ABC, abstractmethod
import typing
from typing import Optional, Any, Iterable

from ._api import get_server_api_connection
from .utils import create_entity_id, REMOVED_VALUE, NOT_SET

if typing.TYPE_CHECKING:
    from .server_api import ServerAPI
    from .typing import (
        NewFolderDict,
        NewProductDict,
        NewVersionDict,
        NewRepresentationDict,
        NewWorkfileDict,
    )


def _create_or_convert_to_id(entity_id: Optional[str] = None) -> str:
    if entity_id is None:
        return create_entity_id()

    # Validate if can be converted to uuid
    uuid.UUID(entity_id)
    return entity_id


def prepare_changes(
    old_entity: dict[str, Any],
    new_entity: dict[str, Any],
    entity_type: str,
) -> dict[str, Any]:
    """Prepare changes for entity update.

    Notes:
        Argument 'entity_type' is not used, yet. But there might be
            differences in future.

    Args:
        old_entity (dict[str, Any]): Existing entity.
        new_entity (dict[str, Any]): New entity.
        entity_type (str): Entity type. "project", "folder", "product" etc.

    Returns:
        dict[str, Any]: Changes that have new entity.

    """
    changes = {}
    for key in set(new_entity.keys()):
        if key == "attrib":
            continue

        if key in new_entity and new_entity[key] != old_entity.get(key):
            changes[key] = new_entity[key]
            continue

    attrib_changes = {}
    if "attrib" in new_entity:
        old_attrib = old_entity.get("attrib") or {}
        for key, value in new_entity["attrib"].items():
            if value != old_attrib.get(key):
                attrib_changes[key] = value
    if attrib_changes:
        changes["attrib"] = attrib_changes
    return changes


def new_folder_entity(
    name: str,
    folder_type: str,
    parent_id: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    thumbnail_id: Optional[str] = None,
    entity_id: Optional[str] = None
) -> NewFolderDict:
    """Create skeleton data of folder entity.

    Args:
        name (str): Is considered as unique identifier of folder in project.
        folder_type (str): Type of folder.
        parent_id (Optional[str]): Parent folder id.
        status (Optional[str]): Product status.
        tags (Optional[list[str]]): List of tags.
        attribs (Optional[dict[str, Any]]): Explicitly set attributes
            of folder.
        data (Optional[dict[str, Any]]): Custom folder data. Empty dictionary
            is used if not passed.
        thumbnail_id (Optional[str]): Thumbnail id related to folder.
        entity_id (Optional[str]): Predefined id of entity. New id is
            created if not passed.

    Returns:
        NewFolderDict: Skeleton of folder entity.

    """
    if attribs is None:
        attribs = {}

    if data is None:
        data = {}

    if parent_id is not None:
        parent_id = _create_or_convert_to_id(parent_id)

    output = {
        "id": _create_or_convert_to_id(entity_id),
        "name": name,
        # This will be ignored
        "folderType": folder_type,
        "parentId": parent_id,
        "data": data,
        "attrib": attribs,
        "thumbnailId": thumbnail_id,
    }
    if status:
        output["status"] = status
    if tags:
        output["tags"] = tags
    return output


def new_product_entity(
    name: str,
    product_type: str,
    folder_id: str,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> NewProductDict:
    """Create skeleton data of product entity.

    Args:
        name (str): Is considered as unique identifier of
            product under folder.
        product_type (str): Product type.
        folder_id (str): Parent folder id.
        status (Optional[str]): Product status.
        tags (Optional[list[str]]): List of tags.
        attribs (Optional[dict[str, Any]]): Explicitly set attributes
            of product.
        data (Optional[dict[str, Any]]): product entity data. Empty dictionary
            is used if not passed.
        entity_id (Optional[str]): Predefined id of entity. New id is
            created if not passed.

    Returns:
        NewProductDict: Skeleton of product entity.

    """
    if attribs is None:
        attribs = {}

    if data is None:
        data = {}

    output = {
        "id": _create_or_convert_to_id(entity_id),
        "name": name,
        "productType": product_type,
        "attrib": attribs,
        "data": data,
        "folderId": _create_or_convert_to_id(folder_id),
    }
    if status:
        output["status"] = status
    if tags:
        output["tags"] = tags
    return output


def new_version_entity(
    version: int,
    product_id: str,
    task_id: Optional[str] = None,
    thumbnail_id: Optional[str] = None,
    author: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> NewVersionDict:
    """Create skeleton data of version entity.

    Args:
        version (int): Is considered as unique identifier of version
            under product.
        product_id (str): Parent product id.
        task_id (Optional[str]): Task id under which product was created.
        thumbnail_id (Optional[str]): Thumbnail related to version.
        author (Optional[str]): Name of version author.
        status (Optional[str]): Version status.
        tags (Optional[list[str]]): List of tags.
        attribs (Optional[dict[str, Any]]): Explicitly set attributes
            of version.
        data (Optional[dict[str, Any]]): Version entity custom data.
        entity_id (Optional[str]): Predefined id of entity. New id is
            created if not passed.

    Returns:
        NewVersionDict: Skeleton of version entity.

    """
    if attribs is None:
        attribs = {}

    if data is None:
        data = {}

    output = {
        "id": _create_or_convert_to_id(entity_id),
        "version": int(version),
        "productId": _create_or_convert_to_id(product_id),
        "attrib": attribs,
        "data": data
    }
    if task_id:
        output["taskId"] = task_id
    if thumbnail_id:
        output["thumbnailId"] = thumbnail_id
    if author:
        output["author"] = author
    if tags:
        output["tags"] = tags
    if status:
        output["status"] = status
    return output


def new_hero_version_entity(
    version: int,
    product_id: str,
    task_id: Optional[str] = None,
    thumbnail_id: Optional[str] = None,
    author: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> NewVersionDict:
    """Create skeleton data of hero version entity.

    Args:
        version (int): Is considered as unique identifier of version
            under product. Should be same as standard version if there is any.
        product_id (str): Parent product id.
        task_id (Optional[str]): Task id under which product was created.
        thumbnail_id (Optional[str]): Thumbnail related to version.
        author (Optional[str]): Name of version author.
        status (Optional[str]): Version status.
        tags (Optional[list[str]]): List of tags.
        attribs (Optional[dict[str, Any]]): Explicitly set attributes
            of version.
        data (Optional[dict[str, Any]]): Version entity data.
        entity_id (Optional[str]): Predefined id of entity. New id is
            created if not passed.

    Returns:
        NewVersionDict: Skeleton of version entity.

    """
    return new_version_entity(
        -abs(int(version)),
        product_id,
        task_id,
        thumbnail_id,
        author,
        status,
        tags,
        attribs,
        data,
        entity_id
    )


def new_representation_entity(
    name: str,
    version_id: str,
    files,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    traits: Optional[dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> NewRepresentationDict:
    """Create skeleton data of representation entity.

    Args:
        name (str): Representation name considered as unique identifier
            of representation under version.
        version_id (str): Parent version id.
        files (list[dict[str, str]]): List of files in representation.
        status (Optional[str]): Representation status.
        tags (Optional[list[str]]): List of tags.
        attribs (Optional[dict[str, Any]]): Explicitly set attributes
            of representation.
        data (Optional[dict[str, Any]]): Representation entity data.
        traits (Optional[dict[str, Any]]): Representation traits. Empty
            if not passed.
        entity_id (Optional[str]): Predefined id of entity. New id is created
            if not passed.

    Returns:
        NewRepresentationDict: Skeleton of representation entity.

    """
    if attribs is None:
        attribs = {}

    if data is None:
        data = {}

    output = {
        "id": _create_or_convert_to_id(entity_id),
        "versionId": _create_or_convert_to_id(version_id),
        "files": files,
        "name": name,
        "data": data,
        "attrib": attribs,
    }
    if traits:
        output["traits"] = traits
    if tags:
        output["tags"] = tags
    if status:
        output["status"] = status
    return output


def new_workfile_info(
    filepath: str,
    task_id: str,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    attribs: Optional[dict[str, Any]] = None,
    description: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
    entity_id: Optional[str] = None,
) -> NewWorkfileDict:
    """Create skeleton data of workfile info entity.

    Workfile entity is at this moment used primarily for artist notes.

    Args:
        filepath (str): Rootless workfile filepath.
        task_id (str): Task under which was workfile created.
        status (Optional[str]): Workfile status.
        tags (Optional[list[str]]): Workfile tags.
        attribs (Options[dic[str, Any]]): Explicitly set attributes.
        description (Optional[str]): Workfile description.
        data (Optional[dict[str, Any]]): Additional metadata.
        entity_id (Optional[str]): Predefined id of entity. New id is created
            if not passed.

    Returns:
        NewWorkfileDict: Skeleton of workfile info entity.

    """
    if attribs is None:
        attribs = {}

    if "extension" not in attribs:
        attribs["extension"] = os.path.splitext(filepath)[-1]

    if description:
        attribs["description"] = description

    if not data:
        data = {}

    output = {
        "id": _create_or_convert_to_id(entity_id),
        "taskId": task_id,
        "path": filepath,
        "data": data,
        "attrib": attribs
    }
    if status:
        output["status"] = status

    if tags:
        output["tags"] = tags
    return output


class AbstractOperation(ABC):
    """Base operation class.

    Opration represent a call into database. The call can create, change or
    remove data.

    Args:
        project_name (str): On which project operation will happen.
        entity_type (str): Type of entity on which change happens.
            e.g. 'folder', 'representation' etc.

    """
    def __init__(
        self,
        project_name: str,
        entity_type: str,
        session: OperationsSession,
    ) -> None:
        self._project_name = project_name
        self._entity_type = entity_type
        self._session = session
        self._id = str(uuid.uuid4())

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def id(self) -> str:
        """Identifier of operation."""
        return self._id

    @property
    def entity_type(self) -> str:
        return self._entity_type

    @property
    @abstractmethod
    def operation_name(self) -> str:
        """Stringified type of operation."""
        pass

    @property
    def session(self) -> OperationsSession:
        return self._session

    @property
    def con(self) -> ServerAPI:
        return self.session.con

    def to_data(self) -> dict[str, Any]:
        """Convert opration to data that can be converted to json or others.

        Returns:
            dict[str, Any]: Description of operation.

        """
        return {
            "id": self._id,
            "entity_type": self.entity_type,
            "project_name": self.project_name,
            "operation": self.operation_name
        }


class CreateOperation(AbstractOperation):
    """Opeartion to create an entity.

    Args:
        project_name (str): On which project operation will happen.
        entity_type (str): Type of entity on which change happens.
            e.g. 'folder', 'representation' etc.
        data (dict[str, Any]): Data of entity that will be created.

    """
    operation_name = "create"

    def __init__(
        self,
        project_name: str,
        entity_type: str,
        data: Optional[dict[str, Any]],
        session: OperationsSession,
    ) -> None:
        if not data:
            data = {}
        else:
            data = copy.deepcopy(dict(data))

        if "id" not in data:
            data["id"] = create_entity_id()

        self._data = data
        super().__init__(project_name, entity_type, session)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set_value(key, value)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def set_value(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, *args, **kwargs) -> Any:
        return self.data.get(key, *args, **kwargs)

    @property
    def entity_id(self) -> str:
        return self._data["id"]

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def to_data(self) -> dict[str, Any]:
        output = super().to_data()
        output["data"] = copy.deepcopy(self.data)
        return output

    def to_server_operation(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "create",
            "entityType": self.entity_type,
            "entityId": self.entity_id,
            "data": self._data
        }


class UpdateOperation(AbstractOperation):
    """Operation to update an entity.

    Args:
        project_name (str): On which project operation will happen.
        entity_type (str): Type of entity on which change happens.
            e.g. 'folder', 'representation' etc.
        entity_id (str): Identifier of an entity.
        update_data (dict[str, Any]): Key -> value changes that will be set in
            database. If value is set to 'REMOVED_VALUE' the key will be
            removed. Only first level of dictionary is checked (on purpose).

    """
    operation_name = "update"

    def __init__(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        update_data: dict[str, Any],
        session: OperationsSession,
    ):
        super().__init__(project_name, entity_type, session)

        self._entity_id = entity_id
        self._update_data = update_data

    @property
    def entity_id(self) -> str:
        return self._entity_id

    @property
    def update_data(self) -> dict[str, Any]:
        return self._update_data

    def to_data(self) -> dict[str, Any]:
        changes = {}
        for key, value in self._update_data.items():
            if value is REMOVED_VALUE:
                value = None
            changes[key] = value

        output = super().to_data()
        output.update({
            "entity_id": self.entity_id,
            "changes": changes
        })
        return output

    def to_server_operation(self) -> Optional[dict[str, Any]]:
        if not self._update_data:
            return None

        update_data = {}
        for key, value in self._update_data.items():
            if value is REMOVED_VALUE:
                value = None
            update_data[key] = value

        return {
            "id": self.id,
            "type": "update",
            "entityType": self.entity_type,
            "entityId": self.entity_id,
            "data": update_data
        }


class DeleteOperation(AbstractOperation):
    """Opeartion to delete an entity.

    Args:
        project_name (str): On which project operation will happen.
        entity_type (str): Type of entity on which change happens.
            e.g. 'folder', 'representation' etc.
        entity_id (str): Entity id that will be removed.

    """
    operation_name = "delete"

    def __init__(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        session: OperationsSession,
    ) -> None:
        self._entity_id = entity_id

        super().__init__(project_name, entity_type, session)

    @property
    def entity_id(self) -> str:
        return self._entity_id

    def to_data(self) -> dict[str, Any]:
        output = super().to_data()
        output["entity_id"] = self.entity_id
        return output

    def to_server_operation(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.operation_name,
            "entityId": self.entity_id,
            "entityType": self.entity_type,
        }


class OperationsSession(object):
    """Session storing operations that should happen in an order.

    At this moment does not handle anything special can be sonsidered as
    stupid list of operations that will happen after each other. If creation
    of same entity is there multiple times it's handled in any way and entity
    values are not validated.

    All operations must be related to single project.

    Args:
        con (Optional[ServerAPI]): Connection to server. Global connection
            is used if not passed.

    """
    def __init__(self, con: Optional[ServerAPI] = None) -> None:
        if con is None:
            con = get_server_api_connection()
        self._con = con
        self._project_cache = {}
        self._operations = []
        self._nested_operations = collections.defaultdict(list)

    @property
    def con(self) -> ServerAPI:
        return self._con

    def get_project(
        self, project_name: str
    ) -> Optional[dict[str, Any]]:
        if project_name not in self._project_cache:
            self._project_cache[project_name] = self.con.get_project(
                project_name)
        return copy.deepcopy(self._project_cache[project_name])

    def __len__(self) -> int:
        return len(self._operations)

    def add(self, operation: AbstractOperation) -> None:
        """Add operation to be processed.

        Args:
            operation (BaseOperation): Operation that should be processed.

        """
        if not isinstance(
            operation,
            (CreateOperation, UpdateOperation, DeleteOperation)
        ):
            raise TypeError("Expected Operation object got {}".format(
                str(type(operation))
            ))

        self._operations.append(operation)

    def append(self, operation: AbstractOperation) -> None:
        """Add operation to be processed.

        Args:
            operation (BaseOperation): Operation that should be processed.

        """
        self.add(operation)

    def extend(self, operations: list[AbstractOperation]) -> None:
        """Add operations to be processed.

        Args:
            operations (list[BaseOperation]): Operations that should be
                processed.

        """
        for operation in operations:
            self.add(operation)

    def remove(self, operation: AbstractOperation) -> None:
        """Remove operation."""
        self._operations.remove(operation)

    def clear(self) -> None:
        """Clear all registered operations."""
        self._operations = []

    def to_data(self) -> list[dict[str, Any]]:
        return [
            operation.to_data()
            for operation in self._operations
        ]

    def commit(self) -> None:
        """Commit session operations."""
        operations, self._operations = self._operations, []
        if not operations:
            return

        operations_by_project = collections.defaultdict(list)
        for operation in operations:
            operations_by_project[operation.project_name].append(operation)

        for project_name, operations in operations_by_project.items():
            operations_body = []
            for operation in operations:
                body = operation.to_server_operation()
                if body is not None:
                    operations_body.append(body)

            self._con.send_batch_operations(
                project_name, operations_body, can_fail=False
            )

    def create_entity(
        self,
        project_name: str,
        entity_type: str,
        data: dict[str, Any],
        nested_id: Optional[str] = None,
    ) -> CreateOperation:
        """Fast access to 'CreateOperation'.

        Args:
            project_name (str): On which project the creation happens.
            entity_type (str): Which entity type will be created.
            data (Dicst[str, Any]): Entity data.
            nested_id (str): Id of other operation from which is triggered
                operation -> Operations can trigger suboperations but they
                must be added to operations list after it's parent is added.

        Returns:
            CreateOperation: Object of create operation.

        """
        operation = CreateOperation(
            project_name, entity_type, data, self
        )

        if nested_id:
            self._nested_operations[nested_id].append(operation)
        else:
            self.add(operation)
            if operation.id in self._nested_operations:
                self.extend(self._nested_operations.pop(operation.id))

        return operation

    def update_entity(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        update_data: dict[str, Any],
        nested_id: Optional[str] = None,
    ) -> UpdateOperation:
        """Fast access to 'UpdateOperation'.

        Returns:
            UpdateOperation: Object of update operation.

        """
        operation = UpdateOperation(
            project_name, entity_type, entity_id, update_data, self
        )
        if nested_id:
            self._nested_operations[nested_id].append(operation)
        else:
            self.add(operation)
            if operation.id in self._nested_operations:
                self.extend(self._nested_operations.pop(operation.id))
        return operation

    def delete_entity(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
        nested_id: Optional[str] = None,
    ) -> DeleteOperation:
        """Fast access to 'DeleteOperation'.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        operation = DeleteOperation(
            project_name, entity_type, entity_id, self
        )
        if nested_id:
            self._nested_operations[nested_id].append(operation)
        else:
            self.add(operation)
            if operation.id in self._nested_operations:
                self.extend(self._nested_operations.pop(operation.id))
        return operation

    def create_folder(
        self,
        project_name: str,
        name: str,
        folder_type: Optional[str] = None,
        parent_id: Optional[str] = None,
        label: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> CreateOperation:
        """Create new folder.

        Args:
            project_name (str): Project name.
            name (str): Folder name.
            folder_type (Optional[str]): Folder type.
            parent_id (Optional[str]): Parent folder id. Parent is project
                if is ``None``.
            label (Optional[str]): Label of folder.
            attrib (Optional[dict[str, Any]]): Folder attributes.
            data (Optional[dict[str, Any]]): Folder data.
            tags (Optional[Iterable[str]]): Folder tags.
            status (Optional[str]): Folder status.
            active (Optional[bool]): Folder active state.
            thumbnail_id (Optional[str]): Folder thumbnail id.
            folder_id (Optional[str]): Folder id. If not passed new id is
                generated.

        Returns:
            CreateOperation: Object of create operation.

        """
        if not folder_id:
            folder_id = create_entity_id()
        create_data = {
            "id": folder_id,
            "name": name,
        }
        for key, value in (
            ("folderType", folder_type),
            ("parentId", parent_id),
            ("label", label),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not None:
                create_data[key] = value

        return self.create_entity(
            project_name, "folder", create_data
        )

    def update_folder(
        self,
        project_name: str,
        folder_id: str,
        name: Optional[str] = None,
        folder_type: Optional[str] = None,
        parent_id: Optional[str] = NOT_SET,
        label: Optional[str] = NOT_SET,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ):
        """Update folder entity on server.

        Do not pass ``parent_id``, ``label`` amd ``thumbnail_id`` if you don't
            want to change their values. Value ``None`` would unset
            their value.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            folder_id (str): Folder id.
            name (Optional[str]): New name.
            folder_type (Optional[str]): New folder type.
            parent_id (Optional[str]): New parent folder id.
            label (Optional[str]): New label.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[str]): New thumbnail id.

        Returns:
            UpdateOperation: Object of update operation.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("folderType", folder_type),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("label", label),
            ("parentId", parent_id),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        self.update_entity(
            project_name, "folder", folder_id, update_data
        )

    def delete_folder(
        self,
        project_name: str,
        folder_id: str,
    ) -> DeleteOperation:
        """Delete folder.

        Args:
            project_name (str): Project name.
            folder_id (str): Folder id to delete.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        return self.delete_entity(
            project_name, "folder", folder_id
        )

    def create_task(
        self,
        project_name: str,
        name: str,
        task_type: str,
        folder_id: str,
        label: Optional[str] = None,
        assignees: Optional[Iterable[str]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> CreateOperation:
        """Create new task.

        Args:
            project_name (str): Project name.
            name (str): Folder name.
            task_type (str): Task type.
            folder_id (str): Parent folder id.
            label (Optional[str]): Label of folder.
            assignees (Optional[Iterable[str]]): Task assignees.
            attrib (Optional[dict[str, Any]]): Task attributes.
            data (Optional[dict[str, Any]]): Task data.
            tags (Optional[Iterable[str]]): Task tags.
            status (Optional[str]): Task status.
            active (Optional[bool]): Task active state.
            thumbnail_id (Optional[str]): Task thumbnail id.
            task_id (Optional[str]): Task id. If not passed new id is
                generated.

        Returns:
            CreateOperation: Object of create operation.

        """
        if not task_id:
            task_id = create_entity_id()
        create_data = {
            "id": task_id,
            "name": name,
            "taskType": task_type,
            "folderId": folder_id,
        }
        for key, value in (
            ("label", label),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("assignees", assignees),
            ("active", active),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not None:
                create_data[key] = value

        return self.create_entity(
            project_name, "task", create_data
        )

    def update_task(
        self,
        project_name: str,
        task_id: str,
        name: Optional[str] = None,
        task_type: Optional[str] = None,
        folder_id: Optional[str] = None,
        label: Optional[str] = NOT_SET,
        assignees: Optional[list[str]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ) -> UpdateOperation:
        """Update task entity on server.

        Do not pass ``label`` amd ``thumbnail_id`` if you don't
            want to change their values. Value ``None`` would unset
            their value.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            task_id (str): Task id.
            name (Optional[str]): New name.
            task_type (Optional[str]): New task type.
            folder_id (Optional[str]): New folder id.
            label (Optional[str]): New label.
            assignees (Optional[str]): New assignees.
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[str]): New thumbnail id.

        Returns:
            UpdateOperation: Object of update operation.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("taskType", task_type),
            ("folderId", folder_id),
            ("assignees", assignees),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("label", label),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        return self.update_entity(
            project_name, "task", task_id, update_data
        )

    def delete_task(
        self,
        project_name: str,
        task_id: str,
    ) -> DeleteOperation:
        """Delete task.

        Args:
            project_name (str): Project name.
            task_id (str): Task id to delete.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        return self.delete_entity(project_name, "task", task_id)

    def create_product(
        self,
        project_name: str,
        name: str,
        product_type: str,
        folder_id: str,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        product_id: Optional[str] = None,
    ) -> CreateOperation:
        """Create new product.

        Args:
            project_name (str): Project name.
            name (str): Product name.
            product_type (str): Product type.
            folder_id (str): Parent folder id.
            attrib (Optional[dict[str, Any]]): Product attributes.
            data (Optional[dict[str, Any]]): Product data.
            tags (Optional[Iterable[str]]): Product tags.
            status (Optional[str]): Product status.
            active (Optional[bool]): Product active state.
            product_id (Optional[str]): Product id. If not passed new id is
                generated.

        Returns:
            CreateOperation: Object of create operation.

        """
        if not product_id:
            product_id = create_entity_id()
        create_data = {
            "id": product_id,
            "name": name,
            "productType": product_type,
            "folderId": folder_id,
        }
        for key, value in (
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                create_data[key] = value

        return self.create_entity(
            project_name, "product", create_data
        )

    def update_product(
        self,
        project_name: str,
        product_id: str,
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
        product_type: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> UpdateOperation:
        """Update product entity on server.

        Update of ``data`` will override existing value on folder entity.

        Update of ``attrib`` does change only passed attributes. If you want
            to unset value, use ``None``.

        Args:
            project_name (str): Project name.
            product_id (str): Product id.
            name (Optional[str]): New product name.
            folder_id (Optional[str]): New product id.
            product_type (Optional[str]): New product type.
            attrib (Optional[dict[str, Any]]): New product attributes.
            data (Optional[dict[str, Any]]): New product data.
            tags (Optional[Iterable[str]]): New product tags.
            status (Optional[str]): New product status.
            active (Optional[bool]): New product active state.

        Returns:
            UpdateOperation: Object of update operation.

        """
        update_data = {}
        for key, value in (
            ("name", name),
            ("productType", product_type),
            ("folderId", folder_id),
            ("attrib", attrib),
            ("data", data),
            ("tags", tags),
            ("status", status),
            ("active", active),
        ):
            if value is not None:
                update_data[key] = value

        return self.update_entity(
            project_name,
            "product",
            product_id,
            update_data
        )

    def delete_product(
        self,
        project_name: str,
        product_id: str,
    ) -> DeleteOperation:
        """Delete product.

        Args:
            project_name (str): Project name.
            product_id (str): Product id to delete.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        return self.delete_entity(
            project_name, "product", product_id
        )

    def create_version(
        self,
        project_name: str,
        version: int,
        product_id: str,
        task_id: Optional[str] = None,
        author: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> CreateOperation:
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
            CreateOperation: Object of create operation.

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

        return self.create_entity(
            project_name, "version", create_data
        )

    def update_version(
        self,
        project_name: str,
        version_id: str,
        version: Optional[int] = None,
        product_id: Optional[str] = None,
        task_id: Optional[str] = NOT_SET,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        thumbnail_id: Optional[str] = NOT_SET,
    ) -> UpdateOperation:
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
            attrib (Optional[dict[str, Any]]): New attributes.
            data (Optional[dict[str, Any]]): New data.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.
            thumbnail_id (Optional[str]): New thumbnail id.

        Returns:
            UpdateOperation: Object of update operation.

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
        ):
            if value is not None:
                update_data[key] = value

        for key, value in (
            ("taskId", task_id),
            ("thumbnailId", thumbnail_id),
        ):
            if value is not NOT_SET:
                update_data[key] = value

        return self.update_entity(
            project_name, "version", version_id, update_data
        )

    def delete_version(
        self,
        project_name: str,
        version_id: str,
    ) -> DeleteOperation:
        """Delete version.

        Args:
            project_name (str): Project name.
            version_id (str): Version id to delete.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        return self.delete_entity(
            project_name, "version", version_id
        )

    def create_representation(
        self,
        project_name: str,
        name: str,
        version_id: str,
        files: Optional[list[dict[str, Any]]] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        traits: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        representation_id: Optional[str] = None,
    ) -> CreateOperation:
        """Create new representation.

        Args:
            project_name (str): Project name.
            name (str): Representation name.
            version_id (str): Parent version id.
            files (Optional[list[dict]]): Representation files information.
            attrib (Optional[dict[str, Any]]): Representation attributes.
            data (Optional[dict[str, Any]]): Representation data.
            traits (Optional[dict[str, Any]]): Representation traits. Empty
                if not passed.
            tags (Optional[Iterable[str]]): Representation tags.
            status (Optional[str]): Representation status.
            active (Optional[bool]): Representation active state.
            representation_id (Optional[str]): Representation id. If not
                passed new id is generated.

        Returns:
            CreateOperation: Object of create operation.

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

        return self.create_entity(
            project_name,
            "representation",
            create_data
        )

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
    ) -> UpdateOperation:
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
            traits (Optional[dict[str, Any]]): New representation traits.
            tags (Optional[Iterable[str]]): New tags.
            status (Optional[str]): New status.
            active (Optional[bool]): New active state.

        Returns:
            UpdateOperation: Object of update operation.

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

        return self.update_entity(
            project_name,
            "representation",
            representation_id,
            update_data
        )

    def delete_representation(
        self,
        project_name: str,
        representation_id: str,
    ) -> DeleteOperation:
        """Delete representation.

        Args:
            project_name (str): Project name.
            representation_id (str): Representation id to delete.

        Returns:
            DeleteOperation: Object of delete operation.

        """
        return self.delete_entity(
            project_name, "representation", representation_id
        )
