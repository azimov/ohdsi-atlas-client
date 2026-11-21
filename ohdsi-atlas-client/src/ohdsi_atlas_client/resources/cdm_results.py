"""Quick CDM result queries, including concept record counts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..models import ConceptCount
from ..utils import chunked
from .base import Resource


class CdmResultsResource(Resource):
    """Query Achilles/CDM results caches for quick descriptive statistics."""

    def concept_counts(
        self,
        source_key: str,
        concept_ids: Iterable[int],
        *,
        batch_size: int = 500,
    ) -> list[ConceptCount]:
        """Return record/person counts for concepts.

        This is the canonical concept-count method. ``atlas.concepts.counts``
        is an alias that delegates here.

        WebAPI's CDM results cache usually returns four values per concept:
        record count, descendant record count, person count, and descendant
        person count. Older configurations return only the first two. The
        raw values are preserved on :class:`ConceptCount.values`.

        The numbers come from the Achilles results tables, not from the CDM
        directly. If Achilles has not run against a source, every value is
        zero even though the CDM has data.

        Args:
            source_key: CDM source key.
            concept_ids: Concept IDs to query.
            batch_size: Maximum IDs per request (WebAPI accepts a JSON array).
        """
        identifiers = list(dict.fromkeys(int(value) for value in concept_ids))
        if not identifiers:
            return []
        results: list[ConceptCount] = []
        for batch in chunked(identifiers, batch_size):
            payload = self._post(f"/cdmresults/{source_key}/conceptRecordCount", json=batch)
            results.extend(self._parse_counts(payload))
        return results

    def concept_counts_map(
        self,
        source_key: str,
        concept_ids: Iterable[int],
        *,
        batch_size: int = 500,
    ) -> dict[int, ConceptCount]:
        """Return concept counts keyed by concept ID."""
        return {
            item.concept_id: item
            for item in self.concept_counts(source_key, concept_ids, batch_size=batch_size)
        }

    @staticmethod
    def _parse_counts(payload: Any) -> list[ConceptCount]:
        if not isinstance(payload, list):
            return []
        results: list[ConceptCount] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            for key, values in entry.items():
                try:
                    concept_id = int(key)
                except (TypeError, ValueError):
                    continue
                if not isinstance(values, list):
                    values = [values]
                results.append(
                    ConceptCount(
                        concept_id=concept_id,
                        values=[int(value) for value in values if value is not None],
                    )
                )
        return results

    def dashboard(self, source_key: str) -> dict[str, Any]:
        """Return the Achilles dashboard summary for a source."""
        return self._get(f"/cdmresults/{source_key}/dashboard") or {}

    def person(self, source_key: str) -> dict[str, Any]:
        """Return the person summary for a source."""
        return self._get(f"/cdmresults/{source_key}/person") or {}

    def warm_cache(self, source_key: str) -> dict[str, Any]:
        """Warm the CDM results cache for a source."""
        return self._get(f"/cdmresults/{source_key}/warmCache") or {}

    def refresh_cache(self, source_key: str) -> dict[str, Any]:
        """Refresh the CDM results cache for a source (admin)."""
        return self._get(f"/cdmresults/{source_key}/refreshCache") or {}

    def clear_cache(self, source_key: str) -> None:
        """Clear the CDM and Achilles caches for a source (admin)."""
        self._post(f"/cdmresults/{source_key}/clearCache")
