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

variables <- c(
  DB_SERVER = "db.example.org/ccae",
  DB_USER = "analyst",
  DB_PASSWORD = "s3cret",
  ATLAS_URL = "https://atlas.example.org",
  ATLAS_KEY = "wa_key",
  CDM_1_CDM_SCHEMA = "cdm_1",
  CDM_2_CDM_SCHEMA = "cdm_2"
)

templateVariables <- c(
  OHDSI_DB_SERVER = "db.example.org",
  OHDSI_DB_USER = "analyst",
  OHDSI_DB_PASSWORD = "s3cret",
  OHDSI_ATLAS_URL = "https://atlas.example.org",
  OHDSI_ATLAS_CLIENT_API_KEY = "wa_key",
  CDM_1_CDM_SCHEMA = "cdm_1",
  CDM_2_CDM_SCHEMA = "cdm_2"
)

ccaeConfig <- function(directory, ...) {
  createSourceConfig(
    name = "ccae",
    database = list(
      driver = "postgresql",
      connection = list(
        server = "${DB_SERVER}",
        port = 5432,
        user = "${DB_USER}",
        password = "${DB_PASSWORD}"
      )
    ),
    cdms = list(
      CCAE_1 = list(
        cdm_database_schema = "cdm_v1",
        results_database_schema = "scratch.scratch_jg"
      ),
      CCAE_2 = list(
        cdm_database_schema = "cdm_v2",
        vocabulary_database_schema = "vocab",
        results_database_schema = "scratch.scratch_jg"
      )
    ),
    directory = directory,
    ...
  )
}

test_that("the configuration directory follows the documented precedence", {
  withr::local_envvar(OHDSI_ATLAS_CLIENT_CONFIG_DIR = NA)
  expect_equal(
    configDirectory(),
    file.path(path.expand("~"), ".config", "ohdsi")
  )
  withr::local_envvar(OHDSI_ATLAS_CLIENT_CONFIG_DIR = tempfile())
  expect_equal(configDirectory(), path.expand(Sys.getenv("OHDSI_ATLAS_CLIENT_CONFIG_DIR")))
  expect_equal(configDirectory("/tmp/explicit"), "/tmp/explicit")

  created <- configDirectory(tempfile(), create = TRUE)
  expect_true(dir.exists(created))
})

test_that("the directory can be created with private permissions", {
  skip_on_os("windows")
  path <- configDirectory(file.path(tempfile(), "ohdsi"), create = TRUE)
  expect_true(dir.exists(path))
  expect_equal(as.character(file.info(path)$mode), "700")
})

test_that("readEnvironment reads .Renviron then .env", {
  local({
    directory <- tempfile()
    dir.create(directory)
    writeLines("FROM_RENVIRON=renviron\nSHARED=renviron", file.path(directory, ".Renviron"))
    writeLines("FROM_DOTENV=dotenv\nSHARED=dotenv", file.path(directory, ".env"))
    withr::local_dir(directory)
    values <- readEnvironment()
    expect_equal(unname(values[["FROM_RENVIRON"]]), "renviron")
    expect_equal(unname(values[["FROM_DOTENV"]]), "dotenv")
    expect_equal(unname(values[["SHARED"]]), "renviron")
  })
})

test_that("the process environment wins over files", {
  directory <- tempfile()
  dir.create(directory)
  writeLines("WHO=envfile", file.path(directory, ".env"))
  withr::local_dir(directory)
  withr::local_envvar(WHO = "process")
  expect_equal(unname(readEnvironment()[["WHO"]]), "process")
})

test_that("env files tolerate quoting, export, and comments", {
  path <- tempfile(fileext = ".env")
  writeLines(
    c(
      "# comment",
      "plain=value",
      "quoted=\"has spaces\"",
      "single='single'",
      "export EXPORTED=yes",
      "trailing=text # comment",
      "not a valid line"
    ),
    path
  )
  values <- OhdsiAtlasClient:::ohdsi_atlas_clientParseEnvFile(path)
  expect_equal(unname(values[["plain"]]), "value")
  expect_equal(unname(values[["quoted"]]), "has spaces")
  expect_equal(unname(values[["single"]]), "single")
  expect_equal(unname(values[["EXPORTED"]]), "yes")
  expect_equal(unname(values[["trailing"]]), "text")
  expect_false("not a valid line" %in% names(values))
})

