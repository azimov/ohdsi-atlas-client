"""Cohort definition CRUD, SQL, generation, and reports."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, List

from ..models import Cohort, CohortSummary, GenerationInfo, Job
from ..utils import jsonable
from .base import Resource


class CohortsResource(Resource):
    """Work with ATLAS cohort definitions and their generation jobs."""

    def list(self) -> List[CohortSummary]:
        """Return metadata for all cohort definitions visible to the user."""
        payload = self._get("/cohortdefinition") or []
        return [CohortSummary.model_validate(item) for item in payload]

    def get(self, cohort_id: int) -> Cohort:
        """Return a cohort definition with its Circe expression parsed."""
        return Cohort.from_api(self._get(f"/cohortdefinition/{cohort_id}"))

    def raw(self, cohort_id: int) -> dict[str, Any]:
        """Return the raw WebAPI payload (``expression`` is a JSON string)."""
        return self._get(f"/cohortdefinition/{cohort_id}") or {}

    def expression(self, cohort_id: int) -> dict[str, Any]:
        """Return only the parsed cohort expression."""
        return self.get(cohort_id).expression

    def create(
        self,
        name: str,
        expression: Any,
        *,
        description: str | None = None,
        expression_type: str = "SIMPLE_EXPRESSION",
    ) -> Cohort:
        """Create a cohort definition."""
        payload = {
            "name": name,
            "description": description,
            "expression": jsonable(expression),
            "expressionType": expression_type,
        }
        result = self._post("/cohortdefinition", json=payload)
        cohort = Cohort.from_api(result)
        if not cohort.expression:
            cohort.expression = jsonable(expression)
        return cohort

    def update(
        self,
        cohort_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        expression: Any | None = None,
        expression_type: str | None = None,
    ) -> Cohort:
        """Update a cohort definition. Omitted fields keep their current values."""
        if name is None and description is None and expression is None and expression_type is None:
            raise ValueError(
                "Supply at least one of name, description, expression, or expression_type"
            )
        current = self.get(cohort_id)
        payload = {
            "id": cohort_id,
            "name": name if name is not None else current.name,
            "description": description if description is not None else current.description,
            "expression": jsonable(expression if expression is not None else current.expression),
            "expressionType": expression_type or current.expression_type or "SIMPLE_EXPRESSION",
        }
        return Cohort.from_api(self._put(f"/cohortdefinition/{cohort_id}", json=payload))

    def delete(self, cohort_id: int) -> None:
        """Delete a cohort definition and its generated results."""
        self._delete(f"/cohortdefinition/{cohort_id}")

    def copy(self, cohort_id: int) -> Cohort:
        """Copy a cohort definition, letting WebAPI choose a unique name."""
        return Cohort.from_api(self._get(f"/cohortdefinition/{cohort_id}/copy"))

    def exists(self, name: str, *, cohort_id: int = 0) -> int:
        """Return 1 when another cohort already uses ``name``, else 0."""
        return int(self._get(f"/cohortdefinition/{cohort_id}/exists", params={"name": name}) or 0)

    def sql(self, expression: Any, options: dict[str, Any] | None = None) -> str:
        """Generate OHDSI template SQL for a cohort expression."""
        payload: dict[str, Any] = {"expression": jsonable(expression)}
        if options is not None:
            payload["options"] = jsonable(options)
        result = self._post("/cohortdefinition/sql", json=payload) or {}
        return str(result.get("templateSql") or result)

    def check(self, expression: Any, *, v2: bool = False) -> dict[str, Any]:
        """Run WebAPI's cohort diagnostics (legacy or V2)."""
        path = "/cohortdefinition/checkV2" if v2 else "/cohortdefinition/check"
        return self._post(path, json=jsonable(expression)) or {}

    def generate(self, cohort_id: int, source_key: str, *, demographic: bool = False) -> Job:
        """Queue cohort generation on a source. Poll with ``client.jobs.wait``."""
        payload = self._get(
            f"/cohortdefinition/{cohort_id}/generate/{source_key}",
            params={"demographic": demographic},
        )
        return Job.model_validate(payload)

    def cancel(self, cohort_id: int, source_key: str) -> None:
        """Request cancellation of a cohort generation job."""
        self._get(f"/cohortdefinition/{cohort_id}/cancel/{source_key}")

    def generation_info(self, cohort_id: int) -> List[GenerationInfo]:
        """Return generation status for every source."""
        payload = self._get(f"/cohortdefinition/{cohort_id}/info") or []
        return [GenerationInfo.model_validate(item) for item in payload]

    def inclusion_report(self, cohort_id: int, source_key: str, *, mode: int = 0) -> dict[str, Any]:
        """Return the inclusion-rule report for a generated cohort."""
        return (
            self._get(
                f"/cohortdefinition/{cohort_id}/report/{source_key}/inclusion",
                params={"mode": mode},
            )
            or {}
        )

    def demographics_report(
        self, cohort_id: int, source_key: str, *, cc_generate_id: int | None = None
    ) -> dict[str, Any]:
        """Return the demographics report for a generated cohort."""
        return (
            self._get(
                f"/cohortdefinition/{cohort_id}/report/{source_key}/demographics",
                params={"ccGenerateId": cc_generate_id},
            )
            or {}
        )

    def export_concept_sets_zip(self, cohort_id: int, destination: str | Path) -> Path:
        """Download the concept sets embedded in a cohort as a CSV-in-ZIP file."""
        return self._client.http.download(
            f"/cohortdefinition/{cohort_id}/export/conceptset", destination
        )

    def print_friendly_cohort(self, expression: Any) -> str:
        """Render a cohort expression as print-friendly Markdown/HTML."""
        return str(
            self._post("/cohortdefinition/printfriendly/cohort", json=jsonable(expression)) or ""
        )

    def print_friendly_concept_sets(self, concept_sets: Any) -> str:
        """Render concept sets as print-friendly Markdown/HTML."""
        return str(
            self._post(
                "/cohortdefinition/printfriendly/conceptsets",
                json=jsonable(concept_sets),
            )
            or ""
        )

    # -- versions -----------------------------------------------------------

    def versions(self, cohort_id: int) -> List[dict[str, Any]]:
        """List cohort versions."""
        return self._get(f"/cohortdefinition/{cohort_id}/version") or []

    def version(self, cohort_id: int, version: int) -> dict[str, Any]:
        """Return one cohort version."""
        return self._get(f"/cohortdefinition/{cohort_id}/version/{version}") or {}

    def delete_version(self, cohort_id: int, version: int) -> None:
        """Delete a cohort version."""
        self._delete(f"/cohortdefinition/{cohort_id}/version/{version}")

    def create_asset_from_version(self, cohort_id: int, version: int) -> Cohort:
        """Restore a version into the current cohort."""
        return Cohort.from_api(
            self._put(f"/cohortdefinition/{cohort_id}/version/{version}/createAsset")
        )

    # -- tags ---------------------------------------------------------------

    def by_tags(self, tags: Sequence[str]) -> List[CohortSummary]:
        """List cohorts matching any of the supplied tag names."""
        payload = self._post("/cohortdefinition/byTags", json={"tags": list(tags)}) or []
        return [CohortSummary.model_validate(item) for item in payload]

    def assign_tag(self, cohort_id: int, tag_id: int) -> None:
        """Assign a tag to a cohort."""
        self._post(f"/cohortdefinition/{cohort_id}/tag", json=int(tag_id))

    def unassign_tag(self, cohort_id: int, tag_id: int) -> None:
        """Remove a tag from a cohort."""
        self._delete(f"/cohortdefinition/{cohort_id}/tag/{tag_id}")
