"""Exception hierarchy for the Atlas3 client.

All exceptions inherit from :class:`Atlas3Error` so callers can catch a single
base class. HTTP failures expose ``status_code``, ``method``, ``url``, and the
server's parsed error body (never request headers or credentials).
"""

from __future__ import annotations

from typing import Any


class Atlas3Error(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(Atlas3Error):
    """The client was configured with an invalid or incomplete value."""


class DiscoveryError(Atlas3Error):
    """No WebAPI 3.x endpoint could be found at the supplied URL."""

    def __init__(self, url: str, attempts: list[tuple[str, str]]) -> None:
        self.url = url
        self.attempts = attempts
        detail = "; ".join(f"{candidate} ({reason})" for candidate, reason in attempts)
        super().__init__(
            f"Could not discover an ATLAS 3.0 WebAPI at {url!r}. "
            f"Tried: {detail or 'no candidates'}. "
            "Pass the URL of your ATLAS instance (for example "
            "'https://atlas.example.org') or the WebAPI root "
            "(for example 'https://atlas.example.org/WebAPI')."
        )


class UnsupportedVersionError(Atlas3Error):
    """The discovered WebAPI is older than ATLAS 3.0."""

    def __init__(self, version: str, api_url: str) -> None:
        self.version = version
        self.api_url = api_url
        super().__init__(
            f"WebAPI at {api_url} reports version {version!r}. "
            "These clients require ATLAS/WebAPI 3.0.0 or newer; WebAPI 2.x is not supported."
        )


class AuthenticationError(Atlas3Error):
    """Authentication is required or the supplied credential was rejected."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        self.status_code = status_code
        super().__init__(message)


class PermissionDeniedError(AuthenticationError):
    """The authenticated user is not allowed to perform this operation."""

    def __init__(self, message: str, *, status_code: int = 403) -> None:
        super().__init__(message, status_code=status_code)


class WebApiError(Atlas3Error):
    """An HTTP error returned by WebAPI."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        method: str,
        url: str,
        payload: Any = None,
    ) -> None:
        self.status_code = status_code
        self.method = method
        self.url = url
        self.payload = payload
        super().__init__(message)

    def __str__(self) -> str:
        return f"{self.method} {self.url} -> HTTP {self.status_code}: {self.args[0]}"


class NotFoundError(WebApiError):
    """The requested resource does not exist (HTTP 404)."""


class ConflictError(WebApiError):
    """The request conflicts with the current server state (HTTP 409)."""


class ServerError(WebApiError):
    """WebAPI returned a 5xx response."""


class BundleError(Atlas3Error):
    """A cohort definition set bundle is malformed or cannot be imported."""
