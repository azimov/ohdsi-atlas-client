# Copyright 2026 Observational Health Data Sciences and Informatics
#
# This file is part of Atlas3
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

atlas3BundleFormat <- "atlas3.cohort-definition-set"
atlas3BundleVersion <- "1.0"
atlas3BundleFile <- "cohort-set.json"

atlas3ExpressionConceptSets <- function(expression) {
  value <- expression$ConceptSets
  if (is.null(value)) {
    value <- expression$conceptSets
  }
  if (!is.list(value)) {
    return(list())
  }
  Filter(is.list, value)
}

atlas3ConceptSetChecksum <- function(entry) {
  atlas3StableHash(list(name = entry$name, expression = entry$expression))
}

atlas3Slug <- function(value, fallback = "item") {
  slug <- tolower(gsub("[^A-Za-z0-9._-]+", "-", value))
  slug <- gsub("^-+|-+$", "", slug)
  if (!nzchar(slug)) fallback else substr(slug, 1, 80)
}

#' Build a cohort definition set bundle
#'
#' Creates the portable bundle used by `atlas$cohortSets` and by the Python
#' `atlas3` package. Each input is the raw response from
#' `GET /cohortdefinition/{id}`; the `expression` field may be a JSON string or
#' an object.
#'
#' @param cohorts A list of raw WebAPI cohort payloads.
#' @param atlas Optional list of provenance metadata (URL, WebAPI version).
#' @return An `atlas3_cohort_set_bundle` list.
#' @export
#' @examples
#' cohort <- list(
#'   name = "Demo",
#'   expression = list(ConceptSets = list(), PrimaryCriteria = list())
#' )
#' atlas3BundleFromCohorts(list(cohort))
atlas3BundleFromCohorts <- function(cohorts, atlas = list()) {
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
    embedded <- atlas3ExpressionConceptSets(expression)
    conceptSetIds <- integer()
    for (item in embedded) {
      if (is.null(item$id)) next
      conceptSetIds <- c(conceptSetIds, as.integer(item$id))
      normalised <- list(
        name = as.character(item$name %||% "Unnamed concept set"),
        description = item$description %||% NULL,
        expression = item$expression %||% list(items = list())
      )
      key <- paste0(normalised$name, "|", atlas3ConceptSetChecksum(normalised))
      if (!key %in% seen) {
        seen <- c(seen, key)
        normalised$checksum <- atlas3ConceptSetChecksum(normalised)
        conceptSets[[length(conceptSets) + 1L]] <- normalised
      }
    }
    entries[[length(entries) + 1L]] <- list(
      name = as.character(cohort$name %||% "Unnamed cohort"),
      description = cohort$description %||% NULL,
      expressionType = cohort$expressionType %||% "SIMPLE_EXPRESSION",
      expression = expression,
      conceptSetIds = conceptSetIds,
      checksum = atlas3StableHash(expression)
    )
  }
  bundle <- list(
    format = atlas3BundleFormat,
    formatVersion = atlas3BundleVersion,
    createdAt = atlas3NowIso(),
    generator = list(name = "atlas3-r", version = as.character(utils::packageVersion("Atlas3"))),
    atlas = atlas,
    cohorts = entries,
    conceptSets = conceptSets
  )
  atlas3BundleWithIntegrity(bundle)
}

atlas3BundleWithIntegrity <- function(bundle) {
  value <- bundle
  value$integrity <- NULL
  bundle$integrity <- list(
    algorithm = "sha256",
    digest = atlas3StableHash(value)
  )
  structure(bundle, class = c("atlas3_cohort_set_bundle", "list"))
}

#' Validate a cohort definition set bundle
#'
#' @param bundle An `atlas3_cohort_set_bundle`.
#' @param checkIntegrity Whether to verify the optional SHA-256 digest.
#' @return `TRUE` invisibly; aborts on invalid bundles.
#' @export
#' @examples
#' bundle <- atlas3BundleFromCohorts(list(list(name = "x", expression = list())))
#' atlas3BundleValidate(bundle)
atlas3BundleValidate <- function(bundle, checkIntegrity = TRUE) {
  checkmate::assertList(bundle)
  if (!is.null(bundle$format) && !identical(bundle$format, atlas3BundleFormat)) {
    abort(paste0("Unsupported bundle format: ", bundle$format))
  }
  version <- bundle$formatVersion %||% atlas3BundleVersion
  if (!identical(strsplit(version, ".", fixed = TRUE)[[1]][1], "1")) {
    abort(paste0("Unsupported bundle formatVersion: ", version))
  }
  if (!is.list(bundle$cohorts) || length(bundle$cohorts) == 0) {
    abort("A cohort definition set bundle must contain at least one cohort",
      class = "atlas3_bundle_error"
    )
  }
  names <- vapply(bundle$cohorts, function(cohort) as.character(cohort$name), character(1))
  if (anyDuplicated(names)) {
    abort(
      paste0("Duplicate cohort names in bundle: ", paste(unique(names[duplicated(names)]), collapse = ", ")),
      class = "atlas3_bundle_error"
    )
  }
  for (cohort in bundle$cohorts) {
    if (!is.list(cohort$expression)) {
      abort(paste0("Cohort ", cohort$name, " has an invalid expression"),
        class = "atlas3_bundle_error"
      )
    }
  }
  if (checkIntegrity && !is.null(bundle$integrity$digest)) {
    unsigned <- bundle
    unsigned$integrity <- NULL
    expected <- atlas3StableHash(unsigned)
    if (!identical(expected, as.character(bundle$integrity$digest))) {
      abort(
        "Bundle integrity check failed: the file was modified after export",
        class = "atlas3_bundle_error"
      )
    }
  }
  invisible(TRUE)
}

