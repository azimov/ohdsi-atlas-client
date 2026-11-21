# Copyright 2026 Observational Health Data Sciences and Informatics
#
# This file is part of OhdsiAtlasClient
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Database connection and CDM configuration files.
#
# OHDSI studies usually talk to one database that holds several CDM instances:
# CCAE v1 through v4, or a `cdm` schema alongside a `cdm_2024` rebuild. The
# connection is the same for all of them; only the schemas differ.
#
#   database:
#     driver: postgresql
#     connection:
#       server: ${OHDSI_DB_SERVER}
#       port: 5432
#       user: ${OHDSI_DB_USER}
#       password: ${OHDSI_DB_PASSWORD}
#
#   cdm:
#     CCAE_1:
#       cdm_database_schema: cdm_v1
#       results_database_schema: scratch.scratch_jg
#     CCAE_2:
#       cdm_database_schema: cdm_v2
#       vocabulary_database_schema: vocab
#       results_database_schema: scratch.scratch_jg
#
# Values of the form ${NAME} (or ${NAME:-fallback}) are resolved from the
# environment at load time: the process environment first, then .Renviron,
# then .env. Secrets therefore never live in the YAML file.

## Constants ----------------------------------------------------------------

ohdsiAtlasClientConfigDirVar <- "OHDSI_ATLAS_CLIENT_CONFIG_DIR"
ohdsiAtlasClientEnvFiles <- c(".Renviron", ".env")
ohdsiAtlasClientCdmKeys <- c(
  "cdm_database_schema",
  "vocabulary_database_schema",
  "results_database_schema"
)
ohdsiAtlasClientDriverAliases <- c(
  postgres = "postgresql",
  postgresql = "postgresql",
  redshift = "redshift",
  databricks = "databricks",
  spark = "spark",
  sqlite = "sqlite",
  sqlite3 = "sqlite",
  duckdb = "duckdb",
  "sql server" = "sql server",
  sqlserver = "sql server",
  mssql = "sql server",
  pdw = "pdw",
  oracle = "oracle",
  snowflake = "snowflake",
  bigquery = "bigquery",
  synapse = "synapse",
  hive = "hive",
  impala = "impala",
  netezza = "netezza",
  iris = "iris"
)

## Paths --------------------------------------------------------------------

#' The OHDSI configuration directory
#'
#' Configuration files live in `~/.config/ohdsi` by default. Set the
#' `OHDSI_ATLAS_CLIENT_CONFIG_DIR` environment variable, or pass `directory`,
#' to keep them elsewhere (for example on a shared drive).
#'
#' @param directory Optional directory. Defaults to
#'   `$OHDSI_ATLAS_CLIENT_CONFIG_DIR`, then `~/.config/ohdsi`.
#' @param create Create the directory if it does not exist.
#' @return The configuration directory path.
#' @export
#' @examples
#' configDirectory(directory = tempfile())
configDirectory <- function(directory = NULL, create = FALSE) {
  path <- if (!is.null(directory)) {
    path.expand(directory)
  } else if (nzchar(Sys.getenv(ohdsiAtlasClientConfigDirVar, unset = ""))) {
    path.expand(Sys.getenv(ohdsiAtlasClientConfigDirVar))
  } else {
    file.path(path.expand("~"), ".config", "ohdsi")
  }
  if (isTRUE(create) && !dir.exists(path)) {
    dir.create(path, recursive = TRUE, showWarnings = FALSE)
    Sys.chmod(path, mode = "0700")
  }
  path
}

## Environment --------------------------------------------------------------

