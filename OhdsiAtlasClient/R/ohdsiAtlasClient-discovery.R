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

ohdsi_atlas_clientHttpGet <- function(url, timeout = 10) {
  request <- httr2::request(url)
  request <- httr2::req_timeout(request, timeout)
  request <- httr2::req_user_agent(request, "ohdsi-atlas-client-r")
  request <- httr2::req_headers(request, Accept = "application/json")
  request <- httr2::req_error(request, is_error = function(resp) FALSE)
  tryCatch(
    {
      response <- ohdsiAtlasClientPerform(request)
      list(
        status = httr2::resp_status(response),
        contentType = httr2::resp_content_type(response),
        body = if (grepl("json", httr2::resp_content_type(response), fixed = TRUE)) {
          tryCatch(
            httr2::resp_body_json(response, simplifyVector = FALSE),
            error = function(e) NULL
          )
        } else {
          NULL
        }
      )
    },
    error = function(error) {
      list(status = 0L, contentType = "", body = NULL, error = conditionMessage(error))
    }
  )
}

ohdsi_atlas_clientAtlasUrl <- function(url, apiUrl) {
  normalised <- ohdsiAtlasClientNormalizeUrl(url)
  if (grepl("/atlas(/|$)", normalised, ignore.case = TRUE)) {
    return(normalised)
  }
  sub("/WebAPI$", "", apiUrl, ignore.case = TRUE)
}

#' Discover an ATLAS 3.0 WebAPI
#'
#' Probes the common ATLAS/WebAPI URL layouts and checks the server version.
#' Most users should call [connectAtlas()] instead.
#'
#' @param url ATLAS UI URL, WebAPI URL, or bare host name.
#' @param timeout Per-candidate timeout in seconds.
#' @return An object of class `ohdsi_atlas_client_discovery` with `inputUrl`, `apiUrl`,
#'   `atlasUrl`, `version`, `buildInfo`, and `configuration`.
#' @export
#' @examples
#' \dontrun{
#' discovery <- discoverAtlas("https://atlas.example.org")
#' discovery$apiUrl
#' }
discoverAtlas <- function(url, timeout = 10) {
  candidates <- ohdsiAtlasClientCandidateApiBases(url)
  attempts <- list()
  info <- NULL
  apiUrl <- NULL
  for (candidate in candidates) {
    response <- ohdsi_atlas_clientHttpGet(paste0(candidate, "/info"), timeout = timeout)
    if (response$status == 0L) {
      attempts[[length(attempts) + 1L]] <- list(url = candidate, reason = "connection failed")
      next
    }
    if (response$status == 404L) {
      attempts[[length(attempts) + 1L]] <- list(url = candidate, reason = "HTTP 404")
      next
    }
    if (response$status != 200L || is.null(response$body)) {
      attempts[[length(attempts) + 1L]] <- list(
        url = candidate,
        reason = paste0("HTTP ", response$status)
      )
      next
    }
    if (is.null(response$body$version)) {
      attempts[[length(attempts) + 1L]] <- list(url = candidate, reason = "missing version")
      next
    }
    info <- response$body
    apiUrl <- candidate
    break
  }
  if (is.null(info) || is.null(apiUrl)) {
    abort(
      paste0(
        "Could not discover an ATLAS 3.0 WebAPI at ", url, ". ",
        "Pass the ATLAS URL (for example https://atlas.example.org) or the ",
        "WebAPI root (for example https://atlas.example.org/WebAPI)."
      ),
      class = "ohdsi_atlas_client_discovery_error",
      attempts = attempts
    )
  }
  version <- as.character(info$version)
  if (!ohdsiAtlasClientVersionAtLeast(version, "3.0.0")) {
    abort(
      paste0(
        "WebAPI at ", apiUrl, " reports version ", version,
        ". These clients require ATLAS/WebAPI 3.0.0 or newer."
      ),
      class = "ohdsi_atlas_client_unsupported_version_error",
      version = version,
      apiUrl = apiUrl
    )
  }

  structure(
    list(
      inputUrl = ohdsiAtlasClientNormalizeUrl(url),
      apiUrl = apiUrl,
      atlasUrl = ohdsi_atlas_clientAtlasUrl(url, apiUrl),
      version = version,
      buildInfo = info$buildInfo %||% list(),
      configuration = info$configuration %||% list()
    ),
    class = "ohdsi_atlas_client_discovery"
  )
}

#' @export
print.ohdsi_atlas_client_discovery <- function(x, ...) {
  cat("<OhdsiAtlasClient discovery>\n")
  cat("  ATLAS:  ", x$atlasUrl, "\n", sep = "")
  cat("  WebAPI: ", x$apiUrl, "\n", sep = "")
  cat("  Version:", x$version, "\n", sep = " ")
  invisible(x)
}

ohdsiAtlasClientDiscoveryFromList <- function(value) {
  checkmate::assertList(value, names = "named")
  required <- c("apiUrl", "atlasUrl", "version")
  missing <- setdiff(required, names(value))
  if (length(missing) > 0) {
    abort(paste0("Discovery object is missing: ", paste(missing, collapse = ", ")))
  }
  if (!ohdsiAtlasClientVersionAtLeast(as.character(value$version), "3.0.0")) {
    abort(
      paste0("WebAPI version ", value$version, " is older than ATLAS 3.0"),
      class = "ohdsi_atlas_client_unsupported_version_error"
    )
  }
  structure(value, class = "ohdsi_atlas_client_discovery")
}

`%||%` <- function(left, right) {
  if (is.null(left)) right else left
}
