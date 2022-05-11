import os
import sys
import types
import importlib
import inspect
import logging

import six

log = logging.getLogger(__name__)


def unify_path(path):
    """Make sure the passed path is unique."""
    return os.path.normpath(path)


def unify_paths(paths):
    """Unify multiple paths using 'unify_path'."""

    return [unify_path(path) for path in paths]


def recursive_bases_from_class(klass):
    """Extract all bases from entered class."""
    result = []
    bases = klass.__bases__
    result.extend(bases)
    for base in bases:
        result.extend(recursive_bases_from_class(base))
    return result


def classes_from_module(superclass, module):
    """Return plug-ins from module

    Arguments:
        superclass (superclass): Superclass of subclasses to look for
        module (types.ModuleType): Imported module from which to
            parse valid Avalon plug-ins.

    Returns:
        List of plug-ins, or empty list if none is found.
    """

    classes = list()
    for name in dir(module):
        # It could be anything at this point
        obj = getattr(module, name)
        if not inspect.isclass(obj) or obj is superclass:
            continue

        if issubclass(obj, superclass):
            classes.append(obj)

    return classes


class DynamicModuleCache:
    """Cache object used to store the cache and handle outdated check.

    Args:
        filepath (str): Path that was imported.
        module (types.ModuleType): Imported file as python module.
    """

    def __init__(self, filepath, module):
        self.filepath = filepath
        self.module = module
        # Store last modification of the imported file
        self._file_modifier = os.path.getmtime(filepath)

    @property
    def is_outdated(self):
        """Check if imported file has changed.

        In theory this would return True only during development of fles.
        """

        return self._file_modifier != os.path.getmtime(self.filepath)


class _DynamicModulesCache:
    """Globaly stored cache data about dynamically imported modules.

    Dynamically imported modules are modules that are imported from files or
    directories that are not in 'sys.path'.

    Goal is to avoid reimport file multiple times if the file did not change.
    But in some cases it may be required and expected.
    """

    _cache_by_filepaths = {}
    _cache_by_dirpath = {}

    @classmethod
    def _cache_module(cls, filepath, module):
        # Prepare store values
        normalized = unify_path(filepath)
        dirpath = os.path.dirname(filepath)

        # Make sure dirpath is in dir cache
        if dirpath not in cls._cache_by_dirpath:
            cls._cache_by_dirpath[dirpath] = []

        # Remove previous cache from dirpath caches if there is any
        existing_cache = cls._cache_by_filepaths.get(filepath)
        if existing_cache is not None:
            cls._cache_by_dirpath[dirpath].remove(existing_cache)

        # Create new cache item and store
        cache_item = DynamicModuleCache(normalized, module)
        cls._cache_by_filepaths[filepath] = cache_item
        cls._cache_by_dirpath[dirpath].append(cache_item)

    @classmethod
    def import_module_from_file(cls, filepath):
        filepath = unify_path(filepath)
        cache = cls._cache_by_filepaths.get(filepath)
        if cache and not cache.is_outdated:
            return

        try:
            module = import_filepath(filepath)
            cls._cache_module(filepath, module)

        except Exception:
            pass

    @classmethod
    def import_module_from_dir(cls, dirpath):
        ignore_filenames = []
        any_file_to_import = False
        for filename in os.listdir(dirpath):
            filepath = unify_path(os.path.join(dirpath, filename))
            cls.import_module_from_file(filepath)
            cache = cls._cache_by_filepaths.get(filepath)
            if cache and not cache.is_outdated:
                ignore_filenames.append(filename)
            else:
                any_file_to_import = False

        if any_file_to_import:
            discovered, _ = modules_from_path(dirpath, ignore_filenames)
            for filepath, module in discovered:
                cls._cache_module(filepath, module)

    @classmethod
    def get_module_from_filepath(cls, filepath):
        unified_path = unify_path(filepath)
        cls.import_module_from_file(unified_path)
        cache = cls._cache_by_filepaths.get(unified_path)
        if cache:
            return cache.module
        return None

    @classmethod
    def get_modules_from_dir(cls, dirpath):
        unified_path = unify_path(dirpath)
        cls.import_module_from_dir(unified_path)
        caches = cls._cache_by_dirpath.get(unified_path) or []
        return [
            cache.module
            for cache in caches
        ]


