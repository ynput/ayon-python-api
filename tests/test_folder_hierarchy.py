import pytest
import os
from dotenv import load_dotenv

"""
from tests.my_helper_functions import (
    my_get_folder_ids,
    my_get_product_ids,
    my_get_version_ids,
    my_get_representation_ids,
    my_delete_folder,
    
    manual_delete_hierarchy
)
from tests.my_helper_functions import (
    manual_delete_hierarchy
)
"""
from ayon_api.operations import (
    OperationsSession,
    new_folder_entity,
    new_product_entity,
    new_version_entity,
    new_representation_entity
)
from ayon_api import (
    get_versions,
    get_folder_by_id,
    get_product_by_id,
    get_folders,
    get_products,
    get_representations,
    get_folder_by_name
)
from ayon_api.exceptions import (
    FailedOperations
)


PROJECT_NAME = os.getenv("AYON_PROJECT_NAME")


# ---------------------------------------------------

def recursive_delete_hierarchy(folder_id, s):
    # recursively delete all subfolders
    subfolder_ids = my_get_folder_ids(folder_id)
    for subfolder_id in subfolder_ids:
        recursive_delete_hierarchy(subfolder_id, s)

    # delete subsets
    subset_ids = my_get_subset_ids([folder_id])
    for subset_id in subset_ids:
        s.delete_entity(PROJECT_NAME, "subset", subset_id)
    s.commit()

    # delete folder
    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()


def manual_delete_hierarchy(folder_name, s=None):
    if s is None:
        s = OperationsSession()

    folder_id = str()
    subset_ids = []
    try:
        folder_id = get_folder_by_name(PROJECT_NAME, folder_name)["id"]
    except TypeError as exc:
        print(exc)
    else:
        recursive_delete_hierarchy(folder_id, s)

