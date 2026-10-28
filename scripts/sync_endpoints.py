#!/usr/bin/env python3
"""Keep the Python and R endpoint catalogs byte-identical.

The Python catalog is canonical. This script copies it to the R package and
fails if the catalog is malformed or the operation count changes unexpectedly.
Run from anywhere; paths are resolved from the repository root.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_CATALOG = ROOT / "python" / "src" / "atlas3" / "data" / "endpoints.json"
R_CATALOG = ROOT / "r" / "inst" / "extdata" / "endpoints.json"
EXPECTED_OPERATIONS = 344


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing endpoint catalog: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    endpoints = payload.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise SystemExit(f"{path} does not contain an endpoints array")
    declared = payload.get("endpointCount")
    if declared != len(endpoints):
        raise SystemExit(
            f"{path}: endpointCount={declared!r} but {len(endpoints)} operations found"
        )
    ids = [item.get("operationId") for item in endpoints]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path}: duplicate operationId values")
    return payload


def main() -> int:
    payload = load(PY_CATALOG)
    count = len(payload["endpoints"])
    if count != EXPECTED_OPERATIONS:
        raise SystemExit(
            f"Expected {EXPECTED_OPERATIONS} operations, found {count}. "
            "Update EXPECTED_OPERATIONS only after reviewing the new endpoints."
        )
    R_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PY_CATALOG, R_CATALOG)
    print(f"Synced {count} operations to {R_CATALOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
