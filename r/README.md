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

atlas <- connectAtlas("https://atlas.example.org")  # discovers /WebAPI, checks >= 3.0

# If the deployment uses database auth, create and store a personal API key.
atlas$login("my.user", "my.password")

# Or use an existing key:
# atlas <- connectAtlas("https://atlas.example.org", apiKey = "wa_...")

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

* Personal API key: `X-API-KEY: wa_...` (recommended).
* Database login: `POST /user/login/db` -> JWT -> `POST /user/apikeys`.
* Existing JWT: `connectAtlas(url, bearerToken = "...")`.
* Non-interactive: `ATLAS3_API_KEY`, `ATLAS3_USERNAME`, `ATLAS3_PASSWORD`.

Keys are stored in the OS keyring when the optional `keyring` package is
installed, otherwise in a `0600` file under `tools::R_user_dir("Atlas3")`.
Passwords are never stored.

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
