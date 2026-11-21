# Recipes

Short, copy-pasteable answers to common tasks. Every recipe is shown in both
languages; they do the same thing.

Assumes:

```python
from ohdsi_atlas_client import Atlas
atlas = Atlas("https://atlas.example.org", api_key=api_key)
SOURCE = "EUNOMIA"        # a source key from atlas.sources.list()
```

```r
library(OhdsiAtlasClient)
atlas <- connectAtlas("https://atlas.example.org", apiKey = apiKey)
SOURCE <- "EUNOMIA"       # a source key from atlas$sources$list()
```

---

## Configure the database once

Several CDMs usually share one database (CCAE v1 through v4). Store that once
rather than repeating credentials in every script:

```python
from ohdsi_atlas_client import load_source, connection_details

source = load_source("ccae")           # ~/.config/ohdsi/ccae.yaml
cdm = source.cdm("CCAE_3")             # schemas for the third CDM
details = connection_details("ccae", cdm="CCAE_3")
```

```r
source <- readSourceConfig("ccae")
cdm <- selectCdm(source, "CCAE_3")
details <- connectionDetails("ccae", cdm = "CCAE_3")
```

See [Database and CDM configuration](configuration.md).

## Find out what is there

### List data sources

```python
for source in atlas.sources.list():
    print(source.source_key, source.source_name)
```

```r
for (source in atlas$sources$list()) {
  cat(source$sourceKey, source$sourceName, "\n")
}
```

### Which vocabulary is prioritised?

```python
priority = atlas.sources.priority_vocabulary()
```

```r
priority <- atlas$sources$priorityVocabulary()
```

---

## Concepts

### Search for a concept

```python
concepts = atlas.concepts.search(
    SOURCE, "diabetes",
    rows=10, domain="Condition", standard_concept="S",
)
for concept in concepts:
    print(concept.concept_id, concept.concept_name)
```

```r
concepts <- atlas$concepts$search(
  SOURCE, "diabetes",
  rows = 10, domain = "Condition", standardConcept = "S"
)
for (concept in concepts) cat(concept$conceptId, concept$conceptName, "\n")
```

`rows` is applied client-side: WebAPI's search can ignore it and return far
more rows than asked for.

### Fetch a concept by ID

```python
concept = atlas.concepts.get(SOURCE, 201826)      # T2DM
concepts = atlas.concepts.get_many(SOURCE, [201826, 4329847])
```

```r
concept <- atlas$concepts$get(SOURCE, 201826)
concepts <- atlas$concepts$getMany(SOURCE, c(201826, 4329847))
```

### Descendants of a concept

```python
children = atlas.concepts.descendants(SOURCE, 201826)
```

```r
children <- atlas$concepts$descendants(SOURCE, 201826)
```

---

## Concept counts

Records and people for a concept come from the CDM results cache. The
canonical method is `cdm_results.concept_counts`; `concepts.counts` is an
alias for the same call.

```python
counts = atlas.cdm_results.concept_counts(SOURCE, [201826])
record_count, _, person_count, _ = counts[0].values
```

```r
counts <- atlas$cdmResults$conceptCounts(SOURCE, c(201826))
counts[[1]]$values        # record, desc. record, person, desc. person
```

> **These numbers come from Achilles, not from the CDM.** If Achilles has not
> run against a source, every count is `0` even though the CDM has data. On
> the reference lab stack this is the normal state. Verify against the CDM when
> a zero would be surprising.

---

## Concept sets

### Create one from concept IDs

```python
concept_set = atlas.concept_sets.create_from_concepts(
    "T2DM", [201826],
    source_key=SOURCE, include_descendants=True,
)
```

```r
conceptSet <- atlas$conceptSets$createFromConcepts(
  "T2DM", c(201826),
  sourceKey = SOURCE, includeDescendants = TRUE
)
```

### Read back an expression, and count what it includes

```python
expression = atlas.concept_sets.expression(concept_set.id)
included = atlas.concepts.count_included(SOURCE, expression)
```

```r
expression <- atlas$conceptSets$expression(conceptSet$id)
included <- atlas$concepts$countIncluded(SOURCE, expression)
```

### Inspect the item rows

```python
items = atlas.concept_sets.items(concept_set.id)
```

```r
items <- atlas$conceptSets$items(conceptSet$id)
```

> Creating a concept set is a two-step API call (`POST /conceptset`, then
> `PUT /conceptset/{id}/items`). The client does both; a plain `POST` with an
> `expression` field is accepted by the server and then **silently ignored**.

---

## Cohorts

### Read a definition

```python
cohort = atlas.cohorts.get(1)
expression = cohort.expression        # already parsed
```

```r
cohort <- atlas$cohorts$get(1)
expression <- cohort$expression
```

`GET /cohortdefinition/{id}` returns `expression` as a *string*; the clients
parse it. Use `raw()` if you want the untouched payload.

### Create a definition

