"""Tests of users, access groups, teams and project users endpoints.

Tests are running against a real AYON server and expect that the
connection is authorized as an admin user.

To run use: pytest --envfile {environment path}.
Make sure you have set AYON_SERVER_URL and AYON_API_KEY in your
environment.

All users, access groups and teams created by the tests have unique names
and are removed at the end of each test.

"""

import time
import uuid

import pytest

from ayon_api import (
    ServerAPI,
    get_base_url,
    get_user,
    create_user,
    update_user,
    delete_user,
    rename_user,
    change_password,
    set_user_access_groups,
    get_user_sessions,
    delete_user_session,
    get_user_api_keys,
    create_user_api_key,
    update_user_api_key,
    delete_user_api_key,
    get_user_permissions,
    get_access_groups,
    get_access_group_schema,
    get_access_group,
    save_access_group,
    delete_access_group,
    set_projects_access,
    get_teams,
    update_teams,
    save_team,
    delete_team,
    save_team_member,
    delete_team_member,
    get_project_users,
    set_project_user_access_groups,
)
from ayon_api.exceptions import AuthenticationError, HTTPRequestError

from .conftest import project_entity_fixture


def _unique_name(prefix):
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _new_password():
    # Admin is not affected by password complexity check, but use
    #   a strong password anyway
    return f"Ayon_{uuid.uuid4().hex}.9"


def _user_exists(user_name):
    try:
        return get_user(user_name) is not None
    except HTTPRequestError:
        return False


def _safe_delete_user(user_name):
    if _user_exists(user_name):
        delete_user(user_name)


@pytest.fixture
def temp_user():
    """Create a temporary non-manager user with a password.

    Yields:
        dict[str, str]: Mutable dictionary with 'name' and 'password'.
            Tests that rename the user must update the 'name' so
            the teardown removes the right user.

    """
    user_info = {
        "name": _unique_name("ayonapitest"),
        "password": _new_password(),
    }
    create_user(
        user_info["name"],
        password=user_info["password"],
        attrib={"fullName": "AYON API Test User"},
        data={"isAdmin": False, "isManager": False},
        active=True,
    )
    try:
        yield user_info
    finally:
        _safe_delete_user(user_info["name"])


@pytest.fixture
def temp_access_group():
    """Create a temporary studio level access group.

    Yields:
        str: Name of the access group.

    """
    access_group_name = _unique_name("ayonapitest_ag_")
    save_access_group(access_group_name, {"read": {"enabled": False}})
    try:
        yield access_group_name
    finally:
        studio_names = {
            access_group["name"]
            for access_group in get_access_groups()
        }
        if access_group_name in studio_names:
            delete_access_group(access_group_name)


def _login(user_name, password):
    """Login to server as a different user.

    Returns:
        ServerAPI: Connection authorized as the user.

    """
    con = ServerAPI(get_base_url())
    con.login(user_name, password)
    return con


def _get_team(project_name, team_name, show_members=True):
    for team in get_teams(project_name, show_members=show_members):
        if team["name"] == team_name:
            return team
    return None


def _safe_delete_team(project_name, team_name):
    if _get_team(project_name, team_name, show_members=False) is not None:
        delete_team(project_name, team_name)


# --- Users ---
def test_create_update_delete_user():
    """Create a user, update attributes and active state, then delete."""
    user_name = _unique_name("ayonapitest")
    create_user(
        user_name,
        password=_new_password(),
        attrib={"fullName": "Before Update"},
        active=True,
    )
    try:
        user = get_user(user_name)
        assert user["name"] == user_name
        assert user["attrib"]["fullName"] == "Before Update"
        assert user["active"] is True

        # Creating already existing user fails
        with pytest.raises(HTTPRequestError):
            create_user(user_name, password=_new_password())

        update_user(
            user_name,
            attrib={"fullName": "After Update"},
            active=False,
        )
        user = get_user(user_name)
        assert user["attrib"]["fullName"] == "After Update"
        assert user["active"] is False

        delete_user(user_name)
        assert not _user_exists(user_name)
    finally:
        _safe_delete_user(user_name)


