import os
import time

from openpype.client import (
    get_system_settings,
    get_project_settings,
)
from openpype.pipeline.plugin_discover import discover_class

from .plugin import LoadPlugin


class LoadPluginsContext:
    """Context which care about load plugins.

    Discovery, caching and registerion.

    QUESTION:
    Should it also handle callbacks on plugins? Direct calling of plugins
    without single acces point can cause that the Plugin source (in
    sys.modules)
    """

    # How long will be plugins cached
    # - it is not practical to initialize plugins all the time
    cache_time = 10

    def __init__(self, host):
        self._host = host

        self._registered_plugins = []
        self._registered_plugin_paths = []

        self._last_discovered_plugins = {}
        self._last_loaded = None

        # Classes that will be skipped on initialization and discovery
        # - host may have it's custo abstract methods that would be discovered
        #   and could possible cause issues
        self._known_abstract_classes = []

    def add_known_abstract_class(self, cls):
        self._known_abstract_classes.append(cls)

    def clear_plugins(self):
        self._last_loaded = None
        self._registered_plugins = []
        self._registered_plugin_paths = []
        self._last_discovered_plugins = {}

    @property
    def is_cache_outdated(self):
        if self._last_loaded is None:
            return True
        return (time.time() - self._last_loaded) > self.cache_time

    @property
    def host(self):
        return self._host

    def get_load_plugins(self):
        if self.is_cache_outdated:
            self._discover()
        return self._last_discovered_plugins

    def register_plugin_path(self, path):
        self._last_loaded = None
        self._registered_plugin_paths.append(path)

    def register_plugin(self, plugin):
        self._last_loaded = None
        self._registered_plugins.append(plugin)

    def _discover(self):
        # TODO add validations
        # - abstract methods
        # Discover plugin classes
        plugins = []
        plugins.extend(self._registered_plugins)
        plugins.extend(
            discover_class(self._registered_plugin_paths, LoadPlugin)
        )

        # Initialized plugins
        system_settings = get_system_settings()
        project_settings = get_project_settings(self.host.project_name)

        duplicated_identifiers = []
        plugins_by_idenfiers = {}
        for plugin_class in plugins:
            plugin = plugin_class(self, system_settings, project_settings)
            if plugin.identifier in plugins_by_idenfiers:
                duplicated_identifiers.append(plugin)
            else:
                plugins_by_idenfiers[plugin.identifier] = plugin

        self._last_discovered_plugins = plugins
