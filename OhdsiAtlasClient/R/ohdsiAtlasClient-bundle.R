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

ohdsiAtlasClientBundleFormat <- "ohdsi-atlas-client.cohort-definition-set"
ohdsi_atlas_clientBundleVersion <- "1.0"
ohdsiAtlasClientBundleFile <- "cohort-set.json"

ohdsi_atlas_clientExpressionConceptSets <- function(expression) {
  value <- expression$ConceptSets
  if (is.null(value)) {
    value <- expression$conceptSets
  }
  if (!is.list(value)) {
    return(list())
  }
  Filter(is.list, value)
}

ohdsiAtlasClientConceptSetChecksum <- function(entry) {
  ohdsiAtlasClientStableHash(list(name = entry$name, expression = entry$expression))
}

ohdsiAtlasClientSlug <- function(value, fallback = "item") {
  slug <- tolower(gsub("[^A-Za-z0-9._-]+", "-", value))
  slug <- gsub("^-+|-+$", "", slug)
  if (!nzchar(slug)) fallback else substr(slug, 1, 80)
}

#' Build a cohort definition set bundle
#'
#' Creates the portable bundle used by `atlas$cohortSets` and by the Python
#' `ohdsi_atlas_client` package. Each input is the raw response from
#' `GET /cohortdefinition/{id}`; the `expression` field may be a JSON string or
#' an object.
#'
#' @param cohorts A list of raw WebAPI cohort payloads.
#' @param atlas Optional list of provenance metadata (URL, WebAPI version).
#' @return An `ohdsi_atlas_client_cohort_set_bundle` list.
#' @export
#' @examples
#' cohort <- list(
#'   name = "Demo",
#'   expression = list(ConceptSets = list(), PrimaryCriteria = list())
#' )
#' ohdsiAtlasClientBundleFromCohorts(list(cohort))
ohdsiAtlasClientBundleFromCohorts <- function(cohorts, atlas = list()) {
  checkmate::assertList(cohorts, min.len = 1)
  entries <- list()
  conceptSets <- list()
  seen <- character()
  for (cohort in cohorts) {
    expression <- cohort$expression
    if (is.character(expression) && length(expression) == 1) {
      expression <- jsonlite::fromJSON(expression, simplifyVector = FALSE)
    }
    if (!is.list(expression)) {
      abort(paste0("Cohort ", cohort$name %||% "<unnamed>", " has no expression"))
    }
    embedded <- ohdsi_atlas_clientExpressionConceptSets(expression)
    conceptSetIds <- integer()
    for (item in embedded) {
      if (is.null(item$id)) next
      conceptSetIds <- c(conceptSetIds, as.integer(item$id))
      normalised <- list(
        name = as.character(item$name %||% "Unnamed concept set"),
        description = item$description %||% NULL,
        expression = item$expression %||% list(items = list())
      )
      key <- paste0(normalised$name, "|", ohdsiAtlasClientConceptSetChecksum(normalised))
      if (!key %in% seen) {
        seen <- c(seen, key)
        normalised$checksum <- ohdsiAtlasClientConceptSetChecksum(normalised)
        conceptSets[[length(conceptSets) + 1L]] <- normalised
      }
    }
    entries[[length(entries) + 1L]] <- list(
      name = as.character(cohort$name %||% "Unnamed cohort"),
      description = cohort$description %||% NULL,
      expressionType = cohort$expressionType %||% "SIMPLE_EXPRESSION",
      expression = expression,
      conceptSetIds = conceptSetIds,
      checksum = ohdsiAtlasClientStableHash(expression)
    )
  }
  bundle <- list(
    format = ohdsiAtlasClientBundleFormat,
    formatVersion = ohdsi_atlas_clientBundleVersion,
    createdAt = ohdsiAtlasClientNowIso(),
    generator = list(
      name = "ohdsi-atlas-client-r",
      version = as.character(utils::packageVersion("OhdsiAtlasClient"))
    ),
    atlas = atlas,
    cohorts = entries,
    conceptSets = conceptSets
  )
  ohdsi_atlas_clientBundleWithIntegrity(bundle)
}

