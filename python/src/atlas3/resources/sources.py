"""CDM source management and discovery."""

from __future__ import annotations

from typing import Any, List

from ..models import Source
from .base import Resource, as_payload


class SourcesResource(Resource):
    """Read and administer WebAPI CDM sources."""

    def list(self) -> List[Source]:
        """Return all configured sources visible to the current user."""
        payload = self._get("/source/sources")
        return [Source.model_validate(item) for item in payload or []]

    def get(self, source_key: str) -> Source:
        """Return one source by its source key."""
        return Source.model_validate(self._get(f"/source/{source_key}"))

    def priority(self) -> dict[str, Source]:
        """Return the priority source for each daimon type."""
        payload = self._get("/source/daimon/priority") or {}
        return {key: Source.model_validate(value) for key, value in payload.items()}

    def priority_vocabulary(self) -> Source | None:
        """Return the source marked as the priority vocabulary source."""
        payload = self._get("/source/priorityVocabulary")
        return Source.model_validate(payload) if payload else None

    def details(self, source_id: int) -> dict[str, Any]:
        """Return administrative connection details for a source (admin only)."""
        return dict(self._get(f"/source/details/{source_id}") or {})

    def check(self, source_key: str) -> Source:
        """Ask WebAPI to test a source connection."""
        return Source.model_validate(self._get(f"/source/connection/{source_key}"))

    def refresh(self) -> List[Source]:
        """Refresh WebAPI's source cache and return the sources."""
        payload = self._get("/source/refresh")
        return [Source.model_validate(item) for item in payload or []]

    def set_priority(self, source_key: str, daimon_type: str) -> None:
        """Make ``source_key`` the priority source for ``daimon_type`` (admin)."""
        self._post(f"/source/{source_key}/daimons/{daimon_type}/set-priority")

    def create(
        self,
        source: dict[str, Any] | Source,
        *,
        keyfile: bytes | None = None,
        keyfile_name: str = "keyfile",
    ) -> Source:
        """Create a source (admin). ``source`` is a ``SourceRequest`` payload."""
        files: dict[str, Any] = {
            "source": (None, _json_bytes(as_payload(source)), "application/json"),
        }
        if keyfile is not None:
            files["keyfile"] = (keyfile_name, keyfile, "application/octet-stream")
        payload = self._post("/source", files=files)
        return Source.model_validate(payload)

    def update(
        self,
        source_id: int,
        source: dict[str, Any] | Source,
        *,
        keyfile: bytes | None = None,
        keyfile_name: str = "keyfile",
    ) -> Source:
        """Update a source (admin)."""
        files: dict[str, Any] = {
            "source": (None, _json_bytes(as_payload(source)), "application/json"),
        }
        if keyfile is not None:
            files["keyfile"] = (keyfile_name, keyfile, "application/octet-stream")
        payload = self._put(f"/source/{source_id}", files=files)
        return Source.model_validate(payload)

    def delete(self, source_id: int) -> None:
        """Delete a source (admin). WebAPI performs a soft delete."""
        self._delete(f"/source/{source_id}")


def _json_bytes(value: Any) -> bytes:
    import json

    return json.dumps(value, default=str).encode("utf-8")
