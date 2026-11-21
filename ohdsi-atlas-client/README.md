# ohdsi-atlas-client

Modern Python client for **OHDSI ATLAS 3.0** and **WebAPI 3.0**.

```bash
pip install ohdsi-atlas-client
# optional: Circepy models and OS keyring storage
pip install "ohdsi-atlas-client[circe,keyring]"
```

## Quick start

```python
import os

from ohdsi_atlas_client import Atlas

atlas = Atlas(
    "https://atlas.example.org",
    api_key=os.environ["OHDSI_ATLAS_CLIENT_API_KEY"],
)

# Or store a key for later:
# atlas = Atlas("https://atlas.example.org")
# atlas.login(os.environ["OHDSI_ATLAS_CLIENT_API_KEY"])

print(atlas.version)
for source in atlas.sources.list():
    print(source.source_key, source.source_name)

concepts = atlas.concepts.search("EUNOMIA", "diclofenac", rows=10)
counts = atlas.cdm_results.concept_counts("EUNOMIA", [1124300])
```

## Concept sets

```python
concept_set = atlas.concept_sets.create_from_concepts(
    "Diclofenac ingredients",
    [1124300],
    source_key="EUNOMIA",
    include_descendants=True,
)
print(concept_set.id)
print(atlas.concept_sets.resolve(concept_set.id, source_key="EUNOMIA"))
```

## Cohorts

```python
cohort = atlas.cohorts.create("My cohort", expression)
print(atlas.cohorts.sql(expression))
job = atlas.cohorts.generate(cohort.id, "EUNOMIA")
atlas.jobs.wait(job, timeout=600)
```

Circе expressions can be dictionaries or Circepy models:

```python
from circe import CohortExpression

expression = CohortExpression.model_validate(payload)
cohort = atlas.cohorts.create("From Circepy", expression)
```

## Cohort definition sets

```python
# Export every readable cohort and its embedded concept sets.
atlas.cohort_sets.export(path="my-cohorts.zip")

# Import into another ATLAS instance. Conflict policy: error | skip | rename | update.
result = atlas.cohort_sets.import_("my-cohorts.zip", on_conflict="rename")
print(result.created_cohorts)
```

The bundle format is documented in the repository's `docs/cohort-sets.md` and
is shared byte-for-byte (schema-wise) with the R package `OhdsiAtlasClient`.

## All endpoints

```python
atlas.call("cohortdefinition.generateCohort", id=1, sourceKey="EUNOMIA")
atlas.request("GET", "/cohortdefinition/1/info")
print(atlas.endpoints.describe())
```

## Authentication

Only personal API keys are supported. Every request sends `X-API-KEY`. There is
no username/password or JWT login.

Keys come from `Atlas(..., api_key=...)`, `OHDSI_ATLAS_CLIENT_API_KEY`, or a key stored by
`atlas.login(...)`. `login()` validates the key against `/user/me` before
persisting it. Keys are stored in the OS keyring when available, otherwise in a
`0600` credentials file.

## Requirements

* Python 3.10+
* ATLAS / WebAPI 3.0.0+ (WebAPI 2.x is rejected at discovery)

## License

Apache License 2.0.