def test_create_service_user_with_api_key():
    """Service users can be created with api key, and key can change.

    Service users must not have password.
    """
    user_name = _unique_name("ayonapitestsvc")
    create_user(
        user_name,
        api_key=uuid.uuid4().hex,
        data={"isService": True},
    )
    try:
        user = get_user(user_name)
        assert user["name"] == user_name
        assert user["data"].get("isService") is True

        change_password(user_name, api_key=uuid.uuid4().hex)

        # Password can't be set on service user on creation
        invalid_name = _unique_name("ayonapitestsvc")
        try:
            with pytest.raises(HTTPRequestError):
                create_user(
                    invalid_name,
                    password=_new_password(),
                    data={"isService": True},
                )
        finally:
            _safe_delete_user(invalid_name)
    finally:
        _safe_delete_user(user_name)


def test_rename_user(temp_user):
    """Rename user and validate the old name does not exist anymore."""
    old_name = temp_user["name"]
    new_name = _unique_name("ayonapitestrenamed")
    rename_user(old_name, new_name)
    # Make sure the fixture deletes the renamed user
    temp_user["name"] = new_name

    assert not _user_exists(old_name)
    user = get_user(new_name)
    assert user["name"] == new_name
    assert user["attrib"]["fullName"] == "AYON API Test User"


def test_change_password(temp_user):
    """Change password and validate login works only with the new one."""
    user_name = temp_user["name"]
    new_password = _new_password()

    with pytest.raises(ValueError):
        change_password(user_name)

    change_password(user_name, password=new_password)
    temp_user["password"] = new_password

    con = _login(user_name, new_password)
    try:
        assert con.get_user()["name"] == user_name
    finally:
        con.logout()

    with pytest.raises(AuthenticationError):
        _login(user_name, "invalid_" + new_password)


def test_set_user_access_groups(
    project_entity_fixture, temp_user, temp_access_group
):
    """Set and remove access groups of a user on a project."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]

    set_user_access_groups(
        user_name, {project_name: [temp_access_group]}
    )
    user = get_user(user_name)
    assert user["data"]["accessGroups"][project_name] == [
        temp_access_group
    ]
    assert get_project_users(project_name)[user_name] == [
        temp_access_group
    ]

    # Empty list removes access to the project
    set_user_access_groups(user_name, {project_name: []})
    user = get_user(user_name)
    assert project_name not in user["data"].get("accessGroups", {})
    assert user_name not in get_project_users(project_name)


def test_user_sessions(temp_user):
    """Login as temp user, list its sessions and delete the session."""
    user_name = temp_user["name"]
    con = _login(user_name, temp_user["password"])
    try:
        token = con.access_token
        sessions = get_user_sessions(user_name)
        assert isinstance(sessions, list)
        sessions_by_token = {
            session["token"]: session
            for session in sessions
        }
        assert token in sessions_by_token
        session = sessions_by_token[token]
        assert session["isService"] is False
        assert isinstance(session["lastUsed"], (int, float))

        delete_user_session(user_name, token)
        tokens = {
            session["token"]
            for session in get_user_sessions(user_name)
        }
        assert token not in tokens

        # Deleting not existing session fails
        with pytest.raises(HTTPRequestError):
            delete_user_session(user_name, token)
    finally:
        # Session was already removed on server, avoid logout request
        con.logout(soft=True)


@pytest.fixture
def temp_user_with_api_keys():
    """Create a temporary user with initialized 'apiKeys' in data.

    Server (1.16.8) api key endpoints fail with 500 if user does not have
        'apiKeys' set in data, because 'data->'apiKeys'' is NULL and is
        iterated. The key is pre-filled on creation to work around it.

    Yields:
        str: Name of the user.

    """
    user_name = _unique_name("ayonapitest")
    create_user(
        user_name,
        password=_new_password(),
        data={"apiKeys": []},
    )
    try:
        yield user_name
    finally:
        _safe_delete_user(user_name)


def test_user_api_keys(temp_user_with_api_keys):
    """Create, list, update and delete api key of a user."""
    user_name = temp_user_with_api_keys
    assert get_user_api_keys(user_name) == []

    key = uuid.uuid4().hex
    label = _unique_name("label_")
    expires = time.time() + 3600
    create_user_api_key(user_name, label, key, expires=expires)

    api_keys = get_user_api_keys(user_name)
    assert len(api_keys) == 1
    api_key = api_keys[0]
    assert api_key["label"] == label
    assert api_key["expires"] == pytest.approx(expires)
    assert api_key["preview"] == f"{key[:4]}*****{key[-4:]}"
    assert isinstance(api_key["created"], (int, float))
    api_key_id = api_key["id"]

    # Label must be unique
    with pytest.raises(HTTPRequestError):
        create_user_api_key(user_name, label, uuid.uuid4().hex)

    new_label = _unique_name("label_")
    new_expires = expires + 3600
    update_user_api_key(
        user_name, api_key_id, label=new_label, expires=new_expires
    )
    api_key = get_user_api_keys(user_name)[0]
    assert api_key["id"] == api_key_id
    assert api_key["label"] == new_label
    assert api_key["expires"] == pytest.approx(new_expires)

    # Update only label, expiration stays unchanged
    update_user_api_key(user_name, api_key_id, label=label)
    api_key = get_user_api_keys(user_name)[0]
    assert api_key["label"] == label
    assert api_key["expires"] == pytest.approx(new_expires)

    delete_user_api_key(user_name, api_key_id)
    assert get_user_api_keys(user_name) == []


def test_get_user_permissions(
    project_entity_fixture, temp_user, temp_access_group
):
    """Get permissions of current user and of other user."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]

    my_permissions = get_user_permissions()
    assert my_permissions["user_level"] in ("admin", "manager")

    my_project_permissions = get_user_permissions(
        project_name=project_name
    )
    assert "read" in my_project_permissions
    assert "project" in my_project_permissions

    studio_permissions = get_user_permissions(user_name)
    assert "studio" in studio_permissions

    # User without access to the project can't have project permissions
    with pytest.raises(HTTPRequestError):
        get_user_permissions(user_name, project_name)

    set_user_access_groups(
        user_name, {project_name: [temp_access_group]}
    )
    try:
        project_permissions = get_user_permissions(user_name, project_name)
        assert "read" in project_permissions
    finally:
        set_user_access_groups(user_name, {project_name: []})