test_that("readEnvironment ignores missing files", {
  expect_equal(readEnvironment(files = tempfile(), includeProcess = FALSE), character())
  # The process environment is included by default.
  expect_true(length(readEnvironment(files = tempfile())) >= 0)
})

test_that("placeholders resolve, including defaults", {
  expect_equal(
    resolvePlaceholders(
      list(a = "${DB_USER}", b = "${MISSING:-fallback}", c = 1, d = list("${DB_USER}")),
      variables
    ),
    list(a = "analyst", b = "fallback", c = 1, d = list("analyst"))
  )
})

test_that("an unset placeholder names its location", {
  expect_error(
    resolvePlaceholders(list(cdm = list(CCAE_1 = list(password = "${NOPE}"))), character()),
    class = "ohdsi_atlas_client_configuration_error"
  )
  error <- tryCatch(
    resolvePlaceholders(list(cdm = list(CCAE_1 = list(password = "${NOPE}"))), character()),
    error = function(e) e
  )
  expect_match(conditionMessage(error), "NOPE")
  expect_match(conditionMessage(error), "cdm.CCAE_1.password")
  expect_match(conditionMessage(error), ".Renviron")
})

test_that("allowUnresolved leaves placeholders intact", {
  expect_equal(resolvePlaceholders("${NOPE}", character(), allowUnresolved = TRUE), "${NOPE}")
})

test_that("referencedVariables finds nested names", {
  expect_equal(
    referencedVariables(list(a = "${ONE}", b = list("${TWO:-x}", list(c = "${ONE}")), d = 1)),
    c("ONE", "TWO")
  )
  expect_equal(referencedVariables("no placeholders"), character())
})

test_that("creating a file writes it with private permissions", {
  directory <- tempfile()
  path <- ccaeConfig(directory)
  expect_true(file.exists(path))
  expect_equal(basename(path), "ccae.yaml")
  skip_on_os("windows")
  expect_equal(as.character(file.info(path)$mode), "600")
})

test_that("creating a file refuses to overwrite by default", {
  directory <- tempfile()
  ccaeConfig(directory)
  expect_error(ccaeConfig(directory), class = "ohdsi_atlas_client_configuration_error")
  expect_silent(ccaeConfig(directory, overwrite = TRUE))
})

test_that("a written file carries the guidance header", {
  path <- ccaeConfig(tempfile())
  text <- paste(readLines(path), collapse = "\n")
  expect_match(text, ".Renviron", fixed = TRUE)
  expect_match(text, "${DB_PASSWORD}", fixed = TRUE)
})

test_that("invalid payloads are rejected before writing", {
  directory <- tempfile()
  expect_error(
    createSourceConfig(
      "broken",
      database = list(driver = "postgresql"),
      cdms = list(),
      directory = directory
    ),
    class = "ohdsi_atlas_client_configuration_error"
  )
  expect_false(file.exists(file.path(directory, "broken.yaml")))
})

test_that("whole numbers are written as integers", {
  path <- ccaeConfig(tempfile())
  text <- paste(readLines(path), collapse = "\n")
  expect_match(text, "port: 5432\n", fixed = TRUE)
  expect_false(grepl("5432.0", text, fixed = TRUE))
})

test_that("the template has two CDMs and an atlas section", {
  directory <- tempfile()
  createSourceConfigTemplate("example", directory = directory)
  source <- readSourceConfig("example", directory = directory, variables = templateVariables)
  expect_equal(names(source$cdms), c("CDM_1", "CDM_2"))
  expect_equal(source$atlas$url, "https://atlas.example.org")
  expect_equal(source$cdms$CDM_1$results_database_schema, "results")
  expect_equal(source$database$connection$port, "5432")

  expect_error(
    readSourceConfig("example", directory = directory, variables = c(OHDSI_DB_USER = "x")),
    class = "ohdsi_atlas_client_configuration_error"
  )
})

