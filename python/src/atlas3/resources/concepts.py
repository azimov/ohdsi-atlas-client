"""Vocabulary search and concept-set expression helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from ..models import Concept, ConceptCount
from ..utils import as_list, jsonable
from .base import Resource


class ConceptsResource(Resource):
    """Search concepts and resolve concept-set expressions against a source."""

    def search(
        self,
        source_key: str,
        query: str,
        *,
        rows: int = 100,
        domain: str | Sequence[str] | None = None,
        vocabulary: str | Sequence[str] | None = None,
        concept_class: str | Sequence[str] | None = None,
        standard_concept: str | None = None,
        invalid_reason: str | None = None,
        lexical: bool = False,
    ) -> list[Concept]:
        """Search a source's vocabulary.

        Unfiltered searches use the lightweight ``GET /search`` endpoint.
        Domain, vocabulary, class, and validity filters use the POST search
        body (WebAPI's uppercase field names are handled for you).
        """
        domains = [str(item) for item in as_list(domain)]
        vocabularies = [str(item) for item in as_list(vocabulary)]
        classes = [str(item) for item in as_list(concept_class)]

        if not (
            domains or vocabularies or classes or standard_concept or invalid_reason or lexical
        ):
            payload = self._get(
                f"/vocabulary/{source_key}/search",
                params={"query": query, "rows": rows},
            )
            return [Concept.model_validate(item) for item in payload or []][:rows]

        body: dict[str, Any] = {
            "QUERY": query,
            "IS_LEXICAL": lexical,
        }
        if domains:
            body["DOMAIN_ID"] = domains
        if vocabularies:
            body["VOCABULARY_ID"] = vocabularies
        if classes:
            body["CONCEPT_CLASS_ID"] = classes
        if standard_concept:
            body["STANDARD_CONCEPT"] = standard_concept
        if invalid_reason:
            body["INVALID_REASON"] = invalid_reason
        # WebAPI ignores row limits on this endpoint; enforce them client-side
        # so callers can rely on a small result set.
        payload = self._post(f"/vocabulary/{source_key}/search", json=body)
        return [Concept.model_validate(item) for item in payload or []][:rows]

    def get(self, source_key: str, concept_id: int) -> Concept:
        """Return one concept by ID."""
        return Concept.model_validate(self._get(f"/vocabulary/{source_key}/concept/{concept_id}"))

    def get_many(self, source_key: str, concept_ids: Iterable[int]) -> list[Concept]:
        """Look up many concepts by ID in one request."""
        ids = [int(value) for value in concept_ids]
        if not ids:
            return []
        payload = self._post(f"/vocabulary/{source_key}/lookup/identifiers", json=ids)
        return [Concept.model_validate(item) for item in payload or []]

    def lookup_source_codes(self, source_key: str, source_codes: Iterable[str]) -> list[Concept]:
        """Look up concepts by source concept code."""
        codes = [str(value) for value in source_codes]
        if not codes:
            return []
        payload = self._post(f"/vocabulary/{source_key}/lookup/sourcecodes", json=codes)
        return [Concept.model_validate(item) for item in payload or []]

    def mapped(self, source_key: str, concept_ids: Iterable[int]) -> list[Concept]:
        """Return concepts mapped to the supplied non-standard concepts."""
        ids = [int(value) for value in concept_ids]
        if not ids:
            return []
        payload = self._post(f"/vocabulary/{source_key}/lookup/mapped", json=ids)
        return [Concept.model_validate(item) for item in payload or []]

    def related(self, source_key: str, concept_id: int) -> list[dict[str, Any]]:
        """Return related concepts (parents, children, mappings)."""
        return self._get(f"/vocabulary/{source_key}/concept/{concept_id}/related") or []

    def descendants(self, source_key: str, concept_id: int) -> list[dict[str, Any]]:
        """Return descendant concepts."""
        return self._get(f"/vocabulary/{source_key}/concept/{concept_id}/descendants") or []

    def ancestors_descendants(self, source_key: str, concept_id: int) -> list[dict[str, Any]]:
        """Return ancestors and descendants of a concept."""
        return (
            self._get(f"/vocabulary/{source_key}/concept/{concept_id}/ancestorAndDescendant") or []
        )

    def common_ancestors(self, source_key: str, concept_ids: Iterable[int]) -> list[dict[str, Any]]:
        """Return common ancestors for a list of concepts."""
        payload = self._post(
            f"/vocabulary/{source_key}/commonAncestors",
            json=[int(value) for value in concept_ids],
        )
        return payload or []

    def recommended(self, source_key: str, concept_ids: Iterable[int]) -> list[dict[str, Any]]:
        """Return recommended concepts for a list of concept IDs."""
        payload = self._post(
            f"/vocabulary/{source_key}/lookup/recommended",
            json=[int(value) for value in concept_ids],
        )
        return payload or []

    def domains(self, source_key: str) -> list[dict[str, Any]]:
        """List vocabulary domains for a source."""
        return self._get(f"/vocabulary/{source_key}/domains") or []

    def vocabularies(self, source_key: str) -> list[dict[str, Any]]:
        """List vocabularies loaded in a source."""
        return self._get(f"/vocabulary/{source_key}/vocabularies") or []

    def info(self, source_key: str) -> dict[str, Any]:
        """Return vocabulary version information for a source."""
        return self._get(f"/vocabulary/{source_key}/info") or {}

    def resolve(self, source_key: str, expression: Any) -> list[int]:
        """Resolve a concept-set expression to included concept IDs."""
        payload = self._post(
            f"/vocabulary/{source_key}/resolveConceptSetExpression",
            json=jsonable(expression),
        )
        return [int(value) for value in payload or []]

    def count_included(self, source_key: str, expression: Any) -> int:
        """Count concepts included by a concept-set expression."""
        count = self._post(
            f"/vocabulary/{source_key}/included-concepts/count",
            json=jsonable(expression),
        )
        return int(count or 0)

    def expression_sql(self, expression: Any) -> str:
        """Return the OHDSI SQL that resolves a concept-set expression."""
        return str(self._post("/vocabulary/conceptSetExpressionSQL", json=jsonable(expression)))

    def compare(self, source_key: str, expressions: Sequence[Any]) -> list[dict[str, Any]]:
        """Compare two or more concept-set expressions."""
        payload = self._post(
            f"/vocabulary/{source_key}/compare",
            json=[jsonable(item) for item in expressions],
        )
        return payload or []

    def optimize(self, source_key: str, expression: Any) -> dict[str, Any]:
        """Optimise a concept-set expression."""
        return self._post(f"/vocabulary/{source_key}/optimize", json=jsonable(expression)) or {}

    def counts(self, source_key: str, concept_ids: Iterable[int]) -> list[ConceptCount]:
        """Return CDM record/person counts for concepts (via CDM results cache)."""
        return self.client.cdm_results.concept_counts(source_key, concept_ids)
