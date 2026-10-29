"""End-to-end Python example against a live ATLAS 3.0 deployment.

Usage:
    # ATLAS3_API_KEY must be set in the environment (or a secret manager).
    export ATLAS3_URL=https://atlas.example.org
    export ATLAS3_SOURCE=EUNOMIA
    python examples/python-quickstart.py
"""

from __future__ import annotations

import os

from atlas3 import Atlas


def main() -> None:
    url = os.environ.get("ATLAS3_URL")
    if not url:
        raise SystemExit("Set ATLAS3_URL")
    source = os.environ.get("ATLAS3_SOURCE", "EUNOMIA")

    atlas = Atlas(url, api_key=os.environ.get("ATLAS3_API_KEY"))
    if not atlas.is_authenticated:
        raise SystemExit("Set ATLAS3_API_KEY")

    print(f"Connected to {atlas.api_url} (WebAPI {atlas.version}) as {atlas.user.login}")
    print(f"Permissions: {len(atlas.permissions)}")

    sources = atlas.sources.list()
    print("Sources:", [(item.source_key, item.source_name) for item in sources])

    concepts = atlas.concepts.search(source, "diclofenac", rows=5)
    print("Concepts:", [(item.concept_id, item.concept_name) for item in concepts])

    counts = atlas.cdm_results.concept_counts(source, [1124300])
    print("Counts:", [(item.concept_id, item.values) for item in counts])

    demo = atlas.cohorts.get(1)
    print("Demo cohort:", demo.name, "concept sets:", len(demo.expression.get("ConceptSets", [])))

    plan = atlas.cohort_sets.import_(
        atlas.cohort_sets.export([1], path="/tmp/atlas3-demo-set.zip"),
        on_conflict="rename",
        dry_run=True,
    )
    print("Cohort-set dry run:", len(plan.created_cohorts), "cohorts would be created")


if __name__ == "__main__":
    main()
