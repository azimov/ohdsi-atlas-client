"""Small, dependency-free helpers shared by the client modules."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_VERSION_RE = re.compile(r"^(?:v)?(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?$", re.IGNORECASE)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(tz=timezone.utc)


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with a ``Z`` suffix."""
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a WebAPI version such as ``3.0.0`` or ``3.0.1-SNAPSHOT``.

    Raises:
        ValueError: If the string does not start with a semantic version.
    """
    match = _VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"Unrecognised WebAPI version: {version!r}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def is_at_least(version: str, minimum: str = "3.0.0") -> bool:
    """Return whether ``version`` is at least ``minimum``."""
    return parse_version(version) >= parse_version(minimum)


def normalize_url(url: str) -> str:
    """Normalise a user-supplied URL: add https:// if needed, strip trailing slash.

    A bare host such as ``atlas.example.org`` becomes ``https://atlas.example.org``.
    Query strings and fragments are discarded. ``http://`` is preserved.
    """
    value = url.strip()
    if not value:
        raise ValueError("The ATLAS URL must not be empty")
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parts.scheme!r}")
    if not parts.netloc:
        raise ValueError(f"Invalid URL: {url!r}")
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _strip_ui_path(path: str) -> str:
    path = path.rstrip("/")
    lowered = path.lower()
    for suffix in ("/index.html", "/index.htm"):
        if lowered.endswith(suffix):
            path = path[: -len(suffix)]
            lowered = path.lower()
    if lowered.endswith("/atlas"):
        path = path[: -len("/atlas")]
    return path.rstrip("/")


def candidate_api_bases(url: str) -> list[str]:
    """Return candidate WebAPI roots for an ATLAS UI or WebAPI URL.

    ATLAS deployments commonly expose the UI at ``/atlas`` and proxy
    ``/WebAPI`` at the site root. Self-hosted single-port deployments sometimes
    expose WebAPI below the UI path. The candidates are ordered by likelihood.
    """
    normalised = normalize_url(url)
    parts = urlsplit(normalised)
    path = _strip_ui_path(parts.path)
    lowered = path.lower()

    candidates: list[str] = []

    def add(candidate_path: str) -> None:
        candidate = urlunsplit((parts.scheme, parts.netloc, candidate_path.rstrip("/"), "", ""))
        if candidate not in candidates:
            candidates.append(candidate)

    if lowered.endswith("/webapi"):
        add(path)
    else:
        add(f"{path}/WebAPI")
        add(f"{path}/webapi")
        add(path)
        add(f"{path}/atlas/WebAPI")

    return candidates


def clean_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop ``None`` values and normalise booleans for query strings."""
    if not params:
        return {}
    result: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            result[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            result[key] = ",".join(str(item) for item in value)
        else:
            result[key] = value
    return result


def chunked(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    """Yield lists of at most ``size`` items."""
    if size < 1:
        raise ValueError("size must be positive")
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash of JSON-serialisable data."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def unique_name(name: str, existing: set[str], suffix: str = " (imported)") -> str:
    """Return a name that is not in ``existing``, adding a numeric suffix if needed."""
    if name not in existing:
        return name
    candidate = f"{name}{suffix}"
    index = 2
    while candidate in existing:
        candidate = f"{name}{suffix} {index}"
        index += 1
    return candidate


def as_list(value: Any) -> list[Any]:
    """Coerce ``None``, a scalar, or an iterable to a list."""
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def jsonable(value: Any) -> Any:
    """Convert pydantic models, dataclasses, and paths to JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return jsonable(dump(by_alias=True, exclude_none=True))
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))  # type: ignore[arg-type]
    asdict = getattr(value, "__dict__", None)
    if isinstance(asdict, dict):
        return jsonable(asdict)
    return value


def write_json(path: str | Path, data: Any) -> Path:
    """Write pretty JSON atomically and return the path."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(jsonable(data), indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def read_json(path: str | Path) -> Any:
    """Read JSON from ``path`` with a helpful error on malformed input."""
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source} is not valid JSON: {exc}") from exc


def redact_key(key: str | None) -> str:
    """Return a safe display form of an API key."""
    if not key:
        return "<none>"
    if len(key) <= 12:
        return "***"
    return f"{key[:7]}...{key[-4:]}"
