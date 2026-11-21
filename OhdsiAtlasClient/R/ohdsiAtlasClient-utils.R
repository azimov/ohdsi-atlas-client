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

#' Normalise an ATLAS URL
#'
#' Adds `https://` when no scheme is present and removes a trailing slash,
#' query string, and fragment.
#'
#' @param url A character string with an ATLAS or WebAPI URL.
#' @return A normalised URL.
#' @export
#' @examples
#' ohdsiAtlasClientNormalizeUrl("atlas.example.org/atlas/")
ohdsiAtlasClientNormalizeUrl <- function(url) {
  checkmate::assertString(url, min.chars = 1)
  value <- trimws(url)
  if (!grepl("^[A-Za-z][A-Za-z0-9+.-]*://", value)) {
    value <- paste0("https://", value)
  }
  value <- sub("[?#].*$", "", value)
  value <- sub("/+$", "", value)
  if (!grepl("^https?://[^/]+", value)) {
    abort("Invalid URL: {.val {url}}")
  }
  value
}

#' Candidate WebAPI roots for an ATLAS URL
#'
#' ATLAS deployments commonly expose the UI at `/atlas` and proxy `/WebAPI`
#' at the site root. This function returns the likely WebAPI roots in probing
#' order.
#'
#' @param url An ATLAS UI or WebAPI URL.
#' @return A character vector of candidate WebAPI roots.
#' @export
#' @examples
#' ohdsiAtlasClientCandidateApiBases("https://atlas.example.org/atlas")
ohdsiAtlasClientCandidateApiBases <- function(url) {
  normalised <- ohdsiAtlasClientNormalizeUrl(url)
  match <- regmatches(
    normalised,
    regexec("^(https?://[^/]+)(/.*)?$", normalised)
  )[[1]]
  root <- match[[2]]
  path <- if (length(match) >= 3) match[[3]] else ""
  path <- sub("/+$", "", path)
  path <- sub("/(index\\.html?|index\\.htm)$", "", path, ignore.case = TRUE)
  path <- sub("/atlas$", "", path, ignore.case = TRUE)
  lower <- tolower(path)
  candidates <- character()
  add <- function(candidate) {
    candidate <- sub("/+$", "", candidate)
    if (!candidate %in% candidates) {
      candidates <<- c(candidates, candidate)
    }
  }
  if (grepl("/webapi$", lower)) {
    add(normalised)
  } else {
    add(paste0(root, path, "/WebAPI"))
    add(paste0(root, path, "/webapi"))
    add(paste0(root, path))
    add(paste0(root, path, "/atlas/WebAPI"))
  }
  candidates
}

#' Parse a WebAPI version
#'
#' @param version A version string such as `"3.0.0"` or `"3.0.1-SNAPSHOT"`.
#' @return An integer vector of length three.
#' @export
#' @examples
#' ohdsiAtlasClientParseVersion("3.0.0-SNAPSHOT")
ohdsiAtlasClientParseVersion <- function(version) {
  checkmate::assertString(version, min.chars = 1)
  match <- regmatches(
    version,
    regexec("^[vV]?([0-9]+)\\.([0-9]+)(?:\\.([0-9]+))?", version, perl = TRUE)
  )[[1]]
  if (length(match) < 2) {
    abort("Unrecognised WebAPI version: {.val {version}}")
  }
  patch <- if (length(match) >= 4 && nzchar(match[[4]])) match[[4]] else "0"
  as.integer(c(match[[2]], match[[3]], patch))
}

#' Check the minimum ATLAS version
#'
#' @param version A WebAPI version string.
#' @param minimum Minimum acceptable version (default `"3.0.0"`).
#' @return `TRUE` when `version` is at least `minimum`.
#' @export
#' @examples
#' ohdsiAtlasClientVersionAtLeast("3.0.1")
ohdsiAtlasClientVersionAtLeast <- function(version, minimum = "3.0.0") {
  current <- ohdsiAtlasClientParseVersion(version)
  required <- ohdsiAtlasClientParseVersion(minimum)
  current[[1]] > required[[1]] ||
    (current[[1]] == required[[1]] && current[[2]] > required[[2]]) ||
    (current[[1]] == required[[1]] &&
      current[[2]] == required[[2]] &&
      current[[3]] >= required[[3]])
}

