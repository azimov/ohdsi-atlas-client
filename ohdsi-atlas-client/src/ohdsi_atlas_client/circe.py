"""Optional Circepy integration.

The client works without Circepy: expressions are plain dictionaries and the
server validates them. When ``ohdsi-circepy`` is installed these helpers
convert to/from typed models and run Circepy's local cohort checks.

Conversion is intentionally one-way for validation and construction:

* :func:`to_dict` never depends on Circepy.
* :func:`to_circe_cohort` / :func:`to_circe_concept_set` build models.
* :func:`from_circe` serialises with aliases so WebAPI receives Circe's
  uppercase concept fields and ``ConceptSets`` capitalisation.

Circepy models are a *subset* of WebAPI's wire format (caption and date fields
on concepts are not modelled), so keep the original dictionary when exact
round-trip fidelity matters.
"""

from __future__ import annotations

import json
from typing import Any

from .exceptions import ConfigurationError

_circe: Any = None
try:  # pragma: no cover - exercised when the extra is installed
    import circe as _circe_module

    _circe = _circe_module
    CIRCE_AVAILABLE = True
except Exception:  # pragma: no cover - the default installation
    CIRCE_AVAILABLE = False


def require_circe() -> Any:
    """Return the ``circe`` module or raise a helpful error."""
    if not CIRCE_AVAILABLE:
        raise ConfigurationError(
            "Circepy is not installed. Install it with 'pip install ohdsi-atlas-client[circe]' "
            "or 'pip install ohdsi-circepy'."
        )
    return _circe


def is_circe_model(value: Any) -> bool:
    """Return whether ``value`` is a Circepy pydantic model."""
    if not CIRCE_AVAILABLE or value is None:
        return False
    return value.__class__.__module__.startswith("circe.") and callable(
        getattr(value, "model_dump", None)
    )


def to_dict(value: Any) -> Any:
    """Convert a dictionary, pydantic model, or Circepy model to plain data."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return to_dict(dump(by_alias=True, exclude_none=True))
    return value


def to_circe_cohort(expression: Any) -> Any:
    """Convert a dictionary or model to ``circe.CohortExpression``.

    Raises:
        ConfigurationError: If Circepy is not installed.
        pydantic.ValidationError: If the expression is invalid.
    """
    module = require_circe()
    if is_circe_model(expression) and isinstance(expression, module.CohortExpression):
        return expression
    value = json.loads(expression) if isinstance(expression, str) else to_dict(expression)
    if isinstance(value, dict) and "expression" in value and "PrimaryCriteria" not in value:
        value = value.get("expression") or {}
    if isinstance(value, str):
        value = json.loads(value)
    return module.CohortExpression.model_validate(value)


def to_circe_concept_set(expression: Any) -> Any:
    """Convert a dictionary or model to ``circe.ConceptSetExpression``."""
    module = require_circe()
    if is_circe_model(expression) and isinstance(expression, module.ConceptSetExpression):
        return expression
    if isinstance(expression, str):
        return module.ConceptSetExpression.model_validate(json.loads(expression))
    value = to_dict(expression)
    if isinstance(value, dict) and "items" not in value and "expression" in value:
        value = value.get("expression") or {}
    return module.ConceptSetExpression.model_validate(value)


def from_circe(value: Any) -> Any:
    """Serialise a Circepy model to the WebAPI wire format (aliases, no nulls)."""
    if not is_circe_model(value):
        return to_dict(value)
    return value.model_dump(by_alias=True, exclude_none=True, mode="json")


def _criteria_key_paths(value: Any, path: str = "") -> list[tuple[str, tuple[str, ...]]]:
    """Collect the criteria-class keys at every ``CriteriaList`` in an expression."""
    found: list[tuple[str, tuple[str, ...]]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else key
            if key == "CriteriaList" and isinstance(item, list):
                for index, entry in enumerate(item):
                    if isinstance(entry, dict) and entry:
                        found.append((f"{child}[{index}]", tuple(entry.keys())))
                continue
            found.extend(_criteria_key_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_criteria_key_paths(item, f"{path}[{index}]"))
    return found


def assert_criteria_preserved(expression: Any) -> None:
    """Guard against Circepy's silent criteria-union fallback.

    Circepy's smart union substitutes a default ``ConditionOccurrence`` when a
    criteria object fails validation. That changes the cohort's meaning without
    raising. Compare criteria class names before and after validation and raise
    when they differ.
    """
    if is_circe_model(expression):
        return
    original = to_dict(expression)
    if not isinstance(original, dict):
        return
    model = to_circe_cohort(original)
    normalised = from_circe(model)
    before = _criteria_key_paths(original)
    after = dict(_criteria_key_paths(normalised))
    for path, keys in before:
        if path in after and after[path] != keys:
            raise ValueError(
                "Circepy silently changed criteria at "
                f"{path}: {keys} became {after[path]}. "
                "The cohort expression is invalid (check criteria keys and field "
                "types); refusing to treat it as parsed."
            )


def validate_cohort(expression: Any) -> list[dict[str, Any]]:
    """Run Circepy's local cohort checks.

    Returns a list of warning dictionaries with ``severity`` and ``message``
    (plus any fields Circepy exposes). An empty list means no warnings.
    """
    assert_criteria_preserved(expression)
    model = to_circe_cohort(expression)
    warnings = model.check()
    result: list[dict[str, Any]] = []
    for warning in warnings:
        severity = getattr(warning, "severity", None)
        result.append(
            {
                "severity": getattr(severity, "name", str(severity)),
                "message": getattr(warning, "message", str(warning)),
                "warning": warning,
            }
        )
    return result


def cohort_sql(expression: Any, options: Any = None) -> str:
    """Build OHDSI template SQL locally with Circepy (no WebAPI call)."""
    module = require_circe()
    model = to_circe_cohort(expression)
    if options is not None and not hasattr(options, "cdm_schema"):
        from circe.cohortdefinition import (
            BuildExpressionQueryOptions,
        )

        values = to_dict(options) or {}
        built = BuildExpressionQueryOptions()  # type: ignore[no-untyped-call]
        for key, value in values.items():
            if hasattr(built, key):
                setattr(built, key, value)
        options = built
    return str(module.build_cohort_query(model, options))


def checksum(expression: Any) -> str:
    """Return Circepy's normalised SHA-256 checksum for a cohort expression."""
    return str(to_circe_cohort(expression).checksum())