# --- Access groups ---
def test_access_group_schema(project_entity_fixture):
    """Access group schema is a settings schema with properties."""
    schema = get_access_group_schema()
    assert isinstance(schema, dict)
    assert "read" in schema["properties"]

    project_schema = get_access_group_schema(
        project_entity_fixture["name"]
    )
    assert "read" in project_schema["properties"]


def test_studio_access_group():
    """Create, update, read and delete studio level access group."""
    access_group_name = _unique_name("ayonapitest_ag_")
    save_access_group(access_group_name, {"read": {"enabled": True}})
    try:
        access_groups = {
            access_group["name"]: access_group
            for access_group in get_access_groups()
        }
        assert access_group_name in access_groups
        assert access_groups[access_group_name]["isProjectLevel"] is False

        access_group = get_access_group(access_group_name)
        assert access_group["read"]["enabled"] is True

        # Save existing access group updates it
        save_access_group(access_group_name, {"read": {"enabled": False}})
        access_group = get_access_group(access_group_name)
        assert access_group["read"]["enabled"] is False

        delete_access_group(access_group_name)
        names = {
            access_group["name"]
            for access_group in get_access_groups()
        }
        assert access_group_name not in names
        with pytest.raises(HTTPRequestError):
            get_access_group(access_group_name)
    finally:
        names = {
            access_group["name"]
            for access_group in get_access_groups()
        }
        if access_group_name in names:
            delete_access_group(access_group_name)


def test_project_access_group(project_entity_fixture, temp_access_group):
    """Project level override of a studio access group."""
    project_name = project_entity_fixture["name"]

    access_groups = {
        access_group["name"]: access_group
        for access_group in get_access_groups(project_name)
    }
    assert access_groups[temp_access_group]["isProjectLevel"] is False

    save_access_group(
        temp_access_group,
        {"read": {"enabled": True}},
        project_name=project_name,
    )
    try:
        access_groups = {
            access_group["name"]: access_group
            for access_group in get_access_groups(project_name)
        }
        assert access_groups[temp_access_group]["isProjectLevel"] is True

        project_group = get_access_group(temp_access_group, project_name)
        assert project_group["read"]["enabled"] is True
        # Studio access group is not affected
        studio_group = get_access_group(temp_access_group)
        assert studio_group["read"]["enabled"] is False
    finally:
        delete_access_group(temp_access_group, project_name)

    access_groups = {
        access_group["name"]: access_group
        for access_group in get_access_groups(project_name)
    }
    assert access_groups[temp_access_group]["isProjectLevel"] is False
    # Project access group falls back to studio data
    project_group = get_access_group(temp_access_group, project_name)
    assert project_group["read"]["enabled"] is False

    # Studio access group still exists
    assert temp_access_group in {
        access_group["name"]
        for access_group in get_access_groups()
    }


