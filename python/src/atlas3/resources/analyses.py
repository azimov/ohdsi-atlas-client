"""Analysis resources: cohort characterization, feature analysis, incidence, pathway.

The WebAPI analyses share a CRUD/version/tag pattern but differ in a few
endpoint names. This module keeps those differences in one small configurable
class instead of duplicating six near-identical classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Literal

from ..models import Job, Page
from ..utils import jsonable
from .base import Resource, page_from


class AnalysesResource(Resource):
    """A configurable WebAPI analysis resource."""

    def __init__(
        self,
        client: Any,
        *,
        path: str,
        copy_method: Literal["get", "post"] = "get",
        import_path: str = "/import",
        export_path: str = "/{id}/export",
        generate_method: Literal["get", "post"] | None = "post",
        generate_path: str = "/{id}/generation/{sourceKey}",
        cancel_method: Literal["get", "delete"] = "delete",
        cancel_path: str = "/{id}/generation/{sourceKey}",
        generation_path: str = "/{id}/generation",
        versions: bool = True,
        tags: bool = True,
        tag_param: bool = False,
        designs: bool = False,
    ) -> None:
        super().__init__(client)
        self.path = path
        self.copy_method = copy_method
        self.import_path = import_path
        self.export_path = export_path
        self.generate_method = generate_method
        self.generate_path = generate_path
        self.cancel_method = cancel_method
        self.cancel_path = cancel_path
        self.generation_path = generation_path
        self.versions_enabled = versions
        self.tags_enabled = tags
        self.tag_param = tag_param
        self.designs_enabled = designs

    def list(self, *, page: int | None = None, size: int | None = None) -> Page[dict[str, Any]]:
        """List analyses (paginated where WebAPI supports it)."""
        payload = self._get(
            self.path,
            params={"page": page, "size": size} if page is not None or size is not None else None,
        )
        return page_from(payload or [])

    def get(self, analysis_id: int) -> dict[str, Any]:
        """Return one analysis."""
        return self._get(f"{self.path}/{analysis_id}") or {}

    def create(self, analysis: dict[str, Any] | Any) -> dict[str, Any]:
        """Create an analysis from its DTO."""
        return self._post(self.path, json=jsonable(analysis)) or {}

    def update(self, analysis_id: int, analysis: dict[str, Any] | Any) -> dict[str, Any]:
        """Update an analysis from its DTO."""
        return self._put(f"{self.path}/{analysis_id}", json=jsonable(analysis)) or {}

    def delete(self, analysis_id: int) -> None:
        """Delete an analysis."""
        self._delete(f"{self.path}/{analysis_id}")

    def copy(self, analysis_id: int) -> dict[str, Any]:
        """Copy an analysis."""
        if self.copy_method == "get":
            return self._get(f"{self.path}/{analysis_id}/copy") or {}
        return self._post(f"{self.path}/{analysis_id}") or {}

    def exists(self, analysis_id: int, name: str) -> int:
        """Return 1 when another analysis uses ``name``, else 0."""
        return int(self._get(f"{self.path}/{analysis_id}/exists", params={"name": name}) or 0)

    def import_(self, design: dict[str, Any] | Any) -> dict[str, Any]:
        """Import an exported analysis design."""
        return self._post(f"{self.path}{self.import_path}", json=jsonable(design)) or {}

    def export(self, analysis_id: int) -> Any:
        """Export an analysis design or ZIP (depends on the resource)."""
        return self._get(f"{self.path}{self.export_path.format(id=analysis_id)}")

    def design(self, analysis_id: int) -> dict[str, Any]:
        """Return the analysis design (for resources with ``/design``)."""
        return self._get(f"{self.path}/{analysis_id}/design") or {}

    def check(self, analysis: dict[str, Any] | Any) -> dict[str, Any]:
        """Run analysis diagnostics."""
        return self._post(f"{self.path}/check", json=jsonable(analysis)) or {}

    def generate(self, analysis_id: int, source_key: str) -> Job:
        """Queue an analysis execution."""
        if self.generate_method is None:
            raise NotImplementedError(f"{self.path} has no execution endpoint")
        path = f"{self.path}{self.generate_path.format(id=analysis_id, sourceKey=source_key)}"
        payload = self._get(path) if self.generate_method == "get" else self._post(path)
        return Job.model_validate(payload)

    def cancel(self, analysis_id: int, source_key: str) -> None:
        """Cancel an analysis execution."""
        path = f"{self.path}{self.cancel_path.format(id=analysis_id, sourceKey=source_key)}"
        if self.cancel_method == "get":
            self._get(path)
        else:
            self._delete(path)

    def generations(self, analysis_id: int) -> List[dict[str, Any]]:
        """List generations for an analysis."""
        return self._get(f"{self.path}{self.generation_path.format(id=analysis_id)}") or []

    def generation(self, generation_id: int) -> dict[str, Any]:
        """Return one generation."""
        return self._get(f"{self.path}/generation/{generation_id}") or {}

    def generation_results(self, generation_id: int) -> dict[str, Any]:
        """Return generation results."""
        return self._get(f"{self.path}/generation/{generation_id}/result") or {}

    def generation_design(self, generation_id: int) -> dict[str, Any]:
        """Return the design used by a generation."""
        return self._get(f"{self.path}/generation/{generation_id}/design") or {}

    # -- versions -----------------------------------------------------------

    def versions(self, analysis_id: int) -> List[dict[str, Any]]:
        """List versions."""
        self._require(self.versions_enabled, "versions")
        return self._get(f"{self.path}/{analysis_id}/version") or []

    def version(self, analysis_id: int, version: int) -> dict[str, Any]:
        """Return one version."""
        self._require(self.versions_enabled, "versions")
        return self._get(f"{self.path}/{analysis_id}/version/{version}") or {}

    def delete_version(self, analysis_id: int, version: int) -> None:
        """Delete a version."""
        self._require(self.versions_enabled, "versions")
        self._delete(f"{self.path}/{analysis_id}/version/{version}")

    def create_asset_from_version(self, analysis_id: int, version: int) -> dict[str, Any]:
        """Restore a version into the current analysis."""
        self._require(self.versions_enabled, "versions")
        return self._put(f"{self.path}/{analysis_id}/version/{version}/createAsset") or {}

    # -- tags ---------------------------------------------------------------

    def assign_tag(self, analysis_id: int, tag_id: int) -> None:
        """Assign a tag."""
        self._require(self.tags_enabled, "tags")
        if self.tag_param:
            self._post(f"{self.path}/{analysis_id}/tag", params={"tagId": tag_id})
        else:
            self._post(f"{self.path}/{analysis_id}/tag", json=int(tag_id))

    def unassign_tag(self, analysis_id: int, tag_id: int) -> None:
        """Remove a tag."""
        self._require(self.tags_enabled, "tags")
        self._delete(f"{self.path}/{analysis_id}/tag/{tag_id}")

    def by_tags(self, tags: List[str]) -> List[dict[str, Any]]:
        """List analyses matching any of the supplied tag names."""
        self._require(self.tags_enabled, "tags")
        return self._post(f"{self.path}/byTags", json={"tags": tags}) or []

    @staticmethod
    def _require(enabled: bool, feature: str) -> None:
        if not enabled:
            raise NotImplementedError(f"This resource does not support {feature}")


class FeatureAnalysesResource(AnalysesResource):
    """Feature analysis definitions (design only; no execution endpoint)."""

    def __init__(self, client: Any) -> None:
        super().__init__(
            client,
            path="/feature-analysis",
            copy_method="get",
            import_path="",  # POST /feature-analysis is create
            export_path="/{id}/export/conceptset",
            generate_method=None,
            versions=False,
            tags=False,
        )

    def domains(self) -> List[dict[str, Any]]:
        """List feature-analysis domains."""
        return self._get(f"{self.path}/domains") or []

    def aggregates(self) -> List[dict[str, Any]]:
        """List feature-analysis aggregate options."""
        return self._get(f"{self.path}/aggregates") or []

    def export_concept_sets_zip(self, analysis_id: int, destination: str | Path) -> Path:
        """Download the concept sets used by a feature analysis."""
        return self._client.http.download(
            f"{self.path}/{analysis_id}/export/conceptset", destination
        )


class IncidenceRatesResource(AnalysesResource):
    """Incidence-rate analyses (``/ir``)."""

    def __init__(self, client: Any) -> None:
        super().__init__(
            client,
            path="/ir",
            copy_method="get",
            import_path="/design",
            export_path="/{id}/design",
            generate_method="get",
            generate_path="/{id}/execute/{sourceKey}",
            cancel_path="/{id}/execute/{sourceKey}",
            generation_path="/{id}/info",
            versions=True,
            tags=True,
            tag_param=True,
        )

    def info(self, analysis_id: int, source_key: str | None = None) -> Any:
        """Return execution info for an incidence-rate analysis."""
        path = f"{self.path}/{analysis_id}/info"
        if source_key:
            path = f"{path}/{source_key}"
        return self._get(path) or []

    def report(
        self, analysis_id: int, source_key: str, *, target_id: int, outcome_id: int
    ) -> dict[str, Any]:
        """Return an incidence-rate analysis report."""
        return (
            self._get(
                f"{self.path}/{analysis_id}/report/{source_key}",
                params={"targetId": target_id, "outcomeId": outcome_id},
            )
            or {}
        )

    def export_zip(self, analysis_id: int, destination: str | Path) -> Path:
        """Download the full incidence-rate analysis export."""
        return self._client.http.download(f"{self.path}/{analysis_id}/export", destination)

    def sql(self, request: dict[str, Any]) -> str:
        """Generate incidence-rate SQL for a request payload."""
        result = self._post(f"{self.path}/sql", json=jsonable(request)) or {}
        return str(result.get("templateSql") or result)


class CohortCharacterizationsResource(AnalysesResource):
    """Cohort characterization analyses."""

    def __init__(self, client: Any) -> None:
        super().__init__(
            client,
            path="/cohort-characterization",
            copy_method="post",
            import_path="/import",
            export_path="/{id}/export",
            generate_method="post",
            generate_path="/{id}/generation/{sourceKey}",
            cancel_method="delete",
            cancel_path="/{id}/generation/{sourceKey}",
            generation_path="/{id}/generation",
            versions=True,
            tags=True,
            tag_param=False,
        )

    def export_concept_sets_zip(self, analysis_id: int, destination: str | Path) -> Path:
        """Download the concept sets used by a characterization."""
        return self._client.http.download(
            f"{self.path}/{analysis_id}/export/conceptset", destination
        )


class PathwaysResource(AnalysesResource):
    """Pathway analyses."""

    def __init__(self, client: Any) -> None:
        super().__init__(
            client,
            path="/pathway-analysis",
            copy_method="post",
            import_path="/import",
            export_path="/{id}/export",
            generate_method="post",
            generate_path="/{id}/generation/{sourceKey}",
            cancel_method="delete",
            cancel_path="/{id}/generation/{sourceKey}",
            generation_path="/{id}/generation",
            versions=True,
            tags=True,
            tag_param=False,
        )

    def sql(self, analysis_id: int, source_key: str) -> str:
        """Return the SQL for a pathway analysis and source."""
        return str(self._get(f"{self.path}/{analysis_id}/sql/{source_key}") or "")


class ReusableResource(AnalysesResource):
    """Reusable analysis components."""

    def __init__(self, client: Any) -> None:
        super().__init__(
            client,
            path="/reusable",
            copy_method="post",
            import_path="",
            export_path="/{id}",
            generate_method=None,
            versions=True,
            tags=True,
            tag_param=False,
        )
