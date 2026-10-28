"""URL discovery for ATLAS 3.0 deployments.

Users normally know the URL of their ATLAS instance, not the exact WebAPI
context path. This module probes the common layouts and verifies the server
version before the client is constructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from .exceptions import DiscoveryError, UnsupportedVersionError
from .utils import candidate_api_bases, is_at_least, normalize_url


@dataclass(frozen=True, slots=True)
class AuthProvider:
    """An authentication provider advertised by WebAPI."""

    name: str
    url: str | None = None
    ajax: bool = False
    use_credentials_form: bool = False

    @property
    def key(self) -> str:
        return self.name.strip().lower()

    @property
    def is_database(self) -> bool:
        return self.key == "db" or "login/db" in (self.url or "").lower()

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AuthProvider:
        return cls(
            name=str(payload.get("name") or ""),
            url=payload.get("url"),
            ajax=bool(payload.get("ajax", False)),
            use_credentials_form=bool(
                payload.get("useCredentialsForm", payload.get("use_credentials_form", False))
            ),
        )


@dataclass(frozen=True, slots=True)
class Discovery:
    """The result of probing an ATLAS URL."""

    input_url: str
    api_url: str
    atlas_url: str
    version: str
    build: dict[str, Any] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)
    auth_providers: tuple[AuthProvider, ...] = ()

    @property
    def supports_database_login(self) -> bool:
        return any(provider.is_database for provider in self.auth_providers)

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self.auth_providers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputUrl": self.input_url,
            "apiUrl": self.api_url,
            "atlasUrl": self.atlas_url,
            "version": self.version,
            "build": self.build,
            "configuration": self.configuration,
            "authProviders": [
                {
                    "name": provider.name,
                    "url": provider.url,
                    "ajax": provider.ajax,
                    "useCredentialsForm": provider.use_credentials_form,
                }
                for provider in self.auth_providers
            ],
        }


def _atlas_url(url: str, api_url: str) -> str:
    parts = urlsplit(normalize_url(url))
    lowered = parts.path.lower()
    if lowered.rstrip("/").endswith("/atlas") or "/atlas/" in lowered:
        return normalize_url(url)
    api_parts = urlsplit(api_url)
    path = api_parts.path
    if path.lower().rstrip("/").endswith("/webapi"):
        path = path[: -len("/WebAPI")]
    return f"{api_parts.scheme}://{api_parts.netloc}{path}".rstrip("/")


def discover(
    url: str,
    *,
    timeout: float = 10.0,
    verify: bool = True,
    client: httpx.Client | None = None,
) -> Discovery:
    """Discover the WebAPI root, version, and auth providers for ``url``.

    Args:
        url: ATLAS UI URL, WebAPI URL, or bare host name.
        timeout: Per-candidate timeout in seconds.
        verify: Verify TLS certificates.
        client: Optional pre-configured ``httpx.Client`` (mainly for tests).

    Raises:
        DiscoveryError: If no candidate looks like a WebAPI 3.x server.
        UnsupportedVersionError: If the server is older than ATLAS 3.0.
    """
    candidates = candidate_api_bases(url)
    attempts: list[tuple[str, str]] = []
    owned_client = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        verify=verify,
        headers={"Accept": "application/json", "User-Agent": "atlas3-python"},
    )

    info: dict[str, Any] | None = None
    api_url: str | None = None
    providers: tuple[AuthProvider, ...] = ()
    try:
        for candidate in candidates:
            try:
                response = http.get(f"{candidate}/info", timeout=timeout)
            except httpx.HTTPError as exc:
                attempts.append((candidate, type(exc).__name__))
                continue
            if response.status_code == 404:
                attempts.append((candidate, "HTTP 404"))
                continue
            if response.status_code != 200:
                attempts.append((candidate, f"HTTP {response.status_code}"))
                continue
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower():
                attempts.append((candidate, "not JSON"))
                continue
            try:
                payload = response.json()
            except ValueError:
                attempts.append((candidate, "invalid JSON"))
                continue
            if not isinstance(payload, dict) or "version" not in payload:
                attempts.append((candidate, "missing version"))
                continue
            info = payload
            api_url = candidate
            break

        if api_url is not None:
            try:
                auth_response = http.get(f"{api_url}/auth/providers", timeout=timeout)
                if auth_response.status_code == 200 and "json" in auth_response.headers.get(
                    "content-type", ""
                ):
                    raw = auth_response.json()
                    if isinstance(raw, list):
                        providers = tuple(
                            AuthProvider.from_api(item) for item in raw if isinstance(item, dict)
                        )
            except (httpx.HTTPError, ValueError):
                providers = ()
    finally:
        if owned_client:
            http.close()

    if info is None or api_url is None:
        raise DiscoveryError(url, attempts)

    version = str(info.get("version", ""))
    try:
        supported = is_at_least(version, "3.0.0")
    except ValueError:
        attempts.append((api_url, f"unparseable version {version!r}"))
        raise DiscoveryError(url, attempts) from None
    if not supported:
        raise UnsupportedVersionError(version, api_url)

    return Discovery(
        input_url=normalize_url(url),
        api_url=api_url,
        atlas_url=_atlas_url(url, api_url),
        version=version,
        build=dict(info.get("buildInfo") or {}),
        configuration=dict(info.get("configuration") or {}),
        auth_providers=providers,
    )
