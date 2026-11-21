# Endpoint coverage

Both packages ship the same endpoint catalog: **344 operations** from WebAPI
3.0.0 (branch `3.0-dev`), generated from the Spring controllers and verified
against a live deployment. The catalog is checked into both packages:

* `python/src/ohdsi_atlas_client/data/endpoints.json`
* `r/inst/extdata/endpoints.json`

Run `python scripts/sync_endpoints.py` after updating either copy; CI verifies
that they are identical and that the count is 344.

## Groups

| Group | Operations | Examples |
|---|---:|---|
| `conceptset` | 32 | list, create, items, expression, export, versions, annotations |
| `cohortdefinition` | 28 | list, create, raw expression, SQL, generate, reports, export concept sets |
| `ir` (incidence rates) | 28 | CRUD, design, execute, info, report, SQL, versions |
| `user` | 29 | login, logout, API keys, user import, current user |
| `cohort-characterization` | 35 | CRUD, generation, results, temporal results, prevalence |
| `vocabulary` | 26 | search, lookup, related, resolve, count included, compare, optimize |
| `pathway-analysis` | 27 | CRUD, import/export, generation, results |
| `evidence` | 21 | drug labels, negative controls, evidence search |
| `role` | 19 | roles, mappings, role permissions |
| `reusable` | 17 | CRUD, versions, tags |
| `cdmresults` | 12 | concept record counts, dashboard, person, cache |
| `source` | 11 | list, priority, details, create/update/delete, connection |
| `feature-analysis` | 10 | CRUD, domains, aggregates, concept-set export |
| `tag` | 9 | CRUD, search, assignment permissions, multi-assign |
| `cohortsample` | 8 | cohort sample generation and results |
| `permission` | 6 | permission list, role search, entity access grants |
| `job` | 6 | job list, executions, lookup by name |
| `tool` | 5 | ATLAS tools |
| `notifications` | 3 | job notifications |
| `ddl` | 3 | results, Achilles, and negative-control DDL |
| `cache` | 2 | cache info and clear |
| `statistic` | 2 | execution and access statistics |
| `auth` | 1 | enabled auth providers |
| `info` | 1 | server version |
| `sqlrender` | 1 | SQL render/translate |
| `featureextraction` | 1 | default covariate settings |
| `person` | 1 | person profile |

The high-level clients authenticate with API keys only. The catalog still
contains WebAPI's login and provider endpoints for completeness and for raw
`request()` calls, but neither package implements password or JWT login.

## Typed coverage

A typed method exists for most day-to-day resources; the rest is reachable
through `call()` and `request()`, which work for **all 344 operations**.

Rather than quote a number that drifts every time a method is added, the
[API reference](reference.md) is generated from source and lists every typed
method in both languages, plus the differences between them.

Qualitatively:

* **Fully typed in both languages**: `tag`, `tool`, `notifications`, `cache`,
  `sqlrender`, `statistic`, `ddl`, `job`, `cdmresults` (core subset),
  `source`, `cohortdefinition` (except protected tags), `conceptset` (core
  CRUD, versions, plus annotations in Python).
* **Mostly typed**: `vocabulary`, `feature-analysis`, `permission`.
* **Partly typed**: `cohort-characterization`, `pathway-analysis`, `reusable`
  (they share one analysis class, which covers CRUD, versions, tags,
  generation, exports, and results, but not every report), `ir` (design and
  execution are typed; most results endpoints are not), `evidence`,
  `role`, `user`.
* **Not typed at all**: `cohortsample`, `featureextraction`, `person`, and
  login endpoints.

### Known gaps

* **`ddl`**: WebAPI 3.0 has **no `/ddl/cdm`**. It cannot emit CDM DDL. The
  three real endpoints all target a *results* schema and return plain SQL
  text. Both clients send `Accept: text/plain` for these; a request that
  advertises only `application/json` gets HTTP 500. Use
  `CommonDataModel::writeDdl()` (R) or the released DDL scripts for the CDM.
* **`cohortsample`** and **`featureextraction`**: no typed methods; use
  `call()`.
* **`vocabulary`**: descendant-of-ancestor, related-standard, and
  compare-arbitrary have no wrapper.
* **`evidence`**: drug-label bulk search and several negative-control
  endpoints are untyped.
* **Protected tags** on `conceptset` and `cohortdefinition`: untyped.
* **`user`/`role`/`permission`**: role and permission editing is only partly
  typed. **Login endpoints are deliberately untyped**: the clients support API
  keys only and must not invite password login.

## Core recipes

### Concepts and counts

```python
concepts = atlas.concepts.search("EUNOMIA", "diabetes", rows=25,
                                 domain="Condition", standard_concept="S")
concept = atlas.concepts.get("EUNOMIA", 201826)
counts = atlas.cdm_results.concept_counts("EUNOMIA", [201826, 1124300])
```

