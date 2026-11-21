"""Smaller WebAPI resource groups: tools, notifications, caches, SQL, DDL, evidence."""

from __future__ import annotations

from typing import Any

from ..utils import jsonable
from .base import Resource


class ToolsResource(Resource):
    """ATLAS tools (links shown in the UI)."""

    def list(self) -> list[dict[str, Any]]:
        return self._get("/tool") or []

    def get(self, tool_id: int) -> dict[str, Any]:
        return self._get(f"/tool/{tool_id}") or {}

    def create(self, tool: dict[str, Any]) -> dict[str, Any]:
        return self._post("/tool", json=jsonable(tool)) or {}

    def update(self, tool: dict[str, Any]) -> dict[str, Any]:
        return self._put("/tool", json=jsonable(tool)) or {}

    def delete(self, tool_id: int) -> None:
        self._delete(f"/tool/{tool_id}")


class NotificationsResource(Resource):
    """Job notifications for the current user."""

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        return self._get("/notifications", params=filters) or []

    def last_viewed(self) -> Any:
        return self._get("/notifications/viewed")

    def set_viewed(self, stamp: Any) -> None:
        self._post("/notifications/viewed", json=stamp)


class CacheResource(Resource):
    """WebAPI cache administration."""

    def info(self) -> list[dict[str, Any]]:
        return self._get("/cache") or []

    def clear(self) -> dict[str, Any]:
        return self._get("/cache/clear") or {}


class InfoResource(Resource):
    """Server information."""

    def get(self) -> dict[str, Any]:
        return self._get("/info") or {}


class SqlRenderResource(Resource):
    """SQL translation through WebAPI."""

    def translate(
        self,
        sql: str,
        *,
        target_dialect: str,
        parameters: dict[str, str] | None = None,
        oracle_temp_schema: str | None = None,
    ) -> dict[str, Any]:
        """Render and translate OHDSI SQL.

        WebAPI's payload is case-sensitive: ``SQL`` and ``targetdialect``.
        The response contains the translated statement under ``targetSQL``.
        """
        payload = {
            "SQL": sql,
            "targetdialect": target_dialect,
            "parameters": parameters or {},
            "oracleTempSchema": oracle_temp_schema,
        }
        return self._post("/sqlrender/translate", json=payload) or {}


#: The DDL endpoints return plain SQL text. Sending only
#: ``Accept: application/json`` makes WebAPI raise
#: HttpMediaTypeNotAcceptableException (HTTP 500), so these calls ask for
#: text explicitly while still accepting JSON error bodies.
_DDL_ACCEPT = {"Accept": "text/plain, */*"}


class DdlResource(Resource):
    """Generate DDL for the results, Achilles, and negative-control schemas.

    WebAPI 3.0 has no ``/ddl/cdm`` endpoint; it cannot emit OHDSI CDM DDL.
    The three endpoints that exist all target a *results* schema. All of them
    require an authenticated user with admin permission.

    Each method returns SQL text exactly as the server renders it.
    """

    def results(
        self,
        *,
        dialect: str = "postgresql",
        schema: str = "results",
        vocab_schema: str | None = None,
        init_concept_hierarchy: bool = False,
        temp_schema: str | None = None,
    ) -> str:
        """Return DDL for the cohort/results tables in ``schema``."""
        return str(
            self._get(
                "/ddl/results",
                params={
                    "dialect": dialect,
                    "schema": schema,
                    "vocabSchema": vocab_schema,
                    "initConceptHierarchy": init_concept_hierarchy,
                    "tempSchema": temp_schema,
                },
                headers=_DDL_ACCEPT,
            )
            or ""
        )

    def achilles(
        self,
        *,
        dialect: str = "postgresql",
        schema: str = "results",
        vocab_schema: str | None = None,
    ) -> str:
        """Return DDL for the Achilles result tables in ``schema``."""
        return str(
            self._get(
                "/ddl/achilles",
                params={
                    "dialect": dialect,
                    "schema": schema,
                    "vocabSchema": vocab_schema,
                },
                headers=_DDL_ACCEPT,
            )
            or ""
        )

    def cem_results(
        self,
        *,
        dialect: str = "postgresql",
        schema: str = "results",
    ) -> str:
        """Return DDL for the negative-control (CEM) result tables in ``schema``."""
        return str(
            self._get(
                "/ddl/cemresults",
                params={"dialect": dialect, "schema": schema},
                headers=_DDL_ACCEPT,
            )
            or ""
        )


class EvidenceResource(Resource):
    """Evidence and drug-label endpoints (source dependent)."""

    def study_mapping(self, cohort_id: int) -> list[dict[str, Any]]:
        return self._get(f"/evidence/study/{cohort_id}") or []

    def concept_mapping(self, concept_id: int) -> list[dict[str, Any]]:
        return self._get(f"/evidence/mapping/{concept_id}") or []

    def evidence(self, source_key: str, concept_id: int) -> list[dict[str, Any]]:
        return self._get(f"/evidence/{source_key}/{concept_id}") or []

    def info(self, source_key: str) -> list[dict[str, Any]]:
        return self._get(f"/evidence/{source_key}/info") or []

    def label(self, set_id: str) -> list[dict[str, Any]]:
        return self._get(f"/evidence/label/{set_id}") or []

    def search_labels(self, term: str) -> list[dict[str, Any]]:
        return self._get(f"/evidence/labelsearch/{term}") or []

    def negative_controls(self, source_key: str, concept_set_id: int) -> list[dict[str, Any]]:
        return self._get(f"/evidence/{source_key}/negativecontrols/{concept_set_id}") or []


class StatisticResource(Resource):
    """Execution and access statistics."""

    def executions(self, request: dict[str, Any]) -> Any:
        return self._post("/statistic/executions", json=jsonable(request))

    def access_trends(self, request: dict[str, Any]) -> Any:
        return self._post("/statistic/accesstrends", json=jsonable(request))
