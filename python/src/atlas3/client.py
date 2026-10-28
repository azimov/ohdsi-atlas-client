"""The main Atlas3 client."""

from __future__ import annotations

import getpass
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._version import __version__
from .credentials import Credential, CredentialStore, credential_from_key
from .discovery import Discovery, discover
from .endpoints import EndpointCatalog
from .exceptions import AuthenticationError, ConfigurationError
from .http import HttpClient
from .models import CurrentUser, Info, User
from .resources.analyses import (
    CohortCharacterizationsResource,
    FeatureAnalysesResource,
    IncidenceRatesResource,
    PathwaysResource,
    ReusableResource,
)
from .resources.auth import AuthResource
from .resources.cdm_results import CdmResultsResource
from .resources.cohort_sets import CohortSetsResource
from .resources.cohorts import CohortsResource
from .resources.concept_sets import ConceptSetsResource
from .resources.concepts import ConceptsResource
from .resources.jobs import JobsResource
from .resources.misc import (
    CacheResource,
    DdlResource,
    EvidenceResource,
    InfoResource,
    NotificationsResource,
    SqlRenderResource,
    StatisticResource,
    ToolsResource,
)
from .resources.sources import SourcesResource
from .resources.tags import TagsResource
from .utils import normalize_url, redact_key

logger = logging.getLogger("atlas3")

DEFAULT_KEY_NAME = "atlas3-python"


