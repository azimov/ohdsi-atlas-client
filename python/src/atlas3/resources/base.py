"""Shared behaviour for resource namespaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import Page
from ..utils import jsonable

if TYPE_CHECKING:
    from ..client import AtlasClient


class Resource:
    """Base class for a WebAPI resource group."""

    def __init__(self, client: AtlasClient) -> None:
        self._client = client

    @property
    def client(self) -> AtlasClient:
        return self._client

    def _get(self, path: str, **kwargs: Any) -> Any:
        return self._client.request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> Any:
        return self._client.request("POST", path, **kwargs)

    def _put(self, path: str, **kwargs: Any) -> Any:
        return self._client.request("PUT", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> Any:
        return self._client.request("DELETE", path, **kwargs)


def as_payload(value: Any) -> Any:
    """Convert a model/dict to a JSON-ready payload with aliases."""
    return jsonable(value)


def page_from(payload: Any) -> Page[Any]:
    """Parse a Spring ``Page`` response or wrap a plain list."""
    if isinstance(payload, dict) and "content" in payload:
        return Page[Any].model_validate(payload)
    items = payload if isinstance(payload, list) else []
    return Page[Any](
        content=items,
        totalElements=len(items),
        totalPages=1 if items else 0,
        number=0,
        size=len(items),
        first=True,
        last=True,
    )