#' Save a cohort definition set bundle
#'
#' @param bundle An `atlas3_cohort_set_bundle`.
#' @param path Destination. A `.zip` path creates an archive; a path with no
#'   suffix creates a directory; anything else is written as JSON.
#' @param includeComponentFiles Include one JSON file per cohort/concept set in
#'   ZIP and directory output.
#' @return The destination path, invisibly.
#' @export
#' @examples
#' \dontrun{
#' bundle <- atlas3BundleFromCohorts(list(list(name = "x", expression = list())))
#' atlas3BundleSave(bundle, tempfile(fileext = ".json"))
#' }
atlas3BundleSave <- function(bundle, path, includeComponentFiles = TRUE) {
  atlas3BundleValidate(bundle)
  suffix <- tolower(tools::file_ext(path))
  if (identical(suffix, "zip")) {
    directory <- tempfile("atlas3-bundle-")
    dir.create(directory, recursive = TRUE)
    on.exit(unlink(directory, recursive = TRUE), add = TRUE)
    atlas3WriteJson(bundle, file.path(directory, atlas3BundleFile))
    if (includeComponentFiles) {
      atlas3WriteBundleComponents(bundle, directory)
    }
    zip::zipr(path, files = list.files(directory, full.names = FALSE), root = directory)
  } else if (!nzchar(suffix)) {
    dir.create(path, recursive = TRUE, showWarnings = FALSE)
    atlas3WriteJson(bundle, file.path(path, atlas3BundleFile))
    if (includeComponentFiles) {
      atlas3WriteBundleComponents(bundle, path)
    }
  } else {
    atlas3WriteJson(bundle, path)
  }
  invisible(path)
}

atlas3WriteBundleComponents <- function(bundle, directory) {
  cohortDir <- file.path(directory, "cohorts")
  conceptSetDir <- file.path(directory, "concept-sets")
  dir.create(cohortDir, recursive = TRUE, showWarnings = FALSE)
  dir.create(conceptSetDir, recursive = TRUE, showWarnings = FALSE)
  for (index in seq_along(bundle$cohorts)) {
    cohort <- bundle$cohorts[[index]]
    name <- sprintf("%03d-%s.json", index, atlas3Slug(cohort$name, "cohort"))
    atlas3WriteJson(cohort, file.path(cohortDir, name))
  }
  for (index in seq_along(bundle$conceptSets)) {
    conceptSet <- bundle$conceptSets[[index]]
    name <- sprintf("%03d-%s.json", index, atlas3Slug(conceptSet$name, "concept-set"))
    atlas3WriteJson(conceptSet, file.path(conceptSetDir, name))
  }
  invisible(directory)
}

#' Load a cohort definition set bundle
#'
#' @param path A JSON file, ZIP archive, or directory containing
#'   `cohort-set.json`.
#' @return An `atlas3_cohort_set_bundle`.
#' @export
#' @examples
#' \dontrun{
#' atlas3BundleLoad("my-cohorts.zip")
#' }
atlas3BundleLoad <- function(path) {
  checkmate::assertString(path, min.chars = 1)
  if (!file.exists(path)) {
    abort(paste0("Bundle not found: ", path), class = "atlas3_bundle_error")
  }
  if (dir.exists(path)) {
    canonical <- file.path(path, atlas3BundleFile)
    if (!file.exists(canonical)) {
      abort(paste0(path, " does not contain ", atlas3BundleFile),
        class = "atlas3_bundle_error"
      )
    }
    bundle <- atlas3ReadJson(canonical)
  } else if (identical(tolower(tools::file_ext(path)), "zip")) {
    directory <- tempfile("atlas3-bundle-")
    dir.create(directory, recursive = TRUE)
    on.exit(unlink(directory, recursive = TRUE), add = TRUE)
    zip::unzip(path, exdir = directory)
    canonical <- file.path(directory, atlas3BundleFile)
    if (!file.exists(canonical)) {
      candidates <- list.files(directory, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)
      if (length(candidates) != 1) {
        abort(paste0(path, " must contain ", atlas3BundleFile, " or exactly one JSON file"),
          class = "atlas3_bundle_error"
        )
      }
      canonical <- candidates[[1]]
    }
    bundle <- atlas3ReadJson(canonical)
  } else {
    bundle <- atlas3ReadJson(path)
  }
  atlas3BundleValidate(bundle)
  structure(bundle, class = c("atlas3_cohort_set_bundle", "list"))
}

atlas3BundleSummary <- function(bundle) {
  list(
    format = bundle$format,
    formatVersion = bundle$formatVersion,
    cohorts = length(bundle$cohorts),
    conceptSets = length(bundle$conceptSets),
    integrated = !is.null(bundle$integrity$digest),
    names = vapply(bundle$cohorts, function(cohort) cohort$name, character(1))
  )
}
