# Changelog

All notable changes to the `atlas3` Python package are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
* CLI: `atlas3 info|login|sources|concepts|concept-counts|concept-sets|cohorts|cohort-set|call|endpoints`.
* Offline unit tests and opt-in live integration tests.
