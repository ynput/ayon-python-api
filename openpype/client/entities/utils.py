"""Unclear if these will have public functions like these.

Goal is that most of functions here are called on (or with) an object
that has project name as a context (e.g. on 'ProjectEntity'?).

+ We will need more specific functions doing wery specific queires really fast.
"""


def get_system_settings():
    pass


def get_project_settings(project_name):
    pass


def get_projects():
    pass


def get_folders(project_name):
    pass


def get_tasks(project_name, folder_ids=None):
    pass


def get_subsets(project_name, folder_ids=None):
    pass


def get_versions(project_name, folder_ids=None):
    pass


def get_latest_versions(project_name, subset_ids=None, folder_ids=None):
    pass


def get_latest_version(project_name, subset_id):
    pass


def get_subsets(project_name, folder_ids=None):
    pass
