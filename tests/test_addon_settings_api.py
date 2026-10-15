"""Tests of addon settings API (overrides, raw overrides, migration).

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_SERVER_URL and AYON_API_KEY in your environment.
The tests expect an admin user.

Tests use an addon from the production bundle that has a settings model.
Studio level writes are done only on a unique, throwaway settings variant
(not 'production' or 'staging') and the raw studio overrides of that
variant are restored in fixture teardown. Project level writes are done
on the test project created by 'project_entity_fixture'.

"""

import copy
import uuid

import pytest

from ayon_api import (
    delete_addon_project_overrides,
    delete_addon_studio_overrides,
    delete_site,
    get_addon_project_overrides,
    get_addon_project_raw_overrides,
    get_addon_project_settings,
    get_addon_settings_schema,
    get_addon_site_settings,
    get_addon_site_settings_schema,
    get_addon_studio_overrides,
    get_addon_studio_raw_overrides,
    get_addon_studio_settings,
    get_addons_info,
    get_bundles,
    get_client_version,
    get_info,
    get_server_version_tuple,
    get_site_id,
    get_sites,
    migrate_addon_settings,
    migrate_settings_by_bundle,
    modify_addon_project_overrides,
    modify_addon_studio_overrides,
    set_addon_project_raw_overrides,
    set_addon_project_settings,
    set_addon_site_settings,
    set_addon_studio_raw_overrides,
    set_addon_studio_settings,
    set_client_version,
    set_site_id,
    exceptions,
)


PREFERRED_ADDONS = ("core",)


# --- Helpers ---
def _unique_name(prefix="ayon-api-test"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _get_value(data, path):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            raise KeyError(key)
        data = data[key]
    return data


def _has_path(data, path):
    try:
        _get_value(data, path)
    except KeyError:
        return False
    return True


def _set_value(data, path, value):
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


def _build_overrides(path, value):
    overrides = {}
    _set_value(overrides, path, value)
    return overrides


def _override_key(path):
    return "root_" + "_".join(path)


def _resolve_ref(schema, prop):
    """Resolve '$ref' (directly or via 'allOf') of a schema property."""
    ref = prop.get("$ref")
    if ref is None:
        all_of = prop.get("allOf")
        if all_of and len(all_of) == 1:
            ref = all_of[0].get("$ref")
    if not ref or not ref.startswith("#/definitions/"):
        return None
    return schema.get("definitions", {}).get(ref.split("/")[-1])


def _find_bool_path(schema, required_scopes=("studio", "project")):
    """Find path to a boolean settings field that is not inside a group.

    Group fields are stored as a whole in overrides, which would make
    assertions on override paths ambiguous.

    """
    def _crawl(model_schema, path, depth):
        if depth > 5 or model_schema.get("isgroup"):
            return None
        properties = model_schema.get("properties") or {}
        sub_models = []
        for name, prop in properties.items():
            scope = prop.get("scope") or ["studio", "project"]
            if any(s not in scope for s in required_scopes):
                continue
            if prop.get("disabled") or prop.get("conditionalEnum"):
                continue
            if prop.get("type") == "boolean":
                return [*path, name]
            sub_schema = _resolve_ref(schema, prop)
            if sub_schema is not None:
                sub_models.append((name, sub_schema))

        for name, sub_schema in sub_models:
            result = _crawl(sub_schema, [*path, name], depth + 1)
            if result:
                return result
        return None

    return _crawl(schema, [], 0)


def _get_production_bundle():
    bundles = get_bundles()
    production_name = bundles.get("productionBundle")
    if not production_name:
        return None
    for bundle in bundles["bundles"]:
        if bundle["name"] == production_name:
            return bundle
    return None


def _iter_bundle_addons(bundle):
    addons = {
        name: version
        for name, version in bundle.get("addons", {}).items()
        if version
    }
    ordered = [name for name in PREFERRED_ADDONS if name in addons]
    ordered.extend(sorted(name for name in addons if name not in ordered))
    for name in ordered:
        yield name, addons[name]


# --- Fixtures ---
@pytest.fixture(scope="module")
def production_bundle():
    bundle = _get_production_bundle()
    if bundle is None:
        pytest.skip("Server does not have a production bundle.")
    return bundle


@pytest.fixture(scope="module")
def settings_addon(production_bundle):
    """Addon from production bundle with a usable settings model.

    Returns:
        dict[str, Any]: 'name', 'version' of the addon and 'path' to
            a boolean settings field usable on studio and project level.

    """
    for addon_name, addon_version in _iter_bundle_addons(production_bundle):
        try:
            schema = get_addon_settings_schema(addon_name, addon_version)
        except exceptions.HTTPRequestError:
            continue
        if not schema or not schema.get("properties"):
            continue
        path = _find_bool_path(schema)
        if not path:
            continue
        settings = get_addon_studio_settings(
            addon_name, addon_version, variant="production"
        )
        if not _has_path(settings, path):
            continue
        if not isinstance(_get_value(settings, path), bool):
            continue
        return {
            "name": addon_name,
            "version": addon_version,
            "path": path,
        }
    pytest.skip(
        "No addon in production bundle has settings with a boolean field."
    )


@pytest.fixture
def studio_variant(settings_addon):
    """Unique settings variant used for studio level writes.

    Raw studio overrides of the variant are stored before the test and
    restored after it (there should not be any).

    """
    variant = _unique_name()
    name = settings_addon["name"]
    version = settings_addon["version"]
    original = get_addon_studio_raw_overrides(
        name, version, variant=variant
    )
    try:
        yield variant
    finally:
        current = get_addon_studio_raw_overrides(
            name, version, variant=variant
        )
        if current != original:
            if original:
                set_addon_studio_raw_overrides(
                    name, version, original, variant=variant
                )
            else:
                delete_addon_studio_overrides(name, version, variant=variant)


@pytest.fixture
def project_addon(settings_addon, project_entity_fixture):
    """Settings addon with the test project name.

    Project overrides of the addon on the test project are restored
    after the test.

    """
    project_name = project_entity_fixture["name"]
    name = settings_addon["name"]
    version = settings_addon["version"]
    original = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )
    try:
        yield {**settings_addon, "project_name": project_name}
    finally:
        current = get_addon_project_raw_overrides(
            name, version, project_name, variant="production"
        )
        if current != original:
            if original:
                set_addon_project_raw_overrides(
                    name,
                    version,
                    project_name,
                    original,
                    variant="production",
                )
            else:
                delete_addon_project_overrides(
                    name, version, project_name, variant="production"
                )


