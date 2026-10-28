"""Live integration tests against an ATLAS 3.0 deployment.

These tests are skipped unless ``ATLAS3_TEST_URL`` is set. They create resources
with a random suffix and remove them in a ``finally`` block. Set
``ATLAS3_TEST_USERNAME`` and ``ATLAS3_TEST_PASSWORD`` for database login, or
``ATLAS3_TEST_API_KEY`` to use an existing key.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

from atlas3 import Atlas, CredentialStore
from atlas3.bundle import CohortSetBundle

pytestmark = pytest.mark.integration

URL = os.environ.get("ATLAS3_TEST_URL")
USERNAME = os.environ.get("ATLAS3_TEST_USERNAME")
PASSWORD = os.environ.get("ATLAS3_TEST_PASSWORD")
API_KEY = os.environ.get("ATLAS3_TEST_API_KEY")
SOURCE = os.environ.get("ATLAS3_TEST_SOURCE", "EUNOMIA")

if not URL:
    pytest.skip("Set ATLAS3_TEST_URL to run integration tests", allow_module_level=True)


@pytest.fixture(scope="module")
def client() -> Atlas:
    store = CredentialStore(config_dir=tempfile.mkdtemp(), use_keyring=False)
    atlas = Atlas(
        str(URL),
        api_key=API_KEY,
        credential_store=store,
        use_keyring=False,
    )
    if not API_KEY:
        if not USERNAME or not PASSWORD:
            pytest.skip("Set ATLAS3_TEST_USERNAME/PASSWORD or ATLAS3_TEST_API_KEY")
        atlas.login(
            USERNAME,
            PASSWORD,
            key_name=f"atlas3-pytest-{uuid.uuid4().hex[:8]}",
            store=False,
        )
    yield atlas
    if not API_KEY:
        atlas.logout(revoke=True)
    atlas.close()


def test_discovery_and_identity(client: Atlas) -> None:
    assert client.version.startswith("3.")
    assert client.api_url.endswith("/WebAPI") or "/WebAPI" in client.api_url
    me = client.whoami()
    assert me.user.login


def test_sources_and_vocabulary(client: Atlas) -> None:
    sources = client.sources.list()
    assert sources
    assert any(source.source_key == SOURCE for source in sources)
    concepts = client.concepts.search(SOURCE, "diclofenac", rows=5)
    assert concepts
    assert all(concept.concept_id for concept in concepts)


def test_concept_counts(client: Atlas) -> None:
    counts = client.cdm_results.concept_counts(SOURCE, [1124300])
    assert counts
    assert counts[0].concept_id == 1124300
    assert counts[0].record_count is not None


def test_concept_set_crud(client: Atlas) -> None:
    name = f"atlas3-pytest-cs-{uuid.uuid4().hex[:8]}"
    created = client.concept_sets.create_from_concepts(
        name,
        [1124300],
        source_key=SOURCE,
        include_descendants=True,
        description="created by atlas3 integration tests",
    )
    try:
        assert created.id is not None
        expression = client.concept_sets.expression(created.id)
        assert expression.items and expression.items[0].include_descendants
        assert client.concepts.count_included(SOURCE, expression) > 0
        resolved = client.concepts.resolve(SOURCE, expression)
        assert 1124300 in resolved
    finally:
        client.concept_sets.delete(created.id)


def test_cohort_crud_and_sql(client: Atlas) -> None:
    demo = client.cohorts.get(1)
    name = f"atlas3-pytest-cohort-{uuid.uuid4().hex[:8]}"
    cohort = client.cohorts.create(
        name,
        demo.expression,
        description="created by atlas3 integration tests",
    )
    try:
        assert cohort.id is not None
        fetched = client.cohorts.get(cohort.id)
        assert fetched.name == name
        assert fetched.expression["PrimaryCriteria"]
        sql = client.cohorts.sql(fetched.expression)
        assert "CONCEPT" in sql.upper()
        check = client.cohorts.check(fetched.expression)
        assert isinstance(check, dict)
        updated = client.cohorts.update(
            cohort.id, description="updated by atlas3 integration tests"
        )
        assert updated.description.startswith("updated")
    finally:
        client.cohorts.delete(cohort.id)


def test_cohort_set_export_and_dry_run_import(client: Atlas, tmp_path: Path) -> None:
    bundle = client.cohort_sets.export([1], path=tmp_path / "set.zip")
    assert isinstance(bundle, CohortSetBundle)
    assert bundle.cohorts
    assert bundle.concept_sets
    loaded = CohortSetBundle.load(tmp_path / "set.zip")
    plan = client.cohort_sets.import_(loaded, on_conflict="rename", dry_run=True)
    assert plan.dry_run
    assert plan.created_cohorts


def test_jobs_and_catalog(client: Atlas) -> None:
    jobs = client.jobs.list(size=5)
    assert jobs.content is not None
    info = client.call("cohortdefinition.getCohortDefinitionRaw", id=1)
    assert info["name"]
    assert len(client.endpoints) >= 300
