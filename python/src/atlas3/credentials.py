"""Credential storage with an OS-keyring preference and a safe file fallback."""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from .utils import utc_now_iso

logger = logging.getLogger("atlas3.credentials")

_KEYRING_SERVICE = "atlas3"


@dataclass(slots=True)
class Credential:
    """A stored personal API key and its non-secret metadata."""

    api_key: str
    api_url: str
    login: str | None = None
    key_identifier: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "apiKey": payload["api_key"],
            "apiUrl": payload["api_url"],
            "login": payload["login"],
            "keyIdentifier": payload["key_identifier"],
            "createdAt": payload["created_at"],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Credential:
        api_key = payload.get("apiKey", payload.get("api_key"))
        if not api_key:
            raise KeyError("apiKey")
        return cls(
            api_key=str(api_key),
            api_url=str(payload.get("apiUrl", payload.get("api_url", ""))),
            login=payload.get("login"),
            key_identifier=payload.get("keyIdentifier", payload.get("key_identifier")),
            created_at=payload.get("createdAt", payload.get("created_at")),
        )


class CredentialStore:
    """Store one API key per ATLAS WebAPI URL.

    The keyring is preferred when installed and functional. Otherwise a JSON
    file with mode ``0600`` is used. Pass ``use_keyring=False`` to force the
    file backend (useful in containers without a D-Bus/Keychain service).
    """

    def __init__(
        self,
        *,
        config_dir: str | Path | None = None,
        use_keyring: bool = True,
        profile: str = "default",
    ) -> None:
        self.profile = profile
        self.directory = Path(config_dir) if config_dir else Path(user_config_dir("atlas3"))
        self.path = self.directory / "credentials.json"
        self._use_keyring = use_keyring
        self._keyring: Any = None
        if use_keyring:
            try:
                import keyring

                self._keyring = keyring
            except Exception:  # pragma: no cover - depends on host keyring
                logger.debug("keyring is not available; using the credentials file")
                self._keyring = None

    # -- public API ---------------------------------------------------------

    def get(self, api_url: str) -> Credential | None:
        """Return the credential for ``api_url``, if one is stored."""
        key = self._key(api_url)
        if self._keyring is not None:
            try:
                raw = self._keyring.get_password(_KEYRING_SERVICE, key)
                if raw:
                    return Credential.from_dict(json.loads(raw))
            except Exception:  # pragma: no cover - host keyring failure
                logger.debug("keyring read failed; falling back to file")
        payload = self._read_file()
        entry = payload.get(key)
        if not isinstance(entry, dict):
            return None
        try:
            return Credential.from_dict(entry)
        except (KeyError, TypeError):
            logger.warning("Ignoring malformed credential entry for %s", api_url)
            return None

    def set(self, credential: Credential) -> None:
        """Persist ``credential`` for its ``api_url``."""
        if not credential.api_key:
            raise ValueError("Cannot store an empty API key")
        key = self._key(credential.api_url)
        encoded = json.dumps(credential.to_dict(), separators=(",", ":"))
        if self._keyring is not None:
            try:
                self._keyring.set_password(_KEYRING_SERVICE, key, encoded)
                return
            except Exception:  # pragma: no cover - host keyring failure
                logger.debug("keyring write failed; falling back to file")
        payload = self._read_file()
        payload[key] = credential.to_dict()
        self._write_file(payload)

    def delete(self, api_url: str) -> bool:
        """Delete the credential for ``api_url``. Returns whether one existed."""
        key = self._key(api_url)
        existed = False
        if self._keyring is not None:
            try:
                if self._keyring.get_password(_KEYRING_SERVICE, key) is not None:
                    existed = True
                    self._keyring.delete_password(_KEYRING_SERVICE, key)
            except Exception:  # pragma: no cover - host keyring failure
                logger.debug("keyring delete failed")
        payload = self._read_file()
        if key in payload:
            existed = True
            del payload[key]
            self._write_file(payload)
        return existed

    def list_urls(self) -> list[str]:
        """Return the WebAPI URLs with a key in the file store."""
        urls = {key.split("|", 1)[-1] for key in self._read_file()}
        return sorted(urls)

    # -- internals ----------------------------------------------------------

    def _key(self, api_url: str) -> str:
        return f"{self.profile}|{api_url.rstrip('/')}"

    def _read_file(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("Could not read %s; ignoring stored credentials", self.path)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_file(self, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.directory, stat.S_IRWXU)
        except OSError:  # pragma: no cover - non-POSIX
            pass
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - non-POSIX
            pass
        temporary.replace(self.path)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - non-POSIX
            pass


def credential_from_key(
    api_key: str,
    api_url: str,
    *,
    login: str | None = None,
    key_identifier: str | None = None,
) -> Credential:
    """Build a :class:`Credential` with a creation timestamp."""
    return Credential(
        api_key=api_key,
        api_url=api_url,
        login=login,
        key_identifier=key_identifier,
        created_at=utc_now_iso(),
    )
