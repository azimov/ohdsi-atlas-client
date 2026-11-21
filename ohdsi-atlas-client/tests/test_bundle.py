from __future__ import annotations

import json
from pathlib import Path

import pytest

from ohdsi_atlas_client.bundle import (
    CohortSetBundle,
    CohortSetEntry,
    ConceptSetEntry,
    ImportResult,
)
from ohdsi_atlas_client.exceptions import BundleError

COHORT = {
    "id": 1,
    "name": "Demo cohort",
    "description": "A demo",
    "expressionType": "SIMPLE_EXPRESSION",
    "expression": json.dumps(
        {
            "ConceptSets": [
                {
                    "id": 0,
                    "name": "diclofenac",
                    "expression": {
                        "items": [
                            {
                                "concept": {"CONCEPT_ID": 1124300, "CONCEPT_NAME": "Diclofenac"},
                                "isExcluded": False,
                                "includeDescendants": True,
                                "includeMapped": False,
                            }
                        ]
                    },
                }
            ],
            "PrimaryCriteria": {
                "CriteriaList": [{"DrugEra": {"CodesetId": 0}}],
                "ObservationWindow": {"PriorDays": 365, "PostDays": 0},
                "PrimaryCriteriaLimit": {"Type": "First"},
            },
        }
    ),
}


def test_build_bundle_from_raw_payload() -> None:
    bundle = CohortSetBundle.from_cohorts([COHORT], atlas={"url": "https://x"})
    assert len(bundle.cohorts) == 1
    assert bundle.cohorts[0].concept_set_ids == [0]
    assert bundle.cohorts[0].expression["ConceptSets"][0]["name"] == "diclofenac"
    assert len(bundle.concept_sets) == 1
    assert bundle.concept_sets[0].name == "diclofenac"
    assert bundle.integrity is not None


def test_duplicate_embedded_concept_sets_are_deduplicated() -> None:
    second = dict(COHORT)
    second["name"] = "Second"
    bundle = CohortSetBundle.from_cohorts([COHORT, second])
    assert len(bundle.concept_sets) == 1


def test_bundle_roundtrip_json(tmp_path: Path) -> None:
    bundle = CohortSetBundle.from_cohorts([COHORT])
    path = tmp_path / "bundle.json"
    bundle.save(path)
    loaded = CohortSetBundle.load(path)
    assert loaded.cohorts[0].name == "Demo cohort"
    assert loaded.integrity == bundle.integrity
    loaded.validate()


def test_bundle_roundtrip_zip_and_dir(tmp_path: Path) -> None:
    bundle = CohortSetBundle.from_cohorts([COHORT])
    zip_path = tmp_path / "bundle.zip"
    bundle.save(zip_path)
    assert CohortSetBundle.load(zip_path).cohorts[0].name == "Demo cohort"

    directory = tmp_path / "bundle"
    bundle.save(directory)
    assert (directory / "cohort-set.json").exists()
    assert (directory / "cohorts").is_dir()
    assert CohortSetBundle.load(directory).cohorts[0].name == "Demo cohort"


def test_integrity_tampering_is_detected(tmp_path: Path) -> None:
    bundle = CohortSetBundle.from_cohorts([COHORT])
    payload = bundle.to_dict()
    payload["cohorts"][0]["name"] = "Tampered"
    with pytest.raises(BundleError):
        CohortSetBundle.from_dict(payload)


def test_duplicate_cohort_names_rejected() -> None:
    with pytest.raises(BundleError):
        CohortSetBundle(
            cohorts=[
                CohortSetEntry(name="same", expression={"x": 1}),
                CohortSetEntry(name="same", expression={"x": 2}),
            ]
        ).validate()


def test_empty_bundle_rejected() -> None:
    with pytest.raises(BundleError):
        CohortSetBundle.from_dict({"format": "ohdsi-atlas-client.cohort-definition-set", "cohorts": []})


def test_import_result_serialises() -> None:
    result = ImportResult(created_cohorts=[{"name": "x", "id": 1}])
    assert result.to_dict()["created_cohorts"][0]["id"] == 1
    assert result.cohort_count == 1


def test_concept_set_entry_checksum_is_stable() -> None:
    expression = {"items": []}
    first = ConceptSetEntry(name="x", expression=expression)
    second = ConceptSetEntry(name="x", expression=expression)
    assert first.checksum == second.checksum
