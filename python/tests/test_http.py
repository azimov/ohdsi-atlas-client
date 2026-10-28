from __future__ import annotations

import httpx
import pytest

from atlas3.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
)
from atlas3.http import HttpClient


def _client(handler: object, **kwargs: object) -> HttpClient:
    client = HttpClient("https://host/WebAPI", api_key="wa_test", **kwargs)  # type: ignore[arg-type]
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return client


def test_json_request_and_api_key_header() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("X-API-KEY")
        seen["path"] = request.url.path
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    try:
        assert client.request("GET", "/source/sources") == {"ok": True}
    finally:
        client.close()
    assert seen["key"] == "wa_test"
    assert seen["path"] == "/WebAPI/source/sources"


def test_204_returns_none() -> None:
    client = _client(lambda request: httpx.Response(204))
    try:
        assert client.request("DELETE", "/cohortdefinition/1") is None
    finally:
        client.close()


def test_401_maps_to_authentication_error() -> None:
    client = _client(lambda request: httpx.Response(401, json={"message": "Invalid API key"}))
    try:
        with pytest.raises(AuthenticationError) as error:
            client.request("GET", "/user/me")
    finally:
        client.close()
    assert error.value.status_code == 401


def test_403_maps_to_permission_denied() -> None:
    client = _client(lambda request: httpx.Response(403, json={"message": "Access Denied"}))
    try:
        with pytest.raises(PermissionDeniedError):
            client.request("GET", "/source/sources")
    finally:
        client.close()


def test_404_maps_to_not_found() -> None:
    client = _client(lambda request: httpx.Response(404, json={"message": "There is no cohort"}))
    try:
        with pytest.raises(NotFoundError) as error:
            client.request("GET", "/cohortdefinition/999")
    finally:
        client.close()
    assert "no cohort" in str(error.value)


def test_500_maps_to_server_error_without_retry() -> None:
    client = _client(lambda request: httpx.Response(500, text="boom"), max_retries=0)
    try:
        with pytest.raises(ServerError):
            client.request("GET", "/cohortdefinition")
    finally:
        client.close()


def test_get_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("atlas3.http.time.sleep", lambda _: None)
    client = _client(handler, max_retries=1)
    try:
        assert client.request("GET", "/info") == {"ok": True}
    finally:
        client.close()
    assert calls["n"] == 2


def test_post_does_not_retry_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    monkeypatch.setattr("atlas3.http.time.sleep", lambda _: None)
    client = _client(handler, max_retries=2)
    try:
        with pytest.raises(ServerError):
            client.request("POST", "/cohortdefinition", json={"name": "x"})
    finally:
        client.close()
    assert calls["n"] == 1


def test_download_writes_bytes(tmp_path: object) -> None:
    from pathlib import Path

    destination = Path(str(tmp_path)) / "export.zip"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"PK\x03\x04", headers={"content-type": "application/zip"}
        )

    client = _client(handler)
    try:
        result = client.download("/conceptset/1/export", destination)
    finally:
        client.close()
    assert result.read_bytes() == b"PK\x03\x04"
