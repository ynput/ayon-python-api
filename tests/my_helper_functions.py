"""Functions that are often used in tests."""

import pytest
from ayon_api._api import (
    get_folders,
    get_subsets,
    get_versions,
    get_representations,
    get_folder_by_name
)
from ayon_api.operations import (
    OperationsSession
)


PROJECT_NAME = "demo_Commercial"


def my_get_folder_ids(parent = None):
    folders = list(
        get_folders(
            PROJECT_NAME,
            parent_ids=[parent]
        )
    )

    return [folder["id"] for folder in folders]

def my_get_subset_ids(folder_ids):
    if not isinstance(folder_ids, list):
        folder_ids = [folder_ids]

    subsets = list(
        get_subsets(
            PROJECT_NAME,
            folder_ids=folder_ids
        )
    )

    return [subset["id"] for subset in subsets]


def my_get_version_ids(subset_id):
    if not isinstance(subset_id, list):
        subset_ids = [subset_ids]

    versions = list(
        get_versions(
            PROJECT_NAME, 
            subset_ids=subset_ids
        )
    )

    return [version["id"] for version in versions]


def my_get_representation_ids(my_version_ids):
    if not isinstance(my_version_ids, list):
        my_version_ids = [my_version_ids]

    representations = list(
        get_representations(
            PROJECT_NAME, 
            version_ids=my_version_ids
        )
    )

    return [representation["id"] for representation in representations]

def my_delete_folder(s, name, id):
    s.delete_entity(name, "folder", id)
    s.commit()


def manual_delete_hierarchy(folder_name, s=None):
    if not s:
        s = OperationsSession()

    folder_id = str()
    subset_ids = []
    try:
        folder_id = get_folder_by_name(PROJECT_NAME, folder_name)["id"]
    except TypeError as exc:
        print(exc)
    else:
        subset_ids = my_get_subset_ids([folder_id])

        for subset_id in subset_ids:
            s.delete_entity(PROJECT_NAME, "subset", subset_id)
            s.commit()

        s.delete_entity(PROJECT_NAME, "folder", folder_id)
        s.commit()
