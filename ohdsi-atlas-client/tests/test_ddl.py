"""Regression tests for the DDL and CDM-results resources.

The DDL endpoints were originally called as ``GET /ddl/cdm`` with CDM-shaped
parameters. WebAPI 3.0 has no such endpoint (it returns 404), and the three
that do exist take a *results* schema. They also return plain SQL text, so a
request that only advertises ``Accept: application/json`` makes WebAPI answer
HTTP 500. These tests pin the corrected contract.
"""

from __future__ import annotations

from typing import Any

import httpx

from ohdsi_atlas_client import AtlasClient
from ohdsi_atlas_client.discovery import Discovery
from ohdsi_atlas_client.endpoints import EndpointCatalog

DDL_SQL = "CREATE TABLE IF NOT EXISTS results.cohort (cohort_definition_id int);"


def _discovery() -> Discovery:
    return Discovery(
        input_url="https://host/atlas",
        api_url="https://host/WebAPI",
        atlas_url="https://host/atlas",
        version="3.0.0",
    )


def _client(handler: Any) -> AtlasClient:
    client = AtlasClient(
        "https://host/atlas",
        api_key="test-key",
        discovery=_discovery(),
        use_keyring=False,
    )
    client._http._client.close()
    client._http._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _recording_client() -> tuple[AtlasClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=DDL_SQL, headers={"content-type": "text/plain"})

    return _client(handler), seen


def test_results_ddl_uses_real_path_and_schema_param() -> None:
    client, seen = _recording_client()
    sql = client.ddl.results(
        dialect="postgresql", schema="cdm_results", vocab_schema="vocab"
    )

    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/WebAPI/ddl/results"
    params = dict(request.url.params)
    # The server parameter is `schema`, not `cdmSchema`.
    assert params["schema"] == "cdm_results"
    assert params["dialect"] == "postgresql"
    assert params["vocabSchema"] == "vocab"
    for removed in ("cdmSchema", "resultsSchema", "cdmVersion"):
        assert removed not in params
    assert sql == DDL_SQL


def test_achilles_ddl_uses_results_schema_params() -> None:
    client, seen = _recording_client()
    client.ddl.achilles(dialect="postgresql", schema="results", vocab_schema="vocab")

    request = seen[0]
    assert request.url.path == "/WebAPI/ddl/achilles"
    params = dict(request.url.params)
    assert params["schema"] == "results"
    assert params["vocabSchema"] == "vocab"
    assert "resultsSchema" not in params
    assert "cdmVersion" not in params


def test_cem_results_ddl_endpoint() -> None:
    client, seen = _recording_client()
    client.ddl.cem_results(dialect="postgresql", schema="results")

    assert seen[0].url.path == "/WebAPI/ddl/cemresults"
    assert dict(seen[0].url.params)["schema"] == "results"


def test_ddl_requests_accept_text_not_only_json() -> None:
    client, seen = _recording_client()
    client.ddl.results(schema="results")
    client.ddl.achilles(schema="results")
    client.ddl.cem_results(schema="results")

    for request in seen:
        accept = request.headers["accept"]
        assert "text/plain" in accept, f"{request.url.path} must accept SQL text"


def test_no_cdm_ddl_method_remains() -> None:
    client, _ = _recording_client()
    assert not hasattr(client.ddl, "cdm")


def test_every_ddl_typed_call_matches_catalog() -> None:
    """Each typed DDL method must correspond to a real catalog operation."""
    catalog = EndpointCatalog.load()
    paths = {endpoint.path for endpoint in catalog}

    assert "/ddl/results" in paths
    assert "/ddl/achilles" in paths
    assert "/ddl/cemresults" in paths
    assert "/ddl/cdm" not in paths


def test_concept_counts_and_alias_agree() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/WebAPI/cdmresults/EUNOMIA/conceptRecordCount"
        return httpx.Response(200, json=[{"201826": [10, 20, 10, 20]}])

    client = _client(handler)
    canonical = client.cdm_results.concept_counts("EUNOMIA", [201826])
    alias = client.concepts.counts("EUNOMIA", [201826])

    assert canonical[0].concept_id == 201826
    assert canonical[0].values == [10, 20, 10, 20]
    assert [item.values for item in alias] == [canonical[0].values]


def test_jobs_page_metadata_is_read_from_nested_page() -> None:
    """WebAPI 3.0 nests page metadata under ``page``; totals must not be lost."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"executionId": 49, "status": "COMPLETED"}],
                "page": {"size": 20, "number": 0, "totalElements": 49, "totalPages": 3},
            },
        )

    client = _client(handler)
    page = client.jobs.list()

    assert page.total_elements == 49
    assert page.total_pages == 3
    assert page.size == 20
    assert len(page.content) == 1


def test_jobs_page_reads_flat_metadata_too() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"executionId": 1}], "totalElements": 1, "totalPages": 1},
        )

    page = _client(handler).jobs.list()
    assert page.total_elements == 1