#' Collect environment variables for interpolation
#'
#' Reads the process environment, then `.Renviron`, then `.env`. The first
#' definition of a name wins, so a variable exported in your shell overrides
#' the same name in a file. `.Renviron` and `.env` are read from the working
#' directory and then from the home directory.
#'
#' @param files Optional files to read instead of the defaults, in order of
#'   precedence.
#' @param includeProcess Include the process environment (default `TRUE`).
#' @return A named character vector.
#' @export
#' @examples
#' readEnvironment(files = character())
readEnvironment <- function(files = NULL, includeProcess = TRUE) {
  values <- if (isTRUE(includeProcess)) Sys.getenv() else character()
  candidates <- if (is.null(files)) {
    unique(unlist(lapply(ohdsiAtlasClientEnvFiles, function(name) {
      c(file.path(getwd(), name), file.path(path.expand("~"), name))
    })))
  } else {
    path.expand(files)
  }
  candidates <- candidates[!duplicated(candidates)]
  for (path in candidates) {
    if (!file.exists(path)) {
      next
    }
    parsed <- ohdsi_atlas_clientParseEnvFile(path)
    new <- parsed[!names(parsed) %in% names(values)]
    if (length(new) > 0) {
      values <- c(values, new)
    }
  }
  values
}

ohdsi_atlas_clientParseEnvFile <- function(path) {
  lines <- tryCatch(
    readLines(path, warn = FALSE, encoding = "UTF-8"),
    error = function(e) character()
  )
  values <- character()
  for (line in lines) {
    line <- trimws(line)
    if (!nzchar(line) || startsWith(line, "#")) {
      next
    }
    line <- sub("^export[[:space:]]+", "", line)
    if (!grepl("=", line, fixed = TRUE)) {
      next
    }
    key <- trimws(sub("=.*$", "", line))
    raw <- sub("^[^=]*=", "", line)
    if (!grepl("^[A-Za-z_][A-Za-z0-9_]*$", key)) {
      next
    }
    value <- trimws(raw)
    if (nchar(value) >= 2 && substr(value, 1, 1) == substr(value, nchar(value), nchar(value)) &&
          substr(value, 1, 1) %in% c("\"", "'")) {
      value <- substr(value, 2, nchar(value) - 1)
    } else {
      value <- trimws(sub("[[:space:]]+#.*$", "", value))
    }
    values[key] <- value
  }
  values
}

## Placeholders -------------------------------------------------------------

#' Substitute `${VAR}` placeholders
#'
#' Replaces `${NAME}` with the value of an environment variable and
#' `${NAME:-fallback}` with a default when the variable is unset. Works on
#' nested lists, as produced by reading a YAML file.
#'
#' @param value A list, character vector, or scalar to interpolate.
#' @param variables Named character vector, normally from
#'   [readEnvironment()].
#' @param where Path used in error messages, for example `cdm.CCAE_1`.
#' @param allowUnresolved Leave unknown placeholders untouched instead of
#'   raising an error.
#' @return `value` with placeholders replaced.
#' @export
#' @examples
#' resolvePlaceholders("${USER_NAME}", variables = c(USER_NAME = "analyst"))
resolvePlaceholders <- function(value, variables, where = "",
                                allowUnresolved = FALSE) {
  if (is.list(value)) {
    labels <- names(value) %||% rep("", length(value))
    for (index in seq_along(value)) {
      label <- labels[[index]]
      child <- if (!nzchar(label)) {
        paste0(where, "[", index, "]")
      } else if (nzchar(where)) {
        paste0(where, ".", label)
      } else {
        label
      }
      value[[index]] <- resolvePlaceholders(
        value[[index]], variables,
        where = child, allowUnresolved = allowUnresolved
      )
    }
    return(value)
  }
  if (length(value) != 1L || !is.character(value)) {
    return(value)
  }
  pattern <- "\\$\\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\\}"
  matches <- gregexpr(pattern, value, perl = TRUE)[[1]]
  if (identical(as.integer(matches), -1L)) {
    return(value)
  }
  parts <- regmatches(value, list(matches))[[1]]
  for (part in parts) {
    name <- sub("^\\$\\{", "", part)
    name <- sub("(:-.*)?\\}$", "", name)
    replacement <- if (name %in% names(variables)) {
      unname(variables[[name]])
    } else if (grepl(":-", part)) {
      sub("^\\$\\{[^:]+:-", "", sub("\\}$", "", part))
    } else if (isTRUE(allowUnresolved)) {
      part
    } else {
      abort(
        paste0(
          "Environment variable '", name, "' is referenced",
          if (nzchar(where)) paste0(" in ", where) else "", " but is not set. ",
          "Define it in your shell, .Renviron, or .env, or give a default as ${",
          name, ":-fallback}."
        ),
        class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
      )
    }
    value <- gsub(part, replacement, value, fixed = TRUE)
  }
  value
}

