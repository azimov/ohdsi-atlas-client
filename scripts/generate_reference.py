#!/usr/bin/env python3
"""Generate the Python/R API reference and parity report from source.

The reference tables in ``docs/reference.md`` and ``docs/parity.md`` are
generated, not hand-maintained, so they cannot drift from the code.

Usage::

    python scripts/generate_reference.py           # rewrite docs/reference.md
    python scripts/generate_reference.py --check   # fail if docs are stale

The generator reads:

* ``ohdsi-atlas-client/src/ohdsi_atlas_client/resources/*.py`` - Python classes
* ``OhdsiAtlasClient/R/ohdsiAtlasClient-resources.R``         - R6 classes
* ``ohdsi-atlas-client/src/ohdsi_atlas_client/data/endpoints.json``
  - the 344-operation WebAPI catalog
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_RESOURCES = ROOT / "ohdsi-atlas-client" / "src" / "ohdsi_atlas_client" / "resources"
R_RESOURCES = ROOT / "OhdsiAtlasClient" / "R" / "ohdsiAtlasClient-resources.R"
CATALOG = ROOT / "ohdsi-atlas-client" / "src" / "ohdsi_atlas_client" / "data" / "endpoints.json"
REFERENCE_DOC = ROOT / "docs" / "reference.md"

# Python resource class -> (R6 class, atlas attribute name in both languages)
RESOURCES: list[tuple[str, str, str]] = [
    ("SourcesResource", "OhdsiAtlasClientSources", "sources"),
    ("ConceptsResource", "OhdsiAtlasClientConcepts", "concepts"),
    ("ConceptSetsResource", "OhdsiAtlasClientConceptSets", "conceptSets"),
    ("CohortsResource", "OhdsiAtlasClientCohorts", "cohorts"),
    ("CohortSetsResource", "OhdsiAtlasClientCohortSets", "cohortSets"),
    ("CdmResultsResource", "OhdsiAtlasClientCdmResults", "cdmResults"),
    ("JobsResource", "OhdsiAtlasClientJobs", "jobs"),
    ("AnalysesResource", "OhdsiAtlasClientAnalyses", "cohortCharacterizations/pathways/reusable"),
    ("FeatureAnalysesResource", "OhdsiAtlasClientFeatureAnalyses", "featureAnalyses"),
    ("IncidenceRatesResource", "OhdsiAtlasClientIncidenceRates", "incidenceRates"),
    ("TagsResource", "OhdsiAtlasClientTags", "tags"),
    ("AuthResource", "OhdsiAtlasClientAuth", "auth"),
    ("ToolsResource", "OhdsiAtlasClientTools", "tools"),
    ("NotificationsResource", "OhdsiAtlasClientNotifications", "notifications"),
    ("CacheResource", "OhdsiAtlasClientCache", "cache"),
    ("SqlRenderResource", "OhdsiAtlasClientSqlRender", "sqlrender"),
    ("DdlResource", "OhdsiAtlasClientDdl", "ddl"),
    ("EvidenceResource", "OhdsiAtlasClientEvidence", "evidence"),
    ("StatisticResource", "OhdsiAtlasClientStatistic", "statistic"),
]

# Methods that exist only as language glue, not as user-facing operations.
PRIVATE_R = {
    "initialize", "formatPath", "require", "namedById",
    "expressionPayload", "itemRows", "parseCohort",
}
PRIVATE_PY = {"build_bundle", "make_entry", "make_concept_set_entry"}

# Python uses a trailing underscore where the name would shadow a keyword
# (``import_``), or one name covers what R splits into two methods. These are
# naming differences, not missing functionality.
EQUIVALENTS: dict[str, str] = {
    "import_": "import",
}
# Human-readable titles for the section headings.
TITLES: dict[str, str] = {
    "cohortCharacterizations/pathways/reusable": "cohortCharacterizations, pathways, reusable",
}

# Python method -> R method when the names are unrelated.
RENAMED: dict[tuple[str, str], str] = {
    ("SourcesResource", "check"): "checkConnection",
    ("CohortsResource", "print_friendly_cohort"): "printFriendly",
}


def snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def camel_case(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def python_surface() -> dict[str, list[tuple[str, str]]]:
    """Return {class_name: [(method, signature_args)]}."""
    surface: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(PY_RESOURCES.glob("*.py")):
        if path.name in {"base.py", "__init__.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            methods: list[tuple[str, str]] = []
            for item in node.body:
                if not isinstance(item, ast.FunctionDef) or item.name.startswith("_"):
                    continue
                args = [a.arg for a in item.args.args[1:]] + [
                    f"*{a.arg}" for a in item.args.kwonlyargs
                ]
                arg_text = ", ".join(args) if args else ""
                methods.append((item.name, arg_text))
            if methods:
                surface[node.name] = methods
    return surface


def r_surface() -> dict[str, list[tuple[str, str]]]:
    """Return {class_name: [(method, signature_args)]} for R6 classes."""
    text = R_RESOURCES.read_text(encoding="utf-8")
    surface: dict[str, list[tuple[str, str]]] = {}
    parts = re.split(r"(?m)^(OhdsiAtlasClient\w+) <- R6::R6Class\(", text)
    for index in range(1, len(parts), 2):
        name = parts[index]
        body = parts[index + 1]
        methods: list[tuple[str, str]] = []
        for match in re.finditer(r"(?m)^    (\w+) = function\(([^)]*)\)", body):
            methods.append((match.group(1), " ".join(match.group(2).split())))
        surface[name] = methods
    return surface


def catalog_stats() -> tuple[int, dict[str, int]]:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for endpoint in payload["endpoints"]:
        counts[endpoint["group"]] = counts.get(endpoint["group"], 0) + 1
    return payload["endpointCount"], counts


# Module-level helpers: (concept, Python, R). These are functions rather than
# methods, so they are documented from a fixed list that CI verifies.
HELPERS: list[tuple[str, str, str]] = [
    ("Create a client from an ATLAS URL", "Atlas(url, api_key=...)", "connectAtlas(url, apiKey = ...)"),
    ("Discover the WebAPI root", "discover(url)", "discoverAtlas(url)"),
    ("Create a client from a config file", "connect_from_config(name)", "connectAtlas(url) + readSourceConfig()"),
    ("Configuration directory", "config_directory()", "configDirectory()"),
    ("List configuration files", "list_sources()", "listSourceConfigs()"),
    ("Read one configuration file", "load_source(name)", "readSourceConfig(name)"),
    ("Read every configuration file", "load_sources()", "readSourceConfigs()"),
    ("Find a file by CDM key", "find_source(cdm=...)", "findSourceConfig(cdm = ...)"),
    ("Write a configuration file", "write_source(name, database, cdms)", "createSourceConfig(name, database, cdms)"),
    ("Write a starter configuration", "template_config(name)", "createSourceConfigTemplate(name)"),
    ("Select one CDM", "source.cdm(key)", "selectCdm(source, key)"),
    ("Connection details", "connection_details(name, cdm=...)", "connectionDetails(name, cdm = ...)"),
    ("DatabaseConnector arguments", "details.as_dict()", "databaseConnectorArguments(details)"),
    ("Environment for placeholders", "env()", "readEnvironment()"),
    ("Substitute ${VAR} placeholders", "resolve_placeholders(value, vars)", "resolvePlaceholders(value, vars)"),
    ("Which variables are needed", "require_variables(name)", "requiredVariables(name)"),
    ("Validate a parsed configuration", "load_source(..., resolve=False)", "validateSourceConfig(payload)"),
    ("Any WebAPI operation", "atlas.call(operation_id, ...)", "atlas$call(operationId, ...)"),
    ("Any WebAPI path", "atlas.request(method, path, ...)", "atlas$request(method, path, ...)"),
    ("Endpoint catalog", "atlas.endpoints / atlas.endpoints.find()", "atlas$endpoints()"),
    ("Build a cohort-set bundle", "CohortSetBundle.from_cohorts()", "ohdsiAtlasClientBundleFromCohorts()"),
    ("Save a bundle", "atlas.cohort_sets.export(path=...)", "ohdsiAtlasClientBundleSave()"),
    ("Load a bundle", "CohortSetBundle.load(path)", "ohdsiAtlasClientBundleLoad()"),
    ("Validate a bundle", "bundle.validate()", "ohdsiAtlasClientBundleValidate()"),
]


def build_document() -> str:
    py = python_surface()
    r_methods = r_surface()
    total_ops, group_counts = catalog_stats()

    lines: list[str] = []
    add = lines.append
    add("# API reference\n")
    add(
        "<!-- Generated by scripts/generate_reference.py. Do not edit by hand. -->\n"
    )
    add(
        "Every typed method on both clients, grouped by resource. The "
        "`atlas.` column is the Python call path; the R column is the "
        "equivalent. Arguments are shown without defaults - see the "
        "docstrings / `?OhdsiAtlasClient` help for full signatures.\n"
    )
    add(
        f"The WebAPI 3.0 catalog contains **{total_ops} operations**. Typed "
        "methods cover the common ones; anything not listed here is still "
        "reachable with `call()` / `request()` (see [endpoints.md](endpoints.md)).\n"
    )

    summary_rows: list[str] = []
    gaps_rows: list[str] = []

    for py_class, r_class, attr in RESOURCES:
        py_methods = py.get(py_class, [])
        r_methods_list = [
            (name, args) for name, args in r_methods.get(r_class, [])
            if name not in PRIVATE_R
        ]
        r_by_snake = {snake_case(name): (name, args) for name, args in r_methods_list}

        def r_match_for(method: str) -> tuple[str, str] | None:
            renamed = RENAMED.get((py_class, method))
            if renamed:
                return r_by_snake.get(snake_case(renamed))
            return r_by_snake.get(EQUIVALENTS.get(method, method))

        def py_match_for(r_name: str) -> str | None:
            for candidate, target in RENAMED.items():
                if candidate[0] == py_class and snake_case(target) == snake_case(r_name):
                    return candidate[1]
            for method, _ in py_methods:
                if EQUIVALENTS.get(method, method) == snake_case(r_name):
                    return method
            return None

        public_py = [(n, a) for n, a in py_methods if n not in PRIVATE_PY]
        only_py = [n for n, _ in public_py if r_match_for(n) is None]
        only_r = [name for name, _ in r_methods_list if py_match_for(name) is None]

        py_only = len(only_py)
        r_only = len(only_r)
        parity = "exact" if py_only == 0 and r_only == 0 else (
            "Python only" if py_only and not r_only else
            "R only" if r_only and not py_only else
            "differs"
        )
        summary_rows.append(
            f"| `{attr.split('/')[0]}` | {len(public_py)} | {len(r_methods_list)} | {parity} |"
        )
        if only_py or only_r:
            parts = []
            if only_py:
                parts.append("Python only: " + ", ".join(f"`{n}`" for n in only_py))
            if only_r:
                parts.append("R only: " + ", ".join(f"`{n}`" for n in only_r))
            gaps_rows.append(f"| `{attr.split('/')[0]}` | {'; '.join(parts)} |")

        title = TITLES.get(attr, attr)
        add(f"\n## `{title}`\n")
        add(
            f"Python: `atlas.{attr.split('/')[0]}.<method>` &nbsp;&nbsp; "
            f"R: `atlas${attr.split('/')[0]}$<method>`\n"
        )
        add("| Operation | Python | R |")
        add("|---|---|---|")
        # Union, preserving Python order then R-only entries.
        seen_r: set[str] = set()
        for name, args in public_py:
            r_match = r_match_for(name)
            py_cell = f"`{name}({args})`" if args else f"`{name}()`"
            if r_match:
                r_name, r_args = r_match
                seen_r.add(r_name)
                r_cell = f"`{r_name}({r_args})`" if r_args else f"`{r_name}()`"
            else:
                r_cell = "_not implemented_"
            add(f"| `{name}` | {py_cell} | {r_cell} |")
        for name, args in r_methods_list:
            if name in seen_r:
                continue
            r_cell = f"`{name}({args})`" if args else f"`{name}()`"
            add(f"| `{name}` | _not implemented_ | {r_cell} |")

    # Insert summary after the intro, before the first resource section.
    summary = ["\n## Summary\n", "| Resource | Python methods | R methods | Parity |", "|---|---:|---:|---|"]
    summary.extend(summary_rows)
    summary.append("")
    py_total = sum(len([n for n, _ in py.get(c, []) if n not in PRIVATE_PY]) for c, _, _ in RESOURCES)
    r_total = sum(
        len([n for n, _ in r_methods.get(c, []) if n not in PRIVATE_R]) for _, c, _ in RESOURCES
    )
    summary.append(f"**Total:** {py_total} Python methods, {r_total} R methods.\n")

    if gaps_rows:
        summary.append("## Where the two clients differ\n")
        summary.append(
            "These are real gaps, not documentation errors. Use `call()` / "
            "`request()` on the missing side, or add the method.\n"
        )
        summary.append("| Resource | Difference |")
        summary.append("|---|---|")
        summary.extend(gaps_rows)
        summary.append("")

    intro_end = next(
        (i for i, line in enumerate(lines) if line.startswith("## `")), len(lines)
    )
    lines = lines[:intro_end] + summary + lines[intro_end:]
    add = lines.append

    helpers: list[str] = []
    helpers.append("")
    helpers.append("## Helpers outside the resource namespaces")
    helpers.append("")
    helpers.append(
        "Connection, configuration, and bundle helpers are module-level "
        "functions rather than resource methods."
    )
    helpers.append("")
    helpers.append("| Purpose | Python | R |")
    helpers.append("|---|---|---|")
    for purpose, py_name, r_name in HELPERS:
        helpers.append(f"| {purpose} | `{py_name}` | `{r_name}` |")
    helpers.append("")
    insert_at = next(
        (i for i, line in enumerate(lines) if line.startswith("## Summary")), 0
    )
    lines = lines[:insert_at] + helpers + lines[insert_at:]
    add = lines.append

    add("\n## WebAPI operation groups\n")
    add("| Group | Operations |")
    add("|---|---:|")
    for group, count in sorted(group_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        add(f"| `{group}` | {count} |")
    add("")
    add(
        "These counts are the full WebAPI 3.0 surface from the bundled "
        "catalog, not the number of typed methods.\n"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if docs/reference.md is out of date",
    )
    args = parser.parse_args()

    document = build_document()
    if args.check:
        current = REFERENCE_DOC.read_text(encoding="utf-8") if REFERENCE_DOC.exists() else ""
        if current != document:
            print(
                "docs/reference.md is out of date; run "
                "python scripts/generate_reference.py",
                file=sys.stderr,
            )
            return 1
        print("docs/reference.md is up to date")
        return 0

    REFERENCE_DOC.write_text(document, encoding="utf-8")
    print(f"Wrote {REFERENCE_DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
