"""Tests for database/CDM configuration files and environment resolution."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from ohdsi_atlas_client import config
from ohdsi_atlas_client.config import (
    CdmConfig,
    DatabaseConfig,
    config_directory,
    connection_details,
    env,
    find_source,
    list_sources,
    load_source,
    load_sources,
    require_variables,
    resolve_placeholders,
    template_config,
    write_source,
)
from ohdsi_atlas_client.exceptions import ConfigurationError

VARIABLES = {
    "DB_SERVER": "db.example.org/ccae",
    "DB_USER": "analyst",
    "DB_PASSWORD": "s3cret",
    "ATLAS_URL": "https://atlas.example.org",
    "ATLAS_KEY": "wa_key",
    "CCAE_1_CDM_SCHEMA": "cdm_v1",
    "CCAE_2_CDM_SCHEMA": "cdm_v2",
}


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    return tmp_path / "ohdsi"


def _ccae(config_dir: Path, **kwargs: object) -> Path:
    """Write a two-CDM CCAE config with env placeholders."""
    return write_source(
        "ccae",
        database=DatabaseConfig(
            driver="postgresql",
            connection={
                "server": "${DB_SERVER}",
                "port": 5432,
                "user": "${DB_USER}",
                "password": "${DB_PASSWORD}",
            },
        ),
        cdms={
            "CCAE_1": {"cdm_database_schema": "cdm_v1", "results_database_schema": "scratch.jg"},
            "CCAE_2": {
                "cdm_database_schema": "cdm_v2",
                "vocabulary_database_schema": "vocab",
                "results_database_schema": "scratch.jg",
            },
        },
        directory=config_dir,
        **kwargs,  # type: ignore[arg-type]
    )


# -- directory handling ------------------------------------------------------


def test_config_directory_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.CONFIG_DIR_ENV, raising=False)
    assert config_directory() == Path.home() / ".config" / "ohdsi"

    monkeypatch.setenv(config.CONFIG_DIR_ENV, str(tmp_path / "fromenv"))
    assert config_directory() == tmp_path / "fromenv"
    assert config_directory(tmp_path / "explicit") == tmp_path / "explicit"


# -- environment resolution --------------------------------------------------


def test_env_reads_renviron_then_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".Renviron").write_text("FROM_RENVIRON=renviron\nSHARED=renviron\n")
    (tmp_path / ".env").write_text("FROM_DOTENV=dotenv\nSHARED=dotenv\n")
    monkeypatch.chdir(tmp_path)
    uppercase = {"RENVIRON_ONLY": "1"}
    values = env()
    values.update(uppercase)
    assert values["FROM_RENVIRON"] == "renviron"
    assert values["FROM_DOTENV"] == "dotenv"
    # .Renviron wins over .env for the same key.
    assert values["SHARED"] == "renviron"


def test_process_environment_beats_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("WHO=envfile\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WHO", "process")
    assert env()["WHO"] == "process"


def test_env_file_parsing_handles_quotes_and_comments(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        """
# a comment
plain=value
quoted="has spaces"
single='single'
export EXPORTED=yes
trailing=text # comment
blank=
invalid line without equals
""".lstrip()
    )
    values = env(env_files=[path], include_process=False)
    assert values["plain"] == "value"
    assert values["quoted"] == "has spaces"
    assert values["single"] == "single"
    assert values["EXPORTED"] == "yes"
    assert values["trailing"] == "text"
    assert values["blank"] == ""
    assert "invalid line without equals" not in values


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    values = env(env_files=[tmp_path / "nope.env"], include_process=False)
    assert values == {}


# -- placeholder substitution ------------------------------------------------


def test_placeholders_resolve_and_default() -> None:
    resolved = resolve_placeholders(
        {"a": "${DB_USER}", "b": "${MISSING:-fallback}", "c": 1, "d": ["${DB_USER}"]},
        {"DB_USER": "analyst"},
    )
    assert resolved == {"a": "analyst", "b": "fallback", "c": 1, "d": ["analyst"]}


def test_unset_placeholder_names_the_location() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        resolve_placeholders({"cdm": {"CCAE_1": {"password": "${NOPE}"}}}, {})
    message = str(excinfo.value)
    assert "NOPE" in message
    assert "cdm.CCAE_1.password" in message
    assert ".Renviron" in message


def test_allow_unresolved_leaves_placeholder_intact() -> None:
    resolved = resolve_placeholders("${NOPE}", {}, allow_unresolved=True)
    assert resolved == "${NOPE}"


# -- writing -----------------------------------------------------------------


def test_write_creates_private_files(config_dir: Path) -> None:
    path = _ccae(config_dir)
    assert path.exists()
    assert path.name == "ccae.yaml"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(config_dir.stat().st_mode) == 0o700


def test_write_refuses_to_clobber_without_overwrite(config_dir: Path) -> None:
    _ccae(config_dir)
    with pytest.raises(ConfigurationError, match="already exists"):
        _ccae(config_dir)
    _ccae(config_dir, overwrite=True)


def test_write_includes_guidance_header(config_dir: Path) -> None:
    text = _ccae(config_dir).read_text()
    assert ".Renviron" in text
    assert "${DB_PASSWORD}" in text


def test_write_validates_before_writing(config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match="cdm"):
        write_source(
            "broken",
            database={"driver": "postgresql", "connection": {}},
            cdms={},
            directory=config_dir,
        )
    assert not (config_dir / "broken.yaml").exists()


def test_template_has_two_cdms_and_atlas_section(config_dir: Path) -> None:
    path = template_config("example", directory=config_dir)
    assert path.exists()

    # The template is only loadable once its variables are defined; the error
    # names the first missing one rather than failing obscurely later.
    template_vars = dict(
        VARIABLES,
        CDM_1_CDM_SCHEMA="cdm_1",
        CDM_2_CDM_SCHEMA="cdm_2",
        OHDSI_DB_SERVER="db.example.org",
        OHDSI_DB_USER="analyst",
        OHDSI_DB_PASSWORD="s3cret",
        OHDSI_ATLAS_URL="https://atlas.example.org",
        OHDSI_ATLAS_CLIENT_API_KEY="wa_key",
    )
    source = load_source("example", directory=config_dir, variables=template_vars)
    assert source.cdm_keys == ["CDM_1", "CDM_2"]
    assert source.atlas["url"] == "https://atlas.example.org"
    # Defaults fill in the schema and port.
    assert source.cdm("CDM_1").results_database_schema == "results"
    assert source.database.connection["port"] == "5432"

    with pytest.raises(ConfigurationError, match="OHDSI_DB_SERVER"):
        load_source("example", directory=config_dir, variables=VARIABLES)


# -- loading and validation --------------------------------------------------


def test_load_returns_one_database_and_many_cdms(config_dir: Path) -> None:
    _ccae(config_dir)
    source = load_source("ccae", directory=config_dir, variables=VARIABLES)

    assert source.name == "ccae"
    assert source.database.driver == "postgresql"
    assert source.database.connection["server"] == "db.example.org/ccae"
    assert source.database.connection["password"] == "s3cret"
    assert source.cdm_keys == ["CCAE_1", "CCAE_2"]

    first = source.cdm("CCAE_1")
    assert first.cdm_database_schema == "cdm_v1"
    assert first.results_database_schema == "scratch.jg"
    # Vocabulary defaults to the CDM schema when omitted.
    assert first.vocabulary_database_schema == "cdm_v1"


def test_cdm_preserves_extra_settings(config_dir: Path) -> None:
    write_source(
        "extra",
        database={"driver": "postgresql", "connection": {}},
        cdms={"X": {"cdm_database_schema": "cdm", "tempo": "fast"}},
        directory=config_dir,
    )
    source = load_source("extra", directory=config_dir, variables={})
    assert source.cdm("X").settings == {"tempo": "fast"}
    assert source.cdm("X").to_dict()["tempo"] == "fast"


def test_choosing_between_multiple_cdms(config_dir: Path) -> None:
    _ccae(config_dir)
    source = load_source("ccae", directory=config_dir, variables=VARIABLES)
    with pytest.raises(ConfigurationError, match="pass cdm="):
        source.cdm()
    with pytest.raises(ConfigurationError, match="CCAE_1"):
        source.cdm("NOPE")


def test_single_cdm_is_selected_implicitly(config_dir: Path) -> None:
    write_source(
        "one",
        database={"driver": "postgresql", "connection": {}},
        cdms={"ONLY": {"cdm_database_schema": "cdm"}},
        directory=config_dir,
    )
    source = load_source("one", directory=config_dir, variables={})
    assert source.cdm().key == "ONLY"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"cdm": {"A": {"cdm_database_schema": "s"}}}, "database"),
        ({"database": {}, "cdm": {"A": {"cdm_database_schema": "s"}}}, "driver"),
        ({"database": {"driver": "postgresql"}}, "cdm"),
        ({"database": {"driver": "postgresql"}, "cdm": {}}, "cdm"),
        ({"database": {"driver": "postgresql"}, "cdm": {"A": {}}}, "cdm_database_schema"),
        (
            {"database": {"driver": "postgresql", "connection": "nope"}, "cdm": {"A": {"cdm_database_schema": "s"}}},
            "connection",
        ),
        (
            {"database": {"driver": "nonsense"}, "cdm": {"A": {"cdm_database_schema": "s"}}},
            "Unknown database driver",
        ),
        ({"database": {"driver": "postgresql"}, "cdm": {"A": "string"}}, "must be a mapping"),
    ],
)
def test_validation_errors(payload: dict[str, object], message: str, config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match=message):
        config.validate_source(payload)


def test_driver_aliases_are_canonicalised() -> None:
    for written, canonical in [
        ("postgres", "postgresql"),
        ("PostgreSQL", "postgresql"),
        ("sqlserver", "sql server"),
        ("mssql", "sql server"),
        ("spark", "spark"),
    ]:
        assert config.normalize_driver(written) == canonical


def test_invalid_yaml_reports_the_file(config_dir: Path) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "bad.yaml").write_text("database: [unclosed\n")
    with pytest.raises(ConfigurationError, match="not valid YAML"):
        load_source("bad", directory=config_dir, variables={})


def test_non_mapping_file_is_rejected(config_dir: Path) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "list.yaml").write_text("- a\n- b\n")
    with pytest.raises(ConfigurationError, match="mapping"):
        load_source("list", directory=config_dir, variables={})


def test_missing_file_reports_the_path(config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match="Could not read"):
        load_source("absent", directory=config_dir, variables={})


def test_load_without_resolution_keeps_placeholders(config_dir: Path) -> None:
    _ccae(config_dir)
    source = load_source("ccae", directory=config_dir, resolve=False)
    assert source.database.connection["password"] == "${DB_PASSWORD}"


# -- listing and discovery ---------------------------------------------------


def test_list_sources_finds_yaml_files(config_dir: Path) -> None:
    assert list_sources(config_dir) == []
    _ccae(config_dir)
    (config_dir / "notes.txt").write_text("ignored")
    assert list_sources(config_dir) == ["ccae"]


def test_load_sources_collects_all_files(config_dir: Path) -> None:
    _ccae(config_dir)
    write_source(
        "other",
        database={"driver": "sqlite", "connection": {"path": "x.sqlite"}},
        cdms={"YLE": {"cdm_database_schema": "main"}},
        directory=config_dir,
    )
    loaded = load_sources(config_dir, variables=VARIABLES)
    assert set(loaded) == {"ccae", "other"}


def test_load_sources_reports_every_bad_file(config_dir: Path) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "a.yaml").write_text("database: {}\n")
    (config_dir / "b.yaml").write_text("nope: true\n")
    with pytest.raises(ConfigurationError) as excinfo:
        load_sources(config_dir, variables={})
    message = str(excinfo.value)
    assert "a.yaml" in message and "b" in message


def test_find_source_by_cdm_key(config_dir: Path) -> None:
    _ccae(config_dir)
    write_source(
        "other",
        database={"driver": "sqlite", "connection": {}},
        cdms={"OTHER": {"cdm_database_schema": "main"}},
        directory=config_dir,
    )
    source = find_source(cdm="CCAE_2", directory=config_dir, variables=VARIABLES)
    assert source.name == "ccae"


def test_find_source_requires_a_choice_when_ambiguous(config_dir: Path) -> None:
    _ccae(config_dir)
    write_source(
        "other",
        database={"driver": "sqlite", "connection": {}},
        cdms={"OTHER": {"cdm_database_schema": "main"}},
        directory=config_dir,
    )
    with pytest.raises(ConfigurationError, match="pass a name"):
        find_source(directory=config_dir, variables=VARIABLES)


def test_find_source_with_no_files_explains_how_to_start(config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match="create_source_config"):
        find_source(directory=config_dir, variables={})


def test_find_source_finds_single_file(config_dir: Path) -> None:
    _ccae(config_dir)
    assert find_source(directory=config_dir, variables=VARIABLES).name == "ccae"


def test_find_source_unknown_cdm_lists_available(config_dir: Path) -> None:
    _ccae(config_dir)
    with pytest.raises(ConfigurationError, match="CCAE_1"):
        find_source(cdm="NOPE", directory=config_dir, variables=VARIABLES)


def test_duplicate_cdm_key_across_files_is_reported(config_dir: Path) -> None:
    _ccae(config_dir)
    write_source(
        "copy",
        database={"driver": "postgresql", "connection": {}},
        cdms={"CCAE_1": {"cdm_database_schema": "cdm"}},
        directory=config_dir,
    )
    with pytest.raises(ConfigurationError, match="defined in 2"):
        find_source(cdm="CCAE_1", directory=config_dir, variables=VARIABLES)


# -- connection details ------------------------------------------------------


def test_connection_details_merge_driver_and_connection(config_dir: Path) -> None:
    _ccae(config_dir)
    details = connection_details("ccae", cdm="CCAE_1", directory=config_dir, variables=VARIABLES)
    payload = details.as_dict()
    assert payload["driver"] == "postgresql"
    assert payload["server"] == "db.example.org/ccae"
    assert payload["password"] == "s3cret"
    assert details.cdm_key == "CCAE_1"
    assert details.source == "ccae"
    assert details.to_kwargs() == dict(details.connection)


def test_connection_details_overrides(config_dir: Path) -> None:
    _ccae(config_dir)
    details = connection_details(
        "ccae", directory=config_dir, variables=VARIABLES, overrides={"port": 6543}
    )
    assert details.connection["port"] == 6543


def test_connection_details_redact_secrets(config_dir: Path) -> None:
    _ccae(config_dir)
    details = connection_details("ccae", directory=config_dir, variables=VARIABLES)
    redacted = details.redacted()
    assert redacted["password"] == "***"
    assert "s3cret" not in str(redacted)
    assert details.connection["password"] == "s3cret"


# -- required variables ------------------------------------------------------


def test_require_variables_reports_missing(config_dir: Path) -> None:
    _ccae(config_dir)
    report = require_variables("ccae", directory=config_dir, variables={"DB_USER": "a"})
    assert report["required"] == ["DB_PASSWORD", "DB_SERVER", "DB_USER"]
    assert report["missing"] == ["DB_PASSWORD", "DB_SERVER"]


def test_require_variables_ignores_defaults(config_dir: Path) -> None:
    write_source(
        "defaults",
        database={"driver": "postgresql", "connection": {"server": "${S:-localhost}"}},
        cdms={"A": {"cdm_database_schema": "cdm"}},
        directory=config_dir,
    )
    report = require_variables("defaults", directory=config_dir, variables={})
    assert report["required"] == ["S"]
    assert report["missing"] == ["S"]


# -- Atlas settings ----------------------------------------------------------


def test_api_key_is_resolved_from_the_environment(config_dir: Path) -> None:
    _ccae(config_dir)
    write_source(
        "atlas",
        database={"driver": "postgresql", "connection": {}},
        cdms={"A": {"cdm_database_schema": "cdm"}},
        atlas={"url": "${ATLAS_URL}", "api_key": "${ATLAS_KEY}"},
        directory=config_dir,
        overwrite=True,
    )
    source = load_source("atlas", directory=config_dir, variables=VARIABLES)
    assert source.api_key(VARIABLES) == "wa_key"


def test_api_key_is_none_without_an_atlas_section(config_dir: Path) -> None:
    _ccae(config_dir)
    source = load_source("ccae", directory=config_dir, variables=VARIABLES)
    assert source.api_key(VARIABLES) is None


def test_cdm_config_to_dict_round_trips() -> None:
    cdm = CdmConfig(
        key="A",
        cdm_database_schema="cdm",
        vocabulary_database_schema="vocab",
        results_database_schema="res",
        settings={"note": "x"},
    )
    payload = cdm.to_dict()
    assert payload["cdm_database_schema"] == "cdm"
    assert payload["note"] == "x"
    assert config.validate_source(
        {"database": {"driver": "sqlite"}, "cdm": {"A": payload}}
    ).cdm("A").results_database_schema == "res"


def test_validation_edges_are_reported_clearly() -> None:
    with pytest.raises(ConfigurationError, match="must be a mapping"):
        config.validate_source(["not", "a", "mapping"])  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError, match="must not be empty"):
        config.validate_source({"database": {"driver": "  "}, "cdm": {}})
    with pytest.raises(ConfigurationError, match="'atlas' must be a mapping"):
        config.validate_source(
            {
                "database": {"driver": "sqlite"},
                "cdm": {"A": {"cdm_database_schema": "cdm"}},
                "atlas": "https://nope",
            }
        )


def test_secret_fields_must_be_strings() -> None:
    with pytest.raises(ConfigurationError, match="must be a string"):
        config.validate_source(
            {
                "database": {"driver": "sqlite", "connection": {"password": {"nested": 1}}},
                "cdm": {"A": {"cdm_database_schema": "cdm"}},
            }
        )


def test_write_accepts_cdm_config_objects(config_dir: Path) -> None:
    path = write_source(
        "objects",
        database=DatabaseConfig(driver="sqlite", connection={"path": "x.sqlite"}),
        cdms={
            "A": CdmConfig(
                key="A",
                cdm_database_schema="main",
                vocabulary_database_schema="main",
                results_database_schema="results",
                settings={"note": "preserved"},
            )
        },
        directory=config_dir,
        comment=False,
    )
    source = load_source("objects", directory=config_dir, variables={})
    assert source.cdm("A").settings == {"note": "preserved"}
    assert "OHDSI Atlas client configuration" not in path.read_text()


def test_absolute_path_to_a_config_file(tmp_path: Path) -> None:
    directory = tmp_path / "nested"
    path = write_source(
        "abs",
        database={"driver": "sqlite", "connection": {}},
        cdms={"A": {"cdm_database_schema": "main"}},
        directory=directory,
    )
    assert load_source(path, variables={}).cdm_keys == ["A"]


def test_api_key_uses_process_environment_by_default(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_source(
        "envkey",
        database={"driver": "sqlite", "connection": {}},
        cdms={"A": {"cdm_database_schema": "main"}},
        atlas={"url": "https://x", "api_key": "${FROM_PROCESS}"},
        directory=config_dir,
    )
    monkeypatch.setenv("FROM_PROCESS", "live-key")
    source = load_source("envkey", directory=config_dir)
    assert source.api_key() == "live-key"


def test_placeholders_collects_nested_names() -> None:
    names = config.placeholders(
        {"a": "${ONE}", "b": ["${TWO:-x}", {"c": "${ONE}"}], "d": 1}
    )
    assert names == {"ONE", "TWO"}