```r
concepts <- atlas$concepts$search("EUNOMIA", "diabetes", rows = 25,
                                  domain = "Condition", standardConcept = "S")
concept <- atlas$concepts$get("EUNOMIA", 201826)
counts <- atlas$cdmResults$conceptCounts("EUNOMIA", c(201826, 1124300))
```

The CDM results endpoint returns an array of one-key objects. The value array
is `[record, descendant record, person, descendant person]` when
`cache.achilles.usePersonCount=true` (the default on the test stack) and
`[record, descendant record]` otherwise. The clients expose all four named
fields; unavailable values are `None` / `NULL`.

### Concept sets

WebAPI 3.0 creates concept sets in two steps:

1. `POST /conceptset` stores the name/description and returns an ID.
2. `PUT /conceptset/{id}/items` stores the item rows
   (`conceptId`, integer flags).

Both clients implement this transparently in `create` / `createFromConcepts` /
`update`. A plain `POST` with an `expression` field is accepted by the server
but **ignored**, which is why the clients do not use it.

### Cohorts

`GET /cohortdefinition/{id}` returns `expression` as a **JSON string** while
`POST` / `PUT` expect a nested object. The clients parse and serialise this
difference for you.

```python
cohort = atlas.cohorts.get(1)
print(cohort.expression["PrimaryCriteria"])
sql = atlas.cohorts.sql(cohort.expression)
job = atlas.cohorts.generate(1, "EUNOMIA")
atlas.jobs.wait(job, timeout=600)
```

```r
cohort <- atlas$cohorts$get(1)
cohort$expression$PrimaryCriteria
sql <- atlas$cohorts$sql(cohort$expression)
job <- atlas$cohorts$generate(1, "EUNOMIA")
atlas$jobs$wait(job, timeout = 600)
```

### Every other endpoint

The typed methods cover the common resources. The catalog covers everything:

```python
print(atlas.endpoints.describe())
atlas.call("cohortdefinition.getInclusionRuleReport",
           id=1, sourceKey="EUNOMIA", mode=0)
atlas.request("GET", "/cohortdefinition/1/info")
```

```r
length(atlas$endpoints())
vapply(atlas$endpoints(), `[[`, "", "operationId")
atlas$call("cohortdefinition.getInclusionRuleReport",
           id = 1, sourceKey = "EUNOMIA", mode = 0)
atlas$request("GET", "/cohortdefinition/1/info")
```

Operation IDs are `group.controllerMethod`, for example
`cohortdefinition.generateCohort`, `cdmresults.getConceptRecordCount`,
`conceptset.createConceptSet`. There are three `/vocabulary/{sourceKey}/search`
variants; the GET-with-query variant is `vocabulary.executeSearch.3`. Use
`atlas.endpoints.find(group="vocabulary")` in Python or
`atlas$endpoints(group = "vocabulary")` in R to discover IDs.

Note that `query` is a real WebAPI parameter name. In R, `atlas$call(...)` sends
`query="aspirin"` as `?query=aspirin` (a list is treated as extra query-string
parameters instead).

## WebAPI 3.0 quirks

These were observed on the reference stack and are handled or documented:

| Quirk | Client handling |
|---|---|
| Vocabulary search ignores `rows` and can return 10k+ concepts | Results are sliced client-side to `rows`. |
| `POST /cohortdefinition/checkV2` returns 500 (NPE) | Default is `checkV2 = false`; use `/check`. |
| SQLRender payload is case-sensitive (`SQL`, `targetdialect`) | The typed `sqlrender.translate` sends the correct keys. |
| `GET /cohortdefinition/{id}` returns expression as a string | Parsed into an object; `raw()` is available. |
| `GET /{id}/copy` writes a new asset | `copy()` is explicit; do not call it during read-only sync. |
| Tag assignment uses `?tagId=` for `/ir`, body for most others | The analyses resource has a `tagParam` mode. |
| `GET /notifications` may return 500 | The notification resource passes the error through. |
| Anonymous access returns 200 with empty data | Check `whoami()` and permissions. |
| Concept-set and cohort concept-set ZIP exports can be slow (tens of seconds) | Use the typed exports with a longer timeout when needed. |
| No native cohort definition set | Client-side bundle; see [cohort-sets.md](cohort-sets.md). |
| `/conceptset/exportlist` uses `+`-joined IDs | `export_list_zip()` builds the separator. |
| DDL endpoints return `text/plain`, not JSON | DDL methods send `Accept: text/plain`. |
| `/sqlrender/translate` uses `resultSchema`? | It returns `targetSQL`; use the typed method. |

## Catalog maintenance

`scripts/sync_endpoints.py` copies the canonical Python catalog to the R
package and fails if the operation count changes unexpectedly. The catalog is
generated from the WebAPI 3.0 Spring source with an internal mapping parser
and then reviewed against a live server. Keep the canonical copy in the Python
package and synchronise it to R.
