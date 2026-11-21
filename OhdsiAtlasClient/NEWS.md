# OhdsiAtlasClient (development version)

* `$ddl$cdm()` is **removed**. WebAPI 3.0 has no `/ddl/cdm` endpoint (it returns
  404) and cannot emit CDM DDL. Use `CommonDataModel::writeDdl()` instead.
* `$ddl$achilles()` now sends the parameters the server accepts (`schema`,
  `vocabSchema`, `dialect`); it previously sent `cdmSchema`/`resultsSchema`/
  `cdmVersion`, which WebAPI ignores.
* New `$ddl$results()` and `$ddl$cemResults()` for the results and
  negative-control schemas.
* DDL methods now request `text/plain`. Sending only
  `Accept: application/json` made WebAPI return HTTP 500.
* `$call()` no longer swallows an argument named `query`. Operations such as
  `vocabulary.executeSearch.3` now send `?query=...` correctly. A list passed
  as `query` is still treated as extra query-string parameters.
* `$request()` and `$call()` accept a `headers` argument.
* Paged results read page metadata from the nested `page` object WebAPI
  returns, so `page$totalElements` is no longer 0.
* `$concepts$counts()` is documented as an alias for the canonical
  `$cdmResults$conceptCounts()`.
* New vignette: `vignette("migrating-from-rohdsiwebapi")`.
* The getting-started vignette documents connecting when ATLAS and WebAPI are
  on different ports or hosts.
* Added a pkgdown site configuration.

# OhdsiAtlasClient 0.1.0

* First release.
* URL discovery for ATLAS UI / WebAPI roots, with a hard ATLAS 3.0 version gate.
* API-key-only authentication with optional keyring/file storage.
* Credential storage in the OS keyring with a `0600` file fallback.
* Typed resources for sources, concepts, concept sets, cohorts, CDM results,
  jobs, tags, cohort characterizations, feature analyses, incidence rates,
  pathways, reusable assets, users/permissions, tools, notifications, caches,
  SQL translation, DDL, evidence, and statistics.
* Portable cohort definition set bundles (JSON, ZIP, directory) with conflict
  policies and integrity checks.
* Complete WebAPI 3.0 endpoint catalog (344 operations) with a generic `call()`
  invoker.