@pytest.fixture
def project_site_id(project_addon):
    """Unique site id used for project site overrides.

    Project site overrides are stored only in the test project (which is
    deleted at the end of the session) but are removed after the test too.

    """
    site_id = _unique_name()
    try:
        yield site_id
    finally:
        delete_addon_project_overrides(
            project_addon["name"],
            project_addon["version"],
            project_addon["project_name"],
            site_id=site_id,
        )


@pytest.fixture
def site_settings_addon(production_bundle):
    """Addon from production bundle that has site settings."""
    for addon_name, addon_version in _iter_bundle_addons(production_bundle):
        try:
            schema = get_addon_site_settings_schema(addon_name, addon_version)
        except exceptions.HTTPRequestError:
            continue
        if schema and schema.get("properties"):
            return {
                "name": addon_name,
                "version": addon_version,
                "schema": schema,
            }
    pytest.skip("No addon in production bundle has site settings.")


@pytest.fixture
def registered_site():
    """Register a unique site id on server using the connection.

    Site id (and client version, which is required for site registration)
    is set on the connection and 'get_info' registers the site. Site is
    unregistered and connection values are restored after the test.
    Unregistering the site removes its site settings on server.

    """
    site_id = _unique_name()
    orig_site_id = get_site_id()
    orig_client_version = get_client_version()
    registered = False
    try:
        set_site_id(site_id)
        if not orig_client_version:
            set_client_version("0.0.0")
        get_info()
        registered = any(site["id"] == site_id for site in get_sites())
        if not registered:
            pytest.skip("Unable to register a test site on server.")
        yield site_id
    finally:
        set_site_id(orig_site_id)
        set_client_version(orig_client_version)
        if registered:
            delete_site(site_id)


@pytest.fixture
def min_server_1_16_8():
    if get_server_version_tuple() < (1, 16, 8):
        pytest.skip("Server version is lower than 1.16.8.")


# --- Schema ---
def test_get_addon_settings_schema_variant(settings_addon, studio_variant):
    """Studio schema accepts 'variant' argument.

    Verifies:
        - Schema for production and custom variant is returned.
        - Both schemas have the same top level properties.

    """
    name = settings_addon["name"]
    version = settings_addon["version"]
    default_schema = get_addon_settings_schema(name, version)
    production_schema = get_addon_settings_schema(
        name, version, variant="production"
    )
    variant_schema = get_addon_settings_schema(
        name, version, variant=studio_variant
    )
    for schema in (default_schema, production_schema, variant_schema):
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "title" in schema

    assert (
        set(production_schema["properties"])
        == set(variant_schema["properties"])
        == set(default_schema["properties"])
    )


