"""Command-line interface for the OhdsiAtlasClient client.

The CLI is intentionally thin: every command maps to one client method and
writes JSON to stdout. It is useful for shell pipelines and for checking a new
deployment before writing code.

Examples::

    ohdsi_atlas_client login --url https://atlas.example.org
    ohdsi_atlas_client info --url https://atlas.example.org
    ohdsi_atlas_client sources --url https://atlas.example.org
    ohdsi_atlas_client concepts --url ... --source EUNOMIA --query diclofenac
    ohdsi_atlas_client concept-counts --url ... --source EUNOMIA --concept 1124300
    ohdsi_atlas_client cohort-set --url ... --export cohorts.zip
    ohdsi_atlas_client cohort-set --url ... --import cohorts.zip --on-conflict rename
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

from ._version import __version__
from .client import AtlasClient
from .exceptions import OhdsiAtlasClientError
from .utils import jsonable


def _client(args: argparse.Namespace) -> AtlasClient:
    url = args.url or os.environ.get("OHDSI_ATLAS_CLIENT_URL")
    if not url:
        raise SystemExit("Pass --url or set OHDSI_ATLAS_CLIENT_URL")
    return AtlasClient(
        url,
        api_key=args.api_key,
        timeout=args.timeout,
        verify=not args.insecure,
    )


def _print(value: Any) -> None:
    json.dump(jsonable(value), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ohdsi-atlas-client",
        description="Query and manage an OHDSI ATLAS 3.0 deployment.",
    )
    parser.add_argument("--version", action="version", version=f"ohdsi-atlas-client {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--url", help="ATLAS or WebAPI URL (or OHDSI_ATLAS_CLIENT_URL)")
        p.add_argument("--api-key", help="API key (or OHDSI_ATLAS_CLIENT_API_KEY)")
        p.add_argument("--timeout", type=float, default=60.0)
        p.add_argument("--insecure", action="store_true", help="Disable TLS verification")

    p_info = sub.add_parser("info", help="Server version and build information")
    common(p_info)

    p_login = sub.add_parser("login", help="Validate and store an API key")
    common(p_login)

    p_sources = sub.add_parser("sources", help="List CDM sources")
    common(p_sources)

    p_endpoints = sub.add_parser("endpoints", help="List the WebAPI endpoint catalog")
    common(p_endpoints)
    p_endpoints.add_argument("--group")
    p_endpoints.add_argument("--method")

    p_concepts = sub.add_parser("concepts", help="Search concepts")
    common(p_concepts)
    p_concepts.add_argument("--source", required=True)
    p_concepts.add_argument("--query", required=True)
    p_concepts.add_argument("--rows", type=int, default=25)
    p_concepts.add_argument("--domain")
    p_concepts.add_argument("--vocabulary")

    p_counts = sub.add_parser("concept-counts", help="Record/person counts for concepts")
    common(p_counts)
    p_counts.add_argument("--source", required=True)
    p_counts.add_argument("--concept", action="append", type=int, required=True)

    p_cs = sub.add_parser("concept-sets", help="List concept sets")
    common(p_cs)
    p_cs.add_argument("--id", type=int, help="Show one concept-set expression")

    p_cohorts = sub.add_parser("cohorts", help="List cohort definitions")
    common(p_cohorts)
    p_cohorts.add_argument("--id", type=int, help="Show one cohort definition")

    p_cs_export = sub.add_parser("cohort-set", help="Export or import a cohort set")
    common(p_cs_export)
    action = p_cs_export.add_mutually_exclusive_group(required=True)
    action.add_argument("--export", metavar="PATH", help="Export path (.json, .zip, dir)")
    action.add_argument("--import", dest="import_path", metavar="PATH")
    p_cs_export.add_argument("--id", action="append", type=int, help="Cohort ID (repeatable)")
    p_cs_export.add_argument(
        "--on-conflict", choices=["error", "skip", "rename", "update"], default="rename"
    )
    p_cs_export.add_argument("--dry-run", action="store_true")

    p_call = sub.add_parser("call", help="Invoke a catalog endpoint")
    common(p_call)
    p_call.add_argument("operation")
    p_call.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    p_call.add_argument("--body", help="JSON request body")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = _client(args)
        try:
            if args.command == "info":
                _print(client.info())
            elif args.command == "login":
                api_key = args.api_key or getpass.getpass("OHDSI Atlas API key: ")
                client.login(api_key)
                _print(
                    {
                        "url": client.api_url,
                        "user": client.user,
                        "apiKey": client.masked_api_key,
                    }
                )
            elif args.command == "sources":
                _print(client.sources.list())
            elif args.command == "endpoints":
                result = client.endpoints.find(group=args.group, method=args.method)
                _print(result)
            elif args.command == "concepts":
                _print(
                    client.concepts.search(
                        args.source,
                        args.query,
                        rows=args.rows,
                        domain=args.domain,
                        vocabulary=args.vocabulary,
                    )
                )
            elif args.command == "concept-counts":
                _print(client.cdm_results.concept_counts(args.source, args.concept))
            elif args.command == "concept-sets":
                if args.id:
                    _print(client.concept_sets.expression(args.id))
                else:
                    _print(client.concept_sets.list())
            elif args.command == "cohorts":
                if args.id:
                    _print(client.cohorts.get(args.id))
                else:
                    _print(client.cohorts.list())
            elif args.command == "cohort-set":
                if args.export:
                    bundle = client.cohort_sets.export(args.id, path=args.export)
                    _print(
                        {
                            "path": str(Path(args.export)),
                            "cohorts": len(bundle.cohorts),
                            "conceptSets": len(bundle.concept_sets),
                        }
                    )
                else:
                    import_result = client.cohort_sets.import_(
                        args.import_path,
                        on_conflict=args.on_conflict,
                        dry_run=args.dry_run,
                    )
                    _print(import_result)
            elif args.command == "call":
                params: dict[str, Any] = {}
                for item in args.param:
                    if "=" not in item:
                        parser.error(f"--param must be KEY=VALUE, got {item!r}")
                    key, value = item.split("=", 1)
                    params[key] = _coerce(value)
                if args.body:
                    params["body"] = json.loads(args.body)
                _print(client.call(args.operation, **params))
            else:  # pragma: no cover - argparse enforces commands
                parser.error(f"Unknown command {args.command}")
        finally:
            client.close()
    except OhdsiAtlasClientError as exc:
        print(f"ohdsi_atlas_client: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ohdsi_atlas_client: {exc}", file=sys.stderr)
        return 1
    return 0


def _coerce(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
