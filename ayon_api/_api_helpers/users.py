from __future__ import annotations

from typing import Optional, Any

from ayon_api.utils import prepare_query_string

from .base import BaseServerAPI


class UsersAPI(BaseServerAPI):
    """Users, access groups, teams and project users REST endpoints."""

    # --- Users ---
    def create_user(
        self,
        user_name: str,
        *,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Create new user.

        User level and access is defined in 'data', e.g. 'isAdmin',
            'isManager', 'isService', 'isGuest', 'accessGroups'
            ({project_name: [access_group_name, ...]}) or
            'defaultAccessGroups' ([access_group_name, ...]).

        Args:
            user_name (str): Name of the user.
            password (Optional[str]): Password of the user. Service users
                cannot have password.
            api_key (Optional[str]): Api key for a service user.
            attrib (Optional[dict[str, Any]]): User attributes.
            data (Optional[dict[str, Any]]): User data.
            active (Optional[bool]): User active state.

        """
        body = {
            key: value
            for key, value in (
                ("password", password),
                ("apiKey", api_key),
                ("attrib", attrib),
                ("data", data),
                ("active", active),
            )
            if value is not None
        }
        response = self.put(f"users/{user_name}", **body)
        response.raise_for_status()

    def update_user(
        self,
        user_name: str,
        *,
        attrib: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Update user.

        Non-manager users can change only their own attributes.

        Args:
            user_name (str): Name of the user.
            attrib (Optional[dict[str, Any]]): User attributes to change.
            data (Optional[dict[str, Any]]): User data to change.
            active (Optional[bool]): User active state.

        """
        body = {
            key: value
            for key, value in (
                ("attrib", attrib),
                ("data", data),
                ("active", active),
            )
            if value is not None
        }
        response = self.patch(f"users/{user_name}", **body)
        response.raise_for_status()

    def delete_user(self, user_name: str) -> None:
        """Delete user.

        Args:
            user_name (str): Name of the user.

        """
        response = self.delete(f"users/{user_name}")
        response.raise_for_status()

    def rename_user(self, user_name: str, new_user_name: str) -> None:
        """Rename user.

        This is a manager-only operation. Target user name must not exist.

        Args:
            user_name (str): Current name of the user.
            new_user_name (str): New name of the user.

        """
        response = self.post(
            f"users/{user_name}/rename", name=new_user_name
        )
        response.raise_for_status()

    def change_password(
        self,
        user_name: str,
        *,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Change user password or service user api key.

        Only one of 'password' or 'api_key' should be passed. If both are
            passed the password is changed.

        Args:
            user_name (str): Name of the user.
            password (Optional[str]): New password.
            api_key (Optional[str]): New api key of a service user. Must be
                32 characters long hex string.

        """
        body = {}
        if password is not None:
            body["password"] = password
        if api_key is not None:
            body["apiKey"] = api_key
        if not body:
            raise ValueError("Password or api key must be passed.")
        response = self.patch(f"users/{user_name}/password", **body)
        response.raise_for_status()

    def set_user_access_groups(
        self,
        user_name: str,
        access_groups: dict[str, list[str]],
    ) -> None:
        """Set user access groups on projects.

        Projects that are not in 'access_groups' are not affected. Pass
            an empty list to remove access to a project.

        Args:
            user_name (str): Name of the user.
            access_groups (dict[str, list[str]]): Access groups by
                project name.

        """
        response = self.patch(
            f"users/{user_name}/accessGroups",
            accessGroups=[
                {"project": project_name, "accessGroups": list(groups)}
                for project_name, groups in access_groups.items()
            ],
        )
        response.raise_for_status()

    def get_user_sessions(self, user_name: str) -> list[dict[str, Any]]:
        """Get active sessions of user.

        Args:
            user_name (str): Name of the user.

        Returns:
            list[dict[str, Any]]: Sessions with 'token', 'isService',
                'lastUsed' and 'clientInfo' keys.

        """
        response = self.get(f"users/{user_name}/sessions")
        response.raise_for_status()
        return response.data["sessions"]

    def delete_user_session(self, user_name: str, session_id: str) -> None:
        """Delete user session (logout).

        Args:
            user_name (str): Name of the user.
            session_id (str): Session id (token).

        """
        response = self.delete(f"users/{user_name}/sessions/{session_id}")
        response.raise_for_status()

    def get_user_api_keys(self, user_name: str) -> list[dict[str, Any]]:
        """Get api keys of user.

        Args:
            user_name (str): Name of the user.

        Returns:
            list[dict[str, Any]]: Api keys with 'id', 'label', 'preview',
                'created' and 'expires' keys.

        """
        response = self.get(f"users/{user_name}/apikeys")
        response.raise_for_status()
        return response.data

    def create_user_api_key(
        self,
        user_name: str,
        label: str,
        key: str,
        *,
        expires: Optional[float] = None,
    ) -> None:
        """Create api key for user.

        Args:
            user_name (str): Name of the user.
            label (str): Label of the api key. Must be unique for the user.
            key (str): The api key value.
            expires (Optional[float]): Expiration timestamp.

        """
        response = self.post(
            f"users/{user_name}/apikeys",
            label=label,
            key=key,
            expires=expires,
        )
        response.raise_for_status()

    def update_user_api_key(
        self,
        user_name: str,
        api_key_id: str,
        *,
        label: Optional[str] = None,
        expires: Optional[float] = None,
    ) -> None:
        """Update api key of user.

        Args:
            user_name (str): Name of the user.
            api_key_id (str): Api key id.
            label (Optional[str]): New label of the api key.
            expires (Optional[float]): New expiration timestamp.

        """
        response = self.patch(
            f"users/{user_name}/apikeys/{api_key_id}",
            label=label,
            expires=expires,
        )
        response.raise_for_status()

    def delete_user_api_key(self, user_name: str, api_key_id: str) -> None:
        """Delete api key of user.

        Args:
            user_name (str): Name of the user.
            api_key_id (str): Api key id.

        """
        response = self.delete(f"users/{user_name}/apikeys/{api_key_id}")
        response.raise_for_status()

    def get_user_permissions(
        self,
        user_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get user permissions.

        Without 'user_name' are returned permissions of current user. For
            current user without 'project_name' is returned user level with
            studio and per-project permissions. Otherwise, are returned
            studio permissions, or project permissions if 'project_name'
            is passed.

        Args:
            user_name (Optional[str]): Name of the user. Current user is used
                if not passed.
            project_name (Optional[str]): Project name.

        Returns:
            dict[str, Any]: User permissions.

        """
        if user_name is None:
            user_name = "me"
        endpoint = f"users/{user_name}/permissions"
        if project_name:
            endpoint += f"/{project_name}"
        response = self.get(endpoint)
        response.raise_for_status()
        return response.data

    # --- Access groups ---
    def get_access_groups(
        self, project_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get access groups.

        Args:
            project_name (Optional[str]): Project name. Studio level access
                groups are returned if not passed.

        Returns:
            list[dict[str, Any]]: Access groups with 'name' and
                'isProjectLevel' keys.

        """
        response = self.get(f"accessGroups/{project_name or '_'}")
        response.raise_for_status()
        return response.data

    def get_access_group_schema(
        self, project_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Get access group (permissions) settings schema.

        Args:
            project_name (Optional[str]): Project name used as context.

        Returns:
            dict[str, Any]: Access group schema.

        """
        query = prepare_query_string({"project_name": project_name or None})
        response = self.get(f"accessGroups/_schema{query}")
        response.raise_for_status()
        return response.data

    def get_access_group(
        self,
        access_group_name: str,
        project_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get access group definition (permissions).

        Args:
            access_group_name (str): Access group name.
            project_name (Optional[str]): Project name. Studio level access
                group is returned if not passed.

        Returns:
            dict[str, Any]: Access group permissions.

        """
        response = self.get(
            f"accessGroups/{access_group_name}/{project_name or '_'}"
        )
        response.raise_for_status()
        return response.data

    def save_access_group(
        self,
        access_group_name: str,
        permissions: dict[str, Any],
        project_name: Optional[str] = None,
    ) -> None:
        """Create or update access group.

        Args:
            access_group_name (str): Access group name.
            permissions (dict[str, Any]): Access group permissions.
            project_name (Optional[str]): Project name. Studio level access
                group is saved if not passed.

        """
        response = self.put(
            f"accessGroups/{access_group_name}/{project_name or '_'}",
            **permissions,
        )
        response.raise_for_status()

    def delete_access_group(
        self,
        access_group_name: str,
        project_name: Optional[str] = None,
    ) -> None:
        """Delete access group.

        Args:
            access_group_name (str): Access group name.
            project_name (Optional[str]): Project name. Studio level access
                group is deleted if not passed.

        """
        response = self.delete(
            f"accessGroups/{access_group_name}/{project_name or '_'}"
        )
        response.raise_for_status()

    def set_projects_access(
        self, access: dict[str, dict[str, list[str]]]
    ) -> None:
        """Set access of multiple users to multiple projects.

        Projects not present in the payload are not affected. Pass an empty
            list to revoke access to a project.

        Example::

            {
                "alice": {
                    "MyProject01": ["editor"],
                    "MyProject02": ["artist"],
                },
                "bob": {
                    "MyProject01": ["artist", "reviewer"],
                    "MyProject02": [],
                },
            }

        Args:
            access (dict[str, dict[str, list[str]]]): Access groups by
                project name by user name.

        """
        response = self.raw_post("access", json=access)
        response.raise_for_status()

    # --- Teams ---
    def get_teams(
        self,
        project_name: str,
        *,
        show_members: bool = False,
    ) -> list[dict[str, Any]]:
        """Get teams in a project.

        Args:
            project_name (str): Project name.
            show_members (bool): Include team members in the response.

        Returns:
            list[dict[str, Any]]: Teams with 'name', 'memberCount',
                'leaders' and optionally 'members' keys.

        """
        query = prepare_query_string(
            {"show_members": "true" if show_members else None}
        )
        response = self.get(f"projects/{project_name}/teams{query}")
        response.raise_for_status()
        return response.data

    def update_teams(
        self,
        project_name: str,
        teams: list[dict[str, Any]],
    ) -> None:
        """Create or replace multiple teams in a project.

        Teams that are not in 'teams' are not affected.

        Args:
            project_name (str): Project name.
            teams (list[dict[str, Any]]): Teams with 'name' and 'members'
                keys. Member is a dictionary with 'name', 'leader'
                and 'roles' keys.

        """
        response = self.raw_patch(
            f"projects/{project_name}/teams", json=teams
        )
        response.raise_for_status()

    def save_team(
        self,
        project_name: str,
        team_name: str,
        members: list[dict[str, Any]],
    ) -> None:
        """Create or replace a team in a project.

        Args:
            project_name (str): Project name.
            team_name (str): Team name.
            members (list[dict[str, Any]]): Team members. Member is
                a dictionary with 'name', 'leader' and 'roles' keys.

        """
        response = self.put(
            f"projects/{project_name}/teams/{team_name}",
            members=members,
        )
        response.raise_for_status()

    def delete_team(self, project_name: str, team_name: str) -> None:
        """Delete a team from a project.

        Args:
            project_name (str): Project name.
            team_name (str): Team name.

        """
        response = self.delete(f"projects/{project_name}/teams/{team_name}")
        response.raise_for_status()

    def save_team_member(
        self,
        project_name: str,
        team_name: str,
        member_name: str,
        *,
        leader: bool = False,
        roles: Optional[list[str]] = None,
    ) -> None:
        """Add or replace a team member.

        Args:
            project_name (str): Project name.
            team_name (str): Team name.
            member_name (str): User name.
            leader (bool): Is user a leader of the team.
            roles (Optional[list[str]]): User roles in the team.

        """
        response = self.put(
            f"projects/{project_name}/teams/{team_name}"
            f"/members/{member_name}",
            name=member_name,
            leader=leader,
            roles=list(roles or []),
        )
        response.raise_for_status()

    def delete_team_member(
        self,
        project_name: str,
        team_name: str,
        member_name: str,
    ) -> None:
        """Remove a member from a team.

        Args:
            project_name (str): Project name.
            team_name (str): Team name.
            member_name (str): User name.

        """
        response = self.delete(
            f"projects/{project_name}/teams/{team_name}"
            f"/members/{member_name}"
        )
        response.raise_for_status()

    # --- Project users ---
    def get_project_users(self, project_name: str) -> dict[str, list[str]]:
        """Get users with explicitly set access groups on a project.

        Managers and admins are not included as they have access to all
            projects.

        Args:
            project_name (str): Project name.

        Returns:
            dict[str, list[str]]: Access groups by user name.

        """
        response = self.get(f"projects/{project_name}/users")
        response.raise_for_status()
        return response.data

    def set_project_user_access_groups(
        self,
        project_name: str,
        user_name: str,
        access_groups: list[str],
    ) -> dict[str, list[str]]:
        """Set access groups of a user on a project.

        Pass an empty list to remove user access to the project.

        Args:
            project_name (str): Project name.
            user_name (str): User name.
            access_groups (list[str]): Access group names.

        Returns:
            dict[str, list[str]]: Access groups by user name of all users
                on the project.

        """
        response = self.raw_patch(
            f"projects/{project_name}/users/{user_name}",
            json=list(access_groups),
        )
        response.raise_for_status()
        return response.data
