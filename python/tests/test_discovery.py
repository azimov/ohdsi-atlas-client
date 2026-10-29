from __future__ import annotations

import httpx
import pytest

from atlas3.discovery import discover
from atlas3.exceptions import DiscoveryError, UnsupportedVersionError


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/WebAPI/info":
        return httpx.Response(
            200,
            json={
                "version": "3.0.0",
                "buildInfo": {"artifactVersion": "WebAPI 3.0.0"},
                "configuration": {},
            },
        )
    return httpx.Response(404, json={"message": "Resource not found"})


def test_discover_from_atlas_ui_url() -> None:
    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport) as client:
        result = discover("https://atlas.example.org/atlas", client=client)
    assert result.api_url == "https://atlas.example.org/WebAPI"
    assert result.atlas_url == "https://atlas.example.org/atlas"
    assert result.version == "3.0.0"
    assert result.to_dict()["apiUrl"] == "https://atlas.example.org/WebAPI"


def test_discover_rejects_old_version() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "2.14.0"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UnsupportedVersionError):
            discover("https://old.example.org", client=client)


def test_discover_reports_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DiscoveryError) as error:
            discover("https://missing.example.org", client=client)
    assert "https://missing.example.org/WebAPI" in str(error.value)


def test_discover_ignores_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DiscoveryError):
            discover("https://missing.example.org", client=client)
