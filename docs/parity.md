# Python / R parity

Both clients expose the same resources under the same names, differing only in
language convention (`snake_case` in Python, `camelCase` in R). This page is
about where they are *not* identical.

The authoritative, generated list of every method on both sides is the
[API reference](reference.md). It is produced from source by
`scripts/generate_reference.py`; this page explains the patterns behind the
differences.

## Current state

| | Python | R |
|---|---:|---:|
| Public typed methods | 178 | 155 |
| Resources at exact parity | 10 | 10 |
| Resources with a gap | 9 | 9 |

Every resource namespace exists in both languages. The gap is in breadth:
Python has more convenience wrappers around endpoints that R reaches through
`call()`.

> This is a snapshot. Regenerate [reference.md](reference.md) for the live
> numbers rather than trusting this table.

## The same call in both languages

| Capability | Python | R |
|---|---|---|
| Connect from URL | `Atlas(url)` | `connectAtlas(url)` |
| Existing API key | `Atlas(url, api_key=...)` | `connectAtlas(url, apiKey = ...)` |
| Validate + store key | `atlas.login(api_key)` | `atlas$login(apiKey)` |
| Current user | `atlas.whoami()` | `atlas$whoami()` |
| Logout | `atlas.logout(revoke=True)` | `atlas$logout(revoke = TRUE)` |
| Sources | `atlas.sources.list()` | `atlas$sources$list()` |
| Search concepts | `atlas.concepts.search(src, q)` | `atlas$concepts$search(src, q)` |
| Concept counts (canonical) | `atlas.cdm_results.concept_counts(src, ids)` | `atlas$cdmResults$conceptCounts(src, ids)` |
| Concept counts (alias) | `atlas.concepts.counts(src, ids)` | `atlas$concepts$counts(src, ids)` |
| Create concept set from IDs | `atlas.concept_sets.create_from_concepts(...)` | `atlas$conceptSets$createFromConcepts(...)` |
| Create cohort | `atlas.cohorts.create(name, expr)` | `atlas$cohorts$create(name, expr)` |
| Generate + wait | `atlas.jobs.wait(atlas.cohorts.generate(id, src))` | `atlas$jobs$wait(atlas$cohorts$generate(id, src))` |
| Export cohort set | `atlas.cohort_sets.export(ids, path=...)` | `atlas$cohortSets$export(ids, path = ...)` |
| Import cohort set | `atlas.cohort_sets.import_(path)` | `atlas$cohortSets$import(path)` |
| Results DDL | `atlas.ddl.results(schema=...)` | `atlas$ddl$results(schema = ...)` |
| Any catalog endpoint | `atlas.call(operation_id, ...)` | `atlas$call(operationId, ...)` |
| Any raw endpoint | `atlas.request(method, path, ...)` | `atlas$request(method, path, ...)` |

Note `import_`: Python appends an underscore because `import` is a keyword.
It is the same method.

## Known gaps

These are real. Use `call()` on the side that is missing the method.

| Resource | Only in Python |
|---|---|
| `sources` | `create`, `update`, `delete` |
| `concepts` | `lookup_source_codes`, `mapped`, `compare`, `optimize` |
| `concept_sets` | `export_list_zip`, `update_version`, `create_asset_from_version`, `annotations`, `delete_annotation` |
| `cohorts` | `print_friendly_concept_sets`, `create_asset_from_version` |
| `jobs` | `by_name`, `names` |
| `cohort_characterizations` | `design`, `create_asset_from_version` |
| `auth` | `entity_roles`, `set_role_permissions`, `role_permissions`, `assign_role` |
| `evidence` | `negative_controls` |

Only one method is R-only and not a naming difference:

| Resource | Only in R | Notes |
|---|---|---|
| `sources` | `checkConnection(sourceKey)` | Python has `sources.check()` |

Reaching a missing method from R:

```r
atlas$call("vocabulary.compare", sourceKey = "EUNOMIA", body = list(expr1, expr2))
atlas$request("GET", "/evidence/EUNOMIA/negativecontrols/123")
```

## Deliberate differences

These are design choices, not gaps.

* **Return objects.** Python returns pydantic models for core resources
  (`Source`, `Concept`, `Cohort`, `Job`) with `.model_dump()`. R returns the
  parsed JSON as lists. Both preserve unknown WebAPI fields.
* **Paged collections.** In both languages a paged endpoint returns a page
  object, not a bare list: Python `Page` (`.content`, `.total_elements`), R a
  list with `$content` and `$page`. WebAPI nests the counts under `page`; both
  clients normalise that.
* **Nulls.** Python omits `None` when serialising requests; R sends
  `null = "null"` and drops `NULL` list entries. The server treats both as
  absent for the fields used here.
* **Integrity digest.** Both compute SHA-256 over a canonical form of a cohort
  bundle, but canonicalisation is language-specific. The digest is
  self-consistent; it is not a cross-language byte comparison.
* **Authentication.** Both accept only personal API keys. Neither implements
  username/password or JWT login.
* **Circepy.** Only Python has optional Circepy model conversion and local
  validation. R sends expressions as lists and uses WebAPI `/check` and `/sql`.
* **CLI.** Only Python ships a command-line entry point (`ohdsi_atlas_client`).
* **Endpoint discovery.** Python: `atlas.endpoints.find(group=...)`, filtered
  client-side. R: `atlas$endpoints(group = ...)`.

## Keeping this honest

`scripts/generate_reference.py` derives the reference from the Python and R
sources. CI runs it with `--check` and fails if `docs/reference.md` is stale,
so a new method on one side cannot go undocumented.

If you add a method to one client and want parity, add it to the other and
regenerate the docs in the same change.
