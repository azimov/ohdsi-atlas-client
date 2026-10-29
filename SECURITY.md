# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Use GitHub's
private vulnerability reporting on the repository, or email the maintainers
listed in `pyproject.toml` / `DESCRIPTION`. We aim to acknowledge reports
within five business days.

## Credential handling

* API keys are bearer credentials. Anyone with the key can act as the user
  until the key is revoked or expires.
* The clients never write keys to logs, exception messages, or telemetry.
* Python stores keys in the OS keyring when `keyring` is installed, otherwise
  in the platform config directory (`platformdirs.user_config_dir("atlas3")`) with mode `0600`.
* R stores keys in the OS keyring when the optional `keyring` package is
  installed, otherwise in `tools::R_user_dir("Atlas3", "config")` with mode
  `0600`.
* `ATLAS3_API_KEY` is supported for CI. Prefer short-lived keys in CI.
* Use `atlas.logout(revoke=True)` / `atlas$logout(revoke = TRUE)` to revoke the
  key server-side and remove it locally.

## Scope

This policy covers the client packages. Vulnerabilities in ATLAS, WebAPI, or
the deployment are handled by the OHDSI security process.
