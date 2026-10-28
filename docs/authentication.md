# Authentication and URL discovery

## The short version

```python
from atlas3 import Atlas

atlas = Atlas("https://atlas.example.org")
atlas.login("user", "password")       # creates + stores a personal API key
```

```r
library(Atlas3)

atlas <- connectAtlas("https://atlas.example.org")
atlas$login("user", "password")       # creates + stores a personal API key
```

After the first login both clients send `X-API-KEY: wa_<id>_<secret>` on every
request. The password is used once and never stored.

For a one-call setup:

```python
atlas = Atlas("https://atlas.example.org", username="user", password="password")
```

```r
atlas <- connectAtlas("https://atlas.example.org",
                      username = "user", password = "password")
```

## 1. URL discovery

Users know the URL of the ATLAS UI, which is not necessarily the WebAPI root.
Both clients probe a small, ordered list of candidates and accept the first
response from `GET /info` that is JSON containing a `version` field:

| Input | Candidates |
|---|---|
| `https://host` | `https://host/WebAPI`, `https://host/webapi`, `https://host`, `https://host/atlas/WebAPI` |
| `https://host/atlas` | the same list, with `/atlas` removed |
| `https://host/WebAPI` | `https://host/WebAPI` only |
| `https://host/atlas/index.html` | the same list, with the UI suffix removed |

The common OHDSI reverse-proxy layout is:

```
https://host/atlas/      -> ATLAS 3 UI (static SPA)
https://host/WebAPI/...  -> WebAPI 3 (JSON)
```

Both clients also accept a direct WebAPI root, which is useful when ATLAS and
WebAPI are on different ports or hosts.

### Version gate

The discovered version must be `>= 3.0.0`. The parsers accept
`3.0.0-SNAPSHOT`, `v3.1`, and similar suffixes. A WebAPI 2.x deployment raises
`UnsupportedVersionError` (Python) / `atlas3_unsupported_version_error` (R)
with the detected version and URL. There is no 2.x compatibility mode.

## 2. Authentication providers

ATLAS 3.0 exposes the enabled providers at `GET /WebAPI/auth/providers`. The
clients read them during discovery and look for a provider whose name is `DB`
or whose URL contains `login/db`. A typical response is:

```json
[
  {
    "name": "DB",
    "url": "user/login/db",
    "ajax": true,
    "useCredentialsForm": true
  }
]
```

The clients deliberately automate only two flows:

1. **Personal API keys** (recommended for scripts and CI).
2. **Database login**, used once to obtain a JWT that is immediately exchanged
   for an API key.

OAuth/OIDC, LDAP, Windows/AD, and Kerberos deployments are supported by
supplying an existing key or JWT. Creating a key inside those deployments
requires an authenticated browser session; the clients do not scrape browser
cookies or automate a browser login.

## 3. The API-key flow

```
POST /WebAPI/user/login/db
     Content-Type: application/x-www-form-urlencoded
     login=user&password=...
  -> { "login": "user", "jwt": "...", "roles": [...] }

POST /WebAPI/user/apikeys
     Authorization: Bearer <jwt>
     { "name": "atlas3-python", "description": "...", "expiresInDays": null }
  -> { "rawKey": "wa_<identifier>_<secret>", "keyIdentifier": "<identifier>", ... }

GET /WebAPI/user/me
     X-API-KEY: wa_...
  -> { "user": {...}, "authz": { "permissions": [...] } }
```

`rawKey` is returned **once**. The clients store it and never print it.
`GET /user/apikeys` (using a valid key) lists key metadata and can be used to
audit or revoke keys.

### API-key header

The header is `X-API-KEY` (HTTP header names are case-insensitive, so
`X-Api-Key` also works). The clients do not send API keys as
`Authorization: Bearer`; that header is reserved for JWTs.

## 4. Credential storage

### Python

1. `ATLAS3_API_KEY` environment variable (highest priority, never written).
2. OS keyring via the optional `keyring` package (`atlas3` service).
3. the platform config directory (`platformdirs.user_config_dir("atlas3")`) with mode `0600`.

The file is keyed by profile and WebAPI URL. Passwords are never stored.
`Atlas(..., use_keyring=False)` forces the file backend, which is useful in
containers without a D-Bus/Keychain service.

### R

1. `ATLAS3_API_KEY` environment variable.
2. OS keyring via the optional `keyring` package (`atlas3` service).
3. `tools::R_user_dir("Atlas3", "config")/credentials.json` with mode `0600`.

`keyring` is in `Suggests`; if it is not installed the file backend is used.
`connectAtlas(..., useKeyring = FALSE)` forces the file backend.

## 5. Non-interactive use

```bash
export ATLAS3_URL=https://atlas.example.org
export ATLAS3_USERNAME=svc_atlas
export ATLAS3_PASSWORD=...
atlas3 sources
```

```r
atlas <- connectAtlas(Sys.getenv("ATLAS3_URL"), autoLogin = TRUE)
```

For CI, prefer a pre-created short-lived API key:

```bash
export ATLAS3_API_KEY=wa_...
```

```r
atlas <- connectAtlas(Sys.getenv("ATLAS3_URL"))
```

## 6. Existing JWT

OAuth/OIDC users can paste a JWT from their browser session:

```python
atlas = Atlas(url, bearer_token=jwt)
# or exchange it for a long-lived key:
atlas.login_with_jwt(jwt, create_api_key=True)
```

```r
atlas <- connectAtlas(url, bearerToken = jwt)
atlas$loginWithJwt(jwt, createApiKey = TRUE)
```

## 7. Anonymous access is not authorization

WebAPI can allow anonymous access while still returning `200` for many
endpoints. For example, `GET /source/sources` and `GET /user/me` may return
empty results and an anonymous user. A `200` response does **not** mean the
request was authorized. Check `whoami()` / `whoami()$user$login` and the
permission list when a call unexpectedly returns nothing.

## 8. Revocation

```python
atlas.logout(revoke=True)     # DELETE /user/apikeys/{id}?remove=true, then clear store
```

```r
atlas$logout(revoke = TRUE)
```

If the key identifier is unknown, the local credential is still removed but
the server-side key must be revoked from ATLAS or with
`GET /user/apikeys` + `DELETE /user/apikeys/{id}`.

## 9. Threat model

* API keys are bearer credentials. Anyone with a key can act as the user until
  it expires or is revoked.
* The clients never log keys, passwords, or `Authorization` headers.
* TLS verification is always on in R. Python exposes `verify=False` only for
  local development; do not use it against a production server.
* The credential file is created with `0600`; the directory is created with
  user-only permissions where the OS allows it.
* A compromised workstation with access to the keyring/file can read the key.
  Use short-lived keys and revoke them when a machine is retired.
