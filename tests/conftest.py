import pytest

from ayon_api import (
    get_project,
    create_project,
    update_project,
    delete_project,
)


class _Cache:
    # Cache project entity as scope 'session' of a fixture does not handle
    #   parametrized fixtures.
    project_entity = None


@pytest.fixture(scope="session")
def project_name_fixture():
    return "AYONApiTestProject"


@pytest.fixture(scope="session")
def project_entity_fixture(project_name_fixture):
    project_entity = _Cache.project_entity
    created = False
    if _Cache.project_entity is None:
        created = True
        project_entity = get_project(project_name_fixture)
        if project_entity:
            delete_project(project_name_fixture)
        create_project(project_name_fixture, "AYTP")
        update_project(
            project_name_fixture,
            folder_types=[
                {
                    "name": "Folder",
                    "icon": "folder",
                    "shortName": ""
                },
                {
                    "name": "Episode",
                    "icon": "live_tv",
                    "shortName": ""
                },
                {
                    "name": "Sequence",
                    "icon": "theaters",
                    "shortName": ""
                },
                {
                    "name": "Shot",
                    "icon": "movie",
                    "shortName": ""
                }
            ]
        )
        project_entity = get_project(project_name_fixture)
        _Cache.project_entity = project_entity

    yield project_entity
    if created:
        delete_project(project_name_fixture)
