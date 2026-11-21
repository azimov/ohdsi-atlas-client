"""Database connection and CDM configuration files.

OHDSI studies usually talk to one database that holds *several* CDM instances:
CCAE v1 through v4, or a ``cdm`` schema alongside a ``cdm_2024`` rebuild. The
connection is the same for all of them; only the schemas differ.

This module stores that shape in a YAML file per source under
``~/.config/ohdsi``:

.. code-block:: yaml

    database:
      driver: postgresql
      connection:
        server: db.example.org/ccae
        port: 5432
        user: ${OHDSI_DB_USER}
        password: ${OHDSI_DB_PASSWORD}

    cdm:
      CCAE_1:
        cdm_database_schema: cdm_v1
        results_database_schema: scratch.scratch_jg
      CCAE_2:
        cdm_database_schema: cdm_v2
        vocabulary_database_schema: vocab
        results_database_schema: scratch.scratch_jg

Values of the form ``${NAME}`` (or ``${NAME:-fallback}``) are resolved from the
environment at load time: the process environment first, then ``.Renviron``,
then ``.env``. Secrets therefore never live in the YAML file.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError

try:  # PyYAML is a dependency, but keep the error message useful.
    import yaml
except ImportError:  # pragma: no cover - exercised only on broken installs
    yaml = None

#: Root of the shared OHDSI configuration directory (``~/.config/ohdsi``).
CONFIG_DIR_ENV = "OHDSI_ATLAS_CLIENT_CONFIG_DIR"

#: Environment variables read in addition to the process environment, in
#: this order. Later files do not override earlier sources.
ENV_FILES: tuple[str, ...] = (".Renviron", ".env")

#: Default CDM subkeys and the fallbacks applied when they are omitted.
CDM_KEYS = (
    "cdm_database_schema",
    "vocabulary_database_schema",
    "results_database_schema",
)

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

#: Accepted ``database.driver`` values, with the aliases people actually write.
DRIVER_ALIASES: dict[str, str] = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "postgres_driver": "postgresql",
    "redshift": "redshift",
    "databricks": "databricks",
    "spark": "spark",
    "sqlite": "sqlite",
    "sqlite3": "sqlite",
    "duckdb": "duckdb",
    "sql server": "sql server",
    "sqlserver": "sql server",
    "mssql": "sql server",
    "pdw": "pdw",
    "oracle": "oracle",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "synapse": "synapse",
    "hive": "hive",
    "impala": "impala",
    "netezza": "netezza",
    "iris": "iris",
}


def config_directory(directory: str | Path | None = None) -> Path:
    """Return the configuration directory, creating it if necessary.

    Precedence: the ``directory`` argument, then
    ``$OHDSI_ATLAS_CLIENT_CONFIG_DIR``, then ``~/.config/ohdsi``.
    """
    if directory is not None:
        path = Path(directory).expanduser()
    elif os.environ.get(CONFIG_DIR_ENV):
        path = Path(os.environ[CONFIG_DIR_ENV]).expanduser()
    else:
        path = Path.home() / ".config" / "ohdsi"
    return path


def env(
    *,
    env_files: Iterable[str | Path] | None = None,
    include_process: bool = True,
) -> dict[str, str]:
    """Collect environment variables from the process, ``.Renviron``, ``.env``.

    Precedence is first-wins: the process environment beats ``.Renviron``,
    which beats ``.env``. ``.Renviron`` is read from the current directory and
    then the home directory, the same order R uses.

    Args:
        env_files: Explicit files to read, in order of precedence, instead of
            the defaults.
        include_process: Include ``os.environ`` (default ``True``).
    """
    collected: dict[str, str] = {}
    if include_process:
        collected.update(os.environ)

    if env_files is not None:
        candidates = [Path(item).expanduser() for item in env_files]
    else:
        candidates = []
        for name in ENV_FILES:
            for base in (Path.cwd(), Path.home()):
                path = base / name
                if path.is_file() and path not in candidates:
                    candidates.append(path)

    for path in candidates:
        if not path.is_file():
            continue
        for key, value in _parse_env_file(path).items():
            collected.setdefault(key, value)
    return collected


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=value`` file, tolerating ``export`` and quotes."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        else:
            # Unquoted values end at the first comment.
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[key] = value
    return values


def resolve_placeholders(
    value: Any,
    variables: Mapping[str, str],
    *,
    where: str = "",
    allow_unresolved: bool = False,
) -> Any:
    """Substitute ``${NAME}`` and ``${NAME:-default}`` in a nested structure.

    Args:
        value: Any nested combination of dicts, lists, and strings.
        variables: Name-to-value mapping, normally from :func:`env`.
        where: Path used in error messages, e.g. ``cdm.CCAE_1``.
        allow_unresolved: Leave unknown placeholders untouched instead of
            raising. Used when only reporting which variables are needed.

    Raises:
        ConfigurationError: An unknown variable is referenced without a
            default and ``allow_unresolved`` is false.
    """
    if isinstance(value, dict):
        return {
            key: resolve_placeholders(
                item, variables, where=_join(where, str(key)), allow_unresolved=allow_unresolved
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            resolve_placeholders(
                item, variables, where=f"{where}[{index}]", allow_unresolved=allow_unresolved
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, str):
        return value

    def substitute(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        if name in variables:
            return variables[name]
        if default is not None:
            return default
        if allow_unresolved:
            return match.group(0)
        location = f" in {where}" if where else ""
        raise ConfigurationError(
            f"Environment variable '{name}' is referenced{location} but is not set. "
            "Define it in your shell, .Renviron, or .env, or give a default "
            f"as ${{{name}:-fallback}}."
        )

    return _PLACEHOLDER.sub(substitute, value)


def placeholders(value: Any) -> set[str]:
    """Return every environment variable name referenced in a structure."""
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found |= placeholders(item)
    elif isinstance(value, list):
        for item in value:
            found |= placeholders(item)
    elif isinstance(value, str):
        found |= {match.group(1) for match in _PLACEHOLDER.finditer(value)}
    return found


def _join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def normalize_driver(driver: str) -> str:
    """Map a user-written driver name onto the canonical DatabaseConnector name."""
    key = str(driver).strip().lower()
    if key in DRIVER_ALIASES:
        return DRIVER_ALIASES[key]
    if not key:
        raise ConfigurationError("database.driver must not be empty")
    raise ConfigurationError(
        f"Unknown database driver '{driver}'. "
        f"Known drivers: {', '.join(sorted(set(DRIVER_ALIASES.values())))}."
    )


@dataclass(slots=True)
class CdmConfig:
    """One CDM instance: the schema layout within a database.

    Attributes:
        key: The name used in the YAML, for example ``CCAE_1``.
        cdm_database_schema: Schema holding the CDM clinical tables.
        vocabulary_database_schema: Schema holding the vocabulary. Defaults to
            ``cdm_database_schema`` when omitted.
        results_database_schema: Schema for cohort and analysis results.
            Defaults to ``cdm_database_schema`` when omitted.
        settings: Any other keys present in the YAML, preserved verbatim.
    """

    key: str
    cdm_database_schema: str
    vocabulary_database_schema: str
    results_database_schema: str
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML-ready mapping for this CDM."""
        payload: dict[str, Any] = {
            "cdm_database_schema": self.cdm_database_schema,
            "vocabulary_database_schema": self.vocabulary_database_schema,
            "results_database_schema": self.results_database_schema,
        }
        payload.update(self.settings)
        return payload