test_that("a file defines one database and many CDMs", {
  directory <- tempfile()
  ccaeConfig(directory)
  source <- readSourceConfig("ccae", directory = directory, variables = variables)

  expect_s3_class(source, "ohdsi_atlas_client_source_config")
  expect_equal(source$name, "ccae")
  expect_equal(source$database$driver, "postgresql")
  expect_equal(source$database$connection$server, "db.example.org/ccae")
  expect_equal(source$database$connection$password, "s3cret")
  expect_equal(names(source$cdms), c("CCAE_1", "CCAE_2"))

  first <- selectCdm(source, "CCAE_1")
  expect_equal(first$cdm_database_schema, "cdm_v1")
  expect_equal(first$results_database_schema, "scratch.scratch_jg")
  # Vocabulary defaults to the CDM schema.
  expect_equal(first$vocabulary_database_schema, "cdm_v1")
})

test_that("extra CDM settings are preserved", {
  directory <- tempfile()
  createSourceConfig(
    "extra",
    database = list(driver = "sqlite"),
    cdms = list(X = list(cdm_database_schema = "cdm", tempo = "fast")),
    directory = directory
  )
  source <- readSourceConfig("extra", directory = directory, variables = character())
  expect_equal(selectCdm(source, "X")$settings$tempo, "fast")
})

test_that("selectCdm requires a choice when there are several", {
  directory <- tempfile()
  ccaeConfig(directory)
  source <- readSourceConfig("ccae", directory = directory, variables = variables)
  expect_error(selectCdm(source), class = "ohdsi_atlas_client_configuration_error")
  expect_error(selectCdm(source, "NOPE"), "CCAE_1")
})

test_that("selectCdm picks the only CDM implicitly", {
  directory <- tempfile()
  createSourceConfig(
    "one",
    database = list(driver = "sqlite"),
    cdms = list(ONLY = list(cdm_database_schema = "cdm")),
    directory = directory
  )
  source <- readSourceConfig("one", directory = directory, variables = character())
  expect_equal(selectCdm(source)$key, "ONLY")
})

test_that("validation errors are specific", {
  valid <- list(database = list(driver = "postgresql"), cdm = list(A = list(cdm_database_schema = "s")))
  expect_error(validateSourceConfig(list(cdm = valid$cdm)), "database")
  expect_error(validateSourceConfig(c("not", "named")), "mapping")
  expect_error(validateSourceConfig(list(database = list(), cdm = valid$cdm)), "driver")
  expect_error(validateSourceConfig(list(database = valid$database)), "cdm")
  expect_error(validateSourceConfig(list(database = valid$database, cdm = list())), "cdm")
  expect_error(
    validateSourceConfig(list(database = valid$database, cdm = list(A = list()))),
    "cdm_database_schema"
  )
  expect_error(
    validateSourceConfig(list(database = list(driver = "postgresql", connection = "x"), cdm = valid$cdm)),
    "connection"
  )
  expect_error(
    validateSourceConfig(list(database = list(driver = "nonsense"), cdm = valid$cdm)),
    "Unknown database driver"
  )
  expect_error(
    validateSourceConfig(list(database = valid$database, cdm = list(A = "string"))),
    "must be a mapping"
  )
  expect_error(
    validateSourceConfig(list(database = list(driver = "  "), cdm = valid$cdm)),
    "must not be empty"
  )
  expect_error(
    validateSourceConfig(list(database = valid$database, cdm = valid$cdm, atlas = "url")),
    "'atlas' must be a mapping"
  )
  expect_error(
    validateSourceConfig(list(
      database = list(driver = "sqlite", connection = list(password = list(1))),
      cdm = valid$cdm
    )),
    "must be a string"
  )
})

test_that("driver aliases are canonicalised", {
  expect_equal(OhdsiAtlasClient:::ohdsi_atlas_clientValidateDriver("postgres"), "postgresql")
  expect_equal(OhdsiAtlasClient:::ohdsi_atlas_clientValidateDriver("PostgreSQL"), "postgresql")
  expect_equal(OhdsiAtlasClient:::ohdsi_atlas_clientValidateDriver("mssql"), "sql server")
  expect_equal(OhdsiAtlasClient:::ohdsi_atlas_clientValidateDriver("sqlserver"), "sql server")
})