#' Environment variables referenced by a configuration file
#'
#' @param value A parsed configuration list.
#' @return A sorted character vector of variable names.
#' @export
#' @examples
#' referencedVariables(list(password = "${DB_PASSWORD}"))
referencedVariables <- function(value) {
  if (is.list(value)) {
    return(sort(unique(unlist(lapply(unname(value), referencedVariables), use.names = FALSE))))
  }
  if (length(value) != 1L || !is.character(value)) {
    return(character())
  }
  matches <- regmatches(
    value,
    gregexpr("\\$\\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\\}", value, perl = TRUE)
  )[[1]]
  if (length(matches) == 0 || identical(matches, "")) {
    return(character())
  }
  names <- sub("^\\$\\{", "", matches)
  sort(unique(sub("(:-.*)?\\}$", "", names)))
}

## Reading ------------------------------------------------------------------

ohdsi_atlas_clientRequireYaml <- function() {
  if (!requireNamespace("yaml", quietly = TRUE)) {
    abort(
      "Reading configuration files requires the 'yaml' package.",
      class = "ohdsi_atlas_client_configuration_error"
    )
  }
  invisible(TRUE)
}

ohdsi_atlas_clientValidateDriver <- function(driver) {
  key <- tolower(trimws(as.character(driver)))
  if (!nzchar(key)) {
    abort(
      "database.driver must not be empty",
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  if (!key %in% names(ohdsiAtlasClientDriverAliases)) {
    abort(
      paste0(
        "Unknown database driver '", driver, "'. Known drivers: ",
        paste(sort(unique(ohdsiAtlasClientDriverAliases)), collapse = ", "), "."
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  unname(ohdsiAtlasClientDriverAliases[key])
}

#' Validate a parsed configuration
#'
#' Applies the defaults (`vocabulary_database_schema` and
#' `results_database_schema` fall back to `cdm_database_schema`) and
#' canonicalises the driver name.
#'
#' @param payload A list with `database` and `cdm` sections.
#' @param name File name used in error messages.
#' @return A `source_config` object.
#' @export
#' @examples
#' validateSourceConfig(
#'   payload = list(
#'     database = list(driver = "postgres"),
#'     cdm = list(CDM_1 = list(cdm_database_schema = "cdm"))
#'   ),
#'   name = "example"
#' )
validateSourceConfig <- function(payload, name = "") {
  label <- if (nzchar(name)) paste0(" in ", name) else ""
  fail <- function(message) {
    abort(
      paste0(message, label),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  if (!is.list(payload) || is.null(names(payload))) {
    fail("Configuration must be a mapping")
  }
  database <- payload$database
  if (!is.list(database)) {
    fail("Missing or invalid 'database' section")
  }
  if (is.null(database$driver)) {
    fail("Missing 'database.driver'")
  }
  driver <- ohdsi_atlas_clientValidateDriver(database$driver)

  connection <- database$connection
  if (is.null(connection)) {
    connection <- list()
  }
  if (!is.list(connection)) {
    fail("'database.connection' must be a mapping")
  }
  for (key in c("password", "token", "api_key")) {
    if (!is.null(connection[[key]]) && !is.character(connection[[key]])) {
      fail(
        paste0(
          "'database.connection.", key, "' must be a string after placeholder ",
          "resolution; got ", class(connection[[key]])[1], "."
        )
      )
    }
  }

  cdms <- payload$cdm
  if (!is.list(cdms) || length(cdms) == 0) {
    fail(
      paste0(
        "Missing or empty 'cdm' section. Define at least one CDM, for example ",
        "'cdm: {CDM_1: {cdm_database_schema: cdm}}'"
      )
    )
  }
  parsed <- list()
  for (key in names(cdms)) {
    entry <- cdms[[key]]
    if (!is.list(entry)) {
      fail(paste0("'cdm.", key, "' must be a mapping"))
    }
    cdmSchema <- entry$cdm_database_schema
    if (!is.character(cdmSchema) || !nzchar(trimws(cdmSchema))) {
      fail(paste0("'cdm.", key, ".cdm_database_schema' is required"))
    }
    vocab <- entry$vocabulary_database_schema
    if (is.null(vocab) || !nzchar(as.character(vocab))) {
      vocab <- cdmSchema
    }
    results <- entry$results_database_schema
    if (is.null(results) || !nzchar(as.character(results))) {
      results <- cdmSchema
    }
    extra <- entry[setdiff(names(entry), ohdsiAtlasClientCdmKeys)]
    parsed[[key]] <- list(
      key = key,
      cdm_database_schema = as.character(cdmSchema),
      vocabulary_database_schema = as.character(vocab),
      results_database_schema = as.character(results),
      settings = extra
    )
  }

  atlas <- payload$atlas
  if (is.null(atlas)) {
    atlas <- list()
  }
  if (!is.list(atlas)) {
    fail("'atlas' must be a mapping")
  }

  structure(
    list(
      name = name,
      database = list(driver = driver, connection = connection),
      cdms = parsed,
      atlas = atlas,
      raw = payload
    ),
    class = "ohdsi_atlas_client_source_config"
  )
}

ohdsi_atlas_clientResolvePath <- function(name, directory = NULL) {
  path <- path.expand(name)
  if (grepl("\\.ya?ml$", path, ignore.case = TRUE) || grepl("^(/|~|[A-Za-z]:)", path)) {
    return(path)
  }
  file.path(configDirectory(directory), paste0(basename(path), ".yaml"))
}

#' Read and validate a configuration file
#'
#' @inheritParams validateSourceConfig
#' @param name File stem such as `"ccae"`, or a path to a YAML file.
#' @param directory Configuration directory; see [configDirectory()].
#' @param variables Named character vector for placeholder substitution.
#'   Defaults to [readEnvironment()].
#' @param resolve Substitute `${VAR}` placeholders (default `TRUE`).
#' @return A `source_config` object.
#' @export
#' @examples
#' \dontrun{
#' source <- readSourceConfig("ccae")
#' source$cdms$CCAE_1$cdm_database_schema
#' }
readSourceConfig <- function(name, directory = NULL, variables = NULL,
                             resolve = TRUE) {
  ohdsi_atlas_clientRequireYaml()
  path <- ohdsi_atlas_clientResolvePath(name, directory)
  if (!file.exists(path)) {
    abort(
      paste0("Could not read ", path, ": file does not exist."),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  raw <- tryCatch(
    yaml::read_yaml(path),
    error = function(e) {
      abort(
        paste0(path, " is not valid YAML: ", conditionMessage(e)),
        class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
      )
    }
  )
  if (is.null(raw)) {
    raw <- list()
  }
  if (!is.list(raw) || is.null(names(raw))) {
    abort(
      paste0(basename(path), " must contain a mapping at the top level."),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  payload <- if (isTRUE(resolve)) {
    resolvePlaceholders(raw, variables %||% readEnvironment())
  } else {
    raw
  }
  config <- validateSourceConfig(
    payload,
    name = sub("\\.ya?ml$", "", basename(path), ignore.case = TRUE)
  )
  config$raw <- raw
  config
}

#' List configuration files
#'
#' @inheritParams configDirectory
#' @return A sorted character vector of file stems.
#' @export
#' @examples
#' length(listSourceConfigs(directory = tempdir()))
listSourceConfigs <- function(directory = NULL) {
  root <- configDirectory(directory)
  if (!dir.exists(root)) {
    return(character())
  }
  files <- list.files(root, pattern = "\\.ya?ml$", full.names = FALSE, ignore.case = TRUE)
  sort(unique(sub("\\.ya?ml$", "", files, ignore.case = TRUE)))
}

#' Read every configuration file
#'
#' @inheritParams readSourceConfig
#' @return A named list of `source_config` objects.
#' @export
#' @examples
#' length(readSourceConfigs(directory = tempdir()))
readSourceConfigs <- function(directory = NULL, variables = NULL) {
  values <- variables %||% readEnvironment()
  stems <- listSourceConfigs(directory)
  loaded <- list()
  problems <- character()
  for (stem in stems) {
    loaded[[stem]] <- tryCatch(
      readSourceConfig(stem, directory = directory, variables = values),
      error = function(e) {
        problems <<- c(problems, conditionMessage(e))
        NULL
      }
    )
  }
  loaded <- Filter(Negate(is.null), loaded)
  if (length(problems) > 0) {
    abort(
      paste0("Invalid configuration files:\n  ", paste(problems, collapse = "\n  ")),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  loaded
}

#' Find a configuration file
#'
#' Loads a named file, or searches every file for a CDM key. With no
#' arguments and exactly one configuration file, that file is used.
#'
#' @param name File stem or path. Optional when `cdm` is given.
#' @param cdm CDM key to look for across all files.
#' @inheritParams readSourceConfig
#' @return A `source_config` object.
#' @export
#' @examples
#' \dontrun{
#' findSourceConfig(cdm = "CCAE_2")
#' }
findSourceConfig <- function(name = NULL, cdm = NULL, directory = NULL,
                             variables = NULL) {
  if (!is.null(name)) {
    return(readSourceConfig(name, directory = directory, variables = variables))
  }
  values <- variables %||% readEnvironment()
  loaded <- readSourceConfigs(directory, variables = values)
  if (is.null(cdm)) {
    if (length(loaded) == 1) {
      return(loaded[[1]])
    }
    if (length(loaded) == 0) {
      abort(
        paste0(
          "No configuration files found in ", configDirectory(directory),
          ". Create one with createSourceConfig()."
        ),
        class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
      )
    }
    abort(
      paste0(
        length(loaded), " configuration files found (",
        paste(sort(names(loaded)), collapse = ", "),
        "); pass a name or cdm= to choose one."
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  matches <- Filter(function(source) cdm %in% names(source$cdms), loaded)
  if (length(matches) == 0) {
    available <- sort(unique(unlist(lapply(loaded, function(source) names(source$cdms)))))
    abort(
      paste0(
        "No configuration defines a CDM named '", cdm, "'. Available: ",
        paste(available, collapse = ", ")
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  if (length(matches) > 1) {
    abort(
      paste0(
        "CDM '", cdm, "' is defined in ", length(matches), " configuration files (",
        paste(vapply(matches, function(source) source$name, ""), collapse = ", "),
        "); pass the file name too."
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  matches[[1]]
}

#' Select one CDM from a configuration
#'
#' @param config A `source_config` object.
#' @param cdm CDM key. May be omitted when the file defines exactly one CDM.
#' @return The CDM settings, with `vocabulary_database_schema` and
#'   `results_database_schema` defaulted.
#' @export
#' @examples
#' config <- validateSourceConfig(
#'   list(
#'     database = list(driver = "sqlite"),
#'     cdm = list(CDM_1 = list(cdm_database_schema = "cdm"))
#'   ),
#'   name = "example"
#' )
#' selectCdm(config)
selectCdm <- function(config, cdm = NULL) {
  if (is.null(cdm)) {
    if (length(config$cdms) == 1) {
      return(config$cdms[[1]])
    }
    abort(
      paste0(
        "'", config$name, "' defines ", length(config$cdms), " CDMs (",
        paste(names(config$cdms), collapse = ", "), "); pass cdm= to choose one."
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  selected <- config$cdms[[cdm]]
  if (is.null(selected)) {
    abort(
      paste0(
        "'", config$name, "' has no CDM '", cdm, "'. Available: ",
        paste(names(config$cdms), collapse = ", "), "."
      ),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  selected
}

## Writing ------------------------------------------------------------------

# yaml::as.yaml() writes integers as floats (5432.0). Convert whole numbers
# back so a written file round-trips byte-for-byte across languages.
ohdsi_atlas_clientYamlSafe <- function(value) {
  if (is.list(value)) {
    return(lapply(value, ohdsi_atlas_clientYamlSafe))
  }
  if (is.numeric(value) && length(value) == 1L && !is.na(value) &&
        value == round(value) && abs(value) < .Machine$integer.max) {
    return(as.integer(value))
  }
  value
}

ohdsi_atlas_clientDefaultHeader <- c(
  "# OHDSI Atlas client configuration.",
  "# One database, any number of CDMs.",
  "#",
  "# Values like ${MY_VARIABLE} are read from the environment at load time:",
  "# the process environment first, then .Renviron, then .env.",
  "# Never put passwords or API tokens in this file.",
  "#",
  "# database:",
  "#   driver: postgresql            # postgres, databricks, sqlite, sql server, ...",
  "#   connection:                   # passed to DatabaseConnector",
  "#     server: ${OHDSI_DB_SERVER}",
  "#     port: 5432",
  "#     user: ${OHDSI_DB_USER}",
  "#     password: ${OHDSI_DB_PASSWORD}"
)

#' Write a configuration file
#'
#' The file is created with mode `0600` because it names hosts and users, and
#' the directory with `0700`. Use `${VAR}` placeholders for secrets rather
#' than literal values.
#'
#' @param name File stem, for example `"ccae"`.
#' @param database A list with `driver` and `connection`.
#' @param cdms Named list of CDMs, each with `cdm_database_schema` and
#'   optionally `vocabulary_database_schema` and `results_database_schema`.
#' @param atlas Optional list with `url` and `api_key`.
#' @param directory Configuration directory; see [configDirectory()].
#' @param overwrite Replace an existing file.
#' @param comment Prepend a short header explaining placeholders, or supply
#'   your own header lines.
#' @return The path written, invisibly.
#' @export
#' @examples
#' # Always pass `directory` in scripts and examples; otherwise files are
#' # written to ~/.config/ohdsi.
#' path <- createSourceConfig(
#'   name = "ccae",
#'   directory = tempfile(),
#'   database = list(
#'     driver = "postgresql",
#'     connection = list(server = "${DB_SERVER}", password = "${DB_PASSWORD}")
#'   ),
#'   cdms = list(
#'     CCAE_1 = list(cdm_database_schema = "cdm_v1"),
#'     CCAE_2 = list(cdm_database_schema = "cdm_v2")
#'   )
#' )
#' file.exists(path)
createSourceConfig <- function(name, database, cdms, atlas = NULL,
                               directory = NULL, overwrite = FALSE,
                               comment = TRUE) {
  ohdsi_atlas_clientRequireYaml()
  payload <- list(
    database = list(
      driver = database$driver,
      connection = database$connection %||% list()
    ),
    cdm = cdms
  )
  if (!is.null(atlas)) {
    payload$atlas <- atlas
  }
  # Validate before touching the disk.
  validateSourceConfig(payload, name = basename(name))

  root <- configDirectory(directory, create = TRUE)
  path <- file.path(root, paste0(sub("\\.ya?ml$", "", basename(name), ignore.case = TRUE), ".yaml"))
  if (file.exists(path) && !isTRUE(overwrite)) {
    abort(
      paste0(path, " already exists; pass overwrite = TRUE to replace it."),
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  text <- yaml::as.yaml(ohdsi_atlas_clientYamlSafe(payload), indent.mapping.sequence = TRUE)
  if (isTRUE(comment)) {
    text <- paste0(paste(ohdsi_atlas_clientDefaultHeader, collapse = "\n"), "\n\n", text)
  } else if (is.character(comment)) {
    text <- paste0(paste(comment, collapse = "\n"), "\n\n", text)
  }
  writeLines(text, path, useBytes = TRUE)
  Sys.chmod(path, mode = "0600")
  invisible(path)
}

#' Write a starter configuration file
#'
#' Shows two CDMs pointing at the same database, which is the common case
#' (one source, several versions).
#'
#' @param name File stem.
#' @param driver Database driver, for example `"postgresql"`.
#' @param cdms CDM keys to include.
#' @inheritParams createSourceConfig
#' @return The path written, invisibly.
#' @export
#' @examples
#' path <- createSourceConfigTemplate("example", directory = tempfile())
#' file.exists(path)
createSourceConfigTemplate <- function(name = "example", driver = "postgresql",
                                       cdms = c("CDM_1", "CDM_2"),
                                       directory = NULL, overwrite = FALSE) {
  cdmPayload <- lapply(cdms, function(key) {
    list(
      cdm_database_schema = paste0("${", key, "_CDM_SCHEMA}"),
      results_database_schema = "${OHDSI_RESULTS_SCHEMA:-results}"
    )
  })
  names(cdmPayload) <- cdms
  createSourceConfig(
    name = name,
    database = list(
      driver = driver,
      connection = list(
        server = "${OHDSI_DB_SERVER}",
        port = "${OHDSI_DB_PORT:-5432}",
        user = "${OHDSI_DB_USER}",
        password = "${OHDSI_DB_PASSWORD}"
      )
    ),
    cdms = cdmPayload,
    atlas = list(
      url = "${OHDSI_ATLAS_URL}",
      api_key = "${OHDSI_ATLAS_CLIENT_API_KEY}"
    ),
    directory = directory,
    overwrite = overwrite
  )
}

## Connection details -------------------------------------------------------

#' Build DatabaseConnector connection details from a configuration file
#'
#' Returns what [DatabaseConnector::createConnectionDetails()] expects, so the
#' result can be passed straight to `DatabaseConnector::connect()`, or used
#' with `CDMConnector` and other HADES packages.
#'
#' @param name File stem or path; omit to search by `cdm`.
#' @param cdm CDM key to bind to the connection.
#' @inheritParams readSourceConfig
#' @param overrides Connection arguments that win over the file, for example
#'   `list(port = 5433)`.
#' @return A `cdm_connection_details` list with `driver`, `connection`,
#'   `source`, and `cdm`.
#' @export
#' @examples
#' directory <- tempfile()
#' createSourceConfig(
#'   name = "db",
#'   database = list(driver = "sqlite", connection = list(server = "x.sqlite")),
#'   cdms = list(CDM_1 = list(cdm_database_schema = "main")),
#'   directory = directory
#' )
#' details <- connectionDetails("db", directory = directory)
#' details$driver
connectionDetails <- function(name = NULL, cdm = NULL, directory = NULL,
                              variables = NULL, overrides = list()) {
  config <- findSourceConfig(name, cdm = cdm, directory = directory, variables = variables)
  connection <- config$database$connection
  for (key in names(overrides)) {
    connection[[key]] <- overrides[[key]]
  }
  structure(
    list(
      driver = config$database$driver,
      connection = connection,
      source = config$name,
      cdm = cdm
    ),
    class = "ohdsi_atlas_client_connection_details"
  )
}

#' Convert connection details for DatabaseConnector
#'
#' Maps our `driver` onto DatabaseConnector's `dbms` argument and passes the
#' connection arguments through unchanged. The result can be handed straight to
#' [DatabaseConnector::connect()], `CDMConnector::cdmFromCon()` and other HADES
#' packages.
#'
#' DatabaseConnector is only suggested, so it does not have to be installed to
#' build the arguments.
#'
#' @param details A `cdm_connection_details` object from [connectionDetails()].
#' @param dbms Optional override for the DatabaseConnector platform name.
#' @param ... Further arguments passed to
#'   [DatabaseConnector::createConnectionDetails()], for example
#'   `pathToDriver`.
#' @return A list of arguments for `DatabaseConnector::createConnectionDetails()`.
#' @export
#' @examples
#' directory <- tempfile()
#' createSourceConfig(
#'   name = "db",
#'   database = list(driver = "sqlite", connection = list(server = "x.sqlite")),
#'   cdms = list(CDM_1 = list(cdm_database_schema = "main")),
#'   directory = directory
#' )
#' args <- databaseConnectorArguments(connectionDetails("db", directory = directory))
#' args$dbms
databaseConnectorArguments <- function(details, dbms = NULL, ...) {
  if (!inherits(details, "ohdsi_atlas_client_connection_details")) {
    abort(
      "details must come from connectionDetails()",
      class = c("ohdsi_atlas_client_configuration_error", "ohdsi_atlas_client_error")
    )
  }
  args <- list(dbms = dbms %||% details$driver)
  for (key in names(details$connection)) {
    args[[key]] <- details$connection[[key]]
  }
  extra <- list(...)
  for (key in names(extra)) {
    args[[key]] <- extra[[key]]
  }
  args
}

#' Report which environment variables are missing
#'
#' Useful in CI, where failing with the list of unset names is more helpful
#' than failing on the first connection attempt.
#'
#' @inheritParams readSourceConfig
#' @return A list with `required` and `missing` character vectors.
#' @export
#' @examples
#' directory <- tempfile()
#' createSourceConfig(
#'   name = "env",
#'   database = list(driver = "sqlite", connection = list(password = "${NOPE_VAR}")),
#'   cdms = list(CDM_1 = list(cdm_database_schema = "main")),
#'   directory = directory
#' )
#' requiredVariables("env", directory = directory, variables = character())$missing
requiredVariables <- function(name, directory = NULL, variables = NULL) {
  ohdsi_atlas_clientRequireYaml()
  path <- ohdsi_atlas_clientResolvePath(name, directory)
  raw <- yaml::read_yaml(path)
  needed <- referencedVariables(raw)
  values <- variables %||% readEnvironment()
  list(
    required = needed,
    missing = sort(setdiff(needed, names(values)))
  )
}

#' Print connection details without secrets
#'
#' @param x A `cdm_connection_details` object from [connectionDetails()].
#' @param ... Ignored.
#' @return `x`, invisibly.
#' @export
print.ohdsi_atlas_client_connection_details <- function(x, ...) {
  secret <- c("password", "token", "api_key", "apikey", "secret")
  connection <- x$connection
  for (key in names(connection)) {
    if (tolower(key) %in% secret && !is.null(connection[[key]])) {
      connection[[key]] <- "***"
    }
  }
  cat("<ohdsi_atlas_client_connection_details>\n")
  cat("  source: ", x$source, "\n", sep = "")
  cat("  cdm:    ", x$cdm %||% "<not bound>", "\n", sep = "")
  cat("  driver: ", x$driver, "\n", sep = "")
  for (key in names(connection)) {
    cat("  ", key, ": ", as.character(connection[[key]]), "\n", sep = "")
  }
  invisible(x)
}

#' Print a source configuration
#'
#' @param x A `source_config` object.
#' @param ... Ignored.
#' @return `x`, invisibly.
#' @export
print.ohdsi_atlas_client_source_config <- function(x, ...) {
  cat("<source_config> ", x$name, "\n", sep = "")
  cat("  driver: ", x$database$driver, "\n", sep = "")
  cat("  cdms:   ", length(x$cdms), " (", paste(names(x$cdms), collapse = ", "), ")\n", sep = "")
  for (key in names(x$cdms)) {
    cdm <- x$cdms[[key]]
    cat(
      "    ", key, ": ", cdm$cdm_database_schema,
      " (vocab: ", cdm$vocabulary_database_schema,
      ", results: ", cdm$results_database_schema, ")\n",
      sep = ""
    )
  }
  invisible(x)
}
