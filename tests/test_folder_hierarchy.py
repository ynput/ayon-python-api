import pytest
import os
from dotenv import load_dotenv
from tests.my_helper_functions import (
    my_get_folder_ids,
    my_get_subset_ids,
    my_get_version_ids,
    my_get_representation_ids,
    my_delete_folder,
    manual_delete_hierarchy
)
from ayon_api.operations import (
    OperationsSession,
    new_folder_entity,
    new_subset_entity,
    new_version_entity,
    new_representation_entity
)
from ayon_api import (
    get_versions,
    get_folder_by_id,
    get_subset_by_id,
    get_folders,
    get_subsets,
)
from ayon_api.exceptions import (
    FailedOperations
)


PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


@pytest.mark.parametrize(
    "folder_name",
    [
        ("operations_with_folder1"),
        ("operations_with_folder2"),
        ("operations_with_folder3")
    ]
)
def test_operations_with_folder(folder_name):
    """Updates folder entity.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
    s.commit()

    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    s.update_entity(
        PROJECT_NAME,
        "folder",
        folder_entity["id"],
        {"attrib": {"frameStart": 1002}}
    )
    s.commit()

    folder_entity = get_folder_by_id(PROJECT_NAME, folder_id)
    assert folder_entity["attrib"]["frameStart"] == 1002

    my_delete_folder(s, PROJECT_NAME, folder_entity["id"])
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name",
    [
        ("!invalid"),
        ("in/valid"),
        ("in~valid")
    ]
)
def test_folder_name_invalid_characters(folder_name):
    """Tries to create folders with invalid
    names and checks if exception was raised.
    """

    s = OperationsSession()

    with pytest.raises(FailedOperations):
        folder = new_folder_entity(folder_name, "Folder")
        tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
        s.commit()
        assert tmp_id not in my_get_folder_ids()


@pytest.mark.parametrize(
    "folder_name",
    [
        ("folder_duplicated_names"),
    ]
)
def test_folder_duplicated_names(folder_name):
    """Tries to create folders with duplicated 
    names and checks if exception was raised.
    Checks if the folder was really created after commit.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
    s.commit()

    assert folder_id in my_get_folder_ids()

    with pytest.raises(FailedOperations):
        folder = new_folder_entity(folder_name, "Folder")
        tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
        s.commit()
        assert tmp_id not in my_get_folder_ids()

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name, subset_names",
    [
        ("subset_duplicated_names", ["modelMain", "modelProxy", "modelSculpt"]),
    ]
)
def test_subset_duplicated_names(
    folder_name,
    subset_names
    ):
    """Tries to create subsets with duplicated 
    names and checks if exception was raised.
    Checks if the subset was really created after commit.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
    s.commit()

    subset_ids = []
    for name in subset_names:
        subset = new_subset_entity(name, "model", folder_id)
        subset_id = s.create_entity(PROJECT_NAME, "subset", subset)["id"]   
        s.commit()

        assert subset_id in my_get_subset_ids([folder_id])
        subset_ids.append(subset_id)

    for name in subset_names:
        with pytest.raises(FailedOperations):
            subset = new_subset_entity(name, "model", folder_id)
            tmp_id = s.create_entity(PROJECT_NAME, "subset", subset)    
            s.commit()
            assert tmp_id not in my_get_subset_ids([folder_id])


    for subset_id in subset_ids:
        s.delete_entity(PROJECT_NAME, "subset", subset_id)
        s.commit()
        assert get_subset_by_id(PROJECT_NAME, subset_id) is None

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name, subset_name, version_name, representation_name, num_of_versions, num_of_representations",
    [
        ("whole_hierarchy", "modelMain", "version", "representation", 2, 3)
    ]
)
def test_whole_hierarchy(
    folder_name, 
    subset_name, 
    version_name, 
    representation_name,
    num_of_versions,
    num_of_representations
):
    """Creates the whole hierarchy (folder, subset, version, representation).
    Tries to create versions and representations with duplicated 
    names and checks if exceptions are raised.
    """

    s = OperationsSession()

    # create folder
    folder = new_folder_entity(folder_name, "Folder")
    op = s.create_entity(PROJECT_NAME, "folder", folder)    
    folder_id = op.entity_id
    s.commit()

    assert folder_id in my_get_folder_ids()

    # create subset
    subset = new_subset_entity(subset_name, "model", folder_id)
    op = s.create_entity(PROJECT_NAME, "subset", subset)    
    subset_id = op.entity_id
    s.commit()

    assert subset_id in my_get_subset_ids(folder_id)

    # create versions
    my_version_ids = []
    for i in range(num_of_versions):
        version = new_version_entity(i, subset_id)
        version_id = s.create_entity(PROJECT_NAME, "version", version)["id"]   
        s.commit()

        my_version_ids.append(version_id)        

        # test duplicate name
        with pytest.raises(FailedOperations):
            version = new_version_entity(i, subset_id)
            op = s.create_entity(PROJECT_NAME, "version", version)   
            s.commit()
            assert tmp_id not in my_get_version_ids(subset_id)

        
        # check if everything is created
        s_version_ids = my_get_version_ids(subset_id)
        assert len(my_version_ids) == len(s_version_ids)
        assert version_id in s_version_ids

    # create representations
    for i, version_id in enumerate(my_version_ids):
        for j in range(num_of_representations):
            unique_name = str(i) + "v" + str(j)  # unique in this version
            representation = new_representation_entity(unique_name, version_id)
            representation_id = s.create_entity(PROJECT_NAME, "representation", representation)["id"]
            s.commit()

            assert representation_id in my_get_representation_ids([version_id])
            
            # doesn't raise an exception
            """
            # not unique under this version
            with pytest.raises(FailedOperations):
                representation = new_representation_entity(unique_name, version_id)
                tmp_id = s.create_entity(PROJECT_NAME, "representation", representation)["id"] 
                s.commit()
                assert tmp_id not in my_get_representation_ids(version_id)
            """

            # under different version will be created
            if i > 0:
                representation = new_representation_entity(unique_name, my_version_ids[i-1])
                representation_id = s.create_entity(PROJECT_NAME, "representation", representation)["id"]
                s.commit()

                assert representation_id in my_get_representation_ids(my_version_ids)

    s.delete_entity(PROJECT_NAME, "subset", subset_id)
    s.commit()

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()


@pytest.mark.parametrize(
    "folder_name, subset_name",
    [
        ("test_folder_with_subset001", "modelMain"),
    ]
)
def test_delete_folder_with_subset(
    folder_name,
    subset_name
    ):
    """Creates subset in folder and tries to delete the folder.
    Checks if exception was raised.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]   
    s.commit()

    assert folder_id in my_get_folder_ids()

    subset = new_subset_entity(subset_name, "model", folder_id)
    subset_id = s.create_entity(PROJECT_NAME, "subset", subset)["id"]  
    s.commit()

    assert subset_id in my_get_subset_ids([folder_id])

    with pytest.raises(FailedOperations):
        s.delete_entity(PROJECT_NAME, "folder", folder_id)
        s.commit()
        assert folder_id in my_get_folder_ids()

    
    s.delete_entity(PROJECT_NAME, "subset", subset_id)
    s.commit()

    assert subset_id not in my_get_subset_ids([folder_id])

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()

    assert folder_id not in my_get_folder_ids()