@dataclass(slots=True)
class DatabaseConfig:
    """The connection shared by every CDM in one configuration file.

    Attributes:
        driver: Canonical driver name, for example ``postgresql``.
        connection: Connection arguments, for example ``server``, ``port``,
            ``user``, ``password``. These map onto DatabaseConnector's
            ``createConnectionDetails()`` arguments.
    """

    driver: str
    connection: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceConfig:
    """A parsed configuration file: one database, many CDMs.

    Attributes:
        name: File stem, for example ``ccae`` for ``~/.config/ohdsi/ccae.yaml``.
        path: Absolute path to the file.
        database: The shared connection.
        cdms: Mapping of CDM key to :class:`CdmConfig`.
        atlas: Optional ATLAS/WebAPI settings (``url``, ``api_key``).
        raw: The file contents before placeholder resolution.
    """

    name: str
    path: Path
    database: DatabaseConfig
    cdms: dict[str, CdmConfig]
    atlas: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def cdm_keys(self) -> list[str]:
        """The CDM keys, in file order."""
        return list(self.cdms)

    def cdm(self, key: str | None = None) -> CdmConfig:
        """Return one CDM by key, or the only CDM when ``key`` is ``None``.

        Raises:
            ConfigurationError: The key is unknown, or ``key`` is ``None`` and
                the file holds more than one CDM.
        """
        if key is None:
            if len(self.cdms) == 1:
                return next(iter(self.cdms.values()))
            raise ConfigurationError(
                f"'{self.name}' defines {len(self.cdms)} CDMs "
                f"({', '.join(self.cdm_keys)}); pass cdm= to choose one."
            )
        try:
            return self.cdms[key]
        except KeyError:
            raise ConfigurationError(
                f"'{self.name}' has no CDM '{key}'. Available: {', '.join(self.cdm_keys) or 'none'}."
            ) from None

    def api_key(self, variables: Mapping[str, str] | None = None) -> str | None:
        """Return the resolved ATLAS API key, if the file defines one."""
        if variables is None:
            variables = env()
        raw = self.raw.get("atlas") or {}
        key = raw.get("api_key")
        if key is None:
            return None
        return str(resolve_placeholders(key, variables))


