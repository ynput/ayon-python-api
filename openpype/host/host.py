from abc import ABCMeta, abstractproperty, abstractmethod
import six

from openpype.lib.event_system import EventSystem
from openpype.pipeline.load import LoaderContext


class CurrentContext(object):
    """Definition of context.

    QUESTION:
    - What should contain? Some hosts may change context based on current UI.
    TODO:
    - setter methods to update project, folder and task.
    - getters of folder and task related data (based on client implementation)
    """

    def __init__(self, project_name, folder_id, task_id):
        self._project_name = project_name
        self._folder_id = folder_id
        self._task_id = task_id

    @property
    def project_name(self):
        return self._project_name

    @property
    def folder_id(self):
        return self._folder_id

    @property
    def task_id(self):
        return self._task_id


@six.add_metaclass(ABCMeta)
class HostDefinition(object):
    """Public interface of host.

    Implemented definition can be created and imported at any time from any
    python implementation. Is used to execute methods that can be used
    out (and in) of DCC process.
    """

    @abstractproperty
    def name(self):
        """Name of host, must be unique in single OpenPype server environment.

        There just can't be 2 implementations of 'maya' host.
        """
        pass

    def add_implementation_envs(self, env, application):
        """Modify environments before the DCC application is launched.

        Args:
            env (dict): Environments that were prepared from settings and
                prelaunched hooks.
            application (Application): Object of application loaded from
                settings.
        """
        pass

    def get_workfile_extensions(self):
        """Extensions that can be used as workfile.

        Host won't be able to use workfile tool if empty list is returned.

        This method is not required as some virtual hosts without DCC
        application even don't have workfile.

        Returns:
            list[str]: List of extensions with dot ('.').
        """

        return []


@six.add_metaclass(ABCMeta)
class HostImplementation(object):
    """Host implementation class.

    Implementation of host which is

    In OpenPype v3 context:
    What was before considered as functions in host implementation folder. The
    host implementation should primarily care about adding ability of creation
    (mark subsets to be published) and optionaly about referencing published
    representations as containers.

    # TODO
    - should probably care about tools and their loading

    Installation of host in OP3:
    ```python
    from openpype.pipeline import install_host
    import openpype.hosts.maya.api as host

    install_host(host)
    ```

    Expected installation in OP4:
    ```python
    from openpype.hosts.maya.api import MayaHost

    host = MayaHost()
    ```
    """

    # Event system specific for a host
    _event_system = None
    # Load context
    _load_context = None

    def __init__(self):
        """Initialization of host.

        Part of what 'install' did.

        QUESTIONS
        - Maybe this class should create 'HostDefinition' object
            to have access to host name (avoid duplicity) and file extensions.
        - We may need to implement global variable 'registered_host' in global
            scope for backwards compatibility with OP3 and easier backport
            of already implemented hosts.
            - This is connected to registering load, create and publish paths.
        """

        pass

    @property
    def load_context(self):
        """Access to host load context to load/update/remove containers.

        Load context is 'dynamically created' on first access of the attribute.

        Returns:
            LoaderContext: Load context containing load related logic.
        """

        if self._load_context is None:
            self._load_context = LoaderContext(self)
        return self._load_context

    @property
    def event_system(self):
        """Access to host event system to catch/trigger events.

        Event system is 'dynamically created' on first access of the attribute.

        Returns:
            EventSystem: Event system which cares about triggering of events.
        """

        if self._event_system is None:
            self._event_system = EventSystem()
        return self._event_system

    @abstractproperty
    def name(self):
        """Host implementation name."""

        pass

    @abstractmethod
    def get_current_context(self):
        """Return current context object.

        Returns:
            CurrentContext
        """

        pass

    @abstractmethod
    def set_current_context(self, project_name, folder_id, task_id):
        """Change current context and trigger related changes.

        For example change plugin paths that are specific for project.
        """

        pass

    @abstractmethod
    def get_context_data(self):
        """Global context related to creation/publishing.

        Data are not related to publishing context but are prepared in
        creation, for example enabled/disabled global plugin.
        """

        pass

    @abstractmethod
    def update_context_data(self, changes):
        """Update global context data."""

        pass

    @abstractmethod
    def get_context_title(self):
        """Context in which host currently is.

        Implementation priparily for UI purposes. Default implementation will
        probably return curent context:
            "{project name}/{hierarchy}/{folder}/{task}"

        At this moment is this method used only in new publisher but can be
        used at multiple places.

        It must be possible to return different value for hosts where context
        cannot be defined or is dynamic. E.g. based on opened scene which can
        be changed with tabs in application.
        """

        pass


class ILoadHost:
    """Implementation requirements to be able use reference of representations.

    The load plugins can do referencing even without implementation of methods
    here, but switch and removement of containers would not be possible.

    QUESTIONS
    - Is list container dependency of host or load plugins?
    - Should this be directly in HostImplementation?
        - how to find out if referencing is available?
        - do we need to know that?
    """

    def list_containers(self):
        """Retreive referenced containers from scene.

        This can be implemented in hosts where referencing can be used.

        NOTE: This method is not abstract because there are hosts that do
            not support loading at all.
        """
        return []


@six.add_metaclass(ABCMeta)
class IWorkfileHost:
    """Implementation requirements to be able use workfile utils and tool.

    This interface is more or less just giving idea what is needed to implement
    in host implementation, but does not have necessarily to inherit from this
    interface.
    """

    @abstractmethod
    def get_workfile_extensions(self):
        """Extensions that can be used as save.

        QUESTION: This could potentially use 'HostDefinition'.
        """

        return []

    @abstractmethod
    def save_workfile(self, dst_path=None):
        """Save currently opened scene.

        Args:
            dst_path (str): Where the current scene should be saved. Or use
                current path if 'None' is passed.
        """

        pass

    @abstractmethod
    def open_workfile(self, filepath):
        """Open passed filepath in the host.

        Args:
            filepath (str): Path to workfile.
        """

        pass

    @abstractmethod
    def get_current_workfile(self):
        """Retreive path to current opened file.

        Returns:
            str: Path to file which is currently opened.
            None: If nothing is opened.
        """

        return None

    def has_unsaved_changes(self):
        """Currently opened scene is saved.

        Not all hosts can know if current scene is saved because the API of
        dcc does not support it.

        Returns:
            bool: Scene is saved.
            None: Can't tell.
        """

        return None
