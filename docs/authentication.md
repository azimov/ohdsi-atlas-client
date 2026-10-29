# Authentication

Both clients authenticate with **personal API keys only**. They do not accept
database passwords, OAuth browser sessions, or JWTs.

## The short version

```python
import os

from atlas3 import Atlas

atlas = Atlas(
    "https://atlas.example.org",
    api_key=os.environ["ATLAS3_API_KEY"],
)
# or store a key for later:
atlas = Atlas("https://atlas.example.org")
atlas.login(os.environ["ATLAS3_API_KEY"])
```

```r
library(Atlas3)

atlas <- connectAtlas(
  "https://atlas.example.org",
  apiKey = Sys.getenv("ATLAS3_API_KEY")
)
# or store a key for later:
atlas <- connectAtlas("https://atlas.example.org")
atlas$login(Sys.getenv("ATLAS3_API_KEY"))
```

Every request sends:

```http
X-API-KEY: <your API key>
```

## 1. Get an API key

Create a key in ATLAS under the user menu → **API keys** (the screen backed by
`GET/POST /WebAPI/user/apikeys`). The plaintext key is shown **once**; copy it
into a secret manager or pass it to the client.

Ask an administrator if the deployment hides API-key creation or if you need a
service account key. The client cannot create a key from a username/password,
because that would require supporting password login.

## 2. URL discovery

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

The discovered version must be `>= 3.0.0`. The parsers accept
`3.0.0-SNAPSHOT`, `v3.1`, and similar suffixes. A WebAPI 2.x deployment raises
`UnsupportedVersionError` (Python) / `atlas3_unsupported_version_error` (R)
with the detected version and URL.

## 3. Supplying a key

In priority order:

1. The `api_key` argument (Python) / `apiKey` argument (R).
2. The `ATLAS3_API_KEY` environment variable.
3. A key stored by `login()` in the OS keyring or credentials file.
4. No key: the client is anonymous. WebAPI may still answer `200` with empty
   data; that is not authorization.

One-call use:

```python
import os
atlas = Atlas("https://atlas.example.org", api_key=os.environ["ATLAS3_API_KEY"])
```

```r
atlas <- connectAtlas("https://atlas.example.org",
                      apiKey = Sys.getenv("ATLAS3_API_KEY"))
```

### `login(api_key)`

`login()` validates the key against `GET /user/me` before storing it. An
invalid key raises an authentication error and leaves any previously configured
key unchanged.

```python
import os

atlas = Atlas("https://atlas.example.org")
atlas.login(os.environ["ATLAS3_API_KEY"], store=True)
```

```r
atlas <- connectAtlas("https://atlas.example.org")
atlas$login(Sys.getenv("ATLAS3_API_KEY"), store = TRUE)
```

### Stored credentials

**Python**

1. `ATLAS3_API_KEY` (never written).
2. OS keyring via the optional `keyring` package (`atlas3` service).
3. The platform config directory (`platformdirs.user_config_dir("atlas3")`)
   with mode `0600`.

Pass `Atlas(..., use_keyring=False)` to force the file backend, which is useful
in containers without a D-Bus/Keychain service.

**R**

1. `ATLAS3_API_KEY`.
2. OS keyring via the optional `keyring` package (`atlas3` service).
3. `tools::R_user_dir("Atlas3", "config")/credentials.json` with mode `0600`.

`keyring` is in `Suggests`; if it is not installed the file backend is used.
`connectAtlas(..., useKeyring = FALSE)` forces the file backend.

Only the key and its public identifier are stored. There is no password field.

## 4. Key rotation and revocation

```python
import os

atlas.logout(revoke=True)     # DELETE /user/apikeys/{id}?remove=true, then clear store
atlas.set_api_key(os.environ["ATLAS3_NEW_API_KEY"])
```

```r
atlas$logout(revoke = TRUE)
atlas$login(Sys.getenv("ATLAS3_NEW_API_KEY"))
```

The identifier is the 16-hex-character segment after the key prefix.
If the client cannot parse the identifier (for example a key from a custom
format), it removes the local credential but leaves server-side revocation to
the ATLAS UI.

## 5. Anonymous access is not authorization

WebAPI can allow anonymous access while still returning `200` for many
endpoints. `GET /source/sources` and `GET /user/me` may return empty results and
an anonymous user. A `200` response does **not** mean the request was
authorized. Check `whoami()` / `whoami()$user$login` and the permission list
when a call unexpectedly returns nothing.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `401 Invalid or expired API key` | Key is wrong, disabled, or expired. Create a new one in ATLAS. |
| `403 Access Denied` | Key is valid but the user/role lacks permission or source access. |
| Empty lists with `200` | Anonymous access. Supply a key. |
| `Could not discover ... /WebAPI` | Pass the ATLAS UI URL or the exact `/WebAPI` root. |
| `UnsupportedVersionError` | The deployment is WebAPI 2.x; these clients require 3.0+. |
| Key works in the UI but not the CLI | Check the key was copied completely and has no trailing newline. |

## 7. Threat model

* API keys are bearer credentials. Anyone with a key can act as the user until
  it expires or is revoked.
* The clients never log keys or `X-API-KEY` headers.
* TLS verification is always on in R. Python exposes `verify=False` only for
  local development; do not use it against a production server.
* The credential file is created with `0600`; the directory is created with
  user-only permissions where the OS allows it.
* Use short-lived keys in CI and revoke them when a machine is retired.
