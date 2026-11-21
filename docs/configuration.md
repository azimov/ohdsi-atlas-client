# Database and CDM configuration

OHDSI studies usually talk to **one database that holds several CDM instances**:
CCAE v1 through v4, a `cdm` schema alongside a `cdm_2024` rebuild, or a
production and a test copy of the same source. The connection is identical for
all of them; only the schemas differ.

Both clients store that shape as a YAML file — one file per database — under
`~/.config/ohdsi`. **The same file works in Python and R.** Secrets stay in the
environment, never in the file.

## The file

`~/.config/ohdsi/ccae.yaml`:

```yaml
database:
  driver: postgresql            # postgres, databricks, sqlite, sql server, ...
  connection:
    server: ${OHDSI_DB_SERVER}
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
```

### `database`

| Key | Meaning |
|---|---|
| `driver` | Database platform. Aliases are normalised: `postgres` → `postgresql`, `mssql`/`sqlserver` → `sql server`. |
| `connection` | Passed to the driver. In R these are exactly the arguments of `DatabaseConnector::createConnectionDetails()`: `server`, `port`, `user`, `password`, `extraSettings`, `connectionString`, `pathToDriver`, … |

### `cdm`

One entry per CDM instance. The key (`CCAE_1`) is what you pass as `cdm=`.

| Key | Required | Meaning |
|---|---|---|
| `cdm_database_schema` | yes | Schema holding the CDM clinical tables. |
| `vocabulary_database_schema` | no | Defaults to `cdm_database_schema`. |
| `results_database_schema` | no | Defaults to `cdm_database_schema`. Use `scratch.scratch_<you>` for a shared read-only CDM. |

Any other key you add is preserved, so you can carry study-specific settings
alongside the schemas.

### `atlas` (optional)

ATLAS/WebAPI settings, so one file covers the API as well as the database:

```yaml
atlas:
  url: https://atlas.example.org
  api_key: ${OHDSI_ATLAS_CLIENT_API_KEY}
```

## Secrets: `${VAR}` placeholders

Any string value may contain `${NAME}` or `${NAME:-fallback}`. Placeholders are
resolved when the file is read, in this order:

1. the **process environment** (`export VAR=...`);
2. **`.Renviron`**;
3. **`.env`**.

The first definition wins. `.Renviron` and `.env` are looked for in the working
directory, then the home directory.

If a placeholder has no value and no default, loading fails with a message
naming the variable and exactly where it is used:

```
Environment variable 'OHDSI_DB_PASSWORD' is referenced in database.connection.password
but is not set. Define it in your shell, .Renviron, or .env, or give a default
as ${OHDSI_DB_PASSWORD:-fallback}.
```

Because the files hold no secrets, they are safe to keep in a shared directory
or a team repo.

## Python

```python
from ohdsi_atlas_client import (
    connection_details,   # connection details for a config
    find_source,          # locate a config by name or CDM key
    load_source,          # load and validate one file
    require_variables,    # which env vars are missing
    template_config,      # write a commented starter file
    write_source,         # write a config
)
```

### Create a file

```python
from ohdsi_atlas_client import write_source

path = write_source(
    "ccae",
    database={
        "driver": "postgresql",
        "connection": {
            "server": "${OHDSI_DB_SERVER}",
            "port": 5432,
            "user": "${OHDSI_DB_USER}",
            "password": "${OHDSI_DB_PASSWORD}",
        },
    },
    cdms={
        "CCAE_1": {"cdm_database_schema": "cdm_v1",
                   "results_database_schema": "scratch.scratch_jg"},
        "CCAE_2": {"cdm_database_schema": "cdm_v2",
                   "vocabulary_database_schema": "vocab",
                   "results_database_schema": "scratch.scratch_jg"},
    },
    atlas={"url": "${OHDSI_ATLAS_URL}",
           "api_key": "${OHDSI_ATLAS_CLIENT_API_KEY}"},
)
print(path)   # ~/.config/ohdsi/ccae.yaml
```

Run this once, open the file, and fill in the schemas. Or start from a template:

```python
from ohdsi_atlas_client import template_config

template_config("my-source")      # writes ~/.config/ohdsi/my-source.yaml
```

Files are written `0600` and the directory `0700`. Existing files are not
overwritten unless you pass `overwrite=True`.

### Use a file

```python
from ohdsi_atlas_client import connection_details, load_source

source = load_source("ccae")                      # or load_source(cdm="CCAE_2")
print(source.cdm_keys)                            # ['CCAE_1', 'CCAE_2']
print(source.database.driver)                     # 'postgresql'

cdm = source.cdm("CCAE_2")
print(cdm.cdm_database_schema)                    # 'cdm_v2'
print(cdm.results_database_schema)                # 'scratch.scratch_jg'

details = connection_details("ccae", cdm="CCAE_2")
print(details.redacted())                         # safe to log
```

