from __future__ import annotations

from typing import Any

import pytest

from ohdsi_atlas_client.endpoints import EndpointCatalog


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self.calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}


def test_catalog_has_all_groups() -> None:
    catalog = EndpointCatalog.load()
    assert len(catalog) >= 300
    assert "cohortdefinition.generateCohort" in catalog
    assert "vocabulary.executeSearch.3" in catalog
    described = catalog.describe()
    assert "WebAPI 3.0" in described
    assert "cohortdefinition" in described


def test_call_substitutes_path_and_query() -> None:
    catalog = EndpointCatalog.load()
    client = FakeClient()
    catalog.call(
        client,
        "cohortdefinition.generateCohort",
        id=1,
        sourceKey="EUNOMIA",
        demographic=False,
    )
    call = client.calls[0]
    assert call["method"] == "GET"
    assert call["path"] == "/cohortdefinition/1/generate/EUNOMIA"
    assert call["params"] == {"demographic": False}


def test_call_accepts_query_mapping_and_body() -> None:
    catalog = EndpointCatalog.load()
    client = FakeClient()
    catalog.call(
        client,
        "vocabulary.executeSearch",
        sourceKey="EUNOMIA",
        body={"QUERY": "x"},
    )
    call = client.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/vocabulary/EUNOMIA/search"
    assert call["json"] == {"QUERY": "x"}


def test_call_allows_query_named_parameter() -> None:
    catalog = EndpointCatalog.load()
    client = FakeClient()
    catalog.call(
        client,
        "vocabulary.executeSearch.3",
        sourceKey="EUNOMIA",
        query="diabetes",
        rows=5,
    )
    call = client.calls[0]
    assert call["params"] == {"query": "diabetes", "rows": 5}


def test_missing_path_parameter_raises() -> None:
    catalog = EndpointCatalog.load()
    with pytest.raises(TypeError, match="sourceKey"):
        catalog.call(FakeClient(), "cohortdefinition.generateCohort", id=1)


def test_unknown_operation_suggests() -> None:
    catalog = EndpointCatalog.load()
    with pytest.raises(KeyError, match="cohortdefinition"):
        catalog.get("cohortdefinition.nope")


def test_find_filters() -> None:
    catalog = EndpointCatalog.load()
    endpoints = catalog.find(group="cohortdefinition", method="GET")
    assert endpoints
    assert all(endpoint.method == "GET" for endpoint in endpoints)
    assert all(endpoint.group == "cohortdefinition" for endpoint in endpoints)
