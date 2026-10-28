"""Current user, roles, permissions, and personal API keys."""

from __future__ import annotations

from typing import Any

from ..models import ApiKey, CurrentUser, Permission, Role, User
from ..utils import jsonable
from .base import Resource


class AuthResource(Resource):
    """Inspect the current principal and manage personal API keys."""

    def me(self) -> CurrentUser:
        """Return the current user and authorization summary."""
        return CurrentUser.model_validate(self._get("/user/me"))

    def providers(self) -> list[dict[str, Any]]:
        """Return the authentication providers advertised by WebAPI."""
        return self._get("/auth/providers") or []

    def api_keys(self) -> list[ApiKey]:
        """List the current user's API keys (no secrets)."""
        payload = self._get("/user/apikeys") or []
        return [ApiKey.model_validate(item) for item in payload]

    def create_api_key(
        self,
        name: str,
        *,
        description: str | None = None,
        expires_in_days: int | None = None,
    ) -> ApiKey:
        """Create a personal API key. The raw key is returned only once."""
        return ApiKey.model_validate(
            self._post(
                "/user/apikeys",
                json={
                    "name": name,
                    "description": description,
                    "expiresInDays": expires_in_days,
                },
            )
        )

    def revoke_api_key(self, key_identifier: str, *, remove: bool = False) -> None:
        """Disable (or permanently remove) an API key."""
        self._delete(
            f"/user/apikeys/{key_identifier}",
            params={"remove": "true"} if remove else None,
        )

    # -- users and roles ----------------------------------------------------

    def users(self) -> list[User]:
        """List users (requires the ``list`` permission)."""
        return [User.model_validate(item) for item in self._get("/user") or []]

    def user_permissions(self, user_id: int) -> list[Permission]:
        """List a user's global permissions."""
        return [
            Permission.model_validate(item)
            for item in self._get(f"/user/{user_id}/permissions") or []
        ]

    def user_roles(self, user_id: int) -> list[Role]:
        """List a user's roles."""
        return [Role.model_validate(item) for item in self._get(f"/user/{user_id}/roles") or []]

    def roles(self, *, include_personal: bool = False) -> list[Role]:
        """List roles."""
        return [
            Role.model_validate(item)
            for item in self._get("/role", params={"include_personal": include_personal}) or []
        ]

    def permissions(self) -> list[Permission]:
        """List every global permission defined by WebAPI."""
        return [Permission.model_validate(item) for item in self._get("/permission") or []]

    def suggest_roles(self, search: str | None = None) -> list[Role]:
        """Search roles for entity-access grants."""
        return [
            Role.model_validate(item)
            for item in self._get("/permission/access/suggest", params={"roleSearch": search}) or []
        ]

    def grant_entity_access(
        self,
        entity_type: str,
        entity_id: int,
        role_id: int,
        *,
        access_type: str = "READ",
    ) -> None:
        """Grant a role read/write access to an entity."""
        self._post(
            f"/permission/access/{entity_type}/{entity_id}/role/{role_id}",
            json={"accessType": access_type},
        )

    def revoke_entity_access(self, entity_type: str, entity_id: int, role_id: int) -> None:
        """Revoke a role's access to an entity."""
        self._delete(f"/permission/access/{entity_type}/{entity_id}/role/{role_id}")

    def entity_roles(
        self, entity_type: str, entity_id: int, *, access_type: str | None = None
    ) -> list[Role]:
        """List roles with access to an entity."""
        path = f"/permission/access/{entity_type}/{entity_id}"
        if access_type:
            path = f"{path}/{access_type}"
        return [Role.model_validate(item) for item in self._get(path) or []]

    def create_role(self, name: str) -> Role:
        """Create a role (admin)."""
        return Role.model_validate(self._post("/role", json={"name": name}))

    def delete_role(self, role_id: int) -> None:
        """Delete a role (admin)."""
        self._delete(f"/role/{role_id}")

    def set_role_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        """Replace a role's permissions (admin)."""
        self._put(f"/role/{role_id}/permissions/{'+'.join(str(value) for value in permission_ids)}")

    def role_permissions(self, role_id: int) -> list[Permission]:
        """List a role's permissions."""
        return [
            Permission.model_validate(item)
            for item in self._get(f"/role/{role_id}/permissions") or []
        ]

    def assign_role(self, user_id: int, role_id: int) -> None:
        """Assign a role to a user (admin)."""
        self._put(f"/user/{user_id}/role/{role_id}")

    def run_as(self, login: str) -> dict[str, Any]:
        """Impersonate a user (requires ``admin:run-as``)."""
        return self._post("/user/runas", params={"login": login}) or {}


def _json(value: Any) -> Any:
    return jsonable(value)
