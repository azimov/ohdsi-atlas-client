# Changelog

All notable changes to the `ohdsi_atlas_client` Python package are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

* **Breaking:** `atlas.ddl.cdm()` is removed. WebAPI 3.0 has no `/ddl/cdm`
  endpoint (404) and cannot emit CDM DDL; use the released CDM DDL scripts or
  `CommonDataModel::writeDdl()` in R.
* `atlas.ddl.achilles()` now sends `schema`, `vocabSchema`, and `dialect`
  instead of `cdmSchema`/`resultsSchema`/`cdmVersion`.

### Added

* `atlas.ddl.results()` and `atlas.ddl.cem_results()`.
* `headers` argument on `atlas.request()` and `atlas.ddl.*`.
* `Page.total_elements` now reads WebAPI's nested `page` object.

### Fixed

* DDL endpoints return HTTP 500 when only `Accept: application/json` is sent;
  they are now requested as `text/plain`.
* `atlas.call()` no longer treats a parameter named `query` (for example on
  `/vocabulary/{sourceKey}/search`) as the extra query-string override.
* Paged responses reported `total_elements = 0` because WebAPI nests the counts
  under `page`.

### Documentation

* New generated API reference (`docs/reference.md`) covering both languages.
* New recipes and troubleshooting guides.
* `atlas.concepts.counts()` is documented as an alias for the canonical
  `atlas.cdm_results.concept_counts()`.

## [0.1.0] - 2026-10-28

### Added

* URL discovery for ATLAS UI / WebAPI roots, with a hard ATLAS 3.0 version gate.
* API-key-only authentication with optional keyring/file storage.
* Credential storage in the OS keyring with a `0600` file fallback.
* Typed resources for sources, concepts, concept sets, cohorts, CDM results,
  jobs, tags, cohort characterizations, feature analyses, incidence rates,
  pathways, reusable assets, users/permissions, tools, notifications, caches,
  SQL translation, DDL, evidence, and statistics.
* Portable cohort definition set bundles (JSON, ZIP, directory) with conflict
  policies and integrity checks.
* Optional Circepy conversion, validation, silent-substitution guard, and local
  SQL generation.
* Complete WebAPI 3.0 endpoint catalog with a generic `call()` invoker.
* CLI: `ohdsi_atlas_client info|login|sources|concepts|concept-counts|concept-sets|cohorts|cohort-set|call|endpoints`.
* Offline unit tests and opt-in live integration tests.