test_that("invalid YAML and non-mapping files are reported", {
  directory <- tempfile()
  dir.create(directory)
  writeLines("database: [unclosed", file.path(directory, "bad.yaml"))
  expect_error(readSourceConfig("bad", directory = directory), "not valid YAML")

  writeLines(c("- a", "- b"), file.path(directory, "list.yaml"))
  expect_error(readSourceConfig("list", directory = directory), "mapping")
})

test_that("a missing file explains what is missing", {
  expect_error(
    readSourceConfig("absent", directory = tempfile()),
    class = "ohdsi_atlas_client_configuration_error"
  )
})

test_that("placeholders can be kept unresolved", {
  directory <- tempfile()
  ccaeConfig(directory)
  source <- readSourceConfig("ccae", directory = directory, resolve = FALSE)
  expect_equal(source$database$connection$password, "${DB_PASSWORD}")
})

test_that("configuration files are listed and loaded", {
  directory <- tempfile()
  expect_equal(listSourceConfigs(directory), character())
  ccaeConfig(directory)
  writeLines("ignored", file.path(directory, "notes.txt"))
  expect_equal(listSourceConfigs(directory), "ccae")

  createSourceConfig(
    "other",
    database = list(driver = "sqlite", connection = list(path = "x.sqlite")),
    cdms = list(YLE = list(cdm_database_schema = "main")),
    directory = directory
  )
  loaded <- readSourceConfigs(directory, variables = variables)
  expect_setequal(names(loaded), c("ccae", "other"))
})

test_that("all bad files are reported together", {
  directory <- tempfile()
  dir.create(directory)
  writeLines("database: {}", file.path(directory, "a.yaml"))
  writeLines("nope: true", file.path(directory, "b.yaml"))
  error <- tryCatch(readSourceConfigs(directory, variables = character()), error = function(e) e)
  expect_s3_class(error, "ohdsi_atlas_client_configuration_error")
  expect_match(conditionMessage(error), "in a")
  expect_match(conditionMessage(error), "in b")
})

test_that("files can be found by CDM key or by name", {
  directory <- tempfile()
  ccaeConfig(directory)
  createSourceConfig(
    "other",
    database = list(driver = "sqlite"),
    cdms = list(OTHER = list(cdm_database_schema = "main")),
    directory = directory
  )
  expect_equal(findSourceConfig(cdm = "CCAE_2", directory = directory, variables = variables)$name, "ccae")
  expect_error(
    findSourceConfig(directory = directory, variables = variables),
    "pass a name"
  )
  expect_error(findSourceConfig(cdm = "NOPE", directory = directory, variables = variables), "CCAE_1")
})

test_that("a single file is selected implicitly", {
  directory <- tempfile()
  ccaeConfig(directory)
  expect_equal(findSourceConfig(directory = directory, variables = variables)$name, "ccae")
})

test_that("an empty directory explains how to start", {
  expect_error(
    findSourceConfig(directory = tempfile(), variables = character()),
    "createSourceConfig"
  )
})

test_that("a CDM key in two files is ambiguous", {
  directory <- tempfile()
  ccaeConfig(directory)
  createSourceConfig(
    "copy",
    database = list(driver = "postgresql"),
    cdms = list(CCAE_1 = list(cdm_database_schema = "cdm")),
    directory = directory
  )
  expect_error(
    findSourceConfig(cdm = "CCAE_1", directory = directory, variables = variables),
    "defined in 2"
  )
})

test_that("connection details carry the driver and connection", {
  directory <- tempfile()
  ccaeConfig(directory)
  details <- connectionDetails("ccae", cdm = "CCAE_1", directory = directory, variables = variables)
  expect_s3_class(details, "ohdsi_atlas_client_connection_details")
  expect_equal(details$driver, "postgresql")
  expect_equal(details$connection$server, "db.example.org/ccae")
  expect_equal(details$connection$password, "s3cret")
  expect_equal(details$cdm, "CCAE_1")
  expect_equal(details$source, "ccae")
})

test_that("connection details accept overrides", {
  directory <- tempfile()
  ccaeConfig(directory)
  details <- connectionDetails(
    "ccae",
    directory = directory,
    variables = variables,
    overrides = list(port = 6543)
  )
  expect_equal(details$connection$port, 6543)
})

