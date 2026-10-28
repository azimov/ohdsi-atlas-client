# Architecture

## Layers

```
                 +-------------------------------+
                 |  Atlas3 / AtlasClient         |
                 |  URL, auth, resources, call   |
                 +---------------+---------------+
                                 |
        +------------------------+------------------------+
        |                                                 |
+-------v--------+                               +--------v--------+
|  Discovery     |                               |  HTTP transport |
|  /info         |                               |  headers        |
|  /auth/providers|                              |  retries        |
|  version gate  |                               |  errors         |
+----------------+                               +-----------------+
                                 |
        +------------------------+------------------------+
        |                        |                        |
+-------v--------+      +--------v--------+      +--------v--------+
|  Resources     |      |  Bundle         |      |  Endpoint      |
|  sources       |      |  export/import  |      |  catalog       |
|  concepts      |      |  integrity      |      |  344 ops       |
|  concept sets  |      |  conflicts      |      |  call()        |
|  cohorts       |      +-----------------+      +----------------+
|  cohort sets   |
|  analyses      |
+----------------+
```

## Python layout

```
src/atlas3/
  client.py          AtlasClient, login, resources, request/call
  discovery.py       URL candidates, /info, version gate, auth providers
  credentials.py     keyring + 0600 JSON fallback
  http.py            httpx transport, retry policy, error mapping
  models.py          pydantic models for the typed resources
  bundle.py          cohort definition set schema + import planning
  endpoints.py       catalog loader + generic invoker
  circe.py           optional Circepy adapters and validation
  resources/         one module per resource group
  data/endpoints.json
  cli.py
```

## R layout

```
R/
  atlas3-client.R        Atlas3 R6 class, connectAtlas, login, request
  atlas3-discovery.R     URL candidates, /info, version gate
  atlas3-credentials.R   keyring + 0600 JSON fallback
  atlas3-http.R          httr2 transport, retry policy, errors
  atlas3-endpoints.R     catalog loader + generic invoker
  atlas3-bundle.R        cohort definition set schema + helpers
  atlas3-resources.R     resource R6 classes
  atlas3-utils.R         URL/version/hash helpers
inst/extdata/endpoints.json
tests/testthat/
vignettes/
```

## Error model

| Condition | Python | R |
|---|---|---|
| Invalid config | `ConfigurationError` | `atlas3_configuration_error` |
| No WebAPI found | `DiscoveryError` | `atlas3_discovery_error` |
| WebAPI < 3.0 | `UnsupportedVersionError` | `atlas3_unsupported_version_error` |
| Bad key | `AuthenticationError` | `atlas3_authentication_error` |
| No permission | `PermissionDeniedError` | `atlas3_permission_error` |
| Missing resource | `NotFoundError` | `atlas3_not_found_error` |
| Conflict | `ConflictError` | `atlas3_conflict_error` |
| Server error | `ServerError` | `atlas3_server_error` |
| Bad bundle | `BundleError` | `atlas3_bundle_error` |

All HTTP errors expose the status, method, URL, and a safe server message.
Headers and credentials are never included in exception text.

## Retries

* Idempotent methods (`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`) retry up to
  three times on `429`, `500`, `502`, `503`, and `504`.
* `POST` and `PATCH` do not retry by default, to avoid duplicate asset
  creation. Python allows `idempotent=True` for a specific call.
* `Retry-After` is honoured up to 30 seconds; exponential backoff is capped.
* TLS verification is always on in R; Python exposes `verify=False` only for
  local development.

## Serialisation

* Python sends pydantic models with `by_alias=True, exclude_none=True`.
* R sends lists with `auto_unbox = TRUE, null = "null"`; JSON arrays that must
  stay arrays (concept ID lists) are wrapped with `I()`.
* Cohort expressions returned by WebAPI as strings are parsed into objects;
  the raw string is kept in `rawExpression` on the Python model.
* Concept set creation is two-step on the server; `create`/`update` hide it.

## Testing

* Python: pytest unit tests (no network) + `-m integration` against a live
  deployment. `httpx.MockTransport` covers discovery and HTTP errors.
* R: testthat unit tests (no network) + opt-in live tests. R CMD check runs
  offline and passes with `_R_CHECK_FORCE_SUGGESTS_=false` when the optional
  `keyring` package is unavailable.
* The endpoint catalog is checked in both packages and compared in
  `scripts/sync_endpoints.py` and CI.

## Versioning

Both packages use semantic versioning. The major version tracks breaking API
changes, not the ATLAS version. The supported WebAPI range is expressed in the
discovery gate (`>= 3.0.0`) and documented in the README.

## Design decisions

* **No generated client from OpenAPI.** WebAPI 3.0 does not expose an OpenAPI
  document on the reference deployment; the endpoint catalog is generated from
  the Spring annotations and reviewed against a live server.
* **Dicts/lists at the boundary.** Python models are convenient but the client
  accepts plain dicts everywhere and never requires Circepy. R returns lists so
  unknown fields survive.
* **No hidden global state.** Credentials live on the client instance and in
  the credential store; there is no package-global token environment.
* **No browser automation.** The clients automate database login and API-key
  creation, not OAuth browser flows.
* **Client-side cohort sets.** WebAPI has no set resource; implementing the
  bundle in both languages keeps behavior identical and avoids a server-side
  migration.
