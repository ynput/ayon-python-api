from typing import Literal, Dict, List, Any, TypedDict, Union, Optional

ActivityType = Literal[
    "comment",
    "watch",
    "reviewable",
    "status.change",
    "assignee.add",
    "assignee.remove",
    "version.publish"
]

ActivityReferenceType = Literal[
    "origin",
    "mention",
    "author",
    "relation",
    "watching",
]

BaseEntity = Dict[str, Any]

EventFilterValueType = Union[
    None,
    str, int, float,
    List[str], List[int], List[float],
]


class EventFilterCondition(TypedDict):
    key: str
    value: EventFilterValueType
    operator: Literal[
        "eq",
        "lt",
        "gt",
        "lte",
        "gte",
        "ne",
        "isnull",
        "notnull",
        "in",
        "notin",
        "contains",
        "excludes",
        "like",
    ]


class EventFilter(TypedDict):
    conditions: List[EventFilterCondition]
    operator: Literal["and", "or"]


AttributeScope = Literal[
    "project",
    "folder",
    "task",
    "product",
    "version",
    "representation",
    "workfile",
    "user"
]
AttributeType = Literal[
    "string",
    "integer",
    "float",
    "boolean",
    "datetime",
    "list_of_strings",
    "list_of_integers",
    "list_of_any",
    "list_of_submodels",
    "dict",
]


class AttributeEnumItemDict(TypedDict):
    value: Union[str, int, float, bool]
    label: str
    icon: Union[str, None]
    color: Union[str, None]


class AttributeSchemaDataDict(TypedDict):
    type: AttributeType
    inherit: bool
    title: str
    description: Optional[str]
    example: Optional[Any]
    default: Optional[Any]
    gt: Union[int, float, None]
    lt: Union[int, float, None]
    ge: Union[int, float, None]
    le: Union[int, float, None]
    minLength: Optional[int]
    maxLength: Optional[int]
    minItems: Optional[int]
    maxItems: Optional[int]
    regex: Optional[str]
    enum: Optional[List[AttributeEnumItemDict]]


class AttributeSchemaDict(TypedDict):
    name: str
    position: int
    scope: List[AttributeScope]
    builtin: bool
    data: AttributeSchemaDataDict


class AttributesSchemaDict(TypedDict):
    attributes: List[AttributeSchemaDict]


class AddonVersionInfoDict(TypedDict):
    hasSettings: bool
    hasSiteSettings: bool
    frontendScopes: Dict[str, Any]
    clientPyproject: Dict[str, Any]
    clientSourceInfo: List[Dict[str, Any]]
    isBroken: bool


class AddonInfoDict(TypedDict):
    name: str
    title: str
    versions: Dict[str, AddonVersionInfoDict]


class AddonsInfoDict(TypedDict):
    addons: List[AddonInfoDict]


class InstallerInfoDict(TypedDict):
    filename: str
    platform: str
    size: int
    checksum: str
    checksumAlgorithm: str
    sources: List[Dict[str, Any]]
    version: str
    pythonVersion: str
    pythonModules: Dict[str, str]
    runtimePythonModules: Dict[str, str]


class InstallersInfoDict(TypedDict):
    installers: List[InstallerInfoDict]


class DependencyPackageDict(TypedDict):
    filename: str
    platform: str
    size: int
    checksum: str
    checksumAlgorithm: str
    sources: List[Dict[str, Any]]
    installerVersion: str
    sourceAddons: Dict[str, str]
    pythonModules: Dict[str, str]


class DependencyPackagesDict(TypedDict):
    packages: List[DependencyPackageDict]