ohdsi_atlas_clientBundleWithIntegrity <- function(bundle) {
  value <- bundle
  value$integrity <- NULL
  bundle$integrity <- list(
    algorithm = "sha256",
    digest = ohdsiAtlasClientStableHash(value)
  )
  structure(bundle, class = c("ohdsi_atlas_client_cohort_set_bundle", "list"))
}

#' Validate a cohort definition set bundle
#'
#' @param bundle An `ohdsi_atlas_client_cohort_set_bundle`.
#' @param checkIntegrity Whether to verify the optional SHA-256 digest.
#' @return `TRUE` invisibly; aborts on invalid bundles.
#' @export
#' @examples
#' bundle <- ohdsiAtlasClientBundleFromCohorts(list(list(name = "x", expression = list())))
#' ohdsiAtlasClientBundleValidate(bundle)
ohdsiAtlasClientBundleValidate <- function(bundle, checkIntegrity = TRUE) {
  checkmate::assertList(bundle)
  if (!is.null(bundle$format) && !identical(bundle$format, ohdsiAtlasClientBundleFormat)) {
    abort(paste0("Unsupported bundle format: ", bundle$format))
  }
  version <- bundle$formatVersion %||% ohdsi_atlas_clientBundleVersion
  if (!identical(strsplit(version, ".", fixed = TRUE)[[1]][1], "1")) {
    abort(paste0("Unsupported bundle formatVersion: ", version))
  }
  if (!is.list(bundle$cohorts) || length(bundle$cohorts) == 0) {
    abort("A cohort definition set bundle must contain at least one cohort",
      class = "ohdsi_atlas_client_bundle_error"
    )
  }
  names <- vapply(bundle$cohorts, function(cohort) as.character(cohort$name), character(1))
  if (anyDuplicated(names)) {
    abort(
      paste0(
        "Duplicate cohort names in bundle: ",
        paste(unique(names[duplicated(names)]), collapse = ", ")
      ),
      class = "ohdsi_atlas_client_bundle_error"
    )
  }
  for (cohort in bundle$cohorts) {
    if (!is.list(cohort$expression)) {
      abort(paste0("Cohort ", cohort$name, " has an invalid expression"),
        class = "ohdsi_atlas_client_bundle_error"
      )
    }
  }
  if (checkIntegrity && !is.null(bundle$integrity$digest)) {
    unsigned <- bundle
    unsigned$integrity <- NULL
    expected <- ohdsiAtlasClientStableHash(unsigned)
    if (!identical(expected, as.character(bundle$integrity$digest))) {
      abort(
        "Bundle integrity check failed: the file was modified after export",
        class = "ohdsi_atlas_client_bundle_error"
      )
    }
  }
  invisible(TRUE)
}

#' Save a cohort definition set bundle
#'
#' @param bundle An `ohdsi_atlas_client_cohort_set_bundle`.
#' @param path Destination. A `.zip` path creates an archive; a path with no
#'   suffix creates a directory; anything else is written as JSON.
#' @param includeComponentFiles Include one JSON file per cohort/concept set in
#'   ZIP and directory output.
#' @return The destination path, invisibly.
#' @export
#' @examples
#' \dontrun{
#' bundle <- ohdsiAtlasClientBundleFromCohorts(list(list(name = "x", expression = list())))
#' ohdsiAtlasClientBundleSave(bundle, tempfile(fileext = ".json"))
#' }
ohdsiAtlasClientBundleSave <- function(bundle, path, includeComponentFiles = TRUE) {
  ohdsiAtlasClientBundleValidate(bundle)
  suffix <- tolower(tools::file_ext(path))
  if (identical(suffix, "zip")) {
    directory <- tempfile("ohdsi-atlas-client-bundle-")
    dir.create(directory, recursive = TRUE)
    on.exit(unlink(directory, recursive = TRUE), add = TRUE)
    ohdsiAtlasClientWriteJson(bundle, file.path(directory, ohdsiAtlasClientBundleFile))
    if (includeComponentFiles) {
      ohdsiAtlasClientWriteBundleComponents(bundle, directory)
    }
    zip::zipr(path, files = list.files(directory, full.names = FALSE), root = directory)
  } else if (!nzchar(suffix)) {
    dir.create(path, recursive = TRUE, showWarnings = FALSE)
    ohdsiAtlasClientWriteJson(bundle, file.path(path, ohdsiAtlasClientBundleFile))
    if (includeComponentFiles) {
      ohdsiAtlasClientWriteBundleComponents(bundle, path)
    }
  } else {
    ohdsiAtlasClientWriteJson(bundle, path)
  }
  invisible(path)
}

