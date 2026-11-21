# OhdsiAtlasClient

Python (`ohdsi_atlas_client`) and R (`OhdsiAtlasClient`) clients for **OHDSI ATLAS 3.0** and
**WebAPI 3.0**.

```bash
pip install ohdsi-atlas-client            # Python
```

```r
# R: not yet on CRAN
remotes::install_github("OHDSI/OhdsiAtlasClient", subdir = "OhdsiAtlasClient")
```

Both clients discover WebAPI from an ATLAS URL, refuse servers older than
WebAPI 3.0, and authenticate with personal API keys.

## Find what you need

| I want to... | Go to |
|---|---|
| Get something working in two minutes | [Quick start](#quick-start) |
| Do one specific thing (search a concept, make a cohort, generate it) | [Recipes](recipes.md) |
| Look up a method by name | [API reference](reference.md) |
| Move an existing script off `ROhdsiWebApi` | [R: migrating from ROhdsiWebApi](migrating-from-rohdsiwebapi.md) |
| Know exactly what is and is not implemented | [Python / R parity](parity.md) |
| Call an endpoint that has no typed method | [Endpoint coverage](endpoints.md) |
| Set up or store an API key | [Authentication](authentication.md) |
| Configure one database with several CDMs | [Database and CDM configuration](configuration.md) |
| Move cohorts between servers | [Cohort definition sets](cohort-sets.md) |
| Understand why the design is what it is | [Architecture](architecture.md) |
| Understand a puzzling server response | [Troubleshooting](troubleshooting.md) |

## Quick start

Connect, then use the resource namespaces. The two languages mirror each
other: Python uses `snake_case`, R uses `camelCase`.

```python
import os
from ohdsi_atlas_client import Atlas

atlas = Atlas("https://atlas.example.org", api_key=os.environ["OHDSI_ATLAS_CLIENT_API_KEY"])
print(atlas.version)                       # e.g. "3.0.0"
print([s.source_key for s in atlas.sources.list()])
```

```r
library(OhdsiAtlasClient)

atlas <- connectAtlas(
  "https://atlas.example.org",
  apiKey = Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY")
)
atlas$version
vapply(atlas$sources$list(), `[[`, "", "sourceKey")
```

That is the whole setup. The rest of the docs assume `atlas` already exists.

## How to read a method name

| Python | R | Meaning |
|---|---|---|
| `atlas.sources.list()` | `atlas$sources$list()` | `sources` is the resource namespace |
| `atlas.cdm_results.concept_counts(...)` | `atlas$cdmResults$conceptCounts(...)` | `snake_case` -> `camelCase`, same order |
| `atlas.concept_sets.create_from_concepts(...)` | `atlas$conceptSets$createFromConcepts(...)` | |

Anything a typed method does not cover is still reachable:

```python
atlas.request("GET", "/cohortdefinition/1/info")
atlas.call("cohortdefinition.getCohortDefinitionRaw", id=1)
```

```r
atlas$request("GET", "/cohortdefinition/1/info")
atlas$call("cohortdefinition.getCohortDefinitionRaw", id = 1)
```

## R vignettes

The R package ships two vignettes, also available as articles:

```r
vignette("ohdsi_atlas_client", package = "OhdsiAtlasClient")                       # getting started
vignette("migrating-from-rohdsiwebapi", package = "OhdsiAtlasClient")  # switch from ROhdsiWebApi
```
