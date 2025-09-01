from __future__ import annotations

import io
from typing import (
    Literal,
    Any,
    TypedDict,
    Union,
    Optional,
    BinaryIO,
)


ServerVersion = tuple[int, int, int, str, str]

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

EntityListEntityType = Literal[
    "folder",
    "product",
    "version",
    "representation",
    "task",
    "workfile",
]

EntityListItemMode = Literal[
    "replace",
    "merge",
    "delete",
]

EventFilterValueType = Union[
    None,
    str, int, float,
    list[str], list[int], list[float],
]


IconType = Literal["material-symbols", "url"]


class IconDefType(TypedDict):
    type: IconType
    name: Optional[str]
    color: Optional[str]
    icon: Optional[str]


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
    conditions: list[EventFilterCondition]
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

LinkDirection = Literal["in", "out"]


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
    enum: Optional[list[AttributeEnumItemDict]]


class AttributeSchemaDict(TypedDict):
    name: str
    position: int
    scope: list[AttributeScope]
    builtin: bool
    data: AttributeSchemaDataDict


class AttributesSchemaDict(TypedDict):
    attributes: list[AttributeSchemaDict]


class AddonVersionInfoDict(TypedDict):
    hasSettings: bool
    hasSiteSettings: bool
    frontendScopes: dict[str, Any]
    clientPyproject: dict[str, Any]
    clientSourceInfo: list[dict[str, Any]]
    isBroken: bool


class AddonInfoDict(TypedDict):
    name: str
    title: str
    versions: dict[str, AddonVersionInfoDict]


class AddonsInfoDict(TypedDict):
    addons: list[AddonInfoDict]


class InstallerInfoDict(TypedDict):
    filename: str
    platform: str
    size: int
    checksum: str
    checksumAlgorithm: str
    sources: list[dict[str, Any]]
    version: str
    pythonVersion: str
    pythonModules: dict[str, str]
    runtimePythonModules: dict[str, str]


class InstallersInfoDict(TypedDict):
    installers: list[InstallerInfoDict]


class DependencyPackageDict(TypedDict):
    filename: str
    platform: str
    size: int
    checksum: str
    checksumAlgorithm: str
    sources: list[dict[str, Any]]
    installerVersion: str
    sourceAddons: dict[str, str]
    pythonModules: dict[str, str]


class DependencyPackagesDict(TypedDict):
    packages: list[DependencyPackageDict]


class DevBundleAddonInfoDict(TypedDict):
    enabled: bool
    path: str


class BundleInfoDict(TypedDict):
    name: str
    createdAt: str
    addons: dict[str, str]
    installerVersion: str
    dependencyPackages: dict[str, str]
    addonDevelopment: dict[str, DevBundleAddonInfoDict]
    isProduction: bool
    isStaging: bool
    isArchived: bool
    isDev: bool
    activeUser: Optional[str]


class BundlesInfoDict(TypedDict):
    bundles: list[BundleInfoDict]
    productionBundle: str
    devBundles: list[str]


class AnatomyPresetInfoDict(TypedDict):
    name: str
    primary: bool
    version: str


class AnatomyPresetRootDict(TypedDict):
    name: str
    windows: str
    linux: str
    darwin: str


class AnatomyPresetTemplateDict(TypedDict):
    name: str
    directory: str
    file: str


class AnatomyPresetTemplatesDict(TypedDict):
    version_padding: int
    version: str
    frame_padding: int
    frame: str
    work: list[AnatomyPresetTemplateDict]
    publish: list[AnatomyPresetTemplateDict]
    hero: list[AnatomyPresetTemplateDict]
    delivery: list[AnatomyPresetTemplateDict]
    staging: list[AnatomyPresetTemplateDict]
    others: list[AnatomyPresetTemplateDict]


class AnatomyPresetSubtypeDict(TypedDict):
    name: str
    shortName: str
    icon: str
    original_name: str


class AnatomyPresetLinkTypeDict(TypedDict):
    link_type: str
    input_type: str
    output_type: str
    color: str
    style: str


StatusScope = Literal[
    "folder",
    "task",
    "product",
    "version",
    "representation",
    "workfile"
]


class AnatomyPresetStatusDict(TypedDict):
    name: str
    shortName: str
    state: str
    icon: str
    color: str
    scope: list[StatusScope]
    original_name: str


class AnatomyPresetTagDict(TypedDict):
    name: str
    color: str
    original_name: str


class AnatomyPresetDict(TypedDict):
    roots: list[AnatomyPresetRootDict]
    templates: AnatomyPresetTemplatesDict
    attributes: dict[str, Any]
    folder_types: list[AnatomyPresetSubtypeDict]
    task_types: list[AnatomyPresetSubtypeDict]
    link_types: list[AnatomyPresetLinkTypeDict]
    statuses: list[AnatomyPresetStatusDict]
    tags: list[AnatomyPresetTagDict]
    primary: bool
    name: str


class SecretDict(TypedDict):
    name: str
    value: str


