from __future__ import annotations

import json
from pathlib import Path

from atlas3.credentials import Credential, CredentialStore, credential_from_key


def test_credential_roundtrip() -> None:
    credential = Credential(
        api_key="wa_test",
        api_url="https://host/WebAPI",
        login="user",
        key_identifier="abc",
        created_at="2026-01-01T00:00:00Z",
    )
    payload = credential.to_dict()
    assert payload["apiKey"] == "wa_test"
    assert payload["keyIdentifier"] == "abc"
    assert Credential.from_dict(payload) == credential


def test_file_store_roundtrip(tmp_path: Path) -> None:
    store = CredentialStore(config_dir=tmp_path, use_keyring=False)
    assert store.get("https://host/WebAPI") is None
    credential = credential_from_key(
        "wa_test", "https://host/WebAPI", login="user", key_identifier="abc"
    )
    store.set(credential)
    loaded = store.get("https://host/WebAPI")
    assert loaded is not None
    assert loaded.api_key == "wa_test"
    assert loaded.login == "user"
    assert store.list_urls() == ["https://host/WebAPI"]
    assert store.delete("https://host/WebAPI")
    assert store.get("https://host/WebAPI") is None


def test_file_is_private(tmp_path: Path) -> None:
    store = CredentialStore(config_dir=tmp_path, use_keyring=False)
    store.set(credential_from_key("wa_test", "https://host/WebAPI"))
    mode = store.path.stat().st_mode & 0o777
    assert mode == 0o600
    payload = json.loads(store.path.read_text())
    assert payload["default|https://host/WebAPI"]["apiKey"] == "wa_test"