def load_source(
    name: str | Path,
    *,
    directory: str | Path | None = None,
    variables: Mapping[str, str] | None = None,
    resolve: bool = True,
) -> SourceConfig:
    """Load and validate one configuration file.

    Args:
        name: The file stem (``"ccae"``) or a path to a YAML file.
        directory: Configuration directory to search; defaults to
            :func:`config_directory`.
        variables: Environment values for placeholder substitution. Defaults
            to :func:`env`.
        resolve: Substitute ``${VAR}`` placeholders (default). Pass ``False``
            to inspect the raw file.

    Returns:
        A validated :class:`SourceConfig`.

    Raises:
        ConfigurationError: The file is missing, unreadable, invalid YAML, or
            fails validation.
    """
    path = _resolve_path(name, directory)
    if yaml is None:  # pragma: no cover
        raise ConfigurationError("PyYAML is required to read YAML configuration files.")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Could not read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path} must contain a mapping at the top level.")

    if resolve:
        values = resolve_placeholders(raw, variables if variables is not None else env())
    else:
        values = raw
    # Name the file, not just the stem, so multi-file errors are unambiguous.
    return validate_source(values, name=path.name, path=path, raw=raw)


def validate_source(
    payload: Mapping[str, Any],
    *,
    name: str = "",
    path: Path | None = None,
    raw: Mapping[str, Any] | None = None,
) -> SourceConfig:
    """Validate an already-parsed mapping and build a :class:`SourceConfig`.

    Raises:
        ConfigurationError: Required keys are missing or malformed.
    """
    if not isinstance(payload, Mapping):
        raise ConfigurationError("Configuration must be a mapping.")
    label = f" in {name}" if name else ""

    database = payload.get("database")
    if not isinstance(database, Mapping):
        raise ConfigurationError(f"Missing or invalid 'database' section{label}.")
    if "driver" not in database:
        raise ConfigurationError(f"Missing 'database.driver'{label}.")
    driver = normalize_driver(str(database["driver"]))

    connection = database.get("connection")
    if connection is None:
        connection = {}
    if not isinstance(connection, Mapping):
        raise ConfigurationError(f"'database.connection' must be a mapping{label}.")
    connection = dict(connection)
    for key in ("password", "token", "api_key"):
        if key in connection and connection[key] is not None and not isinstance(connection[key], str):
            raise ConfigurationError(
                f"'database.connection.{key}' must be a string after placeholder "
                f"resolution{label}; got {type(connection[key]).__name__}."
            )

    cdms = payload.get("cdm")
    if not isinstance(cdms, Mapping) or not cdms:
        raise ConfigurationError(
            f"Missing or empty 'cdm' section{label}. "
            "Define at least one CDM, for example 'cdm: {CDM_1: {cdm_database_schema: cdm}}'."
        )

    parsed: dict[str, CdmConfig] = {}
    for key, entry in cdms.items():
        if not isinstance(entry, Mapping):
            raise ConfigurationError(f"'cdm.{key}' must be a mapping{label}.")
        cdm_schema = entry.get("cdm_database_schema")
        if not isinstance(cdm_schema, str) or not cdm_schema.strip():
            raise ConfigurationError(f"'cdm.{key}.cdm_database_schema' is required{label}.")
        vocab = entry.get("vocabulary_database_schema") or cdm_schema
        results = entry.get("results_database_schema") or cdm_schema
        unknown = {
            item_key: item_value
            for item_key, item_value in entry.items()
            if item_key not in CDM_KEYS
        }
        parsed[str(key)] = CdmConfig(
            key=str(key),
            cdm_database_schema=str(cdm_schema),
            vocabulary_database_schema=str(vocab),
            results_database_schema=str(results),
            settings=dict(unknown),
        )

    atlas_section = payload.get("atlas") or {}
    if not isinstance(atlas_section, Mapping):
        raise ConfigurationError(f"'atlas' must be a mapping{label}.")

    return SourceConfig(
        name=path.stem if path is not None else name,
        path=path or Path(name or "config"),
        database=DatabaseConfig(driver=driver, connection=connection),
        cdms=parsed,
        atlas=dict(atlas_section),
        raw=dict(raw if raw is not None else payload),
    )