ohdsiAtlasClientWriteBundleComponents <- function(bundle, directory) {
  cohortDir <- file.path(directory, "cohorts")
  conceptSetDir <- file.path(directory, "concept-sets")
  dir.create(cohortDir, recursive = TRUE, showWarnings = FALSE)
  dir.create(conceptSetDir, recursive = TRUE, showWarnings = FALSE)
  for (index in seq_along(bundle$cohorts)) {
    cohort <- bundle$cohorts[[index]]
    name <- sprintf("%03d-%s.json", index, ohdsiAtlasClientSlug(cohort$name, "cohort"))
    ohdsiAtlasClientWriteJson(cohort, file.path(cohortDir, name))
  }
  for (index in seq_along(bundle$conceptSets)) {
    conceptSet <- bundle$conceptSets[[index]]
    name <- sprintf("%03d-%s.json", index, ohdsiAtlasClientSlug(conceptSet$name, "concept-set"))
    ohdsiAtlasClientWriteJson(conceptSet, file.path(conceptSetDir, name))
  }
  invisible(directory)
}

#' Load a cohort definition set bundle
#'
#' @param path A JSON file, ZIP archive, or directory containing
#'   `cohort-set.json`.
#' @return An `ohdsi_atlas_client_cohort_set_bundle`.
#' @export
#' @examples
#' \dontrun{
#' ohdsiAtlasClientBundleLoad("my-cohorts.zip")
#' }
ohdsiAtlasClientBundleLoad <- function(path) {
  checkmate::assertString(path, min.chars = 1)
  if (!file.exists(path)) {
    abort(paste0("Bundle not found: ", path), class = "ohdsi_atlas_client_bundle_error")
  }
  if (dir.exists(path)) {
    canonical <- file.path(path, ohdsiAtlasClientBundleFile)
    if (!file.exists(canonical)) {
      abort(paste0(path, " does not contain ", ohdsiAtlasClientBundleFile),
        class = "ohdsi_atlas_client_bundle_error"
      )
    }
    bundle <- ohdsiAtlasClientReadJson(canonical)
  } else if (identical(tolower(tools::file_ext(path)), "zip")) {
    directory <- tempfile("ohdsi-atlas-client-bundle-")
    dir.create(directory, recursive = TRUE)
    on.exit(unlink(directory, recursive = TRUE), add = TRUE)
    zip::unzip(path, exdir = directory)
    canonical <- file.path(directory, ohdsiAtlasClientBundleFile)
    if (!file.exists(canonical)) {
      candidates <- list.files(directory, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)
      if (length(candidates) != 1) {
        abort(
          paste0(path, " must contain ", ohdsiAtlasClientBundleFile, " or exactly one JSON file"),
          class = "ohdsi_atlas_client_bundle_error"
        )
      }
      canonical <- candidates[[1]]
    }
    bundle <- ohdsiAtlasClientReadJson(canonical)
  } else {
    bundle <- ohdsiAtlasClientReadJson(path)
  }
  ohdsiAtlasClientBundleValidate(bundle)
  structure(bundle, class = c("ohdsi_atlas_client_cohort_set_bundle", "list"))
}

ohdsi_atlas_clientBundleSummary <- function(bundle) {
  list(
    format = bundle$format,
    formatVersion = bundle$formatVersion,
    cohorts = length(bundle$cohorts),
    conceptSets = length(bundle$conceptSets),
    integrated = !is.null(bundle$integrity$digest),
    names = vapply(bundle$cohorts, function(cohort) cohort$name, character(1))
  )
}
