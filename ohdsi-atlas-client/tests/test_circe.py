from __future__ import annotations

import pytest

circe = pytest.importorskip("circe")

from ohdsi_atlas_client import circe as adapter  # noqa: E402

EXPRESSION = {
    "cdmVersionRange": ">=5.0.0",
    "ConceptSets": [
        {
            "id": 0,
            "name": "diclofenac",
            "expression": {
                "items": [
                    {
                        "concept": {
                            "CONCEPT_ID": 1124300,
                            "CONCEPT_NAME": "Diclofenac",
                            "DOMAIN_ID": "Drug",
                        },
                        "isExcluded": False,
                        "includeDescendants": True,
                        "includeMapped": False,
                    }
                ]
            },
        }
    ],
    "PrimaryCriteria": {
        "CriteriaList": [{"DrugEra": {"CodesetId": 0, "First": True}}],
        "ObservationWindow": {"PriorDays": 365, "PostDays": 0},
        "PrimaryCriteriaLimit": {"Type": "First"},
    },
    "QualifiedLimit": {"Type": "First"},
    "ExpressionLimit": {"Type": "First"},
    "InclusionRules": [],
    "CensoringCriteria": [],
    "CollapseSettings": {"CollapseType": "ERA", "EraPad": 0},
    "CensorWindow": {},
}


def test_circe_is_available() -> None:
    assert adapter.CIRCE_AVAILABLE


def test_model_validate_preserves_cdm_version_range() -> None:
    model = adapter.to_circe_cohort(EXPRESSION)
    assert model.cdm_version_range == ">=5.0.0"


def test_from_circe_uses_webapi_aliases() -> None:
    model = adapter.to_circe_cohort(EXPRESSION)
    payload = adapter.from_circe(model)
    assert payload["ConceptSets"][0]["id"] == 0
    concept = payload["ConceptSets"][0]["expression"]["items"][0]["concept"]
    assert concept["CONCEPT_ID"] == 1124300
    assert "concept_id" not in concept
    assert "cdmVersionRange" in payload


def test_concept_set_conversion_uses_aliases() -> None:
    model = adapter.to_circe_concept_set(EXPRESSION["ConceptSets"][0])
    payload = adapter.from_circe(model)
    assert payload["items"][0]["concept"]["CONCEPT_ID"] == 1124300
    assert payload["items"][0]["includeDescendants"] is True


def test_validate_cohort_returns_warnings() -> None:
    warnings = adapter.validate_cohort(EXPRESSION)
    assert isinstance(warnings, list)


def test_validate_cohort_detects_silent_criteria_substitution() -> None:
    bad = {
        "ConceptSets": [],
        "PrimaryCriteria": {
            "CriteriaList": [{"DrugEra": {"CodesetId": 0.7}}],
            "ObservationWindow": {"PriorDays": 0, "PostDays": 0},
            "PrimaryCriteriaLimit": {"Type": "First"},
        },
        "QualifiedLimit": {"Type": "First"},
        "ExpressionLimit": {"Type": "First"},
        "InclusionRules": [],
        "CensoringCriteria": [],
        "CollapseSettings": {"CollapseType": "ERA", "EraPad": 0},
        "CensorWindow": {},
    }
    with pytest.raises(ValueError, match="silently changed"):
        adapter.validate_cohort(bad)


def test_local_sql_generation() -> None:
    sql = adapter.cohort_sql(
        EXPRESSION,
        {"cdm_schema": "cdm", "vocabulary_schema": "vocab", "cohort_id": 1},
    )
    assert "CONCEPT" in sql
    assert len(sql) > 100