def test_get_addon_settings_schema_project_variant_site(
    project_addon, project_site_id
):
    """Project schema accepts 'variant' and 'site_id' arguments."""
    name = project_addon["name"]
    version = project_addon["version"]
    project_name = project_addon["project_name"]

    studio_schema = get_addon_settings_schema(name, version)
    project_schema = get_addon_settings_schema(
        name, version, project_name, variant="production"
    )
    site_schema = get_addon_settings_schema(
        name,
        version,
        project_name,
        variant="production",
        site_id=project_site_id,
    )
    for schema in (project_schema, site_schema):
        assert isinstance(schema, dict)
        assert set(schema["properties"]) == set(studio_schema["properties"])

    # Site id is ignored without project name
    studio_site_schema = get_addon_settings_schema(
        name, version, site_id=project_site_id
    )
    assert set(studio_site_schema["properties"]) == set(
        studio_schema["properties"]
    )


# --- Studio settings ---
def test_set_addon_studio_settings(settings_addon, studio_variant):
    """Set full studio settings and check calculated overrides.

    Verifies:
        - Changed value is returned by studio settings getter.
        - Only changed value is stored in raw overrides.
        - Overrides listing contains the changed field on studio level.

    """
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    new_value = not _get_value(settings, path)
    new_settings = copy.deepcopy(settings)
    _set_value(new_settings, path, new_value)

    set_addon_studio_settings(
        name, version, new_settings, variant=studio_variant
    )

    updated = get_addon_studio_settings(name, version, variant=studio_variant)
    assert _get_value(updated, path) is new_value

    raw = get_addon_studio_raw_overrides(name, version, variant=studio_variant)
    assert _get_value(raw, path) is new_value

    overrides = get_addon_studio_overrides(
        name, version, variant=studio_variant
    )
    item = overrides[_override_key(path)]
    assert item["path"] == path
    assert item["value"] is new_value
    assert item["level"] == "studio"

    # Production settings were not affected
    production = get_addon_studio_settings(
        name, version, variant="production"
    )
    assert _get_value(production, path) is _get_value(settings, path)


def test_set_addon_studio_settings_explicit_pin(
    settings_addon, studio_variant
):
    """Unchanged value is stored when pinned with '__pinned_fields__'."""
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    value = _get_value(settings, path)
    payload = copy.deepcopy(settings)
    payload["__pinned_fields__"] = [path]
    set_addon_studio_settings(name, version, payload, variant=studio_variant)

    raw = get_addon_studio_raw_overrides(name, version, variant=studio_variant)
    assert _get_value(raw, path) is value


def test_get_addon_studio_overrides_as_version(
    settings_addon, studio_variant
):
    """Overrides with 'as_version' of the same version are equal."""
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    new_value = not _get_value(settings, path)
    set_addon_studio_raw_overrides(
        name,
        version,
        _build_overrides(path, new_value),
        variant=studio_variant,
    )

    overrides = get_addon_studio_overrides(
        name, version, variant=studio_variant
    )
    as_version_overrides = get_addon_studio_overrides(
        name, version, variant=studio_variant, as_version=version
    )
    assert overrides == as_version_overrides
    assert overrides[_override_key(path)]["value"] is new_value


def test_modify_addon_studio_overrides(settings_addon, studio_variant):
    """Remove and pin studio override on a settings path.

    Verifies:
        - 'delete' action removes the override and default value is used.
        - 'pin' action stores current value as override.

    """
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    default_value = _get_value(
        get_addon_studio_settings(name, version, variant=studio_variant),
        path,
    )
    set_addon_studio_raw_overrides(
        name,
        version,
        _build_overrides(path, not default_value),
        variant=studio_variant,
    )

    modify_addon_studio_overrides(
        name, version, "delete", path, variant=studio_variant
    )
    raw = get_addon_studio_raw_overrides(name, version, variant=studio_variant)
    assert not _has_path(raw, path)
    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    assert _get_value(settings, path) is default_value
    overrides = get_addon_studio_overrides(
        name, version, variant=studio_variant
    )
    assert _override_key(path) not in overrides

    modify_addon_studio_overrides(
        name, version, "pin", path, variant=studio_variant
    )
    raw = get_addon_studio_raw_overrides(name, version, variant=studio_variant)
    assert _get_value(raw, path) is default_value
    overrides = get_addon_studio_overrides(
        name, version, variant=studio_variant
    )
    assert overrides[_override_key(path)]["value"] is default_value