`source.cdm()` with no argument works when the file defines exactly one CDM.
With several it raises rather than guessing.

### ATLAS settings

```python
from ohdsi_atlas_client import connect_from_config

atlas = connect_from_config("ccae")        # uses atlas.url and atlas.api_key
```

### In CI

```python
from ohdsi_atlas_client import require_variables

report = require_variables("ccae")
if report["missing"]:
    raise SystemExit(f"Set these variables: {', '.join(report['missing'])}")
```

## R

```r
library(OhdsiAtlasClient)

# Write a starter file, or build one explicitly
createSourceConfigTemplate("my-source")

createSourceConfig(
  "ccae",
  database = list(
    driver = "postgresql",
    connection = list(
      server   = "${OHDSI_DB_SERVER}",
      port     = 5432,
      user     = "${OHDSI_DB_USER}",
      password = "${OHDSI_DB_PASSWORD}"
    )
  ),
  cdms = list(
    CCAE_1 = list(cdm_database_schema = "cdm_v1",
                  results_database_schema = "scratch.scratch_jg"),
    CCAE_2 = list(cdm_database_schema = "cdm_v2",
                  vocabulary_database_schema = "vocab",
                  results_database_schema = "scratch.scratch_jg")
  )
)
```

Read it back:

```r
source <- readSourceConfig("ccae")          # or findSourceConfig(cdm = "CCAE_2")
source                                       # prints driver and every CDM
cdm <- selectCdm(source, "CCAE_2")
cdm$cdm_database_schema                      # "cdm_v2"
cdm$results_database_schema                  # "scratch.scratch_jg"
```

### Connection details for DatabaseConnector

`connectionDetails()` returns a plain list. `databaseConnectorArguments()` maps
`driver` onto DatabaseConnector's `dbms` argument and passes everything else
through:

```r
details <- connectionDetails("ccae", cdm = "CCAE_2")
print(details)                               # secrets masked as ***

args <- databaseConnectorArguments(
  details,
  pathToDriver = Sys.getenv("DATABASECONNECTOR_JAR_FOLDER")
)
connection <- do.call(DatabaseConnector::createConnectionDetails, args)
con <- DatabaseConnector::connect(connection)
on.exit(DatabaseConnector::disconnect(con))
```

The same `args` drop into `CDMConnector`:

```r
cdm <- selectCdm(source, "CCAE_2")
cdmConn <- CDMConnector::cdmFromCon(
  con = connection,
  cdmSchema = cdm$cdm_database_schema,
  writeSchema = cdm$results_database_schema
)
```

DatabaseConnector is only in `Suggests`, so it does not need to be installed to
build the arguments.

### In CI

```r
report <- requiredVariables("ccae")
if (length(report$missing) > 0) {
  stop("Set these variables: ", paste(report$missing, collapse = ", "))
}
```

## Which file and CDM am I using?

| Call | Behaviour |
|---|---|
| `load_source("ccae")` / `readSourceConfig("ccae")` | Load by name. |
| `load_source(cdm="CCAE_2")` / `findSourceConfig(cdm = "CCAE_2")` | Search every file for that CDM key. Fails if two files define it. |
| `load_source()` / `findSourceConfig()` | Use the only file, if exactly one exists. |
| `source.cdm()` / `selectCdm(source)` | The only CDM, if exactly one exists. |

Errors always list the alternatives, for example
`'ccae' has no CDM 'CCAE_9'. Available: CCAE_1, CCAE_2.`

## Where files live

The directory is, in order: the `directory` argument, the
`OHDSI_ATLAS_CLIENT_CONFIG_DIR` environment variable, then `~/.config/ohdsi`.

```bash
export OHDSI_ATLAS_CLIENT_CONFIG_DIR=/shared/ohdsi-config   # team config
```

| Language | List files | All files |
|---|---|---|
| Python | `list_sources()` | `load_sources()` |
| R | `listSourceConfigs()` | `readSourceConfigs()` |

## Validation

Both clients validate before writing and after reading:

* `database.driver` is required and must be a known platform;
* `cdm` must have at least one entry;
* `cdm_database_schema` is required for every CDM;
* secret fields (`password`, `token`, `api_key`) must resolve to strings.

`load_sources()` / `readSourceConfigs()` load every file and report **all**
problems at once, so one broken file does not hide the others.
