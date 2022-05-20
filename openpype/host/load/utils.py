import os
import platform
import logging
import inspect
import numbers

from openpype.lib import StringTemplate

log = logging.getLogger(__name__)


class HeroVersionType(object):
    def __init__(self, version):
        assert isinstance(version, numbers.Integral), (
            "Version is not an integer. \"{}\" {}".format(
                version, str(type(version))
            )
        )
        self.version = version

    def __str__(self):
        return str(self.version)

    def __int__(self):
        return int(self.version)

    def __format__(self, format_spec):
        return self.version.__format__(format_spec)


class IncompatibleLoaderError(ValueError):
    """Error when Loader is incompatible with a representation."""
    pass


def get_repres_contexts(project_name, representation_ids):
    """Return parenthood context for representation.

    Args:
        representation_ids (list): The representation ids.
        dbcon (AvalonMongoDB): Mongo connection object. `avalon.io` used when
            not entered.

    Returns:
        dict: The full representation context by representation id.
            keys are repre_id, value is dictionary with full:
                asset_doc version_doc subset_doc repre_doc
    """

    pass


def get_subset_contexts(project_name, subset_ids):
    """Return parenthood context for subset.

        Provides context on subset granularity - less detail than
        'get_repre_contexts'.
    Args:
        subset_ids (list): The subset ids.
        dbcon (AvalonMongoDB): Mongo connection object. `avalon.io` used when
            not entered.

    Returns:
        dict: The full representation context by representation id.
    """

    pass


def get_representation_context(project_name, representation):
    """Return parenthood context for representation.

    Args:
        representation (str or ObjectId or dict): The representation id
            or full representation as returned by the database.

    Returns:
        dict: The full representation context.
    """

    pass


def load_with_repre_context(
    Loader, repre_context, namespace=None, name=None, options=None, **kwargs
):

    # Ensure the Loader is compatible for the representation
    if not is_compatible_loader(Loader, repre_context):
        raise IncompatibleLoaderError(
            "Loader {} is incompatible with {}".format(
                Loader.__name__, repre_context["subset"]["name"]
            )
        )

    # Ensure options is a dictionary when no explicit options provided
    if options is None:
        options = kwargs.get("data", dict())  # "data" for backward compat

    assert isinstance(options, dict), "Options must be a dictionary"

    # Fallback to subset when name is None
    if name is None:
        name = repre_context["subset"]["name"]

    log.info(
        "Running '%s' on '%s'" % (
            Loader.__name__, repre_context["asset"]["name"]
        )
    )

    loader = Loader(repre_context)
    return loader.load(repre_context, name, namespace, options)


def load_with_subset_context(
    Loader, subset_context, namespace=None, name=None, options=None, **kwargs
):

    # Ensure options is a dictionary when no explicit options provided
    if options is None:
        options = kwargs.get("data", dict())  # "data" for backward compat

    assert isinstance(options, dict), "Options must be a dictionary"

    # Fallback to subset when name is None
    if name is None:
        name = subset_context["subset"]["name"]

    log.info(
        "Running '%s' on '%s'" % (
            Loader.__name__, subset_context["asset"]["name"]
        )
    )

    loader = Loader(subset_context)
    return loader.load(subset_context, name, namespace, options)


def load_with_subset_contexts(
    Loader, subset_contexts, namespace=None, name=None, options=None, **kwargs
):

    # Ensure options is a dictionary when no explicit options provided
    if options is None:
        options = kwargs.get("data", dict())  # "data" for backward compat

    assert isinstance(options, dict), "Options must be a dictionary"

    # Fallback to subset when name is None
    joined_subset_names = " | ".join(
        context["subset"]["name"]
        for context in subset_contexts
    )
    if name is None:
        name = joined_subset_names

    log.info(
        "Running '{}' on '{}'".format(Loader.__name__, joined_subset_names)
    )

    loader = Loader(subset_contexts)
    return loader.load(subset_contexts, name, namespace, options)


