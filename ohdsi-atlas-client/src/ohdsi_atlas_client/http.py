"""HTTP transport for WebAPI.

The transport keeps authentication, retries, error mapping, and content
negotiation in one place so resource classes stay declarative.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from .exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    OhdsiAtlasClientError,
    PermissionDeniedError,
    ServerError,
    WebApiError,
)
from .utils import clean_params

logger = logging.getLogger("ohdsi_atlas_client.http")

_RETRY_STATUS = {429, 500, 502, 503, 504}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


class HttpClient:
    """A small authenticated JSON client for one WebAPI root."""

    def __init__(
        self,
        api_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
        verify: bool = True,
        user_agent: str = "ohdsi-atlas-client-python",
        max_retries: int = 3,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.verify = verify
        self.user_agent = user_agent
        self.max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            verify=verify,
            follow_redirects=True,
        )

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- public request API -------------------------------------------------

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
        """Send a request and return parsed JSON, text, bytes, or a response.

        Args:
            method: HTTP method.
            path: Path relative to the WebAPI root, or an absolute URL.
            params: Query parameters; ``None`` values are dropped.
            json: JSON request body.
            data: Form data.
            files: Multipart uploads.
            headers: Additional request headers.
            timeout: Per-request timeout override.
            raw: Return the raw ``httpx.Response`` instead of decoding it.
            idempotent: Whether the request may be retried. Defaults to true
                for GET/HEAD/OPTIONS/PUT/DELETE and false for POST/PATCH.
        """
        url = self._url(path)
        request_headers = self._headers(headers)
        retryable = idempotent if idempotent is not None else method.upper() in _SAFE_METHODS
        last_error: httpx.HTTPError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(
                    method.upper(),
                    url,
                    params=clean_params(params),
                    json=json,
                    data=data,
                    files=files,
                    headers=request_headers,
                    timeout=timeout or self.timeout,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.max_retries or not retryable:
                    raise WebApiError(
                        f"Could not reach WebAPI: {exc}",
                        status_code=0,
                        method=method.upper(),
                        url=url,
                    ) from exc
                self._sleep(attempt, None)
                continue

            logger.debug("%s %s -> %s", method.upper(), url, response.status_code)

            if response.status_code >= 400:
                if (
                    response.status_code in _RETRY_STATUS
                    and attempt < self.max_retries
                    and (retryable or response.status_code == 429)
                ):
                    self._sleep(attempt, response.headers.get("retry-after"))
                    continue
                raise self._error(response, method.upper(), url)

            if raw:
                return response
            return self._decode(response)

        raise WebApiError(  # pragma: no cover - defensive
            f"Could not reach WebAPI: {last_error}",
            status_code=0,
            method=method.upper(),
            url=url,
        )

    def download(self, path: str, destination: str | Path, **kwargs: Any) -> Path:
        """Download a binary response (for example a concept-set ZIP)."""
        response = self.request("GET", path, raw=True, **kwargs)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return target

    # -- internals ----------------------------------------------------------

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.api_url}/{path.lstrip('/')}"

    def _headers(self, extra: Mapping[str, str] | None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        if response.status_code == 204 or not response.content:
            return None
        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type:
            return response.json()
        text = response.text
        stripped = text.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                return response.json()
            except ValueError:
                return text
        return text

    @staticmethod
    def _error(response: httpx.Response, method: str, url: str) -> OhdsiAtlasClientError:
        payload: Any = None
        message = ""
        try:
            payload = response.json()
        except ValueError:
            message = response.text.strip()
        if isinstance(payload, dict):
            message = str(
                payload.get("message") or payload.get("error") or payload.get("detail") or payload
            )
        elif payload is not None:
            message = str(payload)
        if not message:
            message = response.reason_phrase or "request failed"
        message = message.strip()
        if len(message) > 2000:
            message = message[:2000] + "..."

        status = response.status_code
        if status == 401:
            return AuthenticationError(
                f"WebAPI rejected the API key: {message}. "
                "Supply a valid key with Atlas(..., api_key=...) or "
                "atlas.login(api_key).",
                status_code=status,
            )
        if status == 403:
            return PermissionDeniedError(
                f"Permission denied: {message}. "
                "Check the user's roles, source access, and entity grants.",
                status_code=status,
            )
        if status == 404:
            return NotFoundError(
                message, status_code=status, method=method, url=url, payload=payload
            )
        if status == 409:
            return ConflictError(
                message, status_code=status, method=method, url=url, payload=payload
            )
        if status >= 500:
            return ServerError(message, status_code=status, method=method, url=url, payload=payload)
        return WebApiError(message, status_code=status, method=method, url=url, payload=payload)

    def _sleep(self, attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                delay = min(float(retry_after), 30.0)
            except ValueError:
                delay = 0.5 * (2**attempt)
        else:
            delay = min(0.5 * (2**attempt), 10.0)
        logger.debug("Retrying after %.1fs", delay)
        time.sleep(delay)

    def absolute_url(self, path: str) -> str:
        """Return an absolute URL for a relative path."""
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(f"{self.api_url}/", path.lstrip("/"))
