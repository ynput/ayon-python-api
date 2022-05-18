"""Modules logic."""
import logging
from uuid import uuid4
from abc import ABCMeta, abstractmethod

import six


@six.add_metaclass(ABCMeta)
class OpenPypeModule(object):
    """Base class of pype module.

    Attributes:
        id (UUID): Module's id.
        enabled (bool): Is module enabled.
        name (str): Module name.
        manager (ModulesManager): Manager that created the module.
    """

    # Disable by default
    enabled = False
    _id = None

    @property
    @abstractmethod
    def name(self):
        """Module's name."""
        pass

    def __init__(self, manager, settings):
        self.manager = manager

        self.log = logging.getLogger(self.name)

        self.initialize(settings)

    @property
    def id(self):
        if self._id is None:
            self._id = uuid4()
        return self._id

    @abstractmethod
    def initialize(self, module_settings):
        """Initialization of module attributes.

        It is not recommended to override __init__ that's why specific method
        was implemented.
        """
        pass

    def connect_with_modules(self, enabled_modules):
        """Connect with other enabled modules."""
        pass

    def get_global_environments(self):
        """Get global environments values of module.

        Environment variables that can be get only from system settings.
        """
        return {}

    def cli(self, module_click_group):
        """Add commands to click group.

        The best practise is to create click group for whole module which is
        used to separate commands.

        class MyPlugin(OpenPypeModule):
            ...
            def cli(self, module_click_group):
                module_click_group.add_command(cli_main)


        @click.group(<module name>, help="<Any help shown in cmd>")
        def cli_main():
            pass

        @cli_main.command()
        def mycommand():
            print("my_command")
        """
        pass
