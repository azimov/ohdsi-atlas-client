# Atlas3 0.1.0

* First release.
* URL discovery for ATLAS UI / WebAPI roots, with a hard ATLAS 3.0 version gate.
* Database login that provisions and stores a personal WebAPI API key.
* Credential storage in the OS keyring with a `0600` file fallback.
* Typed resources for sources, concepts, concept sets, cohorts, CDM results,
  jobs, tags, cohort characterizations, feature analyses, incidence rates,
  pathways, reusable assets, users/permissions, tools, notifications, caches,
  SQL translation, DDL, evidence, and statistics.
* Portable cohort definition set bundles (JSON, ZIP, directory) with conflict
  policies and integrity checks.
* Complete WebAPI 3.0 endpoint catalog (344 operations) with a generic `call()`
  invoker.
