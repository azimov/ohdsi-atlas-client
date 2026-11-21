from __future__ import annotations

import json

from ohdsi_atlas_client.models import Cohort, Concept, ConceptCount, Job, Page, Source


def test_cohort_parses_raw_expression_string() -> None:
    payload = {
        "id": 1,
        "name": "Demo",
        "expression": json.dumps({"ConceptSets": [], "PrimaryCriteria": {}}),
        "expressionType": "SIMPLE_EXPRESSION",
    }
    cohort = Cohort.from_api(payload)
    assert cohort.id == 1
    assert cohort.expression["PrimaryCriteria"] == {}
    assert cohort.raw_expression is not None
    dumped = cohort.model_dump()
    assert "rawExpression" not in dumped
    assert "raw_expression" not in dumped


def test_cohort_keeps_object_expression() -> None:
    cohort = Cohort.from_api({"id": 2, "name": "x", "expression": {"a": 1}})
    assert cohort.expression == {"a": 1}
    assert cohort.raw_expression is None


def test_concept_uppercase_aliases() -> None:
    concept = Concept.model_validate(
        {"CONCEPT_ID": 1, "CONCEPT_NAME": "x", "DOMAIN_ID": "Condition"}
    )
    assert concept.concept_id == 1
    assert concept.domain_id == "Condition"
    assert concept.model_dump(by_alias=True)["CONCEPT_ID"] == 1


def test_concept_count_values() -> None:
    count = ConceptCount(concept_id=1, values=[10, 11, 7, 8])
    assert count.record_count == 10
    assert count.descendant_record_count == 11
    assert count.person_count == 7
    assert count.descendant_person_count == 8
    assert ConceptCount(concept_id=2, values=[1, 2]).person_count is None


def test_source_daimon_lookup() -> None:
    source = Source.model_validate(
        {
            "sourceId": 1,
            "sourceKey": "EUNOMIA",
            "sourceName": "Eunomia",
            "daimons": [
                {"daimonType": "CDM", "tableQualifier": "cdm"},
                {"daimonType": "Vocabulary", "tableQualifier": "vocab"},
            ],
        }
    )
    assert source.key == "EUNOMIA"
    assert source.table_qualifier("CDM") == "cdm"
    assert source.table_qualifier("Vocabulary") == "vocab"
    assert source.table_qualifier("Results") is None


def test_job_status_helpers() -> None:
    job = Job.model_validate({"executionId": 1, "status": "COMPLETED", "exitStatus": "COMPLETED"})
    assert job.finished and job.succeeded
    failed = Job.model_validate({"executionId": 2, "status": "FAILED"})
    assert failed.finished and not failed.succeeded


def test_page() -> None:
    page = Page[dict].model_validate({"content": [{"id": 1}], "totalElements": 1, "totalPages": 1})
    assert page.items == [{"id": 1}]
