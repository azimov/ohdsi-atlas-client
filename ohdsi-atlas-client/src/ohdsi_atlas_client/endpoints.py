"""The WebAPI 3.0 endpoint catalog and a generic invoker.

Typed resource methods cover the common workflows. This module ensures that
*every* endpoint remains reachable without waiting for a typed wrapper::

    atlas.call("cohortdefinition.generateCohort", id=1, sourceKey="EUNOMIA")
    atlas.call("vocabulary.executeSearch", sourceKey="EUNOMIA", body={...})
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from typing import TYPE_CHECKING, Any

from .exceptions import OhdsiAtlasClientError

if TYPE_CHECKING:
    from .client import AtlasClient

_PATH_PARAM = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One WebAPI endpoint from the catalog."""

    operation_id: str
    method: str
    path: str
    group: str = ""
    parameters: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    has_body: bool = False
    returns: str | None = None
    source: str | None = None

    @property
    def path_parameters(self) -> list[str]:
        return [match.split(":")[0] for match in _PATH_PARAM.findall(self.path)]

    @property
    def query_parameters(self) -> list[str]:
        return [
            str(parameter["name"])
            for parameter in self.parameters
            if parameter.get("in") == "query"
        ]

    def describe(self) -> str:
        return f"{self.method} {self.path} ({self.operation_id})"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Endpoint:
        return cls(
            operation_id=str(payload["operationId"]),
            method=str(payload["method"]).upper(),
            path=str(payload["path"]),
            group=str(payload.get("group") or ""),
            parameters=tuple(payload.get("parameters") or ()),
            has_body=bool(payload.get("hasBody")),
            returns=payload.get("returns"),
            source=payload.get("source"),
        )


class EndpointCatalog:
    """A searchable view of the WebAPI 3.0 endpoint catalog."""

    def __init__(self, endpoints: list[Endpoint], metadata: dict[str, Any] | None = None) -> None:
        self._endpoints = endpoints
        self.metadata = metadata or {}
        self._by_id = {endpoint.operation_id: endpoint for endpoint in endpoints}

    @classmethod
    def load(cls) -> EndpointCatalog:
        """Load the catalog bundled with the package."""
        try:
            data_file = resources.files("ohdsi_atlas_client").joinpath("data/endpoints.json")
            payload = json.loads(data_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, ModuleNotFoundError) as exc:  # pragma: no cover
            raise OhdsiAtlasClientError("The bundled endpoint catalog is missing") from exc
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EndpointCatalog:
        endpoints = [
            Endpoint.from_dict(item)
            for item in payload.get("endpoints", [])
            if isinstance(item, dict)
        ]
        metadata = {key: value for key, value in payload.items() if key != "endpoints"}
        return cls(endpoints, metadata)

    def __iter__(self) -> Any:
        return iter(self._endpoints)

    def __len__(self) -> int:
        return len(self._endpoints)

    def __contains__(self, operation_id: object) -> bool:
        return operation_id in self._by_id

    def get(self, operation_id: str) -> Endpoint:
        """Return one endpoint by operation ID."""
        try:
            return self._by_id[operation_id]
        except KeyError:
            close = [
                candidate for candidate in self._by_id if operation_id.lower() in candidate.lower()
            ][:5]
            hint = f" Similar operations: {', '.join(close)}" if close else ""
            raise KeyError(f"Unknown WebAPI operation {operation_id!r}.{hint}") from None

    def find(
        self,
        *,
        group: str | None = None,
        method: str | None = None,
        path_contains: str | None = None,
    ) -> list[Endpoint]:
        """Filter endpoints by group, HTTP method, or path fragment."""
        result = []
        for endpoint in self._endpoints:
            if group and endpoint.group != group:
                continue
            if method and endpoint.method != method.upper():
                continue
            if path_contains and path_contains not in endpoint.path:
                continue
            result.append(endpoint)
        return result

    def call(self, client: AtlasClient, operation_id: str, **kwargs: Any) -> Any:
        """Invoke an endpoint by operation ID.

        Path parameters may be passed directly (``id=1``) or in
        ``path_params={"id": 1}``. Query parameters may be passed directly or
        in ``query={...}``. A JSON body is passed as ``body=...`` (or
        ``json=...``). ``files``, ``headers``, ``timeout``, and ``raw`` are
        forwarded to the HTTP layer.
        """
        endpoint = self.get(operation_id)
        path_params = dict(kwargs.pop("path_params", {}) or {})
        raw_query = kwargs.pop("query", None)
        if raw_query is None:
            query: dict[str, Any] = {}
        elif isinstance(raw_query, Mapping):
            query = dict(raw_query)
        else:
            # ``query`` is also the name of a WebAPI search parameter.
            query = {}
            kwargs["query"] = raw_query
        body = kwargs.pop("body", kwargs.pop("json", None))
        files = kwargs.pop("files", None)
        headers = kwargs.pop("headers", None)
        timeout = kwargs.pop("timeout", None)
        raw = bool(kwargs.pop("raw", False))

        for name in endpoint.path_parameters:
            if name in kwargs:
                path_params[name] = kwargs.pop(name)
            if name not in path_params:
                raise TypeError(
                    f"{operation_id} requires path parameter {name!r} "
                    f"({endpoint.method} {endpoint.path})"
                )

        for name in endpoint.query_parameters:
            if name in kwargs:
                query[name] = kwargs.pop(name)
        # Unknown keyword arguments are treated as query parameters for GET and
        # rejected for body methods, which catches typos without blocking new
        # server-side query parameters.
        if kwargs and endpoint.method == "GET":
            query.update(kwargs)
            kwargs = {}
        if kwargs:
            raise TypeError(f"Unexpected arguments for {operation_id}: {', '.join(sorted(kwargs))}")

        path = endpoint.path
        for name, value in path_params.items():
            path = path.replace(f"{{{name}}}", str(value))

        return client.request(
            endpoint.method,
            path,
            params=query,
            json=body,
            files=files,
            headers=headers,
            timeout=timeout,
            raw=raw,
        )

    def describe(self) -> str:
        """Return a human-readable catalog summary."""
        groups: dict[str, int] = {}
        for endpoint in self._endpoints:
            groups[endpoint.group] = groups.get(endpoint.group, 0) + 1
        lines = [
            f"WebAPI {self.metadata.get('webApiVersion', '3.0')} endpoint catalog",
            f"{len(self._endpoints)} operations across {len(groups)} groups",
            "",
        ]
        lines.extend(f"  {group:<28} {count:>3}" for group, count in sorted(groups.items()))
        return "\n".join(lines)
