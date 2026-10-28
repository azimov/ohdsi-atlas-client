# Atlas3 clients

Modern, aligned Python and R clients for **OHDSI ATLAS 3.0** and **WebAPI 3.0**.

`ROhdsiWebApi` served the community well, but ATLAS 3.0 introduced personal API
keys, a new authentication stack, and a number of API changes. These clients
start from the ATLAS 3.0 API rather than from the legacy R package. They are
designed to be small, predictable, and easy to embed in pipelines and other
OHDSI tools.

| | Python | R |
|---|---|---|
| Package | [`atlas3`](python/) | [`Atlas3`](r/) |
| Install | `pip install atlas3` | `install.packages("Atlas3")` |
| Import | `from atlas3 import Atlas` | `library(Atlas3)` |
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
  the server version, reads the enabled authentication providers, and reuses a
  stored key when one exists.
* **Let it get a key.** If the server uses database authentication, one call
  logs in and provisions a personal **API key** through
  `POST /user/apikeys`. The plaintext key is shown once by WebAPI; the client
  stores it in the OS keyring (Python) or a permission-restricted file and
  never logs it.
* **Cohort definition sets, not just cohorts.** Export a set of cohort
  definitions plus every embedded concept set into one portable JSON/ZIP
  bundle; import it into another ATLAS instance with conflict handling and ID
  remapping.
* **Concept sets are first-class.** Create from concept IDs, resolve
  expressions, count included concepts, fetch items, versions, annotations,
  and CSV exports.
* **Concept counts are one call.** `concept_counts(source, [201826])` wraps the
  CDM results cache and returns record, descendant-record, person, and
  descendant-person counts.
* **Circepy integration (Python).** Expressions can be passed as dictionaries
  or Circepy models, validated locally, and returned as Circepy models when
  `ohdsi-circepy` is installed.
* **Aligned APIs.** Every operation named in the parity table has the same
  semantics in both languages, and both ship the same 344-operation endpoint
  catalog.

## Quick start (Python)

```python
from atlas3 import Atlas

atlas = Atlas("https://atlas.example.org")   # discovers /WebAPI, checks >= 3.0
atlas.login("my.user", "my.password")        # creates and stores an API key
# ...or pass an existing key:
# atlas = Atlas("https://atlas.example.org", api_key="wa_...")

print(atlas.version)                         # "3.0.0"
print([s.source_key for s in atlas.sources.list()])

concepts = atlas.concepts.search("EUNOMIA", "diclofenac", rows=10)
counts = atlas.concepts.counts("EUNOMIA", [1124300])

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
pip install "atlas3[circe,keyring]"
```

## Quick start (R)

```r
library(Atlas3)

atlas <- connectAtlas("https://atlas.example.org")  # discovers /WebAPI, checks >= 3.0
atlas$login("my.user", "my.password")               # creates and stores an API key
# ...or: connectAtlas(url, apiKey = "wa_...")

atlas$version
vapply(atlas$sources$list(), `[[`, "", "sourceKey")

concepts <- atlas$concepts$search("EUNOMIA", "diclofenac", rows = 10)
counts <- atlas$concepts$counts("EUNOMIA", c(1124300))

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

ATLAS 3.0 WebAPI supports several authentication providers. The clients focus
on the two that can be automated safely:

1. **Personal API keys** (`X-API-KEY: wa_<id>_<secret>`), created by
   `POST /WebAPI/user/apikeys`. This is the recommended mode for scripts.
2. **Database login** (`POST /WebAPI/user/login/db`) used once to obtain a JWT
   that is immediately exchanged for an API key.

The login flow is:

```
URL -> /WebAPI/info -> version check
    -> /WebAPI/auth/providers -> provider discovery
    -> POST /user/login/db (JWT)
    -> POST /user/apikeys   (raw key, returned once)
    -> store keyring / 0600 config file
    -> all later calls use X-API-KEY
```

OAuth/OIDC deployments are supported by supplying an existing API key or JWT
(`Atlas(url, bearer_token=...)` in Python, `connectAtlas(url, bearerToken=...)`
in R). Creating a key in those deployments requires an authenticated session
through the ATLAS UI; the clients do not scrape browser cookies.

See [`docs/authentication.md`](docs/authentication.md) for details and threat
model.

## Cohort definition sets

Both clients use the same documented bundle format
(`atlas3.cohort-definition-set`, version 1.0). A bundle contains:

* cohort metadata and complete Circe expressions;
* every concept set embedded in those expressions, deduplicated by name and
  expression;
* provenance (source ATLAS URL, WebAPI version, generator, timestamp, SHA-256
  digest).

`import` supports `error`, `skip`, `rename`, and `update` conflict policies.
Concept sets are created first; cohort expressions are uploaded unchanged
because Circe embeds concept sets by local index. See
[`docs/cohort-sets.md`](docs/cohort-sets.md).

## Endpoint coverage

The clients expose typed methods for the resources people use every day
(sources, concepts, concept sets, cohorts, cohort sets, CDM results, jobs,
tags, characterizations, feature analyses, incidence rates, pathways,
reusable assets, users/permissions). Every endpoint in WebAPI 3.0 is also
reachable through the low-level request method:

```python
atlas.request("GET", "/cohortdefinition/1/report/EUNOMIA/inclusion", params={"mode": 0})
atlas.call("cohortdefinition.generate", id=1, sourceKey="EUNOMIA")
```

```r
atlas$request("GET", "/cohortdefinition/1/report/EUNOMIA/inclusion", query = list(mode = 0))
atlas$call("cohortdefinition.generate", id = 1, sourceKey = "EUNOMIA")
```

The endpoint catalog (`python/src/atlas3/data/endpoints.json` and
`r/inst/extdata/endpoints.json`) is generated from WebAPI 3.0 and checked in CI
for parity between the two packages. See [`docs/endpoints.md`](docs/endpoints.md).

## Repository layout

```
.
├── python/                 # PyPI package: atlas3
├── r/                      # CRAN package: Atlas3
├── docs/                   # shared design and API documentation
├── examples/               # runnable end-to-end examples
├── scripts/                # endpoint sync + integration test helpers
└── .github/workflows/      # Python, R, docs, integration CI
```

## Development

Python:

```bash
cd python
python -m pip install -e ".[dev,circe]"
pytest
ruff check .
mypy src
```

R:

```bash
cd r
Rscript -e 'devtools::document()'
Rscript -e 'devtools::test()'
R CMD build .
R CMD check --no-manual Atlas3_0.1.0.tar.gz
```

Integration tests run against a live ATLAS 3.0 deployment and are skipped by
default. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## HADES

The R package follows HADES package conventions: roxygen documentation for
every exported function, testthat tests, a vignette, `NEWS.md`, Apache 2.0,
and a `R CMD check --as-cran`-clean source tarball. HADES package requirements
currently say that WebAPI communication should go through `ROhdsiWebApi`; this
repository is intended as the ATLAS 3.0 successor and needs that governance
decision recorded by the HADES steering group. `ROhdsiWebApi` is not on CRAN
and cannot be a CRAN dependency.

## Status

`0.1.0` — first release. The clients target WebAPI 3.0.0+ and are tested
against the OHDSI `atlas3:dev` / `webapi:3.0-dev` stack with PostgreSQL and the
Eunomia demo CDM.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