@pytest.mark.parametrize(
    "folder_name, subfolder_name1, subfolder_name2, count_level1, count_level2",
    [
        ("folder_with_subfolders1", "subfolder", "shot", 2, 3),
        ("folder_with_subfolders2", "subfolder", "shot", 2, 3),
    ]
)
def test_subfolder_hierarchy(
    folder_name,
    subfolder_name1, 
    subfolder_name2, 
    count_level1, 
    count_level2
    ):
    """Creates three levels of folder hierarchy and subset in the last one. 
    Tries creating entities with duplicated names and checks raising exceptions.
    After creation of every entity is checked if the entity was really created.
    """

    s = OperationsSession()

    # create parent folder
    folder = new_folder_entity(folder_name, "Folder")
    parent_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]   
    s.commit()

    folder_with_subset = []
    for i in range(count_level1):
        folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Folder", parent_id=parent_id)
        folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
        s.commit()

        assert folder_id in my_get_folder_ids(parent_id)

        # subfolder with same name
        with pytest.raises(FailedOperations):
            folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Folder", parent_id=parent_id)
            tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
            s.commit()
            assert tmp_id not in my_get_folder_ids(parent_id)
        
        # subfolder with same name but different type
        with pytest.raises(FailedOperations):
            folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Shot", parent_id=parent_id)
            tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
            s.commit()
            assert tmp_id not in my_get_folder_ids(parent_id)

        for j in range(count_level2):
            folder = new_folder_entity(f"{subfolder_name2}{j:03}", "Shot", parent_id=folder_id)
            subfolder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
            s.commit()
            folder_with_subset.append(f"{subfolder_name2}{j:03}")

            assert subfolder_id in my_get_folder_ids(folder_id)

            # subfolder with same name
            with pytest.raises(FailedOperations):
                folder = new_folder_entity(f"{subfolder_name2}{j:03}", "Shot", parent_id=folder_id)
                tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
                s.commit()
                assert tmp_id not in my_get_folder_ids(folder_id)

            # subsets in subfolder
            subset = new_subset_entity("modelMain", "model", subfolder_id)
            subset_id = s.create_entity(PROJECT_NAME, "subset", subset)["id"]   
            s.commit()

            assert subset_id in my_get_subset_ids([subfolder_id])

            subset = new_subset_entity("modelProxy", "model", subfolder_id)
            subset_id = s.create_entity(PROJECT_NAME, "subset", subset)["id"]   
            s.commit()

            assert subset_id in my_get_subset_ids([subfolder_id])

            # delete folders with subsets
            with pytest.raises(FailedOperations):
                s.delete_entity(PROJECT_NAME, "folder", parent_id)
                s.commit()
                assert parent_id in my_get_folder_ids()

            for f_id in folder_with_subset:
                with pytest.raises(FailedOperations):
                    s.delete_entity(PROJECT_NAME, "folder", f_id)
                    s.commit()
                    assert f_id in my_get_folder_ids(parent_id)
    
    # delete everything correctly
    for folder_to_del in folder_with_subset:
        manual_delete_hierarchy(folder_to_del, s)
    
    s.delete_entity(PROJECT_NAME, "folder", parent_id)
    s.commit()

"""
@pytest.mark.parametrize(
    "folder_name",
    [
        ("folder_with_subfolders2"),
    ]
)
def test_my_delete_func(folder_name):
    manual_delete_hierarchy(folder_name)
"""