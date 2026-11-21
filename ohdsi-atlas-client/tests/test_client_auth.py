from __future__ import annotations

import httpx
import pytest

from ohdsi_atlas_client import AtlasClient
from ohdsi_atlas_client.discovery import Discovery
from ohdsi_atlas_client.exceptions import AuthenticationError


def _discovery() -> Discovery:
    return Discovery(
        input_url="https://host/atlas",
        api_url="https://host/WebAPI",
        atlas_url="https://host/atlas",
        version="3.0.0",
    )


def _client(handler: object, *, api_key: str | None = None) -> AtlasClient:
    client = AtlasClient(
        "https://host/atlas",
        api_key=api_key,
        discovery=_discovery(),
        use_keyring=False,
    )
    client._http._client.close()
    client._http._client = httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return client


def test_login_validates_and_stores_api_key() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-API-KEY"))
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "user": {"id": 1, "login": "user", "name": "User"},
                "authz": {"permissions": ["read:cohort-definition"]},
            },
        )

    client = _client(handler)
    try:
        current = client.login("wa_1234567890abcdef_secret", store=False)
    finally:
        client.close()
    assert current.user.login == "user"
    assert client.api_key == "wa_1234567890abcdef_secret"
    assert seen == ["wa_1234567890abcdef_secret"]


def test_login_rejects_invalid_key_and_restores_previous() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid or expired API key"})

    client = _client(handler, api_key="wa_aaaaaaaaaaaaaaaa_old")
    try:
        with pytest.raises(AuthenticationError):
            client.login("wa_bbbbbbbbbbbbbbbb_new", store=False)
    finally:
        client.close()
    assert client.api_key == "wa_aaaaaaaaaaaaaaaa_old"


def test_empty_api_key_is_rejected() -> None:
    client = _client(lambda request: httpx.Response(200))
    try:
        with pytest.raises(Exception, match="must not be empty"):
            client.login("")
    finally:
        client.close()