def _resolve_path(name: str | Path, directory: str | Path | None) -> Path:
    path = Path(name).expanduser()
    if path.suffix in {".yaml", ".yml"} or path.is_absolute():
        return path
    return config_directory(directory) / f"{path.name}.yaml"


def list_sources(directory: str | Path | None = None) -> list[str]:
    """List the configuration files available under the OHDSI directory."""
    root = config_directory(directory)
    if not root.is_dir():
        return []
    stems = {item.stem for item in root.glob("*.y*ml") if item.is_file()}
    return sorted(stems)


def load_sources(
    directory: str | Path | None = None,
    *,
    variables: Mapping[str, str] | None = None,
) -> dict[str, SourceConfig]:
    """Load every valid configuration file under the OHDSI directory.

    Files that fail validation are collected and reported together so one
    broken file does not hide the others.

    Raises:
        ConfigurationError: One or more files failed validation.
    """
    values = variables if variables is not None else env()
    loaded: dict[str, SourceConfig] = {}
    problems: list[str] = []
    for stem in list_sources(directory):
        try:
            loaded[stem] = load_source(stem, directory=directory, variables=values)
        except ConfigurationError as exc:
            problems.append(str(exc))
    if problems:
        raise ConfigurationError("Invalid configuration files:\n  " + "\n  ".join(problems))
    return loaded


