"""Unclear if these will have public functions like these.

Goal is that most of functions here are called on (or with) an object
that has project name as a context (e.g. on 'ProjectEntity'?).

+ We will need more specific functions doing wery specific queires really fast.
"""


def get_projects(fields=None):
    pass


def get_project(project_name, fields=None):
    pass


def get_folder(project_name, folder_id, fields=None):
    pass


def get_folders(project_name, folder_ids=None, fields=None):
    pass


def get_tasks(project_name, folder_ids=None, fields=None):
    pass


def get_subsets(project_name, folder_ids=None, subset_ids=None, fields=None):
    pass


def get_version(project_name, version_id, fields=None):
    pass


def get_versions(project_name, version_ids=None, fields=None):
    pass


def get_latest_version(project_name, subset_id, fields=None):
    pass


def get_latest_versions(
    project_name, subset_ids=None, folder_ids=None, fields=None
):
    pass
