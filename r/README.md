# Atlas3

Modern R client for **OHDSI ATLAS 3.0** and **WebAPI 3.0**.

```r
install.packages("Atlas3")
# development version
# remotes::install_github("OHDSI/Atlas3Clients", subdir = "r")
```

## Quick start

```r
library(Atlas3)

atlas <- connectAtlas("https://atlas.example.org", apiKey = "wa_...")

# Or store a key for later:
# atlas <- connectAtlas("https://atlas.example.org")
# atlas$login("wa_...")

atlas$version
vapply(atlas$sources$list(), `[[`, "", "sourceKey")

concepts <- atlas$concepts$search("EUNOMIA", "diclofenac", rows = 10)
counts <- atlas$concepts$counts("EUNOMIA", c(1124300))
```

## Concept sets

```r
conceptSet <- atlas$conceptSets$createFromConcepts(
  "Diclofenac ingredients", c(1124300),
  sourceKey = "EUNOMIA", includeDescendants = TRUE
)
atlas$conceptSets$expression(conceptSet$id)
atlas$concepts$resolve("EUNOMIA", atlas$conceptSets$expression(conceptSet$id))
```

## Cohorts

```r
cohort <- atlas$cohorts$create("My cohort", expression)
print(atlas$cohorts$sql(expression))
job <- atlas$cohorts$generate(cohort$id, "EUNOMIA")
atlas$jobs$wait(job, timeout = 600)
```

## Cohort definition sets

```r
# Export every readable cohort and its embedded concept sets.
atlas$cohortSets$export(path = "my-cohorts.zip")

# Import into another ATLAS instance.
result <- atlas$cohortSets$import("my-cohorts.zip", onConflict = "rename")
result$createdCohorts
```

The bundle format (`atlas3.cohort-definition-set`, version 1.0) is shared with
the Python package `atlas3` and documented in the repository's
`docs/cohort-sets.md`.

## All endpoints

```r
atlas$call("cohortdefinition.generateCohort", id = 1, sourceKey = "EUNOMIA")
atlas$request("GET", "/cohortdefinition/1/info")
length(atlas$endpoints())   # 344 operations from WebAPI 3.0
```

## Authentication

Only personal API keys are supported. Every request sends
`X-API-KEY: wa_...`. There is no username/password or JWT login.

Keys come from `connectAtlas(..., apiKey = ...)`, `ATLAS3_API_KEY`, or a key
stored by `atlas$login("wa_...")`. `login()` validates the key against
`/user/me` before persisting it. Keys are stored in the OS keyring when the
optional `keyring` package is installed, otherwise in a `0600` file under
`tools::R_user_dir("Atlas3")`.

## Requirements

* R 4.1+
* ATLAS / WebAPI 3.0.0+ (WebAPI 2.x is rejected at discovery)

## HADES and CRAN

`Atlas3` follows OHDSI HADES conventions (roxygen documentation, testthat,
vignette, NEWS, pkgdown-ready site, Apache 2.0). Note that HADES package
requirements currently direct WebAPI communication through `ROhdsiWebApi`;
this package is intended as the ATLAS 3.0 successor and should be adopted as
such by the HADES steering group. `ROhdsiWebApi` is not on CRAN and cannot be a
dependency of a CRAN package.

## License

Apache License 2.0.
