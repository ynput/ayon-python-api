import logging
from abc import (
    ABCMeta,
    abstractproperty,
    abstractmethod,
)
import six


@six.add_metaclass(ABCMeta)
class BaseLoadPlugin(object):
    """Plugin handling reference, switch and removement of containers.

    QUESTION: Is import plugin a different kind of plugin or different type?
    """

    _log = None
    order = 0
    # QUESTION is there change then we would want disable load plugin?
    enabled = True

    def __init__(self, system_settings, project_settings, load_context):
        self._load_context = load_context

    @property
    def load_context(self):
        return self._load_context

    @property
    def host(self):
        self.load_context.host

    def get_load_plugin_by_id(self, identifier):
        return self.load_context.get_load_plugin_by_id(identifier)

    @property
    def log(self):
        """Logger object available at the moment of accessing it."""

        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    @abstractproperty
    def identifier(self):
        """Unique (not dynamic) identifier of load plugin."""
        pass

    @abstractmethod
    def is_compatible(self, family, representation):
        # QUESTION what are expected Arguments?
        """Is Load plugin compatible for representation."""

        pass

    @abstractmethod
    def load_representations(self, representations, load_definitions):
        """Load representations."""

        pass

    def get_load_definitions(self):
        """Optional definitions that can be filled for loading.

        Can more specifically define how representation will be loaded.
        """

        return []

    @abstractmethod
    def can_switch_container(self, container):
        """Can load plugin handle swith of a container."""

        pass

    @abstractmethod
    def switch_container(self, container, representation):
        """Switch container to newer version."""

        pass

    @abstractmethod
    def remove_containers(self, containers):
        """Remove container content and metadata from scene."""

        pass

    # QUESTION is getting of containers job for host or load plugins?
    # - what if load plugin disappeared and other replaced it with
    #   different
    # @abstractmethod
    # def get_containers(self):
    #     """Get containers from scene."""
    #
    #     pass


class LoadPlugin(BaseLoadPlugin):
    families = []
    extensions = []

    def is_compatible(self, family, representation):
        if self.families and family not in self.families:
            return False

        if self.extensions and representation["ext"] not in self.extensions:
            return False
        return True

    def can_switch(self, container):
        if container["load_identifier"] == self.identifier:
            return True
        return False
