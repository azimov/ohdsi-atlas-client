"""Export and import portable cohort definition sets."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

from ..bundle import (
    CohortSetBundle,
    CohortSetEntry,
    ConceptSetEntry,
    ImportResult,
)
from ..exceptions import BundleError, ConflictError
from ..utils import unique_name
from .base import Resource

ConflictPolicy = Literal["error", "skip", "rename", "update"]


class CohortSetsResource(Resource):
    """Move complete cohort definition sets between ATLAS instances.

    A set includes cohort definitions and every concept set embedded in their
    expressions. WebAPI 3.0 has no server-side "cohort set" resource, so this
    is implemented as a documented client-side bundle.
    """

    def export(
        self,
        cohort_ids: Iterable[int] | None = None,
        *,
        path: str | Path | None = None,
        include_concept_sets: bool = True,
    ) -> CohortSetBundle:
        """Export cohort definitions (all readable cohorts by default).

        Args:
            cohort_ids: Cohort IDs to include. ``None`` exports every cohort
                visible to the current user.
            path: Optional ``.json``, ``.zip``, or directory destination.
            include_concept_sets: Collect concept sets embedded in cohort
                expressions into the bundle's ``conceptSets`` array.
        """
        if cohort_ids is None:
            cohort_ids = [cohort.id for cohort in self.client.cohorts.list()]
        ids = list(dict.fromkeys(int(value) for value in cohort_ids))
        if not ids:
            raise BundleError("No cohorts selected for export")
        payloads = [self.client.cohorts.raw(cohort_id) for cohort_id in ids]
        bundle = CohortSetBundle.from_cohorts(
            payloads,
            atlas={
                "url": self.client.url,
                "apiUrl": self.client.api_url,
                "webApiVersion": self.client.version,
            },
        )
        if not include_concept_sets:
            bundle.concept_sets = []
        bundle.with_integrity()
        if path is not None:
            bundle.save(path)
        return bundle

    def import_(
        self,
        bundle: CohortSetBundle | dict[str, Any] | str | Path,
        *,
        on_conflict: ConflictPolicy = "rename",
        dry_run: bool = False,
    ) -> ImportResult:
        """Import a cohort definition set.

        Args:
            bundle: A :class:`CohortSetBundle`, a bundle dictionary, or a path
                to a JSON/ZIP/directory bundle.
            on_conflict: What to do when a cohort or concept set name already
                exists: ``error``, ``skip``, ``rename`` (default, safest across
                instances), or ``update``.
            dry_run: Validate and plan without writing to WebAPI.

        Returns:
            An :class:`ImportResult` describing every action.
        """
        if on_conflict not in {"error", "skip", "rename", "update"}:
            raise ValueError("on_conflict must be one of 'error', 'skip', 'rename', 'update'")
        data = self._coerce_bundle(bundle)
        result = ImportResult(dry_run=dry_run)

        existing_concept_sets = {item.name: item for item in self.client.concept_sets.list()}
        concept_set_map: dict[str, int] = {}
        taken_concept_set_names = set(existing_concept_sets)

        for concept_entry in data.concept_sets:
            existing_concept_set = existing_concept_sets.get(concept_entry.name)
            if existing_concept_set is not None:
                if on_conflict == "error":
                    raise ConflictError(
                        f"Concept set {concept_entry.name!r} already exists "
                        f"(id {existing_concept_set.id})",
                        status_code=409,
                        method="POST",
                        url=f"{self.client.api_url}/conceptset",
                    )
                if on_conflict == "skip":
                    result.skipped_concept_sets.append(
                        {"name": concept_entry.name, "id": existing_concept_set.id}
                    )
                    concept_set_map[concept_entry.name] = int(existing_concept_set.id or 0)
                    continue
                if on_conflict == "update":
                    if dry_run:
                        result.updated_concept_sets.append(
                            {
                                "name": concept_entry.name,
                                "id": existing_concept_set.id,
                                "dryRun": True,
                            }
                        )
                    else:
                        updated_concept_set = self.client.concept_sets.update(
                            int(existing_concept_set.id or 0),
                            description=concept_entry.description,
                            expression=concept_entry.expression,
                        )
                        result.updated_concept_sets.append(
                            {"name": concept_entry.name, "id": updated_concept_set.id}
                        )
                    concept_set_map[concept_entry.name] = int(existing_concept_set.id or 0)
                    continue
                # rename
                new_name = unique_name(concept_entry.name, taken_concept_set_names)
                taken_concept_set_names.add(new_name)
                if dry_run:
                    result.created_concept_sets.append(
                        {
                            "name": new_name,
                            "originalName": concept_entry.name,
                            "dryRun": True,
                        }
                    )
                    concept_set_map[concept_entry.name] = 0
                else:
                    created_concept_set = self.client.concept_sets.create(
                        new_name,
                        concept_entry.expression,
                        description=concept_entry.description,
                    )
                    result.created_concept_sets.append(
                        {
                            "name": new_name,
                            "originalName": concept_entry.name,
                            "id": created_concept_set.id,
                        }
                    )
                    concept_set_map[concept_entry.name] = int(created_concept_set.id or 0)
                continue

            taken_concept_set_names.add(concept_entry.name)
            if dry_run:
                result.created_concept_sets.append({"name": concept_entry.name, "dryRun": True})
                concept_set_map[concept_entry.name] = 0
            else:
                created_concept_set = self.client.concept_sets.create(
                    concept_entry.name,
                    concept_entry.expression,
                    description=concept_entry.description,
                )
                result.created_concept_sets.append(
                    {"name": concept_entry.name, "id": created_concept_set.id}
                )
                concept_set_map[concept_entry.name] = int(created_concept_set.id or 0)

        existing_cohorts = {item.name: item for item in self.client.cohorts.list()}
        taken_cohort_names = set(existing_cohorts)

        for cohort_entry in data.cohorts:
            existing_cohort = existing_cohorts.get(cohort_entry.name)
            if existing_cohort is not None:
                if on_conflict == "error":
                    raise ConflictError(
                        f"Cohort {cohort_entry.name!r} already exists (id {existing_cohort.id})",
                        status_code=409,
                        method="POST",
                        url=f"{self.client.api_url}/cohortdefinition",
                    )
                if on_conflict == "skip":
                    result.skipped_cohorts.append(
                        {"name": cohort_entry.name, "id": existing_cohort.id}
                    )
                    continue
                if on_conflict == "update":
                    if dry_run:
                        result.updated_cohorts.append(
                            {
                                "name": cohort_entry.name,
                                "id": existing_cohort.id,
                                "dryRun": True,
                            }
                        )
                    else:
                        updated_cohort = self.client.cohorts.update(
                            int(existing_cohort.id or 0),
                            name=cohort_entry.name,
                            description=cohort_entry.description,
                            expression=cohort_entry.expression,
                            expression_type=cohort_entry.expression_type,
                        )
                        result.updated_cohorts.append(
                            {"name": cohort_entry.name, "id": updated_cohort.id}
                        )
                    continue
                new_name = unique_name(cohort_entry.name, taken_cohort_names)
                taken_cohort_names.add(new_name)
                if dry_run:
                    result.created_cohorts.append(
                        {
                            "name": new_name,
                            "originalName": cohort_entry.name,
                            "dryRun": True,
                        }
                    )
                else:
                    created_cohort = self.client.cohorts.create(
                        new_name,
                        cohort_entry.expression,
                        description=cohort_entry.description,
                        expression_type=cohort_entry.expression_type,
                    )
                    result.created_cohorts.append(
                        {
                            "name": new_name,
                            "originalName": cohort_entry.name,
                            "id": created_cohort.id,
                        }
                    )
                continue

            taken_cohort_names.add(cohort_entry.name)
            if dry_run:
                result.created_cohorts.append({"name": cohort_entry.name, "dryRun": True})
            else:
                created_cohort = self.client.cohorts.create(
                    cohort_entry.name,
                    cohort_entry.expression,
                    description=cohort_entry.description,
                    expression_type=cohort_entry.expression_type,
                )
                result.created_cohorts.append({"name": cohort_entry.name, "id": created_cohort.id})

        result.concept_set_map = concept_set_map
        return result

    def validate(self, bundle: CohortSetBundle | dict[str, Any] | str | Path) -> dict[str, Any]:
        """Validate a bundle and return a short summary."""
        data = self._coerce_bundle(bundle)
        data.validate()
        return {
            "format": data.format,
            "formatVersion": data.format_version,
            "cohorts": len(data.cohorts),
            "conceptSets": len(data.concept_sets),
            "integrated": bool(data.integrity),
            "names": [entry.name for entry in data.cohorts],
        }

    @staticmethod
    def _coerce_bundle(
        bundle: CohortSetBundle | dict[str, Any] | str | Path,
    ) -> CohortSetBundle:
        if isinstance(bundle, CohortSetBundle):
            bundle.validate()
            return bundle
        if isinstance(bundle, (str, Path)):
            return CohortSetBundle.load(bundle)
        if isinstance(bundle, dict):
            return CohortSetBundle.from_dict(bundle)
        raise TypeError(
            f"bundle must be a CohortSetBundle, dictionary, or path, not {type(bundle)!r}"
        )

    @staticmethod
    def build_bundle(
        cohorts: Sequence[dict[str, Any]],
        *,
        atlas: dict[str, Any] | None = None,
    ) -> CohortSetBundle:
        """Build a bundle from raw ``GET /cohortdefinition/{id}`` payloads."""
        return CohortSetBundle.from_cohorts(list(cohorts), atlas=atlas)

    @staticmethod
    def make_entry(
        name: str, expression: dict[str, Any], description: str | None = None
    ) -> CohortSetEntry:
        """Create a cohort entry for a programmatically assembled bundle."""
        return CohortSetEntry(name=name, expression=expression, description=description)

    @staticmethod
    def make_concept_set_entry(
        name: str, expression: dict[str, Any], description: str | None = None
    ) -> ConceptSetEntry:
        """Create a concept-set entry for a programmatically assembled bundle."""
        return ConceptSetEntry(name=name, expression=expression, description=description)