def import_filepath(filepath, module_name=None):
    """Import python file as python module.

    Python 2 and Python 3 compatibility.

    Args:
        filepath(str): Path to python file.
        module_name(str): Name of loaded module. Only for Python 3. By default
            is filled with filename of filepath.
    """
    if module_name is None:
        module_name = os.path.splitext(os.path.basename(filepath))[0]

    # Make sure it is not 'unicode' in Python 2
    module_name = str(module_name)

    # Prepare module object where content of file will be parsed
    module = types.ModuleType(module_name)

    if six.PY3:
        # Use loader so module has full specs
        module_loader = importlib.machinery.SourceFileLoader(
            module_name, filepath
        )
        module_loader.exec_module(module)
    else:
        # Execute module code and store content to module
        with open(filepath) as _stream:
            # Execute content and store it to module object
            six.exec_(_stream.read(), module.__dict__)

        module.__file__ = filepath
    return module


def modules_from_path(folder_path, ignore_filenames=None):
    """Get python scripts as modules from a path.

    Arguments:
        path (str): Path to folder containing python scripts.

    Returns:
        tuple<list, list>: First list contains successfully imported modules
            and second list contains tuples of path and exception.
    """

    ignore_filenames = ignore_filenames or []
    crashed = []
    modules = []
    output = (modules, crashed)
    # Just skip and return empty list if path is not set
    if not folder_path:
        return output

    # Do not allow relative imports
    if folder_path.startswith("."):
        log.warning((
            "BUG: Relative paths are not allowed for security reasons. {}"
        ).format(folder_path))
        return output

    folder_path = os.path.normpath(folder_path)

    if not os.path.isdir(folder_path):
        log.warning("Not a directory path: {}".format(folder_path))
        return output

    for filename in os.listdir(folder_path):
        # Ignore files which start with underscore
        if filename.startswith("_") or filename in ignore_filenames:
            continue

        mod_name, mod_ext = os.path.splitext(filename)
        if not mod_ext == ".py":
            continue

        full_path = os.path.join(folder_path, filename)
        if not os.path.isfile(full_path):
            continue

        try:
            module = import_filepath(full_path, mod_name)
            modules.append((full_path, module))

        except Exception:
            crashed.append((full_path, sys.exc_info()))
            log.warning(
                "Failed to load path: \"{0}\"".format(full_path),
                exc_info=True
            )
            continue

    return output


def import_module_from_dirpath(dirpath, folder_name, dst_module_name=None):
    """Import passed directory as a python module.

    Python 2 and 3 compatible.

    Imported module can be assigned as a child attribute of already loaded
    module from `sys.modules` if has support of `setattr`. That is not default
    behavior of python modules so parent module must be a custom module with
    that ability.

    It is not possible to reimport already cached module. If you need to
    reimport module you have to remove it from caches manually.

    Args:
        dirpath(str): Parent directory path of loaded folder.
        folder_name(str): Folder name which should be imported inside passed
            directory.
        dst_module_name(str): Parent module name under which can be loaded
            module added.
    """
    if six.PY3:
        module = _import_module_from_dirpath_py3(
            dirpath, folder_name, dst_module_name
        )
    else:
        module = _import_module_from_dirpath_py2(
            dirpath, folder_name, dst_module_name
        )
    return module


def _import_module_from_dirpath_py2(dirpath, module_name, dst_module_name):
    """Import passed dirpath as python module using `imp`."""
    if dst_module_name:
        full_module_name = "{}.{}".format(dst_module_name, module_name)
        dst_module = sys.modules[dst_module_name]
    else:
        full_module_name = module_name
        dst_module = None

    if full_module_name in sys.modules:
        return sys.modules[full_module_name]

    import imp

    fp, pathname, description = imp.find_module(module_name, [dirpath])
    module = imp.load_module(full_module_name, fp, pathname, description)
    if dst_module is not None:
        setattr(dst_module, module_name, module)

    return module


def _import_module_from_dirpath_py3(dirpath, module_name, dst_module_name):
    """Import passed dirpath as python module using Python 3 modules."""
    if dst_module_name:
        full_module_name = "{}.{}".format(dst_module_name, module_name)
        dst_module = sys.modules[dst_module_name]
    else:
        full_module_name = module_name
        dst_module = None

    # Skip import if is already imported
    if full_module_name in sys.modules:
        return sys.modules[full_module_name]

    import importlib.util
    from importlib._bootstrap_external import PathFinder

    # Find loader for passed path and name
    loader = PathFinder.find_module(full_module_name, [dirpath])

    # Load specs of module
    spec = importlib.util.spec_from_loader(
        full_module_name, loader, origin=dirpath
    )

    # Create module based on specs
    module = importlib.util.module_from_spec(spec)

    # Store module to destination module and `sys.modules`
    # WARNING this mus be done before module execution
    if dst_module is not None:
        setattr(dst_module, module_name, module)

    sys.modules[full_module_name] = module

    # Execute module import
    loader.exec_module(module)

    return module