def test_delete_addon_studio_overrides(settings_addon, studio_variant):
    """Delete all studio overrides of the variant."""
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    default_value = _get_value(
        get_addon_studio_settings(name, version, variant=studio_variant),
        path,
    )
    set_addon_studio_raw_overrides(
        name,
        version,
        _build_overrides(path, not default_value),
        variant=studio_variant,
    )
    assert get_addon_studio_raw_overrides(
        name, version, variant=studio_variant
    )

    delete_addon_studio_overrides(name, version, variant=studio_variant)

    assert get_addon_studio_raw_overrides(
        name, version, variant=studio_variant
    ) == {}
    assert get_addon_studio_overrides(
        name, version, variant=studio_variant
    ) == {}
    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    assert _get_value(settings, path) is default_value


def test_studio_raw_overrides_roundtrip(settings_addon, studio_variant):
    """Raw studio overrides are stored and returned as they are."""
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    assert get_addon_studio_raw_overrides(
        name, version, variant=studio_variant
    ) == {}

    default_value = _get_value(
        get_addon_studio_settings(name, version, variant=studio_variant),
        path,
    )
    overrides = _build_overrides(path, not default_value)
    set_addon_studio_raw_overrides(
        name, version, overrides, variant=studio_variant
    )

    assert get_addon_studio_raw_overrides(
        name, version, variant=studio_variant
    ) == overrides
    settings = get_addon_studio_settings(name, version, variant=studio_variant)
    assert _get_value(settings, path) is (not default_value)


# --- Project settings ---
def test_set_addon_project_settings(project_addon):
    """Set full project settings and check calculated overrides.

    Verifies:
        - Changed value is returned by project settings getter.
        - Changed value is stored in raw project overrides.
        - Overrides listing contains the field on project level.

    """
    name = project_addon["name"]
    version = project_addon["version"]
    path = project_addon["path"]
    project_name = project_addon["project_name"]

    settings = get_addon_project_settings(
        name, version, project_name, variant="production", use_site=False
    )
    new_value = not _get_value(settings, path)
    new_settings = copy.deepcopy(settings)
    _set_value(new_settings, path, new_value)

    set_addon_project_settings(
        name, version, project_name, new_settings, variant="production"
    )

    updated = get_addon_project_settings(
        name, version, project_name, variant="production", use_site=False
    )
    assert _get_value(updated, path) is new_value

    raw = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )
    assert _get_value(raw, path) is new_value

    overrides = get_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    item = overrides[_override_key(path)]
    assert item["path"] == path
    assert item["value"] is new_value
    assert item["level"] == "project"


def test_modify_addon_project_overrides(project_addon):
    """Remove and pin project override on a settings path."""
    name = project_addon["name"]
    version = project_addon["version"]
    path = project_addon["path"]
    project_name = project_addon["project_name"]

    delete_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    studio_value = _get_value(
        get_addon_project_settings(
            name, version, project_name, variant="production", use_site=False
        ),
        path,
    )
    set_addon_project_raw_overrides(
        name,
        version,
        project_name,
        _build_overrides(path, not studio_value),
        variant="production",
    )

    modify_addon_project_overrides(
        name, version, project_name, "delete", path, variant="production"
    )
    raw = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )
    assert not _has_path(raw, path)
    settings = get_addon_project_settings(
        name, version, project_name, variant="production", use_site=False
    )
    assert _get_value(settings, path) is studio_value

    modify_addon_project_overrides(
        name, version, project_name, "pin", path, variant="production"
    )
    raw = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )
    assert _get_value(raw, path) is studio_value
    overrides = get_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    item = overrides[_override_key(path)]
    assert item["level"] == "project"
    assert item["value"] is studio_value


