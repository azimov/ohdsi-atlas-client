"""Tag management."""

from __future__ import annotations

from typing import Any, List

from ..models import Tag
from .base import Resource


class TagsResource(Resource):
    """Create, list, and assign ATLAS tags."""

    def list(self) -> List[Tag]:
        """List all tags."""
        return [Tag.model_validate(item) for item in self._get("/tag") or []]

    def get(self, tag_id: int) -> Tag:
        """Return one tag."""
        return Tag.model_validate(self._get(f"/tag/{tag_id}"))

    def search(self, name_part: str) -> List[Tag]:
        """Search tags by a partial name."""
        return [
            Tag.model_validate(item)
            for item in self._get("/tag/search", params={"namePart": name_part}) or []
        ]

    def create(self, name: str, *, color: str | None = None, description: str | None = None) -> Tag:
        """Create a tag."""
        return Tag.model_validate(
            self._post(
                "/tag",
                json={"name": name, "color": color, "description": description},
            )
        )

    def update(
        self,
        tag_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> Tag:
        """Update a tag."""
        current = self.get(tag_id)
        return Tag.model_validate(
            self._put(
                f"/tag/{tag_id}",
                json={
                    "id": tag_id,
                    "name": name if name is not None else current.name,
                    "color": color if color is not None else current.color,
                    "description": description if description is not None else current.description,
                },
            )
        )

    def delete(self, tag_id: int) -> None:
        """Delete a tag."""
        self._delete(f"/tag/{tag_id}")

    def assignment_permissions(self) -> dict[str, Any]:
        """Return which entity types the user may tag."""
        return self._get("/tag/assignmentPermissions") or {}

    def assign_many(self, assignment: dict[str, Any]) -> None:
        """Assign a tag group to many entities."""
        self._post("/tag/multiAssign", json=assignment)

    def unassign_many(self, assignment: dict[str, Any]) -> None:
        """Unassign a tag group from many entities."""
        self._post("/tag/multiUnassign", json=assignment)
