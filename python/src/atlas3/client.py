"""The main Atlas3 client."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._version import __version__
from .credentials import Credential, CredentialStore, credential_from_key
from .discovery import Discovery, discover
from .endpoints import EndpointCatalog
from .exceptions import ConfigurationError
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
from .utils import api_key_identifier, normalize_url, redact_key

logger = logging.getLogger("atlas3")


class AtlasClient:
    """A client for one ATLAS 3.0 / WebAPI 3.0 deployment.

    Args:
        url: ATLAS UI URL, WebAPI URL, or bare host. Discovery appends the
            common ``/WebAPI`` context when necessary.
        api_key: Personal API key. Sent as ``X-API-KEY``; prefer the
            ``ATLAS3_API_KEY`` environment variable.
        profile: Credential-store profile, useful for multiple environments.
        timeout: Request timeout in seconds.
        verify: Verify TLS certificates.
        use_keyring: Prefer the OS keyring for credential storage.
        discovery: Pre-built :class:`Discovery` (mainly for tests).
        credential_store: Optional credential store.

    Example:
        >>> import os
        >>> atlas = AtlasClient(
        ...     "https://atlas.example.org",
        ...     api_key=os.environ["ATLAS3_API_KEY"],
        ... )
        >>> atlas.sources.list()

    Authenticate with an API key only. Create a key in ATLAS under
    "My Account" / API keys, or ask an administrator. The client does not
    accept database passwords or JWTs.
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        *,
        profile: str = "default",
        timeout: float = 60.0,
        verify: bool = True,
        use_keyring: bool = True,
        discovery: Discovery | None = None,
        credential_store: CredentialStore | None = None,
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
        if not resolved_key:
            stored = self._credential_store.get(self.discovery.api_url)
            if stored is not None:
                self._credential = stored
                resolved_key = stored.api_key

        self._api_key = resolved_key
        self._http = HttpClient(
            self.discovery.api_url,
            api_key=resolved_key,
            timeout=timeout,
            verify=verify,
            user_agent=f"atlas3-python/{__version__}",
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
        """Whether the client currently has an API key."""
        return bool(self._api_key)

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

    def login(self, api_key: str, *, store: bool = True) -> CurrentUser:
        """Use and optionally store a personal API key.

        The key is validated against ``GET /user/me`` before it is persisted.
        There is no username/password or JWT login; create a key in ATLAS
        under "My Account" / API keys, or ask an administrator.

        Args:
            api_key: Personal API key.
            store: Persist the key in the keyring or credentials file.

        Raises:
            ConfigurationError: If ``api_key`` is empty.
            AuthenticationError: If WebAPI rejects the key.
        """
        value = (api_key or "").strip()
        if not value:
            raise ConfigurationError("api_key must not be empty")
        previous = self._api_key
        self._api_key = value
        self._http.api_key = value
        self._current_user = None
        try:
            current = self.whoami(force=True)
        except Exception:
            self._api_key = previous
            self._http.api_key = previous
            self._current_user = None
            raise
        credential = credential_from_key(value, self.api_url)
        self._credential = credential
        if store:
            self._credential_store.set(credential)
        return current

    def logout(self, *, revoke: bool = True) -> None:
        """Revoke the API key (optionally) and remove local credentials."""
        identifier = (
            self._credential.key_identifier
            if self._credential is not None
            else api_key_identifier(self._api_key)
        )
        if revoke and identifier:
            try:
                self.auth.revoke_api_key(identifier, remove=True)
            except Exception:  # pragma: no cover - best effort on logout
                logger.warning("Could not revoke API key on the server", exc_info=True)
        self._credential_store.delete(self.api_url)
        self._credential = None
        self._api_key = None
        self._http.api_key = None
        self._current_user = None

    def set_api_key(self, api_key: str, *, store: bool = False) -> None:
        """Replace the current API key at runtime without validating it."""
        if not api_key:
            raise ConfigurationError("api_key must not be empty")
        self._api_key = api_key
        self._http.api_key = api_key
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
