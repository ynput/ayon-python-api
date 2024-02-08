from ayon_api._api import (
    get_folders,
    get_subsets,
    get_versions,
    get_representations
)


PROJECT_NAME = "demo_Commercial"


def my_get_folder_ids():
    folders = list(
        get_folders(
            PROJECT_NAME
        )
    )

    return [folder["id"] for folder in folders]

def my_get_subset_ids(folder_ids):
    subsets = list(
        get_subsets(
            PROJECT_NAME,
            folder_ids=folder_ids
        )
    )

    return [subset["id"] for subset in subsets]


def my_get_version_ids(subset_id):
    versions = list(
        get_versions(
            PROJECT_NAME, 
            subset_ids=[subset_id]
        )
    )

    return [version["id"] for version in versions]


def my_get_representation_ids(my_version_ids):
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