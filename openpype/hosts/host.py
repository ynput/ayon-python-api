from abc import ABCMeta, abstractproperty, abstractmethod
import six

from openpype.lib.event_system import EventSystem
from openpype.pipeline.load import LoaderContext


class CurrentContext:
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
class HostImplementation:
    """Host implementation class.

    What was before considered as functions in host implementation folder.

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

    def __init__(self):
        """Initialization of host.

        Part of what 'install' did.
        """

        # Event system specific for a host
        self._event_system = EventSystem()
        # Load context
        self._load_context = LoaderContext(self)
        # ...

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
