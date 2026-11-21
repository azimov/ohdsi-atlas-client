"""Concept set CRUD, expressions, versions, and exports."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, List

from ..models import ConceptSet, ConceptSetExpression, ConceptSetSummary
from ..utils import jsonable
from .base import Resource

#: Concept IDs appear as ``concept.conceptId`` in Circe expressions, but
#: inline expressions copied from older tooling sometimes carry the database
#: column name ``CONCEPT_ID``. Accept either.
_CONCEPT_ID_FIELDS = ("conceptId", "CONCEPT_ID", "concept_id")


def _concept_id(item: dict[str, Any]) -> Any:
    concept = item.get("concept")
    if isinstance(concept, dict):
        for field in _CONCEPT_ID_FIELDS:
            if concept.get(field) is not None:
                return concept[field]
    elif concept is not None:
        value = getattr(concept, "concept_id", None)
        if value is not None:
            return value
    for field in _CONCEPT_ID_FIELDS:
        if item.get(field) is not None:
            return item[field]
    return None


class ConceptSetsResource(Resource):
    """Work with ATLAS concept sets and their expressions."""

    def list(self) -> List[ConceptSetSummary]:
        """Return metadata for all concept sets visible to the user."""
        payload = self._get("/conceptset") or []
        return [ConceptSetSummary.model_validate(item) for item in payload]

    def get(self, concept_set_id: int) -> ConceptSetSummary:
        """Return concept-set metadata."""
        return ConceptSetSummary.model_validate(self._get(f"/conceptset/{concept_set_id}"))

    def expression(
        self, concept_set_id: int, *, source_key: str | None = None
    ) -> ConceptSetExpression:
        """Return the full concept-set expression."""
        path = f"/conceptset/{concept_set_id}/expression"
        if source_key:
            path = f"{path}/{source_key}"
        return ConceptSetExpression.model_validate(self._get(path))

    def items(self, concept_set_id: int) -> List[dict[str, Any]]:
        """Return the stored concept-set item rows.

        These rows contain ``conceptId`` and integer flags; use
        :meth:`expression` when you need full concept metadata.
        """
        return self._get(f"/conceptset/{concept_set_id}/items") or []

    def create(
        self,
        name: str,
        expression: Any,
        *,
        description: str | None = None,
    ) -> ConceptSet:
        """Create a concept set and its items.

        WebAPI 3.0 has a two-step create: ``POST /conceptset`` stores the
        header, then ``PUT /conceptset/{id}/items`` stores the items. This
        method performs both and returns the header with the expression.
        """
        header = self._post("/conceptset", json={"name": name, "description": description})
        result = ConceptSet.model_validate(header)
        if result.id is None:
            raise ValueError("WebAPI did not return a concept set ID")
        expression_payload = self._expression_payload(expression)
        if expression_payload["items"]:
            self._put(
                f"/conceptset/{result.id}/items",
                json=self._item_rows(result.id, expression_payload),
            )
        result.expression = ConceptSetExpression.model_validate(expression_payload)
        return result

    def create_from_concepts(
        self,
        name: str,
        concept_ids: Iterable[int],
        *,
        source_key: str,
        description: str | None = None,
        include_descendants: bool = False,
        include_mapped: bool = False,
        exclude: bool = False,
    ) -> ConceptSet:
        """Create a concept set from concept IDs, fetching the concept metadata.

        Args:
            name: Concept-set name.
            concept_ids: Concept IDs to include.
            source_key: Source whose vocabulary is used to look up concepts.
            description: Optional description.
            include_descendants: Include descendants for every concept.
            include_mapped: Include mapped concepts for every concept.
            exclude: Mark every item as excluded.
        """
        ids = [int(value) for value in concept_ids]
        if not ids:
            raise ValueError("concept_ids must contain at least one concept")
        concepts = {
            concept.concept_id: concept
            for concept in self.client.concepts.get_many(source_key, ids)
        }
        missing = [value for value in ids if value not in concepts]
        if missing:
            raise ValueError(f"Concepts not found in source {source_key!r}: {missing}")
        items = [
            {
                "concept": concepts[value].model_dump(by_alias=True, exclude_none=True),
                "isExcluded": exclude,
                "includeDescendants": include_descendants,
                "includeMapped": include_mapped,
            }
            for value in ids
        ]
        return self.create(name, {"items": items}, description=description)

    def update(
        self,
        concept_set_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        expression: Any | None = None,
    ) -> ConceptSet:
        """Update a concept set. Omitted fields keep their current values."""
        if name is None and description is None and expression is None:
            raise ValueError("Supply at least one of name, description, or expression")
        current = self.get(concept_set_id)
        payload = {
            "id": concept_set_id,
            "name": name if name is not None else current.name,
            "description": description if description is not None else current.description,
        }
        result = ConceptSet.model_validate(self._put(f"/conceptset/{concept_set_id}", json=payload))
        expression_payload = (
            self._expression_payload(expression)
            if expression is not None
            else jsonable(self.expression(concept_set_id))
        )
        if expression is not None:
            self._put(
                f"/conceptset/{concept_set_id}/items",
                json=self._item_rows(concept_set_id, expression_payload),
            )
        result.expression = ConceptSetExpression.model_validate(expression_payload)
        return result

    def delete(self, concept_set_id: int) -> None:
        """Delete a concept set."""
        self._delete(f"/conceptset/{concept_set_id}")

    def copy(self, concept_set_id: int) -> ConceptSet:
        """Copy a concept set, letting WebAPI choose a unique name.

        WebAPI 3.0 has no server-side concept-set copy endpoint; it exposes
        ``copy-name`` and expects the client to create the copy.
        """
        suggestion = self._get(f"/conceptset/{concept_set_id}/copy-name") or {}
        source = self.get(concept_set_id)
        name = str(suggestion.get("copyName") or f"{source.name} copy")
        return self.create(name, self.expression(concept_set_id))

    def exists(self, name: str, *, concept_set_id: int = 0) -> int:
        """Return 1 when another concept set already uses ``name``, else 0."""
        return int(self._get(f"/conceptset/{concept_set_id}/exists", params={"name": name}) or 0)

    def check(self, concept_set: ConceptSet | dict[str, Any]) -> dict[str, Any]:
        """Run WebAPI's concept-set diagnostics."""
        return self._post("/conceptset/check", json=jsonable(concept_set)) or {}

    def resolve(self, concept_set_id: int, *, source_key: str) -> List[int]:
        """Resolve a stored concept set to concept IDs."""
        return self.client.concepts.resolve(
            source_key, self.expression(concept_set_id, source_key=source_key)
        )

    def count_included(self, concept_set_id: int, *, source_key: str) -> int:
        """Count concepts included by a stored concept set."""
        return self.client.concepts.count_included(
            source_key, self.expression(concept_set_id, source_key=source_key)
        )

    def export_zip(self, concept_set_id: int, destination: str | Path) -> Path:
        """Download a concept set as WebAPI's CSV-in-ZIP export."""
        return self._client.http.download(f"/conceptset/{concept_set_id}/export", destination)

    def export_list_zip(self, concept_set_ids: Sequence[int], destination: str | Path) -> Path:
        """Download several concept sets as one CSV-in-ZIP export."""
        ids = "+".join(str(int(value)) for value in concept_set_ids)
        return self._client.http.download(
            "/conceptset/exportlist", destination, params={"conceptsets": ids}
        )

    # -- expression helpers -------------------------------------------------

    @staticmethod
    def _expression_payload(expression: Any) -> dict[str, Any]:
        value = jsonable(expression)
        if isinstance(value, dict) and "items" not in value and "expression" in value:
            value = value.get("expression") or {}
        if not isinstance(value, dict):
            raise ValueError("A concept set expression must be an object")
        items = value.get("items") or []
        if not isinstance(items, list):
            raise ValueError("Concept set expression 'items' must be a list")
        return {"items": items}

    @staticmethod
    def _item_rows(concept_set_id: int, expression: dict[str, Any]) -> List[dict[str, Any]]:
        rows: List[dict[str, Any]] = []
        for item in expression.get("items") or []:
            if not isinstance(item, dict):
                raise ValueError("Concept set items must be objects")
            concept_id = _concept_id(item)
            if concept_id is None:
                raise ValueError("A concept set item is missing concept/conceptId")
            rows.append(
                {
                    "id": 0,
                    "conceptSetId": concept_set_id,
                    "conceptId": int(concept_id),
                    "isExcluded": int(bool(item.get("isExcluded", False))),
                    "includeDescendants": int(bool(item.get("includeDescendants", False))),
                    "includeMapped": int(bool(item.get("includeMapped", False))),
                }
            )
        return rows

    # -- versions -----------------------------------------------------------

    def versions(self, concept_set_id: int) -> List[dict[str, Any]]:
        """List concept-set versions."""
        return self._get(f"/conceptset/{concept_set_id}/version") or []

    def version(self, concept_set_id: int, version: int) -> dict[str, Any]:
        """Return one concept-set version (including items)."""
        return self._get(f"/conceptset/{concept_set_id}/version/{version}") or {}

    def update_version(
        self, concept_set_id: int, version: int, update: dict[str, Any]
    ) -> dict[str, Any]:
        """Update version metadata."""
        return (
            self._put(f"/conceptset/{concept_set_id}/version/{version}", json=jsonable(update))
            or {}
        )

    def delete_version(self, concept_set_id: int, version: int) -> None:
        """Delete a concept-set version."""
        self._delete(f"/conceptset/{concept_set_id}/version/{version}")

    def create_asset_from_version(self, concept_set_id: int, version: int) -> ConceptSet:
        """Restore a version into the current concept set."""
        return ConceptSet.model_validate(
            self._put(f"/conceptset/{concept_set_id}/version/{version}/createAsset")
        )

    # -- annotations --------------------------------------------------------

    def annotations(self, concept_set_id: int) -> List[dict[str, Any]]:
        """List annotations attached to a concept set."""
        return self._get(f"/conceptset/{concept_set_id}/annotation") or []

    def delete_annotation(self, concept_set_id: int, annotation_id: int) -> None:
        """Delete an annotation."""
        self._delete(f"/conceptset/{concept_set_id}/annotation/{annotation_id}")

    # -- tags ---------------------------------------------------------------

    def by_tags(self, tags: Sequence[str]) -> List[ConceptSetSummary]:
        """List concept sets matching any of the supplied tag names."""
        payload = self._post("/conceptset/byTags", json={"tags": list(tags)}) or []
        return [ConceptSetSummary.model_validate(item) for item in payload]

    def assign_tag(self, concept_set_id: int, tag_id: int) -> None:
        """Assign a tag to a concept set."""
        self._post(f"/conceptset/{concept_set_id}/tag", json=int(tag_id))

    def unassign_tag(self, concept_set_id: int, tag_id: int) -> None:
        """Remove a tag from a concept set."""
        self._delete(f"/conceptset/{concept_set_id}/tag/{tag_id}")
