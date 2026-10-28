# Python / R parity

The packages are intentionally aligned. Names differ only by the language
convention (`snake_case` in Python, `camelCase` in R). This table is the
contract used by tests and reviews.

| Capability | Python | R |
|---|---|---|
| Connect from URL | `Atlas(url)` | `connectAtlas(url)` |
| Existing key | `Atlas(url, api_key=...)` | `connectAtlas(url, apiKey = ...)` |
| Existing JWT | `Atlas(url, bearer_token=...)` | `connectAtlas(url, bearerToken = ...)` |
| Login + create key | `atlas.login(user, pass)` | `atlas$login(user, pass)` |
| JWT -> key | `atlas.login_with_jwt(jwt, create_api_key=True)` | `atlas$loginWithJwt(jwt, createApiKey = TRUE)` |
| Current user | `atlas.whoami()` | `atlas$whoami()` |
| Logout | `atlas.logout(revoke=True)` | `atlas$logout(revoke = TRUE)` |
| Sources | `atlas.sources.list()` | `atlas$sources$list()` |
| Priority vocabulary | `atlas.sources.priority_vocabulary()` | `atlas$sources$priorityVocabulary()` |
| Search concepts | `atlas.concepts.search(source, query, rows=...)` | `atlas$concepts$search(source, query, rows = ...)` |
| Get concept | `atlas.concepts.get(source, id)` | `atlas$concepts$get(source, id)` |
| Lookup many | `atlas.concepts.get_many(source, ids)` | `atlas$concepts$getMany(source, ids)` |
| Resolve expression | `atlas.concepts.resolve(source, expression)` | `atlas$concepts$resolve(source, expression)` |
| Count included | `atlas.concepts.count_included(source, expression)` | `atlas$concepts$countIncluded(source, expression)` |
| Concept counts | `atlas.concepts.counts(source, ids)` | `atlas$concepts$counts(source, ids)` |
| Concept count map | `atlas.cdm_results.concept_counts_map(source, ids)` | `atlas$cdmResults$conceptCountsMap(source, ids)` |
| List concept sets | `atlas.concept_sets.list()` | `atlas$conceptSets$list()` |
| Get concept set | `atlas.concept_sets.get(id)` | `atlas$conceptSets$get(id)` |
| Get expression | `atlas.concept_sets.expression(id)` | `atlas$conceptSets$expression(id)` |
| Create concept set | `atlas.concept_sets.create(name, expression)` | `atlas$conceptSets$create(name, expression)` |
| Create from concepts | `atlas.concept_sets.create_from_concepts(name, ids, source_key=...)` | `atlas$conceptSets$createFromConcepts(name, ids, sourceKey = ...)` |
| Update concept set | `atlas.concept_sets.update(id, ...)` | `atlas$conceptSets$update(id, ...)` |
| Delete concept set | `atlas.concept_sets.delete(id)` | `atlas$conceptSets$delete(id)` |
| Copy concept set | `atlas.concept_sets.copy(id)` | `atlas$conceptSets$copy(id)` |
| Export concept set ZIP | `atlas.concept_sets.export_zip(id, path)` | `atlas$conceptSets$exportZip(id, path)` |
| List cohorts | `atlas.cohorts.list()` | `atlas$cohorts$list()` |
| Get cohort | `atlas.cohorts.get(id)` | `atlas$cohorts$get(id)` |
| Raw cohort payload | `atlas.cohorts.raw(id)` | `atlas$cohorts$raw(id)` |
| Create cohort | `atlas.cohorts.create(name, expression)` | `atlas$cohorts$create(name, expression)` |
| Update cohort | `atlas.cohorts.update(id, ...)` | `atlas$cohorts$update(id, ...)` |
| Delete cohort | `atlas.cohorts.delete(id)` | `atlas$cohorts$delete(id)` |
| Cohort SQL | `atlas.cohorts.sql(expression)` | `atlas$cohorts$sql(expression)` |
| Cohort check | `atlas.cohorts.check(expression)` | `atlas$cohorts$check(expression)` |
| Generate cohort | `atlas.cohorts.generate(id, source)` | `atlas$cohorts$generate(id, source)` |
| Generation info | `atlas.cohorts.generation_info(id)` | `atlas$cohorts$generationInfo(id)` |
| Wait for job | `atlas.jobs.wait(job, timeout=...)` | `atlas$jobs$wait(job, timeout = ...)` |
| Export cohort set | `atlas.cohort_sets.export(ids, path=...)` | `atlas$cohortSets$export(ids, path = ...)` |
| Import cohort set | `atlas.cohort_sets.import_(path, on_conflict=...)` | `atlas$cohortSets$import(path, onConflict = ...)` |
| Validate cohort set | `atlas.cohort_sets.validate(path)` | `atlas$cohortSets$validate(path)` |
| Characterizations | `atlas.cohort_characterizations.*` | `atlas$cohortCharacterizations$*` |
| Feature analyses | `atlas.feature_analyses.*` | `atlas$featureAnalyses$*` |
| Incidence rates | `atlas.incidence_rates.*` | `atlas$incidenceRates$*` |
| Pathways | `atlas.pathways.*` | `atlas$pathways$*` |
| Reusable assets | `atlas.reusable.*` | `atlas$reusable$*` |
| Tags | `atlas.tags.*` | `atlas$tags$*` |
| Users/permissions | `atlas.auth.*` | `atlas$auth$*` |
| Any catalog endpoint | `atlas.call(operation_id, ...)` | `atlas$call(operationId, ...)` |
| Any raw endpoint | `atlas.request(method, path, ...)` | `atlas$request(method, path, ...)` |

## Deliberate differences

* **Return objects.** Python returns pydantic models for the core resources
  (`Source`, `Concept`, `Cohort`, ...) with `.model_dump()`; R returns the
  parsed JSON lists. Both preserve unknown WebAPI fields.
* **Nulls.** Python omits `None` when serialising requests; R uses
  `null = "null"` and drops `NULL` list values where appropriate. The server
  treats both as absent/null for the fields used here.
* **Integrity digest.** Both sides compute SHA-256 over a canonical form of the
  bundle, but the canonicalisation is language-specific. The digest is
  self-consistent; it is not a cross-language byte comparison.
* **Circepy.** Only Python has optional Circepy model conversion and local
  validation/SQL generation. R sends expressions as lists and uses WebAPI's
  `/check` and `/sql` endpoints.
* **CLI.** Only Python has a command-line entry point.
