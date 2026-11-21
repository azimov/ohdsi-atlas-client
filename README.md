# OhdsiAtlasClient

[![Build Status](https://github.com/OHDSI/OhdsiAtlasClient/workflows/R-CMD-check/badge.svg)](https://github.com/OHDSI/OhdsiAtlasClient/actions?query=workflow%3AR-CMD-check)
[![Python](https://github.com/OHDSI/OhdsiAtlasClient/actions/workflows/python-ci.yml/badge.svg)](https://github.com/OHDSI/OhdsiAtlasClient/actions/workflows/python-ci.yml)

Aligned Python and R clients for **OHDSI ATLAS 3.0** and **WebAPI 3.0**.

`ROhdsiWebApi` served the community well, but ATLAS 3.0 introduced personal API
keys, a new authentication stack, and a number of API changes. These clients
start from the ATLAS 3.0 API rather than from the legacy R package. They are
designed to be small, predictable, and easy to embed in pipelines and other
OHDSI tools.

`ROhdsiWebApi` remains the client for ATLAS 2.x. `OhdsiAtlasClient` is its
successor for ATLAS 3.0 and later; the R vignette
[migrating from ROhdsiWebApi](docs/migrating-from-rohdsiwebapi.md) maps every
common function across.

| | Python | R |
|---|---|---|
| Distribution | `ohdsi-atlas-client` | `OhdsiAtlasClient` |
| Import package | `ohdsi_atlas_client` | — |
| Source | [`ohdsi-atlas-client/`](ohdsi-atlas-client/) | [`OhdsiAtlasClient/`](OhdsiAtlasClient/) |
| Install | `pip install ohdsi-atlas-client` | `remotes::install_github("OHDSI/OhdsiAtlasClient", subdir = "OhdsiAtlasClient")` |
| Import | `from ohdsi_atlas_client import Atlas` | `library(OhdsiAtlasClient)` |
| Style | `snake_case` | `camelCase` |
| HTTP | `httpx` | `httr2` |
| Models | `pydantic` v2 | plain lists / `data.frame` helpers |
| Circepy | optional, first-class | n/a |
| Minimum ATLAS | 3.0.0 | 3.0.0 |

> **ATLAS 3.0+ only.** Both clients call `/WebAPI/info` during connection and
> refuse to work with older servers. WebAPI 2.x is not supported.

## Why a new client?

* **Give it a URL.** `Atlas("https://atlas.example.org")` discovers the WebAPI
  root (including the common `/atlas` + `/WebAPI` reverse-proxy layout), checks
  the server version, and reuses a stored API key when one exists.
* **API keys only.** Pass a personal **API key** via `api_key` / `apiKey` or
  store one with `login(api_key)`. There are no username/password or JWT login
  paths. Keys
  live in the OS keyring (Python/R) or a permission-restricted file and are
  never logged.
* **Cohort definition sets, not just cohorts.** Export a set of cohort
  definitions plus every embedded concept set into one portable JSON/ZIP
  bundle; import it into another ATLAS instance with conflict handling and ID
  remapping.
* **Concept sets are first-class.** Create from concept IDs, resolve
  expressions, count included concepts, fetch items, versions, annotations,
  and CSV exports.
* **Concept counts are one call.** `cdm_results.concept_counts(source, [201826])`
  wraps the CDM results cache and returns record, descendant-record, person,
  and descendant-person counts. `concepts.counts()` / `concepts$counts()` is a
  documented alias.
* **Circepy integration (Python).** Expressions can be passed as dictionaries
  or Circepy models, validated locally, and returned as Circepy models when
  `ohdsi-circepy` is installed.
* **Aligned APIs.** Both languages expose the same resources with the same
  semantics, and both ship the same 344-operation endpoint catalog. Python has
  a few more convenience wrappers; [docs/parity.md](docs/parity.md) lists the
  gaps explicitly rather than pretending they do not exist.

## Quick start (Python)

```python
import os

from ohdsi_atlas_client import Atlas

atlas = Atlas(
    "https://atlas.example.org",
    api_key=os.environ["OHDSI_ATLAS_CLIENT_API_KEY"],
)
# ...or store a key for later:
# atlas = Atlas("https://atlas.example.org")
# atlas.login(os.environ["OHDSI_ATLAS_CLIENT_API_KEY"])

print(atlas.version)                         # "3.0.0"
print([s.source_key for s in atlas.sources.list()])

concepts = atlas.concepts.search("EUNOMIA", "diclofenac", rows=10)
counts = atlas.cdm_results.concept_counts("EUNOMIA", [1124300])

cs = atlas.concept_sets.create_from_concepts(
    "Diclofenac ingredients", [1124300], source="EUNOMIA",
    include_descendants=True,
)
cohort = atlas.cohorts.create("My cohort", expression_dict)
job = atlas.cohorts.generate(cohort.id, "EUNOMIA")

atlas.cohort_sets.export(path="my-cohort-set.json")          # all readable cohorts
atlas.cohort_sets.import_("my-cohort-set.json", on_conflict="rename")
```

Install the optional Circepy and keyring extras:

```bash
pip install "ohdsi-atlas-client[circe,keyring]"
```

## Quick start (R)

```r
library(OhdsiAtlasClient)

atlas <- connectAtlas(
  "https://atlas.example.org",
  apiKey = Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY")
)
# ...or store a key for later:
# atlas <- connectAtlas("https://atlas.example.org")
# atlas$login(Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY"))

atlas$version
vapply(atlas$sources$list(), `[[`, "", "sourceKey")

concepts <- atlas$concepts$search("EUNOMIA", "diclofenac", rows = 10)
counts <- atlas$cdmResults$conceptCounts("EUNOMIA", c(1124300))

cs <- atlas$conceptSets$createFromConcepts(
  "Diclofenac ingredients", c(1124300),
  source = "EUNOMIA", includeDescendants = TRUE
)
cohort <- atlas$cohorts$create("My cohort", expression)
job <- atlas$cohorts$generate(cohort$id, "EUNOMIA")

atlas$cohortSets$export(path = "my-cohort-set.json")
atlas$cohortSets$import("my-cohort-set.json", onConflict = "rename")
```

## Authentication model

Both clients authenticate with **personal API keys only**. They do not accept
database passwords, OAuth browser sessions, or JWTs.

Every request sends:

```http
X-API-KEY: <your API key>
```

A key is supplied in this order:

1. the `api_key` / `apiKey` constructor argument;
2. the `OHDSI_ATLAS_CLIENT_API_KEY` environment variable;
3. a key stored by `login(api_key)` in the OS keyring or a `0600` credentials
   file;
4. otherwise the client is anonymous (WebAPI may return `200` with empty data;
   that is not authorization).

Create a key in ATLAS under the user menu → **API keys**. The plaintext key is
shown once. The client cannot create a key from a username/password because
that would require supporting password login.

See [`docs/authentication.md`](docs/authentication.md) for key storage,
revocation, and troubleshooting.

## Cohort definition sets

Both clients use the same documented bundle format
(`ohdsi-atlas-client.cohort-definition-set`, version 1.0). A bundle contains:

* cohort metadata and complete Circe expressions;
* every concept set embedded in those expressions, deduplicated by name and
  expression;
* provenance (source ATLAS URL, WebAPI version, generator, timestamp, SHA-256
  digest).

`import` supports `error`, `skip`, `rename`, and `update` conflict policies.
Concept sets are created first; cohort expressions are uploaded unchanged
because Circe embeds concept sets by local index. See
[`docs/cohort-sets.md`](docs/cohort-sets.md).

## Documentation

Full documentation lives in [`docs/`](docs/index.md):

| I want to... | Read |
|---|---|
| Do a specific task | [Recipes](docs/recipes.md) |
| Look up any method | [API reference](docs/reference.md) (generated from source) |
| Move off `ROhdsiWebApi` | [R: migrating from ROhdsiWebApi](docs/migrating-from-rohdsiwebapi.md) |
| Know what differs between the clients | [Parity](docs/parity.md) |
| Call an endpoint with no typed method | [Endpoint coverage](docs/endpoints.md) |
| Configure one database with several CDMs | [Database and CDM configuration](docs/configuration.md) |
| Fix a puzzling error | [Troubleshooting](docs/troubleshooting.md) |

The R package also ships two vignettes:

```r
vignette("ohdsi_atlas_client", package = "OhdsiAtlasClient")
vignette("migrating-from-rohdsiwebapi", package = "OhdsiAtlasClient")
```

## Endpoint coverage

The clients expose typed methods for the resources people use every day
(sources, concepts, concept sets, cohorts, cohort sets, CDM results, jobs,
tags, characterizations, feature analyses, incidence rates, pathways,
reusable assets, users/permissions). Every endpoint in WebAPI 3.0 is also
reachable through the low-level request method:

```python
atlas.request("GET", "/cohortdefinition/1/report/EUNOMIA/inclusion", params={"mode": 0})
atlas.call("cohortdefinition.generateCohort", id=1, sourceKey="EUNOMIA")
```

```r
atlas$request("GET", "/cohortdefinition/1/report/EUNOMIA/inclusion", query = list(mode = 0))
atlas$call("cohortdefinition.generateCohort", id = 1, sourceKey = "EUNOMIA")
```

The endpoint catalog
(`ohdsi-atlas-client/src/ohdsi_atlas_client/data/endpoints.json` and
`OhdsiAtlasClient/inst/extdata/endpoints.json`) is generated from WebAPI 3.0
and checked in CI for parity between the two packages. See [`docs/endpoints.md`](docs/endpoints.md)
for which groups are typed and which have gaps.

WebAPI 3.0 cannot emit CDM DDL: there is no `/ddl/cdm`. Only the results,
Achilles, and negative-control schemas have DDL endpoints, and they return
plain SQL text:

```python
atlas.ddl.results(dialect="postgresql", schema="results")
```

```r
atlas$ddl$results(dialect = "postgresql", schema = "results")
```

## Repository layout

```
.
├── ohdsi-atlas-client/     # PyPI package: ohdsi-atlas-client (import ohdsi_atlas_client)
├── OhdsiAtlasClient/       # R package: OhdsiAtlasClient
├── docs/                   # shared design and API documentation
├── examples/               # runnable end-to-end examples
├── scripts/                # endpoint sync, docs generation, integration helpers
├── compare_versions        # HADES release tooling
├── deploy.sh               # HADES release tooling
└── .github/workflows/      # Python, R (HADES), docs, integration CI
```

## Development

Python:

```bash
cd ohdsi-atlas-client
python -m pip install -e ".[dev,circe]"
pytest
ruff check .
mypy src
```

Regenerate the documentation that is derived from source:

```bash
python scripts/generate_reference.py     # docs/reference.md
python scripts/sync_vignettes.py         # docs/migrating-from-rohdsiwebapi.md
```

Both accept `--check` and are verified in CI, so a new method cannot go
undocumented.

R:

```bash
cd OhdsiAtlasClient
Rscript extras/PackageMaintenance.R      # full HADES release sequence
Rscript -e 'devtools::test()'
R CMD build .
R CMD check --no-manual OhdsiAtlasClient_0.1.0.tar.gz
```

Integration tests run against a live ATLAS 3.0 deployment and are skipped by
default. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## HADES

The R package `OhdsiAtlasClient` is built to
[HADES package requirements](https://ohdsi.github.io/Hades/packageRequirements.html):

* roxygen documentation for every exported function and argument;
* two vignettes (getting started, and migrating from `ROhdsiWebApi`);
* a pkgdown site, `NEWS.md`, and Apache 2.0;
* testthat tests at **85% coverage** (the HADES guideline is ~80%), enforced
  in CI;
* the HADES release tooling — `extras/PackageMaintenance.R`,
  `compare_versions`, `deploy.sh`, and the `R_CMD_check_Hades` /
  `nightly_cleanup_Hades` workflows — checking Windows, macOS, and Linux;
* `R CMD check --as-cran` clean locally.

The full item-by-item mapping is in
[`OhdsiAtlasClient/extras/HADES_COMPLIANCE.md`](OhdsiAtlasClient/extras/HADES_COMPLIANCE.md).

### Relationship to ROhdsiWebApi

HADES requires that WebAPI communication go through `ROhdsiWebApi`.
`ROhdsiWebApi` targets WebAPI 2.x and cannot talk to ATLAS 3.0, so a 3.0 client
cannot be built on it.

The intended resolution is **succession, not duplication**:

* `ROhdsiWebApi` remains the supported client for ATLAS 2.x;
* `OhdsiAtlasClient` is the client for ATLAS 3.0 and later;
* the [migration vignette](OhdsiAtlasClient/vignettes/migrating-from-rohdsiwebapi.Rmd)
  maps every common function across, so users move when they upgrade ATLAS.

The HADES steering group still needs to minute this succession so the
"route all WebAPI traffic through `ROhdsiWebApi`" rule is formally superseded
for ATLAS 3.0. Until then the package is built to every other HADES
requirement. `ROhdsiWebApi` is not on CRAN and is deliberately not a
dependency.

## Status

`0.1.0` — first release. The clients target WebAPI 3.0.0+ and are tested
against the OHDSI `ohdsi_atlas_client:dev` / `webapi:3.0-dev` stack with PostgreSQL and the
Eunomia demo CDM.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
