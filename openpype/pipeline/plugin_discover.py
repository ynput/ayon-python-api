import os
from openpype.lib import modules_from_path


class ModuleCache:
    def __init__(self, filepath, module):
        self.filepath = filepath
        self.module = module
        self._file_modifier = os.path.getmtime(filepath)

    @property
    def is_outdated(self):
        return self._file_modifier != os.path.getmtime(self.filepath)


class _GlobalModulesCache:
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
        cache_item = ModuleCache(normalized, module)
        cls._cache_by_filepaths[filepath] = cache_item
        cls._cache_by_dirpath[dirpath].append(cache_item)

    @classmethod
    def import_module_from_dir(cls, dirpath):
        ignore_filenames = []
        for filename in os.listdir(dirpath):
            filepath = unify_path(os.path.join(dirpath, filename))
            cache = cls._cache_by_filepaths.get(filepath)
            if cache and not cache.is_outdated:
                ignore_filenames.append(filename)

        discovered, _ = modules_from_path(dirpath, ignore_filenames)
        for filepath, module in discovered:
            cls._cache_module(filepath, module)

    @classmethod
    def get_modules_from_dir(cls, dirpath):
        unified_path = unify_path(dirpath)
        if unified_path not in cls._cache_by_dirpath:
            cls.import_module_from_dir(unified_path)
        caches = cls._cache_by_dirpath.get(unified_path) or []
        return [
            cache.module
            for cache in caches
        ]


def unify_path(path):
    return os.path.normpath(path)


def unify_paths(paths):
    return [unify_path(path) for path in paths]


def discover_class(paths, base_cls):
    output = []
    for path in paths:
        modules = _GlobalModulesCache.get_modules_from_dir(path)
        for module in modules:
            output.extend(
                find_class_in_module(module, base_cls)
            )
    return output


def find_class_in_module(module, base_cls):
    output = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name, None)
        if attr is base_cls:
            continue

        if issubclass(attr, base_cls):
            output.append(attr)
    return output
