#!/usr/bin/env python3
"""Small repository checks used by CI and maintainers."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_catalogs() -> list[str]:
    errors: list[str] = []
    python = ROOT / "python" / "src" / "atlas3" / "data" / "endpoints.json"
    r = ROOT / "r" / "inst" / "extdata" / "endpoints.json"
    if not python.exists() or not r.exists():
        errors.append("Endpoint catalog is missing from one of the packages")
        return errors
    if python.read_bytes() != r.read_bytes():
        errors.append("Python and R endpoint catalogs differ; run scripts/sync_endpoints.py")
    payload = json.loads(python.read_text(encoding="utf-8"))
    if len(payload.get("endpoints", [])) != 344:
        errors.append("Expected 344 endpoint operations")
    return errors


def check_no_secrets() -> list[str]:
    errors: list[str] = []
    raw_key = re.compile(r"wa_[0-9a-f]{16}_[A-Za-z0-9_-]{43}")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".zip", ".gz", ".pdf", ".rds", ".duckdb"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if raw_key.search(text):
            if path.name not in {"README.md", "endpoints.json"}:
                errors.append(f"Possible secret in {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    errors = check_catalogs() + check_no_secrets()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Repository checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
