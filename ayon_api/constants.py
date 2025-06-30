# Environments where server url and api key are stored for global connection
SERVER_URL_ENV_KEY = "AYON_SERVER_URL"
SERVER_API_ENV_KEY = "AYON_API_KEY"
SERVER_TIMEOUT_ENV_KEY = "AYON_SERVER_TIMEOUT"
SERVER_RETRIES_ENV_KEY = "AYON_SERVER_RETRIES"
# Default variant used for settings
DEFAULT_VARIANT_ENV_KEY = "AYON_DEFAULT_SETTINGS_VARIANT"
# Default site id used for connection
SITE_ID_ENV_KEY = "AYON_SITE_ID"

# Backwards compatibility
SERVER_TOKEN_ENV_KEY = SERVER_API_ENV_KEY

# --- User ---
DEFAULT_USER_FIELDS = {
    "accessGroups",
    "defaultAccessGroups",
    "name",
    "isService",
    "isManager",
    "isGuest",
    "isAdmin",
    "createdAt",
    "active",
    "hasPassword",
    "updatedAt",
    "apiKeyPreview",
    "attrib.avatarUrl",
    "attrib.email",
    "attrib.fullName",
}

# --- Project folder types ---
DEFAULT_FOLDER_TYPE_FIELDS = {
    "name",
    "icon",
}

# --- Project task types ---
DEFAULT_TASK_TYPE_FIELDS = {
    "name",
}

# --- Project tags ---
DEFAULT_PROJECT_TAGS_FIELDS = {
    "name",
    "color",
}

# --- Project statuses ---
DEFAULT_PROJECT_STATUSES_FIELDS = {
    "color",
    "icon",
    "name",
    "scope",
    "shortName",
    "state",
}

# --- Project link types ---
DEFAULT_PROJECT_LINK_TYPES_FIELDS = {
    "color",
    "inputType",
    "linkType",
    "name",
    "outputType",
    "style",
}

# --- Product types ---
DEFAULT_PRODUCT_TYPE_FIELDS = {
    "name",
    "icon",
    "color",
}

# --- Project ---
DEFAULT_PROJECT_FIELDS = {
    "active",
    "library",
    "name",
    "code",
    "config",
    "createdAt",
    "updatedAt",
    "data",
    "folderTypes",
    "taskTypes",
    "linkTypes",
    "statuses",
    "tags",
    "attrib",
}

# --- Folders ---
DEFAULT_FOLDER_FIELDS = {
    "id",
    "name",
    "label",
    "folderType",
    "path",
    "parentId",
    "active",
    "thumbnailId",
    "data",
    "status",
    "tags",
}

# --- Tasks ---
DEFAULT_TASK_FIELDS = {
    "id",
    "name",
    "label",
    "taskType",
    "folderId",
    "active",
    "thumbnailId",
    "assignees",
    "data",
    "status",
    "tags",
}

# --- Products ---
DEFAULT_PRODUCT_FIELDS = {
    "id",
    "name",
    "folderId",
    "active",
    "productType",
    "data",
    "status",
    "tags",
}

# --- Versions ---
DEFAULT_VERSION_FIELDS = {
    "id",
    "name",
    "version",
    "productId",
    "taskId",
    "active",
    "author",
    "thumbnailId",
    "createdAt",
    "updatedAt",
    "data",
    "status",
    "tags",
}

# --- Representations ---
DEFAULT_REPRESENTATION_FIELDS = {
    "id",
    "name",
    "context",
    "createdAt",
    "active",
    "versionId",
    "data",
    "status",
    "tags",
    "traits",
}

REPRESENTATION_FILES_FIELDS = {
    "files.name",
    "files.hash",
    "files.id",
    "files.path",
    "files.size",
}

# --- Workfile info ---
DEFAULT_WORKFILE_INFO_FIELDS = {
    "active",
    "createdAt",
    "createdBy",
    "id",
    "name",
    "path",
    "projectName",
    "taskId",
    "thumbnailId",
    "updatedAt",
    "updatedBy",
    "data",
    "status",
    "tags",
}

DEFAULT_EVENT_FIELDS = {
    "id",
    "hash",
    "createdAt",
    "dependsOn",
    "description",
    "project",
    "retries",
    "sender",
    "status",
    "topic",
    "updatedAt",
    "user",
}

DEFAULT_LINK_FIELDS = {
    "id",
    "linkType",
    "projectName",
    "entityType",
    "entityId",
    "name",
    "direction",
    "description",
    "author",
}

DEFAULT_ACTIVITY_FIELDS = {
    "activityId",
    "activityType",
    "activityData",
    "body",
    "entityId",
    "entityType",
    "author.name",
}


DEFAULT_ENTITY_LIST_FIELDS = {
    "id",
    "count",
    "attributes",
    "active",
    "createdBy",
    "createdAt",
    "entityListType",
    "data",
    "entityType",
    "label",
    "owner",
    "tags",
    "updatedAt",
    "updatedBy",
}
