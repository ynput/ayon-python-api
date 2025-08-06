import io
from typing import (
    Literal,
    Dict,
    List,
    Any,
    TypedDict,
    Union,
    Optional,
    BinaryIO,
)


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
    List[str], List[int], List[float],
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


class DevBundleAddonInfoDict(TypedDict):
    enabled: bool
    path: str


class BundleInfoDict(TypedDict):
    name: str
    createdAt: str
    addons: Dict[str, str]
    installerVersion: str
    dependencyPackages: Dict[str, str]
    addonDevelopment: Dict[str, DevBundleAddonInfoDict]
    isProduction: bool
    isStaging: bool
    isArchived: bool
    isDev: bool
    activeUser: Optional[str]


class BundlesInfoDict(TypedDict):
    bundles: List[BundleInfoDict]
    productionBundle: str
    devBundles: List[str]


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
    work: List[AnatomyPresetTemplateDict]
    publish: List[AnatomyPresetTemplateDict]
    hero: List[AnatomyPresetTemplateDict]
    delivery: List[AnatomyPresetTemplateDict]
    staging: List[AnatomyPresetTemplateDict]
    others: List[AnatomyPresetTemplateDict]


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
    scope: List[StatusScope]
    original_name: str


class AnatomyPresetTagDict(TypedDict):
    name: str
    color: str
    original_name: str


class AnatomyPresetDict(TypedDict):
    roots: List[AnatomyPresetRootDict]
    templates: AnatomyPresetTemplatesDict
    attributes: Dict[str, Any]
    folder_types: List[AnatomyPresetSubtypeDict]
    task_types: List[AnatomyPresetSubtypeDict]
    link_types: List[AnatomyPresetLinkTypeDict]
    statuses: List[AnatomyPresetStatusDict]
    tags: List[AnatomyPresetTagDict]


class SecretDict(TypedDict):
    name: str
    value: str

ProjectDict = Dict[str, Any]
FolderDict = Dict[str, Any]
TaskDict = Dict[str, Any]
ProductDict = Dict[str, Any]
VersionDict = Dict[str, Any]
RepresentationDict = Dict[str, Any]
WorkfileInfoDict = Dict[str, Any]
EventDict = Dict[str, Any]
ActivityDict = Dict[str, Any]
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


class FlatFolderDict(TypedDict):
    id: str
    parentId: Optional[str]
    path: str
    parents: List[str]
    name: str
    label: Optional[str]
    folderType: str
    hasTasks: bool
    hasChildren: bool
    taskNames: List[str]
    status: str
    attrib: Dict[str, Any]
    ownAttrib: List[str]
    updatedAt: str


class ProjectHierarchyItemDict(TypedDict):
    id: str
    name: str
    label: str
    status: str
    folderType: str
    hasTasks: bool
    taskNames: List[str]
    parents: List[str]
    parentId: Optional[str]
    children: List["ProjectHierarchyItemDict"]


class ProjectHierarchyDict(TypedDict):
    hierarchy: List[ProjectHierarchyItemDict]


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
    configFields: List[Dict[str, Any]]
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
    fields: List[Dict[str, Any]]
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
    args: List[str]
    context: Dict[str, Any]
    addonName: str
    addonVersion: str
    variant: str
    userName: str


class ActionConfigResponse(TypedDict):
    projectName: str
    entityType: str
    entitySubtypes: List[str]
    entityIds: List[str]
    formData: Dict[str, Any]
    value: Dict[str, Any]


StreamType = Union[io.BytesIO, BinaryIO]


class EntityListAttributeDefinitionDict(TypedDict):
    name: str
    data: Dict[str, Any]
