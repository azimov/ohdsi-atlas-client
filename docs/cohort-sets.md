# Cohort definition sets

## Why a client-side bundle?

WebAPI 3.0 has **no server-side cohort-set resource**. The only transfer
endpoints are per asset:

* `GET /cohortdefinition/{id}` — one cohort, with `expression` as a JSON string;
* `GET /cohortdefinition/{id}/export/conceptset` — a ZIP/CSV export of the
  concept sets embedded in one cohort;
* `GET /conceptset/exportlist?conceptsets=1+2` — concept sets only.

There is no bulk cohort import, no `cohortDefinitionSet` type, and no route
that carries cohorts plus concept sets together. Both clients therefore
implement the same documented bundle format on top of the per-asset endpoints.

## Format

Format name: `ohdsi-atlas-client.cohort-definition-set`

Format version: `1.0`

Media type: `application/json` (a `.zip` or directory is a convenience wrapper)

```json
{
  "format": "ohdsi-atlas-client.cohort-definition-set",
  "formatVersion": "1.0",
  "createdAt": "2026-10-28T12:00:00Z",
  "generator": {
    "name": "ohdsi-atlas-client-python",
    "version": "0.1.0"
  },
  "atlas": {
    "url": "https://atlas.example.org",
    "apiUrl": "https://atlas.example.org/WebAPI",
    "webApiVersion": "3.0.0"
  },
  "cohorts": [
    {
      "name": "New users of diclofenac",
      "description": "Demo",
      "expressionType": "SIMPLE_EXPRESSION",
      "expression": {
        "cdmVersionRange": ">=5.0.0",
        "ConceptSets": [
          {
            "id": 0,
            "name": "diclofenac",
            "expression": {
              "items": [
                {
                  "concept": {
                    "CONCEPT_ID": 1124300,
                    "CONCEPT_NAME": "Diclofenac",
                    "DOMAIN_ID": "Drug"
                  },
                  "isExcluded": false,
                  "includeDescendants": true,
                  "includeMapped": false
                }
              ]
            }
          }
        ],
        "PrimaryCriteria": {
          "CriteriaList": [{ "DrugEra": { "CodesetId": 0 } }],
          "ObservationWindow": { "PriorDays": 365, "PostDays": 0 },
          "PrimaryCriteriaLimit": { "Type": "First" }
        }
      },
      "conceptSetIds": [0],
      "checksum": "sha256-of-the-expression"
    }
  ],
  "conceptSets": [
    {
      "name": "diclofenac",
      "description": null,
      "expression": { "items": [] },
      "checksum": "sha256-of-name-and-expression"
    }
  ],
  "integrity": {
    "algorithm": "sha256",
    "digest": "sha256-of-the-bundle-without-this-member"
  }
}
```

### Fields

| Field | Meaning |
|---|---|
| `format` / `formatVersion` | Schema identity; major version must be `1`. |
| `createdAt` | Export timestamp. |
| `generator` | Producing client and version. |
| `atlas` | Provenance; not required on import. |
| `cohorts` | One entry per cohort. `expression` is always a JSON object, never a string. |
| `cohorts[].conceptSetIds` | Local `ConceptSets[].id` values used by the expression. |
| `conceptSets` | Deduplicated concept sets embedded in the cohort expressions. |
| `integrity` | Optional SHA-256 digest; verified on load. |

`checksum` values are informational. They let tools detect duplicate concept
sets and compare definitions without reimplementing Circe normalisation.
Python uses sorted-key canonical JSON; R uses its own canonical JSON. The
`integrity` digest is therefore self-consistent per generator, not guaranteed
byte-identical across languages.

## Export

```python
bundle = atlas.cohort_sets.export()                     # all readable cohorts
bundle = atlas.cohort_sets.export([1, 2])               # selected cohorts
atlas.cohort_sets.export([1], path="set.zip")
atlas.cohort_sets.export([1], path="set.json")
atlas.cohort_sets.export([1], path="set-dir/")
```

```r
bundle <- atlas$cohortSets$export()                     # all readable cohorts
bundle <- atlas$cohortSets$export(c(1, 2))
atlas$cohortSets$export(c(1), path = "set.zip")
```

The exporter fetches each cohort with `GET /cohortdefinition/{id}`, parses the
`expression` string, and collects all `ConceptSets` entries. Concept sets are
deduplicated by name + expression. A `.zip` file contains:

```
cohort-set.json
cohorts/001-new-users-of-diclofenac.json
concept-sets/001-diclofenac.json
```

## Import

```python
result = atlas.cohort_sets.import_("set.zip", on_conflict="rename")
print(result.created_cohorts, result.created_concept_sets)
```

```r
result <- atlas$cohortSets$import("set.zip", onConflict = "rename")
result$createdCohorts
```

### Conflict policies

| `on_conflict` / `onConflict` | Behavior |
|---|---|
| `"error"` | Abort if a cohort or concept-set name already exists. |
| `"skip"` | Keep the existing asset and map the bundle entry to it. |
| `"rename"` (default) | Create a new asset with a unique name (`" (imported)"`, then a numeric suffix). |
| `"update"` | Update the existing asset by ID with the bundle definition. |

`rename` is the default because it is the only policy that is safe when the
same bundle is imported repeatedly or into a different ATLAS instance.

### What happens to IDs?

Circe embeds concept sets inside each cohort expression and references them by
a **local** index (`ConceptSets[].id`, usually 0..n). Importing into another
ATLAS instance does not require rewriting those indices, because the expression
is self-contained. The importer:

1. creates/updates the top-level `conceptSets` so they appear in the Concept
   Sets UI and can be reused;
2. uploads each cohort expression unchanged;
3. records the new server IDs in `concept_set_map` / `conceptSetMap`.

Existing cohort/concept-set IDs are never reused. The bundle does not try to
preserve database IDs across servers.

### Dry run

```python
plan = atlas.cohort_sets.import_("set.zip", dry_run=True)
```

```r
plan <- atlas$cohortSets$import("set.zip", dryRun = TRUE)
```

A dry run validates the bundle, reads existing names, and returns the actions
it would take without writing anything.

## Validation

`atlas.cohort_sets.validate(path)` / `atlas$cohortSets$validate(path)` checks:

* format and major version;
* at least one cohort;
* cohort names are unique;
* every cohort has an object expression;
* the integrity digest, when present.

Import always validates before writing.

## Limitations

* Cohort expressions are uploaded as-is. The clients do not attempt to
  renumber or deduplicate embedded concept sets inside an expression.
* Top-level concept sets are a convenience copy. A cohort's logic always uses
  its embedded concept sets, even if a top-level set with the same name was
  renamed on import.
* Tags, owners, versions, annotations, and generation results are not part of
  the bundle.
* The bundle is not a `CohortGenerator` `Cohorts.csv` directory, although the
  JSON is straightforward to convert.
