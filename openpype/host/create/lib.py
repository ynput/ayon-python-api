import re
from openpype.client import (
    get_project_settings,
    get_task,
)
from openpype.lib.profiles_filtering import filter_profiles


# Subset name template used when plugin does not have defined any
DEFAULT_SUBSET_TEMPLATE = "{family}{Variant}"


class TaskNotSetError(KeyError):
    def __init__(self, msg=None):
        if not msg:
            msg = "Creator's subset name template requires task name."
        super(TaskNotSetError, self).__init__(msg)


def get_subset_name_with_task_entity(
    family,
    variant,
    task_entity,
    host_name,
    project_settings,
    dynamic_data,
    default_template=None
):
    """Calculate subset name based on passed context and OpenPype settings.

    Subst name templates are defined in `project_settings/global/tools/creator
    /subset_name_profiles` where are profiles with host name, family, task name
    and task type filters. If context does not match any profile then
    `DEFAULT_SUBSET_TEMPLATE` is used as default template.

    That's main reason why so many arguments are required to calculate subset
    name.

    Args:
        family (str): Instance family.
        variant (str): In most of cases it is user input during creation.
        task_entity (str): Task entity.
        host_name (str): Name of host used as filtering criteria for
            template profile filters.
        project_settings (dict): Settings for project in which task is.
        dynamic_data (dict): Dynamic data specific for a creator which creates
            instance.
        default_template (str): Default template if any profile does not match
            passed context. Constant 'DEFAULT_SUBSET_TEMPLATE' is used if
            is not passed.
    """
    if not family:
        return None

    task_name = None
    task_type = None
    if task_entity:
        task_name = task_entity["name"]
        task_type = task_entity["type"]

    # Get settings
    tools_settings = project_settings["global"]["tools"]
    profiles = tools_settings["creator"]["subset_name_profiles"]
    filtering_criteria = {
        "families": family,
        "hosts": host_name,
        "tasks": task_name,
        "task_types": task_type
    }

    matching_profile = filter_profiles(profiles, filtering_criteria)
    template = None
    if matching_profile:
        template = matching_profile["template"]

    # Make sure template is set (matching may have empty string)
    if not template:
        template = default_template or DEFAULT_SUBSET_TEMPLATE

    # Simple check of task name existence for template with {task} in
    #   - missing task should be possible only in Standalone publisher
    if not task_name and "{task" in template.lower():
        raise TaskNotSetError()

    fill_pairs = {
        "variant": variant,
        "family": family,
        "task": task_name
    }
    if dynamic_data:
        # Dynamic data may override default values
        for key, value in dynamic_data.items():
            fill_pairs[key] = value

    return template.format(**prepare_template_data(fill_pairs))


def get_subset_name(
    project_name,
    folder_id,
    task_name,
    host_name,
    family,
    variant,
    dynamic_data=None,
    project_settings=None,
    default_template=None
):
    """Calculate subset name using OpenPype settings.

    This variant of function expects asset id as argument.

    This is legacy function should be replaced with
    `get_subset_name_with_data` where asset document is expected.
    """

    if not project_settings:
        project_settings = get_project_settings(project_name)

    if task_name:
        task_entity = get_task(project_name, folder_id, task_name)
    else:
        task_entity = {}

    return get_subset_name_with_task_entity(
        family,
        variant,
        task_entity,
        host_name,
        project_settings,
        dynamic_data,
        default_template
    )


def prepare_template_data(fill_pairs):
    """Prepares formatted data for filling template.

    It produces multiple variants of keys (key, Key, KEY) to control
    format of filled template.

    Args:
        fill_pairs (iterable) of tuples (key, value)
    Returns:
        (dict)
        ('host', 'maya') > {'host':'maya', 'Host': 'Maya', 'HOST': 'MAYA'}
    """

    fill_data = {}
    regex = re.compile(r"[a-zA-Z0-9]")
    for key, value in dict(fill_pairs).items():
        # Handle cases when value is `None` (standalone publisher)
        if value is None:
            continue
        # Keep value as it is
        fill_data[key] = value
        # Both key and value are with upper case
        fill_data[key.upper()] = value.upper()

        # Capitalize only first char of value
        # - conditions are because of possible index errors
        # - regex is to skip symbols that are not chars or numbers
        #   - e.g. "{key}" which starts with curly bracket
        capitalized = ""
        for idx in range(len(value or "")):
            char = value[idx]
            if not regex.match(char):
                capitalized += char
            else:
                capitalized += char.upper()
                capitalized += value[idx + 1:]
                break

        fill_data[key.capitalize()] = capitalized

    return fill_data
