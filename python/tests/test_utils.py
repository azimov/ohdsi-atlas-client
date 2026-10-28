from __future__ import annotations

import pytest

from atlas3.utils import (
    candidate_api_bases,
    clean_params,
    is_at_least,
    normalize_url,
    parse_version,
    redact_key,
    stable_hash,
    unique_name,
)


def test_normalize_url_adds_scheme_and_strips_slash() -> None:
    assert normalize_url("atlas.example.org/atlas/") == "https://atlas.example.org/atlas"
    assert normalize_url("http://host:8080/WebAPI/") == "http://host:8080/WebAPI"
    assert normalize_url("https://host/path?x=1#frag") == "https://host/path"


def test_normalize_url_rejects_empty_and_bad_scheme() -> None:
    with pytest.raises(ValueError):
        normalize_url("  ")
    with pytest.raises(ValueError):
        normalize_url("ftp://host")


def test_candidate_api_bases_for_atlas_ui() -> None:
    assert candidate_api_bases("https://host/atlas") == [
        "https://host/WebAPI",
        "https://host/webapi",
        "https://host",
        "https://host/atlas/WebAPI",
    ]


def test_candidate_api_bases_for_webapi() -> None:
    assert candidate_api_bases("https://host/WebAPI/") == ["https://host/WebAPI"]


def test_candidate_api_bases_for_atlas_index() -> None:
    candidates = candidate_api_bases("https://host/atlas/index.html")
    assert candidates[0] == "https://host/WebAPI"


def test_parse_version_variants() -> None:
    assert parse_version("3.0.0") == (3, 0, 0)
    assert parse_version("v3.1") == (3, 1, 0)
    assert parse_version("3.0.0-SNAPSHOT") == (3, 0, 0)
    with pytest.raises(ValueError):
        parse_version("not-a-version")
    assert is_at_least("3.0.1")
    assert not is_at_least("2.15.0")


def test_clean_params() -> None:
    assert clean_params({"a": 1, "b": None, "c": True, "d": [1, 2]}) == {
        "a": 1,
        "c": "true",
        "d": "1,2",
    }


def test_stable_hash_is_order_independent() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_unique_name() -> None:
    assert unique_name("x", set()) == "x"
    assert unique_name("x", {"x"}) == "x (imported)"
    assert unique_name("x", {"x", "x (imported)"}) == "x (imported) 2"


def test_redact_key() -> None:
    assert redact_key(None) == "<none>"
    assert redact_key("short") == "***"
    assert redact_key("wa_1234567890abcdef").startswith("wa_1234")
