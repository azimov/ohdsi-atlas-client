"""Modern Python client for OHDSI ATLAS 3.0 and WebAPI 3.0.

Quick start::

    from atlas3 import Atlas

    atlas = Atlas("https://atlas.example.org")
    atlas.login("user", "password")
    print(atlas.sources.list())
"""

from __future__ import annotations

from ._version import __version__
from .bundle import (
    FORMAT_NAME,
    FORMAT_VERSION,
    CohortSetBundle,
    CohortSetEntry,
    ConceptSetEntry,
    ImportResult,
)
from .client import Atlas, AtlasClient, connect
from .credentials import Credential, CredentialStore
from .discovery import AuthProvider, Discovery, discover
from .endpoints import Endpoint, EndpointCatalog
from .exceptions import (
    Atlas3Error,
    AuthenticationError,
    BundleError,
    ConfigurationError,
    ConflictError,
    DiscoveryError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    UnsupportedVersionError,
    WebApiError,
)
from .models import (
    ApiKey,
    Cohort,
    CohortSummary,
    Concept,
    ConceptCount,
    ConceptSet,
    ConceptSetExpression,
    ConceptSetItem,
    CurrentUser,
    Info,
    Job,
    Page,
    Source,
    Tag,
    User,
)
from .resources.jobs import JobTimeoutError

__all__ = [
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "ApiKey",
    "Atlas",
    "Atlas3Error",
    "AtlasClient",
    "AuthProvider",
    "AuthenticationError",
    "BundleError",
    "Cohort",
    "CohortSetBundle",
    "CohortSetEntry",
    "CohortSummary",
    "Concept",
    "ConceptCount",
    "ConceptSet",
    "ConceptSetEntry",
    "ConceptSetExpression",
    "ConceptSetItem",
    "ConfigurationError",
    "ConflictError",
    "Credential",
    "CredentialStore",
    "CurrentUser",
    "Discovery",
    "DiscoveryError",
    "Endpoint",
    "EndpointCatalog",
    "ImportResult",
    "Info",
    "Job",
    "JobTimeoutError",
    "NotFoundError",
    "Page",
    "PermissionDeniedError",
    "ServerError",
    "Source",
    "Tag",
    "UnsupportedVersionError",
    "User",
    "WebApiError",
    "__version__",
    "connect",
    "discover",
]