ProjectDict = dict[str, Any]
FolderDict = dict[str, Any]
TaskDict = dict[str, Any]
ProductDict = dict[str, Any]
VersionDict = dict[str, Any]
RepresentationDict = dict[str, Any]
WorkfileInfoDict = dict[str, Any]
EventDict = dict[str, Any]
ActivityDict = dict[str, Any]
AnyEntityDict = Union[
    ProjectDict,
    FolderDict,
    TaskDict,
    ProductDict,
    VersionDict,
    RepresentationDict,
    WorkfileInfoDict,
    EventDict,
    ActivityDict,
]


class NewFolderDict(TypedDict):
    id: str
    name: str
    folderType: str
    parentId: Optional[str]
    data: dict[str, Any]
    attrib: dict[str, Any]
    thumbnailId: Optional[str]
    status: Optional[str]
    tags: Optional[list[str]]


class NewProductDict(TypedDict):
    id: str
    name: str
    productType: str
    folderId: str
    data: dict[str, Any]
    attrib: dict[str, Any]
    status: Optional[str]
    tags: Optional[list[str]]


class NewVersionDict(TypedDict):
    id: str
    version: int
    productId: str
    attrib: dict[str, Any]
    data: dict[str, Any]
    taskId: Optional[str]
    thumbnailId: Optional[str]
    author: Optional[str]
    status: Optional[str]
    tags: Optional[list[str]]


class NewRepresentationDict(TypedDict):
    id: str
    versionId: str
    name: str
    data: dict[str, Any]
    attrib: dict[str, Any]
    files: list[dict[str, str]]
    traits: Optional[dict[str, Any]]
    status: Optional[str]
    tags: Optional[list[str]]


class NewWorkfileDict(TypedDict):
    id: str
    taskId: str
    path: str
    data: dict[str, Any]
    attrib: dict[str, Any]
    status: Optional[str]
    tags: Optional[list[str]]


EventStatus = Literal[
    "pending",
    "in_progress",
    "finished",
    "failed",
    "aborted",
    "restarted",
]


class EnrollEventData(TypedDict):
    id: str
    dependsOn: str
    hash: str
    status: EventStatus


class FlatFolderDict(TypedDict):
    id: str
    parentId: Optional[str]
    path: str
    parents: list[str]
    name: str
    label: Optional[str]
    folderType: str
    hasTasks: bool
    hasChildren: bool
    taskNames: list[str]
    status: str
    attrib: dict[str, Any]
    ownAttrib: list[str]
    updatedAt: str


class ProjectHierarchyItemDict(TypedDict):
    id: str
    name: str
    label: str
    status: str
    folderType: str
    hasTasks: bool
    taskNames: list[str]
    parents: list[str]
    parentId: Optional[str]
    children: list["ProjectHierarchyItemDict"]


class ProjectHierarchyDict(TypedDict):
    hierarchy: list[ProjectHierarchyItemDict]


class ProductTypeDict(TypedDict):
    name: str
    color: Optional[str]
    icon: Optional[str]


ActionEntityTypes = Literal[
    "project",
    "folder",
    "task",
    "product",
    "version",
    "representation",
    "workfile",
    "list",
]


class ActionManifestDict(TypedDict):
    identifier: str
    label: str
    groupLabel: Optional[str]
    category: str
    order: int
    icon: Optional[IconDefType]
    adminOnly: bool
    managerOnly: bool
    configFields: list[dict[str, Any]]
    featured: bool
    addonName: str
    addonVersion: str
    variant: str


ActionResponseType = Literal[
    "form",
    "launcher",
    "navigate",
    "query",
    "redirect",
    "simple",
]

ActionModeType = Literal["simple", "dynamic", "all"]


class BaseActionPayload(TypedDict):
    extra_clipboard: str
    extra_download: str


class ActionLauncherPayload(BaseActionPayload):
    uri: str


class ActionNavigatePayload(BaseActionPayload):
    uri: str


class ActionRedirectPayload(BaseActionPayload):
    uri: str
    new_tab: bool


class ActionQueryPayload(BaseActionPayload):
    query: str


class ActionFormPayload(BaseActionPayload):
    title: str
    fields: list[dict[str, Any]]
    submit_label: str
    submit_icon: str
    cancel_label: str
    cancel_icon: str
    show_cancel_button: bool
    show_submit_button: bool


ActionPayload = Union[
    ActionLauncherPayload,
    ActionNavigatePayload,
    ActionRedirectPayload,
    ActionQueryPayload,
    ActionFormPayload,
]

class ActionTriggerResponse(TypedDict):
    type: ActionResponseType
    success: bool
    message: Optional[str]
    payload: Optional[ActionPayload]


class ActionTakeResponse(TypedDict):
    eventId: str
    actionIdentifier: str
    args: list[str]
    context: dict[str, Any]
    addonName: str
    addonVersion: str
    variant: str
    userName: str


class ActionConfigResponse(TypedDict):
    projectName: str
    entityType: str
    entitySubtypes: list[str]
    entityIds: list[str]
    formData: dict[str, Any]
    value: dict[str, Any]


StreamType = Union[io.BytesIO, BinaryIO]


class EntityListAttributeDefinitionDict(TypedDict):
    name: str
    data: dict[str, Any]