def find_source(
    name: str | Path | None = None,
    *,
    cdm: str | None = None,
    directory: str | Path | None = None,
    variables: Mapping[str, str] | None = None,
) -> SourceConfig:
    """Load a named file, or search every file for a CDM key.

    With no arguments and exactly one configuration file, that file is used.

    Args:
        name: Configuration file stem or path. Optional when ``cdm`` is given.
        cdm: CDM key to look for across all files, for example ``CCAE_2``.
        directory: Configuration directory.
        variables: Environment values for placeholder substitution.

    Raises:
        ConfigurationError: Nothing matched, or more than one file matched.
    """
    if name is not None:
        return load_source(name, directory=directory, variables=variables)
    values = variables if variables is not None else env()
    loaded = load_sources(directory, variables=values)
    if cdm is None:
        if len(loaded) == 1:
            return next(iter(loaded.values()))
        if not loaded:
            raise ConfigurationError(
                f"No configuration files found in {config_directory(directory)}. "
                "Create one with create_source_config()."
            )
        raise ConfigurationError(
            f"{len(loaded)} configuration files found "
            f"({', '.join(sorted(loaded))}); pass a name or cdm= to choose one."
        )
    matches = [
        source for source in loaded.values() if cdm in source.cdms
    ]
    if not matches:
        raise ConfigurationError(
            f"No configuration defines a CDM named '{cdm}'. Available: "
            + ", ".join(sorted({key for source in loaded.values() for key in source.cdms}))
        )
    if len(matches) > 1:
        raise ConfigurationError(
            f"CDM '{cdm}' is defined in {len(matches)} configuration files "
            f"({', '.join(source.name for source in matches)}); pass the file name too."
        )
    return matches[0]


def write_source(
    name: str,
    *,
    database: DatabaseConfig | Mapping[str, Any],
    cdms: Mapping[str, Mapping[str, Any] | CdmConfig],
    atlas: Mapping[str, Any] | None = None,
    directory: str | Path | None = None,
    overwrite: bool = False,
    comment: bool | str = True,
) -> Path:
    """Write a configuration file and return its path.

    The file is created with mode ``0600`` because it names hosts and users,
    and the directory with ``0700``. Secrets should be ``${VAR}`` placeholders,
    not literal values.

    Args:
        name: File stem, for example ``ccae``.
        database: A :class:`DatabaseConfig` or ``{"driver": ..., "connection": {...}}``.
        cdms: Mapping of CDM key to a :class:`CdmConfig` or schema mapping.
        atlas: Optional ``{"url": ..., "api_key": "${VAR}"}`` section.
        directory: Configuration directory.
        overwrite: Replace an existing file (default ``False``).
        comment: Prepend a short header explaining env placeholders.

    Raises:
        ConfigurationError: The file exists and ``overwrite`` is false, or the
            payload does not validate.
    """
    if isinstance(database, DatabaseConfig):
        database_payload: dict[str, Any] = {
            "driver": database.driver,
            "connection": dict(database.connection),
        }
    else:
        database_payload = dict(database)

    cdm_payload: dict[str, Any] = {}
    for key, entry in cdms.items():
        if isinstance(entry, CdmConfig):
            cdm_payload[str(key)] = entry.to_dict()
        else:
            cdm_payload[str(key)] = dict(entry)

    payload: dict[str, Any] = {"database": database_payload, "cdm": cdm_payload}
    if atlas is not None:
        payload["atlas"] = dict(atlas)

    # Validate before touching the disk.
    validate_source(payload, name=str(name))

    root = config_directory(directory)
    root.mkdir(parents=True, exist_ok=True)
    _chmod(root, 0o700)
    path = root / f"{Path(name).stem}.yaml"
    if path.exists() and not overwrite:
        raise ConfigurationError(f"{path} already exists; pass overwrite=True to replace it.")

    body = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    if comment:
        header = comment if isinstance(comment, str) else _DEFAULT_HEADER
        body = header.rstrip("\n") + "\n\n" + body
    path.write_text(body, encoding="utf-8")
    _chmod(path, 0o600)
    return path


_DEFAULT_HEADER = """\
# OHDSI Atlas client configuration.
# One database, any number of CDMs.
#
# Values like ${MY_VARIABLE} are read from the environment at load time:
# the process environment first, then .Renviron, then .env.
# Never put passwords or API tokens in this file.
#
# database:
#   driver: postgresql            # postgres, databricks, sqlite, sql server, ...
#   connection:                   # passed to DatabaseConnector
#     server: ${OHDSI_DB_SERVER}
#     port: 5432
#     user: ${OHDSI_DB_USER}
#     password: ${OHDSI_DB_PASSWORD}
""".rstrip("\n")


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:  # pragma: no cover - Windows or read-only mounts
        pass