def test_project_raw_overrides_and_delete(project_addon):
    """Raw project overrides roundtrip and deletion of all overrides."""
    name = project_addon["name"]
    version = project_addon["version"]
    path = project_addon["path"]
    project_name = project_addon["project_name"]

    delete_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    assert get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    ) == {}

    studio_value = _get_value(
        get_addon_project_settings(
            name, version, project_name, variant="production", use_site=False
        ),
        path,
    )
    overrides = _build_overrides(path, not studio_value)
    set_addon_project_raw_overrides(
        name, version, project_name, overrides, variant="production"
    )
    assert get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    ) == overrides
    settings = get_addon_project_settings(
        name, version, project_name, variant="production", use_site=False
    )
    assert _get_value(settings, path) is (not studio_value)

    delete_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    assert get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    ) == {}
    settings = get_addon_project_settings(
        name, version, project_name, variant="production", use_site=False
    )
    assert _get_value(settings, path) is studio_value


def test_project_site_overrides(project_addon, project_site_id):
    """Project site overrides of current user with 'site_id' argument.

    Verifies:
        - Raw site overrides are separated from project overrides.
        - Overrides listing with site id contains the site level override.
        - Pin/delete actions and deletion of all site overrides.

    """
    name = project_addon["name"]
    version = project_addon["version"]
    path = project_addon["path"]
    project_name = project_addon["project_name"]
    site_id = project_site_id

    assert get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    ) == {}
    project_raw = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )

    project_value = _get_value(
        get_addon_project_settings(
            name, version, project_name, variant="production", use_site=False
        ),
        path,
    )
    overrides = _build_overrides(path, not project_value)
    set_addon_project_raw_overrides(
        name, version, project_name, overrides, site_id=site_id
    )
    assert get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    ) == overrides
    # Project overrides are not affected
    assert get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    ) == project_raw

    site_settings = get_addon_project_settings(
        name, version, project_name, variant="production", site_id=site_id
    )
    assert _get_value(site_settings, path) is (not project_value)

    listing = get_addon_project_overrides(
        name, version, project_name, variant="production", site_id=site_id
    )
    item = listing[_override_key(path)]
    assert item["level"] == "site"
    assert item["value"] is (not project_value)

    # Site overrides are not listed without site id
    listing = get_addon_project_overrides(
        name, version, project_name, variant="production"
    )
    item = listing.get(_override_key(path))
    assert item is None or item["level"] != "site"

    modify_addon_project_overrides(
        name, version, project_name, "delete", path, site_id=site_id
    )
    raw = get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    )
    assert not _has_path(raw, path)

    modify_addon_project_overrides(
        name, version, project_name, "pin", path, site_id=site_id
    )
    raw = get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    )
    assert _get_value(raw, path) is project_value

    delete_addon_project_overrides(
        name, version, project_name, site_id=site_id
    )
    assert get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    ) == {}


def test_set_addon_project_settings_site(project_addon, project_site_id):
    """Set full project settings as site overrides with 'site_id'."""
    name = project_addon["name"]
    version = project_addon["version"]
    path = project_addon["path"]
    project_name = project_addon["project_name"]
    site_id = project_site_id

    project_raw = get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    )
    settings = get_addon_project_settings(
        name, version, project_name, variant="production", site_id=site_id
    )
    new_value = not _get_value(settings, path)
    new_settings = copy.deepcopy(settings)
    _set_value(new_settings, path, new_value)

    set_addon_project_settings(
        name,
        version,
        project_name,
        new_settings,
        variant="production",
        site_id=site_id,
    )

    raw = get_addon_project_raw_overrides(
        name, version, project_name, site_id=site_id
    )
    assert _get_value(raw, path) is new_value
    assert get_addon_project_raw_overrides(
        name, version, project_name, variant="production"
    ) == project_raw

    updated = get_addon_project_settings(
        name, version, project_name, variant="production", site_id=site_id
    )
    assert _get_value(updated, path) is new_value


# --- Site settings ---
def test_set_addon_site_settings(site_settings_addon, registered_site):
    """Set site settings of current user for a registered test site.

    Verifies:
        - Site settings of unused site are defaults.
        - Changed value is returned after set.
        - Site settings of different site are not affected.

    """
    name = site_settings_addon["name"]
    version = site_settings_addon["version"]
    schema = site_settings_addon["schema"]
    site_id = registered_site

    defaults = get_addon_site_settings(name, version, site_id=site_id)
    assert isinstance(defaults, dict)
    # Site id from connection is used by default
    assert get_addon_site_settings(name, version) == defaults

    new_settings = copy.deepcopy(defaults)
    path = _find_bool_path(schema, required_scopes=())
    if path and isinstance(_get_value(defaults, path), bool):
        _set_value(new_settings, path, not _get_value(defaults, path))
    else:
        path = None

    set_addon_site_settings(name, version, new_settings, site_id=site_id)
    assert get_addon_site_settings(
        name, version, site_id=site_id
    ) == new_settings
    if path is not None:
        assert new_settings != defaults
        other_site = _unique_name()
        assert get_addon_site_settings(
            name, version, site_id=other_site
        ) != new_settings

    # Site id from connection is used if not passed
    set_addon_site_settings(name, version, defaults)
    assert get_addon_site_settings(
        name, version, site_id=site_id
    ) == defaults