def test_set_projects_access(
    project_entity_fixture, temp_user, temp_access_group
):
    """Set and revoke project access of a user in bulk."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]

    set_projects_access({user_name: {project_name: [temp_access_group]}})
    try:
        assert get_project_users(project_name)[user_name] == [
            temp_access_group
        ]
        user = get_user(user_name)
        assert user["data"]["accessGroups"][project_name] == [
            temp_access_group
        ]
    finally:
        set_projects_access({user_name: {project_name: []}})

    assert user_name not in get_project_users(project_name)


# --- Project users ---
def test_project_users(
    project_entity_fixture, temp_user, temp_access_group
):
    """Set access groups of a user on a project via project endpoint."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]

    project_users = get_project_users(project_name)
    assert isinstance(project_users, dict)
    assert user_name not in project_users

    result = set_project_user_access_groups(
        project_name, user_name, [temp_access_group]
    )
    try:
        assert result[user_name] == [temp_access_group]
        assert get_project_users(project_name) == result
    finally:
        result = set_project_user_access_groups(
            project_name, user_name, []
        )
    assert user_name not in result
    assert user_name not in get_project_users(project_name)


# --- Teams ---
def test_teams(project_entity_fixture, temp_user):
    """Create team, modify its members and delete it."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]
    team_name = _unique_name("team_")

    try:
        save_team(
            project_name,
            team_name,
            [{"name": user_name, "leader": True, "roles": ["lead"]}],
        )
        team = _get_team(project_name, team_name)
        assert team is not None
        assert team["memberCount"] == 1
        assert team["members"] == [
            {"name": user_name, "leader": True, "roles": ["lead"]}
        ]
        assert [leader["name"] for leader in team["leaders"]] == [
            user_name
        ]

        # Members are not returned without 'show_members'
        team = _get_team(project_name, team_name, show_members=False)
        assert team.get("members") is None
        assert team["memberCount"] == 1

        # Replace member
        save_team_member(
            project_name,
            team_name,
            user_name,
            leader=False,
            roles=["artist", "compositor"],
        )
        team = _get_team(project_name, team_name)
        assert team["memberCount"] == 1
        assert team["members"] == [
            {
                "name": user_name,
                "leader": False,
                "roles": ["artist", "compositor"],
            }
        ]
        assert team["leaders"] == []

        delete_team_member(project_name, team_name, user_name)
        team = _get_team(project_name, team_name)
        assert team["memberCount"] == 0
        assert team["members"] == []

        # Saving member to not existing team fails
        with pytest.raises(HTTPRequestError):
            save_team_member(
                project_name, _unique_name("team_"), user_name
            )

        delete_team(project_name, team_name)
        assert _get_team(project_name, team_name) is None
    finally:
        _safe_delete_team(project_name, team_name)


def test_update_teams(project_entity_fixture, temp_user):
    """Create and replace multiple teams at once."""
    project_name = project_entity_fixture["name"]
    user_name = temp_user["name"]
    team_names = [_unique_name("team_"), _unique_name("team_")]

    try:
        update_teams(
            project_name,
            [
                {"name": team_names[0], "members": []},
                {
                    "name": team_names[1],
                    "members": [
                        {"name": user_name, "leader": False, "roles": []}
                    ],
                },
            ],
        )
        teams_by_name = {
            team["name"]: team
            for team in get_teams(project_name, show_members=True)
        }
        assert teams_by_name[team_names[0]]["memberCount"] == 0
        assert teams_by_name[team_names[1]]["memberCount"] == 1

        # Replace only first team, second must stay unchanged
        update_teams(
            project_name,
            [
                {
                    "name": team_names[0],
                    "members": [
                        {"name": user_name, "leader": True, "roles": []}
                    ],
                },
            ],
        )
        teams_by_name = {
            team["name"]: team
            for team in get_teams(project_name, show_members=True)
        }
        first_team = teams_by_name[team_names[0]]
        assert first_team["memberCount"] == 1
        assert first_team["members"][0]["leader"] is True
        assert teams_by_name[team_names[1]]["memberCount"] == 1
    finally:
        for team_name in team_names:
            _safe_delete_team(project_name, team_name)

    names = {team["name"] for team in get_teams(project_name)}
    assert not names & set(team_names)