def template_config(
    name: str = "example",
    *,
    driver: str = "postgresql",
    cdms: Iterable[str] = ("CDM_1", "CDM_2"),
    directory: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a commented starter configuration file and return its path.

    The template shows two CDMs pointing at the same database, which is the
    common case (one source, several versions).
    """
    cdm_payload = {
        key: {
            # Braces are literal here; the file is templated, not formatted.
            "cdm_database_schema": "${" + f"{key}_CDM_SCHEMA" + "}",
            "results_database_schema": "${OHDSI_RESULTS_SCHEMA:-results}",
        }
        for key in cdms
    }
    return write_source(
        name,
        database={
            "driver": driver,
            "connection": {
                "server": "${OHDSI_DB_SERVER}",
                "port": "${OHDSI_DB_PORT:-5432}",
                "user": "${OHDSI_DB_USER}",
                "password": "${OHDSI_DB_PASSWORD}",
            },
        },
        cdms=cdm_payload,
        atlas={"url": "${OHDSI_ATLAS_URL}", "api_key": "${OHDSI_ATLAS_CLIENT_API_KEY}"},
        directory=directory,
        overwrite=overwrite,
    )


@dataclass(slots=True)
class ConnectionDetails:
    """DatabaseConnector-style connection details for one configuration.

    Mirrors R's ``DatabaseConnector::createConnectionDetails()``: ``driver``,
    plus the connection arguments as attributes. Use :meth:`as_dict` to pass
    them on.

    Attributes:
        driver: Canonical driver name.
        connection: Connection arguments after placeholder resolution.
        source: The configuration name this came from.
        cdm_key: The CDM this is bound to, when one was chosen.
    """

    driver: str
    connection: dict[str, Any]
    source: str = ""
    cdm_key: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return ``{"driver": ..., **connection}`` ready for a driver call."""
        payload: dict[str, Any] = {"driver": self.driver}
        payload.update(self.connection)
        return payload

    def to_kwargs(self) -> dict[str, Any]:
        """Return connection arguments only (no driver), for ``psycopg`` etc."""
        return dict(self.connection)

    def redacted(self) -> dict[str, Any]:
        """Return a copy safe to log: secrets replaced with ``***``."""
        secret = {"password", "token", "api_key", "apikey", "secret"}
        payload = {
            key: ("***" if key.lower() in secret and value else value)
            for key, value in self.connection.items()
        }
        return {"driver": self.driver, **payload}


def connection_details(
    name: str | Path | None = None,
    *,
    cdm: str | None = None,
    directory: str | Path | None = None,
    variables: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> ConnectionDetails:
    """Build connection details from a configuration file.

    Args:
        name: Configuration file stem or path; omit to search by ``cdm``.
        cdm: CDM key to bind to the connection.
        directory: Configuration directory.
        variables: Environment values for placeholder substitution.
        overrides: Connection arguments that win over the file, for example
            ``{"port": 5433}``.
    """
    source = find_source(name, cdm=cdm, directory=directory, variables=variables)
    connection = dict(source.database.connection)
    if overrides:
        connection.update({key: value for key, value in overrides.items() if value is not None})
    return ConnectionDetails(
        driver=source.database.driver,
        connection=connection,
        source=source.name,
        cdm_key=cdm,
    )


def require_variables(
    name: str | Path,
    *,
    directory: str | Path | None = None,
    variables: Mapping[str, str] | None = None,
) -> dict[str, list[str]]:
    """Report which environment variables a file references and which are missing.

    Useful in CI, where failing with the list of unset names is more helpful
    than failing on the first connection attempt.
    """
    path = _resolve_path(name, directory)
    if yaml is None:  # pragma: no cover
        raise ConfigurationError("PyYAML is required to read YAML configuration files.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    needed = placeholders(raw)
    values = variables if variables is not None else env()
    return {
        "required": sorted(needed),
        "missing": sorted(item for item in needed if item not in values),
    }