# ---------------------------------------------------


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
        assert list(get_folders(
            PROJECT_NAME, 
            folder_ids=[folder["id"]])) == []


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

    assert list(get_folders(
            PROJECT_NAME, 
            folder_ids=[folder_id])) != []

    with pytest.raises(FailedOperations):
        folder = new_folder_entity(folder_name, "Folder")
        tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
        s.commit()
        assert list(get_folders(
            PROJECT_NAME, 
            folder_ids=[tmp_id])) == []

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name, product_names",
    [
        ("product_duplicated_names", ["modelMain", "modelProxy", "modelSculpt"]),
    ]
)
def test_product_duplicated_names(
    folder_name,
    product_names
    ):
    """Tries to create products with duplicated 
    names and checks if exception was raised.
    Checks if the product was really created after commit.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
    s.commit()

    product_ids = []
    for name in product_names:
        product = new_product_entity(name, "model", folder_id)
        product_id = s.create_entity(PROJECT_NAME, "product", product)["id"]   
        s.commit()

        assert list(get_folders(
            PROJECT_NAME, 
            folder_ids=[product_id],
            parent_ids=[folder_id])) != []

        product_ids.append(product_id)

    for name in product_names:
        with pytest.raises(FailedOperations):
            product = new_product_entity(name, "model", folder_id)
            tmp_id = s.create_entity(PROJECT_NAME, "product", product)    
            s.commit()
            assert list(get_folders(
                PROJECT_NAME, 
                folder_ids=tmp_id,
                parent_ids=folder_id)) != []

    for product_id in product_ids:
        s.delete_entity(PROJECT_NAME, "product", product_id)
        s.commit()
        assert get_product_by_id(PROJECT_NAME, product_id) is None

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()
    assert get_folder_by_id(PROJECT_NAME, folder_id) is None


@pytest.mark.parametrize(
    "folder_name, product_name, version_name, representation_name, num_of_versions, num_of_representations",
    [
        ("whole_hierarchy", "modelMain", "version", "representation", 2, 3)
    ]
)
def test_whole_hierarchy(
    folder_name, 
    product_name, 
    version_name, 
    representation_name,
    num_of_versions,
    num_of_representations
):
    """Creates the whole hierarchy (folder, product, version, representation).
    Tries to create versions and representations with duplicated 
    names and checks if exceptions are raised.
    """

    s = OperationsSession()

    # create folder
    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]   
    s.commit()

    assert list(get_folders(
        PROJECT_NAME, 
        folder_ids=[folder_id])) != []

    # create product
    product = new_product_entity(product_name, "model", folder_id)
    product_id = s.create_entity(PROJECT_NAME, "product", product)["id"]   
    s.commit()

    assert list(get_products(
        PROJECT_NAME, 
        product_ids=[product_id],
        folder_ids=[folder_id])) != []

    # create versions
    my_version_ids = []
    for i in range(num_of_versions):
        version = new_version_entity(i, product_id)
        version_id = s.create_entity(PROJECT_NAME, "version", version)["id"]   
        s.commit()

        assert list(get_versions(
                PROJECT_NAME, 
                version_ids=version_id,
                product_ids=product_id)) != []

        my_version_ids.append(version_id)        

        # test duplicate name
        with pytest.raises(FailedOperations):
            version = new_version_entity(i, product_id)
            tmp_id = s.create_entity(PROJECT_NAME, "version", version)["id"]  
            s.commit()
            assert list(get_versions(
                PROJECT_NAME, 
                version_ids=tmp_id,
                product_ids=product_id)) == []

    # create representations
    for i, version_id in enumerate(my_version_ids):
        for j in range(num_of_representations):
            unique_name = str(i) + "v" + str(j)  # unique in this version
            representation = new_representation_entity(unique_name, version_id)
            representation_id = s.create_entity(PROJECT_NAME, "representation", representation)["id"]
            s.commit()

            assert list(get_representations(
                PROJECT_NAME, 
                representation_ids=[representation_id],
                version_ids=[version_id])) != []

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

                assert list(get_representations(
                    PROJECT_NAME, 
                    representation_ids=[representation_id],
                    version_ids=[my_version_ids])) != []

    s.delete_entity(PROJECT_NAME, "product", product_id)
    s.commit()

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()


@pytest.mark.parametrize(
    "folder_name, product_name",
    [
        ("test_folder_with_product001", "modelMain"),
    ]
)
def test_delete_folder_with_product(
    folder_name,
    product_name
    ):
    """Creates product in folder and tries to delete the folder.
    Checks if exception was raised.
    """

    s = OperationsSession()

    folder = new_folder_entity(folder_name, "Folder")
    folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]   
    s.commit()

    assert list(get_folders(
        PROJECT_NAME, 
        folder_ids=[folder_id])) != []

    product = new_product_entity(product_name, "model", folder_id)
    product_id = s.create_entity(PROJECT_NAME, "product", product)["id"]  
    s.commit()

    assert list(get_products(
        PROJECT_NAME,
        product_ids=[product_id],
        folder_ids=[folder_id])) != []

    with pytest.raises(FailedOperations):
        s.delete_entity(PROJECT_NAME, "folder", folder_id)
        s.commit()

    assert list(get_folders(
        PROJECT_NAME,
        folder_ids=[folder_id])) != []

    s.delete_entity(PROJECT_NAME, "product", product_id)
    s.commit()

    assert list(get_products(
        PROJECT_NAME,
        product_ids=[product_id],
        folder_ids=[folder_id])) == []

    s.delete_entity(PROJECT_NAME, "folder", folder_id)
    s.commit()

    assert list(get_folders(
        PROJECT_NAME, 
        folder_ids=[folder_id])) == []


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
    """Creates three levels of folder hierarchy and product in the last one. 
    Tries creating entities with duplicated names and checks raising exceptions.
    After creation of every entity is checked if the entity was really created.
    """

    s = OperationsSession()

    # create parent folder
    folder = new_folder_entity(folder_name, "Folder")
    parent_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]   
    s.commit()

    folder_with_product = []
    for i in range(count_level1):
        folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Folder", parent_id=parent_id)
        folder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
        s.commit()

        assert list(get_folders(
            PROJECT_NAME, 
            folder_ids=[folder_id],
            parent_ids=[parent_id])) != []

        # subfolder with same name
        with pytest.raises(FailedOperations):
            folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Folder", parent_id=parent_id)
            tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
            s.commit()
            assert list(get_folders(
                PROJECT_NAME, 
                folder_ids=[folder_id],
                parent_ids=[parent_id])) == []
        
        # subfolder with same name but different type
        with pytest.raises(FailedOperations):
            folder = new_folder_entity(f"{subfolder_name1}{i:03}", "Shot", parent_id=parent_id)
            tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
            s.commit()
            assert list(get_folders(
                PROJECT_NAME, 
                folder_ids=[folder_id],
                parent_ids=[parent_id])) == []

        for j in range(count_level2):
            folder = new_folder_entity(f"{subfolder_name2}{j:03}", "Shot", parent_id=folder_id)
            subfolder_id = s.create_entity(PROJECT_NAME, "folder", folder)["id"]
            s.commit()
            folder_with_product.append(f"{subfolder_name2}{j:03}")

            assert list(get_folders(
                PROJECT_NAME, 
                folder_ids=[subfolder_id],
                parent_ids=[folder_id])) != []

            # subfolder with same name
            with pytest.raises(FailedOperations):
                folder = new_folder_entity(f"{subfolder_name2}{j:03}", "Shot", parent_id=folder_id)
                tmp_id = s.create_entity(PROJECT_NAME, "folder", folder)
                s.commit()
                assert list(get_folders(
                    PROJECT_NAME, 
                    folder_ids=[tmp_id],
                    parent_ids=[folder_id])) == []

            # products in subfolder
            product = new_product_entity("modelMain", "model", subfolder_id)
            product_id = s.create_entity(PROJECT_NAME, "product", product)["id"]   
            s.commit()

            assert list(get_products(
                PROJECT_NAME, 
                product_ids=[product_id],
                folder_ids=[subfolder_id])) != []

            product = new_product_entity("modelProxy", "model", subfolder_id)
            product_id = s.create_entity(PROJECT_NAME, "product", product)["id"]   
            s.commit()

            assert list(get_products(
                PROJECT_NAME, 
                product_ids=[product_id],
                folder_ids=[subfolder_id])) != []

            # delete folders with products
            with pytest.raises(FailedOperations):
                s.delete_entity(PROJECT_NAME, "folder", parent_id)
                s.commit()

                assert parent_id in my_get_folder_ids()

            for f_id in folder_with_product:
                with pytest.raises(FailedOperations):
                    s.delete_entity(PROJECT_NAME, "folder", f_id)
                    s.commit()
                    assert f_id in my_get_folder_ids(parent_id)
    
    # delete everything correctly
    for folder_to_del in folder_with_product:
        manual_delete_hierarchy(folder_to_del, s)
    
    s.delete_entity(PROJECT_NAME, "folder", parent_id)
    s.commit()


@pytest.mark.parametrize(
    "folder_name",
    [
        ("folder_with_subfolders1"),
        ("folder_with_subfolders2"),
        ("operations_with_folder1"),
        ("operations_with_folder2"),
        ("operations_with_folder3"),
        ("test_folder_with_product001"),
        ("whole_hierarchy")
    ]
)
def test_my_delete_func(folder_name):
    manual_delete_hierarchy(folder_name)
