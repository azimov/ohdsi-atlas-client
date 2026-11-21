"""Portable cohort definition set bundles.

The bundle format is shared by the Python and R clients. It is intentionally
simple JSON so it can be produced or consumed by other OHDSI tools.

Layout (``ohdsi-atlas-client.cohort-definition-set`` version 1.0)::

    {
      "format": "ohdsi-atlas-client.cohort-definition-set",
      "formatVersion": "1.0",
      "createdAt": "2026-01-01T00:00:00Z",
      "generator": {"name": "ohdsi-atlas-client-python", "version": "0.1.0"},
      "atlas": {"url": "...", "apiUrl": "...", "webApiVersion": "3.0.0"},
      "cohorts": [
        {"name": "...", "description": "...", "expressionType": "SIMPLE_EXPRESSION",
         "expression": {...}, "conceptSetIds": [0], "checksum": "..."}
      ],
      "conceptSets": [
        {"name": "...", "description": null, "expression": {"items": [...]},
         "checksum": "..."}
      ],
      "integrity": {"algorithm": "sha256", "digest": "..."}
    }

``integrity`` is computed over the canonical JSON of the bundle without the
``integrity`` member, using sorted keys and compact separators. It is optional
on input but always written on output.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ._version import __version__
from .exceptions import BundleError
from .utils import jsonable, stable_hash, utc_now_iso, write_json

FORMAT_NAME = "ohdsi-atlas-client.cohort-definition-set"
FORMAT_VERSION = "1.0"
DEFAULT_BUNDLE_NAME = "cohort-set.json"


def _expression_concept_sets(expression: dict[str, Any]) -> list[dict[str, Any]]:
    value = expression.get("ConceptSets")
    if value is None:
        value = expression.get("conceptSets")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalise_concept_set(entry: dict[str, Any]) -> dict[str, Any]:
    expression = entry.get("expression")
    if not isinstance(expression, dict):
        expression = {"items": []}
    return {
        "name": str(entry.get("name") or "Unnamed concept set"),
        "description": entry.get("description"),
        "expression": expression,
    }


def _concept_set_checksum(entry: dict[str, Any]) -> str:
    return stable_hash(
        {
            "name": entry.get("name"),
            "expression": entry.get("expression"),
        }
    )


def _slug(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._").lower()
    return cleaned[:80] or fallback


@dataclass(slots=True)
class ConceptSetEntry:
    """A concept set carried by a bundle."""

    name: str
    expression: dict[str, Any]
    description: str | None = None
    checksum: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BundleError("A concept set entry has an empty name")
        if not isinstance(self.expression, dict):
            raise BundleError(f"Concept set {self.name!r} has a non-object expression")
        if self.checksum is None:
            self.checksum = _concept_set_checksum(self.to_dict(with_checksum=False))

    def to_dict(self, *, with_checksum: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "expression": self.expression,
        }
        if with_checksum and self.checksum:
            payload["checksum"] = self.checksum
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConceptSetEntry:
        if not isinstance(payload, dict):
            raise BundleError("Concept set entries must be JSON objects")
        expression = payload.get("expression")
        if not isinstance(expression, dict):
            raise BundleError(
                f"Concept set {payload.get('name')!r} is missing an expression object"
            )
        return cls(
            name=str(payload.get("name") or ""),
            description=payload.get("description"),
            expression=expression,
            checksum=payload.get("checksum"),
        )


@dataclass(slots=True)
class CohortSetEntry:
    """A cohort definition carried by a bundle."""

    name: str
    expression: dict[str, Any]
    description: str | None = None
    expression_type: str = "SIMPLE_EXPRESSION"
    concept_set_ids: list[int] = field(default_factory=list)
    checksum: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise BundleError("A cohort entry has an empty name")
        if not isinstance(self.expression, dict):
            raise BundleError(f"Cohort {self.name!r} has a non-object expression")
        if not self.concept_set_ids:
            self.concept_set_ids = [
                int(item["id"])
                for item in _expression_concept_sets(self.expression)
                if isinstance(item.get("id"), int)
            ]
        if self.checksum is None:
            self.checksum = stable_hash(self.expression)

    def to_dict(self, *, with_checksum: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "expressionType": self.expression_type,
            "expression": self.expression,
            "conceptSetIds": self.concept_set_ids,
        }
        if with_checksum and self.checksum:
            payload["checksum"] = self.checksum
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CohortSetEntry:
        if not isinstance(payload, dict):
            raise BundleError("Cohort entries must be JSON objects")
        expression = payload.get("expression")
        if not isinstance(expression, dict):
            raise BundleError(f"Cohort {payload.get('name')!r} is missing an expression object")
        return cls(
            name=str(payload.get("name") or ""),
            description=payload.get("description"),
            expression=expression,
            expression_type=str(payload.get("expressionType") or "SIMPLE_EXPRESSION"),
            concept_set_ids=[int(value) for value in payload.get("conceptSetIds") or []],
            checksum=payload.get("checksum"),
        )


@dataclass(slots=True)
class CohortSetBundle:
    """A portable set of cohort definitions and their concept sets."""

    cohorts: list[CohortSetEntry]
    concept_sets: list[ConceptSetEntry] = field(default_factory=list)
    atlas: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    generator: dict[str, str] = field(
        default_factory=lambda: {"name": "ohdsi-atlas-client-python", "version": __version__}
    )
    format: str = FORMAT_NAME
    format_version: str = FORMAT_VERSION
    integrity: dict[str, str] | None = None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_cohorts(
        cls,
        cohorts: list[dict[str, Any]],
        *,
        atlas: dict[str, Any] | None = None,
    ) -> CohortSetBundle:
        """Build a bundle from raw WebAPI cohort payloads.

        Each payload is the response of ``GET /cohortdefinition/{id}``; its
        ``expression`` may be a JSON string or an object.
        """
        entries: list[CohortSetEntry] = []
        concept_sets: list[ConceptSetEntry] = []
        seen: set[tuple[str, str]] = set()

        for payload in cohorts:
            expression = payload.get("expression")
            if isinstance(expression, str):
                try:
                    expression = json.loads(expression) if expression else {}
                except json.JSONDecodeError as exc:
                    raise BundleError(
                        f"Cohort {payload.get('name')!r} contains invalid expression JSON"
                    ) from exc
            if not isinstance(expression, dict):
                raise BundleError(f"Cohort {payload.get('name')!r} has no expression object")
            entry = CohortSetEntry(
                name=str(payload.get("name") or "Unnamed cohort"),
                description=payload.get("description"),
                expression=expression,
                expression_type=str(payload.get("expressionType") or "SIMPLE_EXPRESSION"),
            )
            entries.append(entry)
            for raw in _expression_concept_sets(expression):
                normalised = _normalise_concept_set(raw)
                key = (normalised["name"], _concept_set_checksum(normalised))
                if key in seen:
                    continue
                seen.add(key)
                concept_sets.append(ConceptSetEntry.from_dict(normalised))

        return cls(
            cohorts=entries,
            concept_sets=concept_sets,
            atlas=atlas or {},
            integrity=None,
        ).with_integrity()

    # -- serialisation ------------------------------------------------------

    def to_dict(self, *, with_integrity: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "format": self.format,
            "formatVersion": self.format_version,
            "createdAt": self.created_at,
            "generator": self.generator,
            "atlas": self.atlas,
            "cohorts": [entry.to_dict() for entry in self.cohorts],
            "conceptSets": [entry.to_dict() for entry in self.concept_sets],
        }
        if with_integrity:
            digest = stable_hash(payload)
            payload["integrity"] = {"algorithm": "sha256", "digest": digest}
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CohortSetBundle:
        if not isinstance(payload, dict):
            raise BundleError("A cohort set bundle must be a JSON object")
        if payload.get("format") not in (None, FORMAT_NAME):
            raise BundleError(
                f"Unsupported bundle format {payload.get('format')!r}; expected {FORMAT_NAME!r}"
            )
        version = str(payload.get("formatVersion") or FORMAT_VERSION)
        if version.split(".")[0] != FORMAT_VERSION.split(".")[0]:
            raise BundleError(
                f"Unsupported bundle formatVersion {version!r}; "
                f"this client supports {FORMAT_VERSION}"
            )
        cohorts_raw = payload.get("cohorts")
        if not isinstance(cohorts_raw, list) or not cohorts_raw:
            raise BundleError("A cohort set bundle must contain at least one cohort")
        concept_sets_raw = payload.get("conceptSets") or []
        if not isinstance(concept_sets_raw, list):
            raise BundleError("conceptSets must be a JSON array")
        bundle = cls(
            cohorts=[CohortSetEntry.from_dict(item) for item in cohorts_raw],
            concept_sets=[ConceptSetEntry.from_dict(item) for item in concept_sets_raw],
            atlas=dict(payload.get("atlas") or {}),
            created_at=str(payload.get("createdAt") or utc_now_iso()),
            generator=dict(payload.get("generator") or {}),
            format=str(payload.get("format") or FORMAT_NAME),
            format_version=version,
            integrity=payload.get("integrity"),
        )
        bundle.validate()
        return bundle

    def with_integrity(self) -> CohortSetBundle:
        """Recompute and store the integrity digest."""
        payload = self.to_dict(with_integrity=False)
        self.integrity = {"algorithm": "sha256", "digest": stable_hash(payload)}
        return self

    def validate(self, *, check_integrity: bool = True) -> None:
        """Validate the bundle structure, names, and optional integrity digest."""
        if not self.cohorts:
            raise BundleError("A cohort set bundle must contain at least one cohort")
        names = [entry.name for entry in self.cohorts]
        if len(names) != len(set(names)):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            raise BundleError(f"Duplicate cohort names in bundle: {duplicates}")
        for cohort in self.cohorts:
            if not isinstance(cohort.expression, dict):
                raise BundleError(f"Cohort {cohort.name!r} has an invalid expression")
            if not cohort.expression:
                raise BundleError(f"Cohort {cohort.name!r} has an empty expression")
        for concept_set in self.concept_sets:
            if not isinstance(concept_set.expression, dict):
                raise BundleError(f"Concept set {concept_set.name!r} has an invalid expression")
        if check_integrity and self.integrity:
            expected = stable_hash(self.to_dict(with_integrity=False))
            actual = str(self.integrity.get("digest") or "")
            if actual and actual != expected:
                raise BundleError(
                    "Bundle integrity check failed: the file was modified after export"
                )

    # -- files --------------------------------------------------------------

    def save(
        self,
        path: str | Path,
        *,
        as_zip: bool | None = None,
        include_component_files: bool = True,
    ) -> Path:
        """Write the bundle as JSON, ZIP, or a directory.

        ``path`` ending in ``.zip`` produces a ZIP archive. A path with no
        suffix produces a directory containing ``cohort-set.json`` and
        per-cohort/per-concept-set JSON files. Everything else is written as a
        single JSON file.
        """
        destination = Path(path)
        bundle_payload = self.to_dict()
        suffix = destination.suffix.lower()
        if as_zip is None:
            as_zip = suffix == ".zip"
        if as_zip:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    DEFAULT_BUNDLE_NAME,
                    json.dumps(bundle_payload, indent=2, ensure_ascii=False) + "\n",
                )
                if include_component_files:
                    self._write_component_files(
                        lambda name, content: archive.writestr(name, content)
                    )
            return destination
        if (
            destination.suffix.lower() in {".json", ""}
            and destination.exists()
            and destination.is_dir()
        ):
            return self.save_directory(destination)
        if suffix == ".json" or suffix:
            return write_json(destination, bundle_payload)
        return self.save_directory(destination)

    def save_directory(self, directory: str | Path) -> Path:
        """Write the canonical JSON plus one file per cohort/concept set."""
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        write_json(root / DEFAULT_BUNDLE_NAME, self.to_dict())

        def writer(name: str, content: str) -> None:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        self._write_component_files(writer)
        return root / DEFAULT_BUNDLE_NAME

    def _write_component_files(self, writer: Any) -> None:
        for index, cohort in enumerate(self.cohorts, start=1):
            name = f"cohorts/{index:03d}-{_slug(cohort.name, 'cohort')}.json"
            writer(
                name,
                json.dumps(cohort.to_dict(), indent=2, ensure_ascii=False) + "\n",
            )
        for index, concept_set in enumerate(self.concept_sets, start=1):
            name = f"concept-sets/{index:03d}-{_slug(concept_set.name, 'concept-set')}.json"
            writer(
                name,
                json.dumps(concept_set.to_dict(), indent=2, ensure_ascii=False) + "\n",
            )

    @classmethod
    def load(cls, path: str | Path) -> CohortSetBundle:
        """Load a bundle from JSON, ZIP, or directory."""
        source = Path(path)
        if not source.exists():
            raise BundleError(f"Bundle not found: {source}")
        if source.is_dir():
            canonical = source / DEFAULT_BUNDLE_NAME
            if canonical.exists():
                return cls.from_dict(json.loads(canonical.read_text(encoding="utf-8")))
            raise BundleError(f"{source} does not contain {DEFAULT_BUNDLE_NAME}")
        if source.suffix.lower() == ".zip":
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                candidate = DEFAULT_BUNDLE_NAME
                if candidate not in names:
                    candidates = [name for name in names if name.endswith(".json")]
                    if len(candidates) != 1:
                        raise BundleError(
                            f"{source} must contain {DEFAULT_BUNDLE_NAME} or exactly one JSON file"
                        )
                    candidate = candidates[0]
                return cls.from_dict(json.loads(archive.read(candidate).decode("utf-8")))
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BundleError(f"{source} is not valid JSON: {exc}") from exc
        return cls.from_dict(payload)


@dataclass(slots=True)
class ImportResult:
    """Outcome of importing a cohort definition set."""

    created_cohorts: list[dict[str, Any]] = field(default_factory=list)
    updated_cohorts: list[dict[str, Any]] = field(default_factory=list)
    skipped_cohorts: list[dict[str, Any]] = field(default_factory=list)
    created_concept_sets: list[dict[str, Any]] = field(default_factory=list)
    updated_concept_sets: list[dict[str, Any]] = field(default_factory=list)
    skipped_concept_sets: list[dict[str, Any]] = field(default_factory=list)
    concept_set_map: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return cast("dict[str, Any]", jsonable(self))

    @property
    def cohort_count(self) -> int:
        return len(self.created_cohorts) + len(self.updated_cohorts)