```python
cohort = atlas.cohorts.create("My cohort", expression)
```

```r
cohort <- atlas$cohorts$create("My cohort", expression)
```

### Get the SQL

```python
sql = atlas.cohorts.sql(expression)
```

```r
sql <- atlas$cohorts$sql(expression)
```

### Check for errors before generating

```python
warnings = atlas.cohorts.check(expression)
```

```r
warnings <- atlas$cohorts$check(expression)
```

### Generate, and wait for the job

```python
job = atlas.cohorts.generate(cohort.id, SOURCE)
job = atlas.jobs.wait(job, timeout=600)
```

```r
job <- atlas$cohorts$generate(cohort$id, SOURCE)
job <- atlas$jobs$wait(job, timeout = 600)
```

### Read the results

```python
report = atlas.cohorts.inclusion_report(cohort.id, SOURCE)
```

```r
report <- atlas$cohorts$inclusionReport(cohort$id, SOURCE)
```

Cohort *membership* lives in the CDM results schema (`cohort` table), not in
WebAPI. Query it with your own database connection:

```sql
SELECT COUNT(DISTINCT subject_id)
FROM results.cohort
WHERE cohort_definition_id = 1;
```

---

## Moving cohorts between servers

### Export a set of cohorts

```python
bundle = atlas.cohort_sets.export([1, 2], path="cohorts.json")
```

```r
bundle <- atlas$cohortSets$export(c(1, 2), path = "cohorts.json")
```

### Import it somewhere else

```python
result = atlas.cohort_sets.import_("cohorts.json", on_conflict="rename")
print(result.created_cohorts)
```

```r
result <- atlas$cohortSets$import("cohorts.json", onConflict = "rename")
result$createdCohorts
```

`on_conflict` / `onConflict` is one of `error`, `skip`, `rename` (default), or
`update`. Use `dry_run=True` / `dryRun = TRUE` to see the plan without writing.
See [Cohort definition sets](cohort-sets.md).

---

## Jobs

`jobs.list()` returns a `Page` of raw job-execution dicts (WebAPI's own shape),
not `Job` models. Use `.content`, and the page metadata for paging:

```python
page = atlas.jobs.list()
page.total_elements, page.total_pages       # e.g. 49, 3
for execution in page.content:
    print(execution["executionId"], execution["jobInstance"]["name"], execution["status"])

page = atlas.jobs.list(page=1, size=50)     # next page

job = atlas.jobs.execution(49)              # this one is a typed Job
job.status, job.exit_status
```

```r
page <- atlas$jobs$list()
for (execution in page$content) cat(execution$executionId, execution$status, "\n")
```

`jobs.wait()` polls until the job reaches a terminal state and raises if it
fails. It is a client-side loop, not a server push.

---

## Permissions and users (admin)

```python
me = atlas.whoami()
print(me.user.login, me.authz.permissions)

for key in atlas.auth.api_keys():
    print(key.key_identifier, key.name)
```

```r
me <- atlas$whoami()
print(me$user$login)
for (key in atlas$auth$apiKeys()) cat(key$keyIdentifier, key$name, "\n")
```

Keys are created and revoked in ATLAS itself (user menu -> API keys) or with
`auth.create_api_key()` / `auth.revoke_api_key()`.

---

## Schema DDL

WebAPI 3.0 has **no CDM DDL endpoint**. It can emit DDL only for *results*
schemas, and those endpoints require admin permission.

```python
results_ddl = atlas.ddl.results(dialect="postgresql", schema="results")
achilles_ddl = atlas.ddl.achilles(dialect="postgresql", schema="results")
cem_ddl = atlas.ddl.cem_results(dialect="postgresql", schema="results")
```

```r
resultsDdl <- atlas$ddl$results(dialect = "postgresql", schema = "results")
achillesDdl <- atlas$ddl$achilles(dialect = "postgresql", schema = "results")
cemDdl <- atlas$ddl$cemResults(dialect = "postgresql", schema = "results")
```

For OHDSI CDM DDL use `CommonDataModel::writeDdl()` (R) or the released DDL
scripts. See [Endpoint coverage](endpoints.md#known-gaps).

---

## Anything else

If a method is missing, call the endpoint directly:

```python
print(atlas.endpoints.describe())                            # whole catalog
for endpoint in atlas.endpoints.find(group="vocabulary"):     # one group
    print(endpoint.describe())
atlas.call("vocabulary.executeSearch.3", sourceKey=SOURCE, query="aspirin", rows=5)
atlas.request("GET", "/cohortdefinition/1/info")
```

```r
# a list of endpoint descriptions, one per operation
vapply(atlas$endpoints(group = "vocabulary"), `[[`, "", "operationId")
atlas$call("vocabulary.executeSearch.3", sourceKey = SOURCE, query = "aspirin", rows = 5)
atlas$request("GET", "/cohortdefinition/1/info")
```

See [Endpoint coverage](endpoints.md) for the operation ID scheme.