def load_container(
    Loader, representation, namespace=None, name=None, options=None, **kwargs
):
    """Use Loader to load a representation.

    Args:
        Loader (Loader): The loader class to trigger.
        representation (str or ObjectId or dict): The representation id
            or full representation as returned by the database.
        namespace (str, Optional): The namespace to assign. Defaults to None.
        name (str, Optional): The name to assign. Defaults to subset name.
        options (dict, Optional): Additional options to pass on to the loader.

    Returns:
        The return of the `loader.load()` method.

    Raises:
        IncompatibleLoaderError: When the loader is not compatible with
            the representation.

    """

    context = get_representation_context(representation)
    return load_with_repre_context(
        Loader,
        context,
        namespace=namespace,
        name=name,
        options=options,
        **kwargs
    )


def get_loader_identifier(loader):
    """Loader identifier from loader plugin or object.

    Identifier should be stored to container for future management.
    """
    if not inspect.isclass(loader):
        loader = loader.__class__
    return loader.__name__


def _get_container_loader(container):
    """Return the Loader corresponding to the container"""
    from .plugins import discover_loader_plugins

    loader = container["loader"]
    for Plugin in discover_loader_plugins():
        # TODO: Ensure the loader is valid
        if get_loader_identifier(Plugin) == loader:
            return Plugin
    return None


def remove_container(container):
    """Remove a container"""

    Loader = _get_container_loader(container)
    if not Loader:
        raise RuntimeError("Can't remove container. See log for details.")

    loader = Loader(get_representation_context(container["representation"]))
    return loader.remove(container)


def update_container(project_name, container, version=-1):
    """Update a container"""

    pass


def switch_container(project_name, container, repre_doc, plugin_name=None):
    """Switch a container to representation

    Args:
        project_name (str): Project name on which representation is updated.
        container (dict): container information.
        repre_doc (dict): representation data from document.

    Returns:
        Result of loader plugin switch method.
    """

    pass


def get_representation_path_from_context(repre_context):
    """Preparation wrapper using only context as a argument"""

    pass


def get_representation_path(project_anatomy, representation):
    """Get filename from representation document

    There are three ways of getting the path from representation which are
    tried in following sequence until successful.
    1. Get template from representation['data']['template'] and data from
       representation['context']. Then format template with the data.
    2. Get template from project['config'] and format it with default data set
    3. Get representation['data']['path'] and use it directly

    Args:
        project_anatomy (Anatomy): Prepared project anatomy.
        representation(dict): representation document from the database

    Returns:
        str: fullpath of the representation

    """

    template = representation["data"]["template"]

    context = representation["context"]
    context["root"] = project_anatomy.roots
    path = StringTemplate.format_strict_template(template, context)
    # Force replacing backslashes with forward slashed if not on
    #   windows
    if platform.system().lower() != "windows":
        path = path.replace("\\", "/")

    if not path:
        return None
    return os.path.normpath(path)


def is_compatible_loader(Loader, context):
    """Return whether a loader is compatible with a context.

    This checks the version's families and the representation for the given
    Loader.

    Returns:
        bool

    """

    repre_entity = context["representation"]
    representations = Loader.get_representations()
    if not (
        "*" in representations
        or repre_entity["name"] in representations
    ):
        return False

    subset_data = context["subset"]["data"]
    if "family" in subset_data:
        families = [subset_data["family"]]

    elif "families" in subset_data:
        families = subset_data["families"]

    else:
        families = context["version"]["data"].get("families") or []

    if not (
        "*" in Loader.families
        or any(family in Loader.families for family in families)
    ):
        return False

    return True


def loaders_from_repre_context(loaders, repre_context):
    """Return compatible loaders for by representaiton's context."""

    return [
        loader
        for loader in loaders
        if is_compatible_loader(loader, repre_context)
    ]


def loaders_from_representation(loaders, representation):
    """Return all compatible loaders for a representation."""

    context = get_representation_context(representation)
    return loaders_from_repre_context(loaders, context)