class AtlasClient:
    """A client for one ATLAS 3.0 / WebAPI 3.0 deployment.

    Args:
        url: ATLAS UI URL, WebAPI URL, or bare host. Discovery appends the
            common ``/WebAPI`` context when necessary.
        api_key: Personal API key (``wa_...``). Sent as ``X-API-KEY``.
        bearer_token: JWT for deployments where API-key creation is not
            available. Sent as ``Authorization: Bearer``.
        profile: Credential-store profile, useful for multiple environments.
        timeout: Request timeout in seconds.
        verify: Verify TLS certificates.
        use_keyring: Prefer the OS keyring for credential storage.
        discovery: Pre-built :class:`Discovery` (mainly for tests).
        auto_login: If true, call :meth:`login` using ``ATLAS3_USERNAME`` and
            ``ATLAS3_PASSWORD`` when no credential is available.
        username: Optional login name; when supplied, the client logs in and
            provisions an API key immediately.
        password: Optional password used only for that login.

    Example:
        >>> atlas = AtlasClient("https://atlas.example.org")
        >>> atlas.login("user", "password")
        >>> atlas.sources.list()
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        bearer_token: str | None = None,
        *,
        profile: str = "default",
        timeout: float = 60.0,
        verify: bool = True,
        use_keyring: bool = True,
        discovery: Discovery | None = None,
        credential_store: CredentialStore | None = None,
        auto_login: bool = False,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.url = normalize_url(url)
        self.profile = profile
        self.timeout = timeout
        self.verify = verify
        self._discovery = discovery
        self._credential_store = credential_store or CredentialStore(
            use_keyring=use_keyring, profile=profile
        )
        self._credential: Credential | None = None
        self._current_user: CurrentUser | None = None
        self._catalog: EndpointCatalog | None = None

        resolved_key = api_key or os.environ.get("ATLAS3_API_KEY")
        resolved_bearer = bearer_token
        if not resolved_key and not resolved_bearer:
            stored = self._credential_store.get(self.discovery.api_url)
            if stored is not None:
                self._credential = stored
                resolved_key = stored.api_key

        self._api_key = resolved_key
        self._http = HttpClient(
            self.discovery.api_url,
            api_key=resolved_key,
            bearer_token=resolved_bearer,
            timeout=timeout,
            verify=verify,
            user_agent=f"atlas3-python/{__version__}",
        )

        if auto_login and not resolved_key and not resolved_bearer:
            self.login(
                os.environ.get("ATLAS3_USERNAME"),
                os.environ.get("ATLAS3_PASSWORD"),
            )

        # Resource namespaces
        self.sources = SourcesResource(self)
        self.concepts = ConceptsResource(self)
        self.concept_sets = ConceptSetsResource(self)
        self.cohorts = CohortsResource(self)
        self.cohort_sets = CohortSetsResource(self)
        self.cdm_results = CdmResultsResource(self)
        self.jobs = JobsResource(self)
        self.cohort_characterizations = CohortCharacterizationsResource(self)
        self.feature_analyses = FeatureAnalysesResource(self)
        self.incidence_rates = IncidenceRatesResource(self)
        self.pathways = PathwaysResource(self)
        self.reusable = ReusableResource(self)
        self.tags = TagsResource(self)
        self.auth = AuthResource(self)
        self.tools = ToolsResource(self)
        self.notifications = NotificationsResource(self)
        self.cache = CacheResource(self)
        self.server_info = InfoResource(self)
        self.sqlrender = SqlRenderResource(self)
        self.ddl = DdlResource(self)
        self.evidence = EvidenceResource(self)
        self.statistic = StatisticResource(self)

        if username is not None or password is not None:
            self.login(username, password)

    # -- discovery and identity --------------------------------------------

    @property
    def discovery(self) -> Discovery:
        """The cached discovery result."""
        if self._discovery is None:
            self._discovery = discover(
                self.url, timeout=min(self.timeout, 15.0), verify=self.verify
            )
        return self._discovery

    @property
    def api_url(self) -> str:
        """The WebAPI root, for example ``https://host/WebAPI``."""
        return self.discovery.api_url

    @property
    def atlas_url(self) -> str:
        """The ATLAS UI URL."""
        return self.discovery.atlas_url

    @property
    def version(self) -> str:
        """The WebAPI version reported by ``/info``."""
        return self.discovery.version

    @property
    def api_key(self) -> str | None:
        """The in-memory API key (use with care; never log it)."""
        return self._api_key

    @property
    def masked_api_key(self) -> str:
        """A safe display form of the API key."""
        return redact_key(self._api_key)

    @property
    def is_authenticated(self) -> bool:
        """Whether the client currently has an API key or bearer token."""
        return bool(self._api_key or self._http.bearer_token)

    def info(self) -> Info:
        """Return server version and build information."""
        return Info.model_validate(self.request("GET", "/info"))

    def whoami(self, *, force: bool = False) -> CurrentUser:
        """Return the current user and authorization summary."""
        if self._current_user is None or force:
            self._current_user = self.auth.me()
        return self._current_user

    @property
    def user(self) -> User:
        """The current WebAPI user (may be the anonymous user)."""
        return self.whoami().user

    @property
    def permissions(self) -> list[str]:
        """The current user's global permissions."""
        return list(self.whoami().authz.permissions)

    def has_permission(self, permission: str) -> bool:
        """Check a global permission, honouring WebAPI's ``*`` wildcard."""
        permissions = set(self.permissions)
        if "*" in permissions or permission in permissions:
            return True
        prefix = permission.split(":", 1)[0]
        return f"{prefix}:*" in permissions

    # -- authentication -----------------------------------------------------

    def login(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        key_name: str = DEFAULT_KEY_NAME,
        description: str | None = None,
        expires_in_days: int | None = None,
        store: bool = True,
        create_api_key: bool = True,
    ) -> CurrentUser:
        """Authenticate with database credentials and provision an API key.

        The password is used only for the login request; it is never stored.
        With ``create_api_key=True`` (the default), the returned JWT is
        immediately exchanged for a personal API key, which is stored in the
        keyring or a ``0600`` credentials file.

        Args:
            username: Login name. Defaults to ``ATLAS3_USERNAME``.
            password: Password. Defaults to ``ATLAS3_PASSWORD`` or a prompt.
            key_name: Label shown in ATLAS for the new key.
            description: Optional key description.
            expires_in_days: Key lifetime; ``None`` or 0 means no expiry.
            store: Whether to persist the new key.
            create_api_key: If false, keep the JWT as a bearer token instead.

        Raises:
            AuthenticationError: If credentials are rejected or DB auth is
                not enabled.
            ConfigurationError: If credentials are missing in a
                non-interactive session.
        """
        username = username or os.environ.get("ATLAS3_USERNAME")
        password = password or os.environ.get("ATLAS3_PASSWORD")
        if not username:
            if not sys.stdin.isatty():
                raise ConfigurationError("No username supplied and ATLAS3_USERNAME is not set")
            username = input("ATLAS3 username: ")
        if not password:
            if not sys.stdin.isatty():
                raise ConfigurationError("No password supplied and ATLAS3_PASSWORD is not set")
            password = getpass.getpass("ATLAS3 password: ")

        provider = self._database_provider()
        login_path = provider.get("url") or "user/login/db"
        auth_http = HttpClient(
            self.api_url,
            timeout=self.timeout,
            verify=self.verify,
            user_agent=f"atlas3-python/{__version__}",
        )
        try:
            try:
                result = auth_http.request(
                    "POST",
                    f"/{str(login_path).lstrip('/')}",
                    data={"login": username, "password": password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except AuthenticationError as exc:
                raise AuthenticationError(
                    f"Database login failed for {username!r}: {exc.args[0]}"
                ) from exc
            jwt = (result or {}).get("jwt")
            if not jwt:
                raise AuthenticationError(
                    "WebAPI did not return a JWT. Check that database "
                    "authentication is enabled and the credentials are correct."
                )
            auth_http.bearer_token = str(jwt)
            if create_api_key:
                key = auth_http.request(
                    "POST",
                    "/user/apikeys",
                    json={
                        "name": key_name,
                        "description": description,
                        "expiresInDays": expires_in_days,
                    },
                )
                raw_key = (key or {}).get("rawKey")
                if not raw_key:
                    raise AuthenticationError("WebAPI created an API key but did not return it")
                self._api_key = str(raw_key)
                self._http.api_key = self._api_key
                self._http.bearer_token = None
                credential = credential_from_key(
                    self._api_key,
                    self.api_url,
                    login=str((result or {}).get("login") or username),
                    key_identifier=(key or {}).get("keyIdentifier"),
                )
                self._credential = credential
                if store:
                    self._credential_store.set(credential)
            else:
                self._http.bearer_token = str(jwt)
                self._http.api_key = None
                self._api_key = None
        finally:
            auth_http.close()

        self._current_user = self.whoami(force=True)
        return self._current_user

    def login_with_jwt(
        self,
        jwt: str,
        *,
        create_api_key: bool = False,
        key_name: str = DEFAULT_KEY_NAME,
        description: str | None = None,
        expires_in_days: int | None = None,
        store: bool = True,
    ) -> CurrentUser:
        """Use an existing JWT, optionally exchanging it for an API key.

        This supports OAuth/OIDC deployments where a browser session produces
        a JWT that can be pasted into a script.
        """
        if not jwt:
            raise ConfigurationError("jwt must not be empty")
        if not create_api_key:
            self._http.bearer_token = jwt
            self._http.api_key = None
            self._api_key = None
            self._current_user = self.whoami(force=True)
            return self._current_user

        auth_http = HttpClient(
            self.api_url,
            bearer_token=jwt,
            timeout=self.timeout,
            verify=self.verify,
            user_agent=f"atlas3-python/{__version__}",
        )
        try:
            key = auth_http.request(
                "POST",
                "/user/apikeys",
                json={
                    "name": key_name,
                    "description": description,
                    "expiresInDays": expires_in_days,
                },
            )
        finally:
            auth_http.close()
        raw_key = (key or {}).get("rawKey")
        if not raw_key:
            raise AuthenticationError("WebAPI did not return a raw API key")
        self._api_key = str(raw_key)
        self._http.api_key = self._api_key
        self._http.bearer_token = None
        self._current_user = self.whoami(force=True)
        credential = credential_from_key(
            self._api_key,
            self.api_url,
            login=self._current_user.user.login,
            key_identifier=(key or {}).get("keyIdentifier"),
        )
        self._credential = credential
        if store:
            self._credential_store.set(credential)
        return self._current_user

    def _database_provider(self) -> dict[str, Any]:
        providers = [provider for provider in self.discovery.auth_providers if provider.is_database]
        if not providers:
            # Refresh discovery once; some reverse proxies hide /auth/providers
            # from the unauthenticated probe but expose it later.
            self._discovery = discover(
                self.url, timeout=min(self.timeout, 15.0), verify=self.verify
            )
            providers = [
                provider for provider in self.discovery.auth_providers if provider.is_database
            ]
        if not providers:
            names = ", ".join(self.discovery.provider_names) or "none"
            raise AuthenticationError(
                "This WebAPI does not advertise database authentication "
                f"(providers: {names}). Supply a personal API key or JWT instead."
            )
        provider = providers[0]
        return {"url": provider.url or "user/login/db"}

    def logout(self, *, revoke: bool = True) -> None:
        """Revoke the stored API key (optionally) and remove local credentials."""
        if revoke and self._credential and self._credential.key_identifier:
            try:
                self.auth.revoke_api_key(self._credential.key_identifier, remove=True)
            except Exception:  # pragma: no cover - best effort on logout
                logger.warning("Could not revoke API key on the server", exc_info=True)
        self._credential_store.delete(self.api_url)
        self._credential = None
        self._api_key = None
        self._http.api_key = None
        self._http.bearer_token = None
        self._current_user = None

    def set_api_key(self, api_key: str, *, store: bool = False) -> None:
        """Replace the current API key at runtime."""
        if not api_key:
            raise ConfigurationError("api_key must not be empty")
        self._api_key = api_key
        self._http.api_key = api_key
        self._http.bearer_token = None
        self._current_user = None
        if store:
            credential = credential_from_key(api_key, self.api_url)
            self._credential = credential
            self._credential_store.set(credential)

    # -- generic HTTP and endpoint catalog ---------------------------------

    @property
    def http(self) -> HttpClient:
        """The underlying HTTP transport (advanced use)."""
        return self._http

    @property
    def endpoints(self) -> EndpointCatalog:
        """The WebAPI 3.0 endpoint catalog."""
        if self._catalog is None:
            self._catalog = EndpointCatalog.load()
        return self._catalog

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        files: Any = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        raw: bool = False,
        idempotent: bool | None = None,
    ) -> Any:
        """Call any WebAPI path.

        This is the escape hatch for endpoints that do not yet have a typed
        wrapper. Authentication, retries, and error mapping are handled.
        """
        return self._http.request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
            headers=headers,
            timeout=timeout,
            raw=raw,
            idempotent=idempotent,
        )

    def call(self, operation_id: str, **kwargs: Any) -> Any:
        """Invoke an endpoint from the catalog by operation ID.

        Example:
            >>> atlas.call(
            ...     "cohortdefinition.generateCohort",
            ...     id=1, sourceKey="EUNOMIA", demographic=False,
            ... )
        """
        return self.endpoints.call(self, operation_id, **kwargs)

    def download(self, path: str, destination: str | Path, **kwargs: Any) -> Path:
        """Download a binary endpoint to ``destination``."""
        return self._http.download(path, destination, **kwargs)

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Close the HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> AtlasClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:
        user = self._current_user.user.login if self._current_user else "unknown"
        return (
            f"AtlasClient(api_url={self.api_url!r}, version={self.version!r}, "
            f"user={user!r}, key={self.masked_api_key})"
        )


# Friendly aliases matching the README.
Atlas = AtlasClient


def connect(url: str, **kwargs: Any) -> AtlasClient:
    """Create an :class:`AtlasClient` (alias for ``AtlasClient(...)``)."""
    return AtlasClient(url, **kwargs)
