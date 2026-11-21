"""Modern Python client for OHDSI ATLAS 3.0 and WebAPI 3.0.

Quick start::

    import os

    from ohdsi_atlas_client import Atlas

    atlas = Atlas(
        "https://atlas.example.org",
        api_key=os.environ["OHDSI_ATLAS_CLIENT_API_KEY"],
    )
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
from .client import Atlas, AtlasClient, connect, connect_from_config
from .config import (
    CdmConfig,
    ConnectionDetails,
    DatabaseConfig,
    SourceConfig,
    config_directory,
    connection_details,
    env,
    find_source,
    list_sources,
    load_source,
    load_sources,
    require_variables,
    resolve_placeholders,
    template_config,
    write_source,
)
from .credentials import Credential, CredentialStore
from .discovery import Discovery, discover
from .endpoints import Endpoint, EndpointCatalog
from .exceptions import (
    AuthenticationError,
    BundleError,
    ConfigurationError,
    ConflictError,
    DiscoveryError,
    NotFoundError,
    OhdsiAtlasClientError,
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
    "AtlasClient",
    "AuthenticationError",
    "BundleError",
    "CdmConfig",
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
    "ConnectionDetails",
    "Credential",
    "CredentialStore",
    "CurrentUser",
    "DatabaseConfig",
    "Discovery",
    "DiscoveryError",
    "Endpoint",
    "EndpointCatalog",
    "ImportResult",
    "Info",
    "Job",
    "JobTimeoutError",
    "NotFoundError",
    "OhdsiAtlasClientError",
    "Page",
    "PermissionDeniedError",
    "ServerError",
    "Source",
    "SourceConfig",
    "Tag",
    "UnsupportedVersionError",
    "User",
    "WebApiError",
    "__version__",
    "config_directory",
    "connect",
    "connect_from_config",
    "connection_details",
    "discover",
    "env",
    "find_source",
    "list_sources",
    "load_source",
    "load_sources",
    "require_variables",
    "resolve_placeholders",
    "template_config",
    "write_source",
]
