from abc import ABCMeta, abstractproperty, abstractmethod
from uuid import uuid4
import six


class SelectionContext(object):
    def __init__(self, project, folders, subsets, representations):
        self.project = project
        self.folders = folders
        self.subsets = subsets
        self.representations = representations


class ActionItem(object):
    """Item representing single action item of loader action.

    Args:
        action (LoaderAction): Action to which is item related to.
        identifier (str): Identifier of the item (not the 'LoaderAction').
        label (str): Label of the action.
        groups (list<str>): Possible groups of sub-labels. Can be used to
            "create submenu/s".
        context (SelectionContext): Context in which will be the action item
            triggered.
    """

    def __init__(self, action, context, label, icon=None, groups=None):
        if groups is None:
            groups = []

        self._id = str(uuid4())
        self.action = action
        self.label = label
        self.icon = icon
        self.groups = groups
        self._context = context

    @property
    def id(self):
        """Each created action item has it's id."""
        return self._id

    @property
    def context(self):
        return self._context

    @property
    def action_identifier(self):
        """Identifier of action which created the item."""

        return self.action.identifier

    def trigger(self):
        """Trigger callback of the action item."""

        self.action.trigger(self)

    def to_dict(self):
        """Convert the action item into serializable data format.

        It should be possible to convert the item into json string to be able
        send it to different process (for UI purposes).

        Returns:
            dict: Data that identify the action item and can be converted to
                json.
        """

        return {
            "id": self.id,
            "icon": self.icon,
            "action_identifier": self.action_identifier,
            "identifier": self.identifier,
            "label": self.label,
            "groups": self.groups,
        }


@six.add_metaclass(ABCMeta)
class LoaderAction(object):
    """Action for loader tool.

    Action can be shown on project, folder, subset, verison, representation.
    """

    def __init__(self, system_settings, project_settings):
        pass

    @abstractproperty
    def identifier(self):
        """A unique identifier.

        So action can be recalled from history e.g.

        Returns:
            str: Identifier of action.
        """
        pass

    @abstractmethod
    def get_action_items_for_context(self, context):
        """Get action items for passed context.

        This method returns action items that are then showed in UI. Can return
        more then one action item with different identifiers.

        Note:
        It is possible to create sub contexts for each action item.

        Args:
            context (SelectionContext): Context for which should be created
                action items.

        Returns:
            list<ActionItem>: Action items that can be triggered on passed
                context.
        """

        return []

    @abstractmethod
    def trigger(self, action_item):
        """ Trigger loader action and do what the action should do.

        Args:
            action_item (ActionItem): Item created by the action to be
                triggered.
        """
        pass
