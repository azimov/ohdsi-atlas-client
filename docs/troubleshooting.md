# Troubleshooting

Error messages, surprising results, and what to check.

## Connection and discovery

### "Could not discover an ATLAS 3.0 WebAPI at ..."

The client probes `/WebAPI`, `/webapi`, the bare root, and `/atlas/WebAPI`
under the URL you gave it.

* **Check the URL is the ATLAS UI**, not a login redirect page.
* **If ATLAS and WebAPI are on different ports or hosts** (common in
  development stacks, e.g. UI on `:8081`, WebAPI on `:8082`), same-origin
  probing cannot work. Pass the WebAPI root directly:

  ```python
  Atlas("http://localhost:8082/WebAPI")
  ```

  ```r
  connectAtlas("http://localhost:8082/WebAPI")
  ```

* **Behind a reverse proxy**, confirm `/WebAPI/info` returns JSON when opened
  in a browser.

### "WebAPI 2.x is not supported"

Discovery reads `/info` and refuses servers older than 3.0.0. There is no
compatibility mode. Use `ROhdsiWebApi` for ATLAS 2.x.

## Authentication

### Everything returns 200 but with empty data

A common trap: **anonymous access can return `200` with an empty array** rather
than `401`. That is not authorisation.

```python
atlas.is_authenticated
atlas.whoami()
```

```r
atlas$whoami()
```

If `whoami()` fails or the key is missing, set one. HTTP `401` from a key you
believe is valid usually means the key was revoked or belongs to another
instance.

### Where does the key come from?

1. the `api_key` / `apiKey` argument;
2. `OHDSI_ATLAS_CLIENT_API_KEY`;
3. a stored key (OS keyring, or a `0600` file);
4. otherwise anonymous.

A stale stored key can shadow a new environment variable. Pass the key
explicitly, or clear it with `logout()`.

### "The client cannot log in with a username and password"

That is deliberate. ATLAS 3.0 personal API keys are the only supported
credential. Create one in ATLAS under user menu -> **API keys**.

## Concepts and counts

### Concept counts are all zero

**Check whether Achilles has run against that source.** Concept counts come
from the CDM results cache, not from the CDM tables. If
`results.achilles_results` is empty, every count is `0` even though the CDM has
data. This is normal for a freshly loaded stack that has not run Achilles.

Verify against the database directly:

```sql
SELECT COUNT(DISTINCT person_id)
FROM cdm.condition_occurrence
WHERE condition_concept_id = 201826;
```

If the CDM returns rows and the API returns zero, the source's results schema
is not populated (or points at the wrong schema).

### Search returns far more rows than `rows`

WebAPI's vocabulary search can ignore `rows` entirely; it has been observed
returning 30k+ concepts for `rows = 10`. The clients slice the response
client-side, so you get what you asked for, but the request is still expensive.
Use `rows` together with `domain` / `vocabulary` filters where possible.

### A concept set I created is empty

Concept sets are written in **two** server calls (`POST /conceptset`, then
`PUT /conceptset/{id}/items`). A plain `POST` that includes an `expression`
field is accepted by WebAPI and then **silently ignored**. Always create through
`create` / `createFromConcepts` rather than raw `request()`.

## Cohorts

### `cohort.expression` is a string

`GET /cohortdefinition/{id}` returns `expression` as a JSON *string*. The typed
`get()` parses it; `raw()` gives you the untouched payload. If you called
`request()` yourself, parse it before use.

### Generation completes, but the cohort table is empty

Generation writes to the source's results schema, not to WebAPI. Cohort
membership lives in the CDM results `cohort` table:

```sql
SELECT cohort_definition_id, COUNT(DISTINCT subject_id)
FROM results.cohort
GROUP BY cohort_definition_id;
```

Also check `cohorts.generation_info()` for a failed job with a message.

### `checkV2` returns 500

`POST /cohortdefinition/checkV2` has been observed returning an NPE. Use
`cohorts.check()` (the `/check` endpoint), which is the default.

## Results that look wrong

### `total_elements` is 0 but there is content

WebAPI nests page metadata under a `page` object:

```json
{"content": [...], "page": {"totalElements": 49, "totalPages": 3}}
```

Both clients normalise this, so `total_elements` / `$page$totalElements` are
correct. If you parse raw responses yourself, read the nested object.

### DDL request returns HTTP 500

The DDL endpoints return **plain SQL text**. A request that advertises only
`Accept: application/json` makes WebAPI raise
`HttpMediaTypeNotAcceptableException` (surfaced as HTTP 500). The typed
`ddl.*` methods set `Accept: text/plain`. If you call them with `request()`,
pass `headers={"Accept": "text/plain"}`.

### `/ddl/cdm` returns 404

It does not exist in WebAPI 3.0. See
[Endpoint coverage](endpoints.md#known-gaps).

## Jobs

### `jobs.wait()` times out

The timeout is client-side polling, not a server limit. Long cohort generations
legitimately exceed the default 600s on large CDMs. Pass a larger `timeout`, or
poll `cohorts.generation_info()` yourself.

### Warnings printed while waiting

Some deployments emit retry backoff messages during polling. They are
informational.

## Endpoints and `call()`

### "Unexpected arguments for <operation>"

The catalog declares each operation's parameters; an unknown keyword is
rejected to catch typos. Check the signature:

```python
atlas.endpoints.get("vocabulary.executeSearch.3").parameters
```

```r
OhdsiAtlasClient:::ohdsiAtlasClientEndpoint("vocabulary.executeSearch.3")$parameters
```

### The same path exists under several operation IDs

WebAPI has variants, for example `vocabulary.executeSearch` (POST with a body),
`vocabulary.executeSearch.2` (GET with the term in the path), and
`vocabulary.executeSearch.3` (GET with `?query=`). Pick the one matching how
you want to pass the term.

## Still stuck?

Bring the failing response:

```python
atlas.request("GET", "/info")          # confirms the API root and version
atlas.masked_api_key                   # safe to share
```

```r
atlas$request("GET", "/info")
ohdsiAtlasClientRedactKey(atlas$apiKey)          # safe to share
```

Never paste a raw API key, a connection string, or a JWT into an issue.