#' Redact an API key for display
#'
#' @param key An API key or `NULL`.
#' @return A short, safe display string.
#' @export
#' @examples
#' ohdsiAtlasClientRedactKey(Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY"))
ohdsiAtlasClientRedactKey <- function(key) {
  if (is.null(key) || !nzchar(key)) {
    return("<none>")
  }
  if (nchar(key) <= 12) {
    return("***")
  }
  paste0(substr(key, 1, 7), "...", substr(key, nchar(key) - 3, nchar(key)))
}

ohdsiAtlasClientNowIso <- function() {
  format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
}

ohdsiAtlasClientStableHash <- function(value) {
  canonical <- ohdsiAtlasClientCanonicalJson(value)
  digest::digest(charToRaw(canonical), algo = "sha256", serialize = FALSE)
}

ohdsiAtlasClientCanonicalJson <- function(value) {
  if (is.null(value)) {
    return("null")
  }
  if (is.list(value)) {
    if (!is.null(names(value)) && all(nzchar(names(value)))) {
      value <- value[order(names(value))]
      parts <- vapply(
        seq_along(value),
        function(index) {
          paste0(
            jsonlite::toJSON(names(value)[[index]], auto_unbox = TRUE),
            ":",
            ohdsiAtlasClientCanonicalJson(value[[index]])
          )
        },
        character(1)
      )
      return(paste0("{", paste(parts, collapse = ","), "}"))
    }
    parts <- vapply(value, ohdsiAtlasClientCanonicalJson, character(1))
    return(paste0("[", paste(parts, collapse = ","), "]"))
  }
  jsonlite::toJSON(value, auto_unbox = TRUE, null = "null", digits = NA)
}

ohdsi_atlas_clientJson <- function(value, pretty = TRUE) {
  jsonlite::toJSON(
    value,
    auto_unbox = TRUE,
    null = "null",
    na = "null",
    digits = NA,
    pretty = pretty
  )
}

ohdsiAtlasClientReadJson <- function(path) {
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

ohdsiAtlasClientWriteJson <- function(value, path, pretty = TRUE) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  temporary <- paste0(path, ".tmp")
  writeLines(
    as.character(ohdsi_atlas_clientJson(value, pretty = pretty)),
    temporary,
    useBytes = TRUE
  )
  file.rename(temporary, path)
  path
}

ohdsiAtlasClientUniqueName <- function(name, existing, suffix = " (imported)") {
  if (!name %in% existing) {
    return(name)
  }
  candidate <- paste0(name, suffix)
  index <- 2L
  while (candidate %in% existing) {
    candidate <- paste0(name, suffix, " ", index)
    index <- index + 1L
  }
  candidate
}

ohdsi_atlas_clientChunk <- function(values, size) {
  checkmate::assertInt(size, lower = 1)
  if (length(values) == 0) {
    return(list())
  }
  split(values, ceiling(seq_along(values) / size))
}

ohdsi_atlas_clientAsList <- function(value) {
  if (is.null(value)) {
    return(list())
  }
  if (is.list(value)) {
    return(value)
  }
  as.list(value)
}

ohdsi_atlas_clientAssertSourceKey <- function(sourceKey) {
  checkmate::assertString(sourceKey, min.chars = 1)
  sourceKey
}


ohdsiAtlasClientKeyIdentifier <- function(apiKey) {
  if (is.null(apiKey) || !nzchar(apiKey)) {
    return(NULL)
  }
  match <- regmatches(apiKey, regexec("^wa_([0-9a-fA-F]{16})_[A-Za-z0-9_-]+$", apiKey))[[1]]
  if (length(match) < 2) {
    return(NULL)
  }
  match[[2]]
}