def test_set_addon_site_settings_without_site_id():
    """ValueError is raised if site id is not available."""
    orig_site_id = get_site_id()
    try:
        set_site_id(None)
        with pytest.raises(ValueError):
            set_addon_site_settings("addon", "1.0.0", {})
    finally:
        set_site_id(orig_site_id)


# --- Migration ---
def test_migrate_addon_settings_same_version(
    settings_addon, min_server_1_16_8
):
    """Server refuses migration to the same addon version."""
    with pytest.raises(exceptions.HTTPRequestError):
        migrate_addon_settings(
            settings_addon["name"],
            settings_addon["version"],
            settings_addon["version"],
            with_projects=False,
        )


def test_migrate_addon_settings(
    settings_addon, studio_variant, min_server_1_16_8
):
    """Migrate studio settings from other installed addon version.

    Both source and target variant is the unique test variant and project
    settings are not migrated, so production settings are not affected.
    Source version does not have overrides for the variant, so target
    overrides are replaced (removed) by the migration.

    """
    name = settings_addon["name"]
    version = settings_addon["version"]
    path = settings_addon["path"]

    other_version = None
    for addon in get_addons_info(details=False)["addons"]:
        if addon["name"] != name:
            continue
        for addon_version in addon["versions"]:
            if addon_version != version:
                other_version = addon_version
                break
    if other_version is None:
        pytest.skip(f"Addon '{name}' does not have other version installed.")

    assert get_addon_studio_raw_overrides(
        name, other_version, variant=studio_variant
    ) == {}

    default_value = _get_value(
        get_addon_studio_settings(name, version, variant=studio_variant),
        path,
    )
    set_addon_studio_raw_overrides(
        name,
        version,
        _build_overrides(path, not default_value),
        variant=studio_variant,
    )

    result = migrate_addon_settings(
        name,
        other_version,
        version,
        source_variant=studio_variant,
        target_variant=studio_variant,
        with_projects=False,
    )
    assert isinstance(result, dict)
    events = result["events"]
    assert isinstance(events, list)
    assert len(events) == 1
    summary = events[0]["summary"]
    assert summary["variant"] == studio_variant
    assert summary["source_version"] == other_version
    assert summary["addon_version"] == version

    # Converted (empty) source overrides replaced the target overrides
    assert get_addon_studio_raw_overrides(
        name, version, variant=studio_variant
    ) != _build_overrides(path, not default_value)
    # Source overrides stay untouched
    assert get_addon_studio_raw_overrides(
        name, other_version, variant=studio_variant
    ) == {}


def test_migrate_settings_by_bundle_same_bundle(
    settings_addon, production_bundle
):
    """Migrate production bundle settings to itself without projects.

    Source and target are the same bundle and variant, so the migration
    does not change any data (overrides are compared with themselves).

    """
    name = settings_addon["name"]
    version = settings_addon["version"]
    original = get_addon_studio_raw_overrides(
        name, version, variant="production"
    )
    try:
        migrate_settings_by_bundle(
            production_bundle["name"],
            production_bundle["name"],
            "production",
            "production",
            with_projects=False,
        )
        assert get_addon_studio_raw_overrides(
            name, version, variant="production"
        ) == original
    finally:
        current = get_addon_studio_raw_overrides(
            name, version, variant="production"
        )
        if current != original and original:
            set_addon_studio_raw_overrides(
                name, version, original, variant="production"
            )


def test_migrate_settings_by_bundle_invalid(production_bundle):
    """Invalid migration requests are refused before any change.

    Verifies:
        - Custom variant must match the bundle name.
        - Unknown bundle is refused.

    """
    bundle_name = production_bundle["name"]
    with pytest.raises(exceptions.HTTPRequestError):
        migrate_settings_by_bundle(
            bundle_name,
            bundle_name,
            "production",
            _unique_name(),
            with_projects=False,
        )

    with pytest.raises(exceptions.HTTPRequestError):
        migrate_settings_by_bundle(
            _unique_name(),
            bundle_name,
            "production",
            "production",
            with_projects=False,
        )