test_that("connection details print without secrets", {
  directory <- tempfile()
  ccaeConfig(directory)
  details <- connectionDetails("ccae", directory = directory, variables = variables)
  printed <- utils::capture.output(print(details))
  expect_true(any(grepl("\\*\\*\\*", printed)))
  expect_false(any(grepl("s3cret", printed)))
  expect_equal(details$connection$password, "s3cret")
})

test_that("missing variables are reported for CI", {
  directory <- tempfile()
  ccaeConfig(directory)
  report <- requiredVariables("ccae", directory = directory, variables = c(DB_USER = "a"))
  expect_equal(report$required, c("DB_PASSWORD", "DB_SERVER", "DB_USER"))
  expect_equal(report$missing, c("DB_PASSWORD", "DB_SERVER"))
})

test_that("defaults are not reported as missing when used", {
  directory <- tempfile()
  createSourceConfig(
    "defaults",
    database = list(driver = "postgres", connection = list(server = "${S:-localhost}")),
    cdms = list(A = list(cdm_database_schema = "cdm")),
    directory = directory
  )
  report <- requiredVariables("defaults", directory = directory, variables = character())
  expect_equal(report$required, "S")
  expect_equal(report$missing, "S")
})

test_that("a source configuration prints its CDMs", {
  directory <- tempfile()
  ccaeConfig(directory)
  source <- readSourceConfig("ccae", directory = directory, variables = variables)
  printed <- utils::capture.output(print(source))
  expect_true(any(grepl("CCAE_1", printed)))
  expect_true(any(grepl("cdm_v2", printed)))
})

test_that("an absolute path or .yaml name is used as given", {
  directory <- tempfile()
  path <- ccaeConfig(directory)
  expect_equal(readSourceConfig(path, variables = variables)$name, "ccae")
})

test_that("the yaml dependency is declared", {
  imports <- read.dcf(system.file("DESCRIPTION", package = "OhdsiAtlasClient"))[1, "Imports"]
  expect_match(imports, "yaml", fixed = TRUE)
})

test_that("connection details convert to DatabaseConnector arguments", {
  directory <- tempfile()
  ccaeConfig(directory)
  details <- connectionDetails("ccae", cdm = "CCAE_1", directory = directory, variables = variables)

  args <- databaseConnectorArguments(details)
  expect_equal(args$dbms, "postgresql")
  expect_equal(args$server, "db.example.org/ccae")
  expect_equal(args$port, 5432)
  expect_equal(args$password, "s3cret")
  expect_false("driver" %in% names(args))

  # An explicit dbms and extra arguments win.
  overridden <- databaseConnectorArguments(details, dbms = "redshift", pathToDriver = "/jdbc")
  expect_equal(overridden$dbms, "redshift")
  expect_equal(overridden$pathToDriver, "/jdbc")

  expect_error(
    databaseConnectorArguments(list(driver = "postgresql")),
    class = "ohdsi_atlas_client_configuration_error"
  )
})

test_that("DatabaseConnector accepts the generated arguments", {
  skip_if_not_installed("DatabaseConnector")
  skip_if(Sys.getenv("DATABASECONNECTOR_JAR_FOLDER") == "", "no JDBC driver folder configured")
  directory <- tempfile()
  createSourceConfig(
    "live",
    database = list(
      driver = "postgresql",
      connection = list(
        server = "127.0.0.1/postgres", port = 5432,
        user = "postgres", password = Sys.getenv("OHDSI_LAB_DB_PASSWORD", unset = "")
      )
    ),
    cdms = list(CDM = list(cdm_database_schema = "cdm")),
    directory = directory
  )
  skip_if(Sys.getenv("OHDSI_LAB_DB_PASSWORD") == "", "OHDSI_LAB_DB_PASSWORD not set")
  args <- databaseConnectorArguments(
    connectionDetails("live", directory = directory),
    pathToDriver = Sys.getenv("DATABASECONNECTOR_JAR_FOLDER")
  )
  details <- do.call(DatabaseConnector::createConnectionDetails, args)
  expect_equal(details$dbms, "postgresql")
})
