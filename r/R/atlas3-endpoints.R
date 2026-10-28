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

atlas3Catalog <- local({
  cache <- NULL
  function() {
    if (is.null(cache)) {
      path <- system.file("extdata", "endpoints.json", package = "Atlas3")
      if (!nzchar(path) || !file.exists(path)) {
        abort("The bundled endpoint catalog is missing", class = "atlas3_error")
      }
      cache <<- jsonlite::fromJSON(path, simplifyVector = FALSE)
    }
    cache
  }
})

atlas3Endpoint <- function(operationId) {
  catalog <- atlas3Catalog()
  matches <- Filter(
    function(endpoint) identical(endpoint$operationId, operationId),
    catalog$endpoints
  )
  if (length(matches) == 0) {
    abort(
      paste0("Unknown WebAPI operation '", operationId, "'"),
      class = "atlas3_endpoint_error"
    )
  }
  matches[[1]]
}

#' List the WebAPI endpoint catalog
#'
#' @param client An [Atlas3] client.
#' @param group Optional resource group filter.
#' @param method Optional HTTP method filter.
#' @param pathContains Optional path fragment filter.
#' @return A list of endpoint records (or a data frame when no filters are
#'   supplied? Always a list to preserve all fields).
#' @export
#' @examples
#' \dontrun{
#' atlas <- connectAtlas("https://atlas.example.org")
#' length(atlas$endpoints())
#' atlas$endpoints(group = "cohortdefinition")
#' }
atlas3Endpoints <- function(client, group = NULL, method = NULL, pathContains = NULL) {
  catalog <- atlas3Catalog()
  endpoints <- catalog$endpoints
  if (!is.null(group)) {
    endpoints <- Filter(function(endpoint) identical(endpoint$group, group), endpoints)
  }
  if (!is.null(method)) {
    endpoints <- Filter(
      function(endpoint) identical(toupper(endpoint$method), toupper(method)),
      endpoints
    )
  }
  if (!is.null(pathContains)) {
    endpoints <- Filter(
      function(endpoint) grepl(pathContains, endpoint$path, fixed = TRUE),
      endpoints
    )
  }
  endpoints
}

#' Invoke an endpoint from the catalog
#'
#' Path parameters, query parameters, and the body may be passed by name:
#' `atlas$call("cohortdefinition.generateCohort", id = 1, sourceKey = "EUNOMIA")`.
#' Use `body =` for a JSON body and `query =` for a query-parameter list.
#'
#' @param client An [Atlas3] client.
#' @param operationId The catalog operation ID.
#' @param ... Path/query parameters, or `body`, `query`, `raw`, `timeout`.
#' @return The parsed response.
#' @export
#' @examples
#' \dontrun{
#' atlas <- connectAtlas("https://atlas.example.org")
#' atlas$call("cohortdefinition.getCohortDefinitionRaw", id = 1)
#' }
atlas3CallEndpoint <- function(client, operationId, ...) {
  endpoint <- atlas3Endpoint(operationId)
  dots <- list(...)
  pathParams <- dots$path_params %||% list()
  dots$path_params <- NULL
  query <- dots$query %||% list()
  dots$query <- NULL
  body <- dots$body %||% NULL
  dots$body <- NULL
  raw <- isTRUE(dots$raw)
  dots$raw <- NULL
  timeout <- dots$timeout %||% NULL
  dots$timeout <- NULL

  for (parameter in endpoint$parameters) {
    if (!identical(parameter[["in"]], "path")) next
    name <- parameter$name
    if (!is.null(dots[[name]])) {
      pathParams[[name]] <- dots[[name]]
      dots[[name]] <- NULL
    }
    if (is.null(pathParams[[name]])) {
      abort(
        paste0(operationId, " requires path parameter '", name, "'"),
        class = "atlas3_endpoint_error"
      )
    }
  }

  for (parameter in endpoint$parameters) {
    if (!identical(parameter[["in"]], "query")) next
    name <- parameter$name
    if (!is.null(dots[[name]])) {
      query[[name]] <- dots[[name]]
      dots[[name]] <- NULL
    }
  }

  if (length(dots) > 0) {
    abort(
      paste0(
        "Unexpected arguments for ", operationId, ": ",
        paste(names(dots), collapse = ", ")
      ),
      class = "atlas3_endpoint_error"
    )
  }

  path <- endpoint$path
  for (name in names(pathParams)) {
    path <- gsub(paste0("{", name, "}"), as.character(pathParams[[name]]), path, fixed = TRUE)
  }
  client$request(
    endpoint$method,
    path,
    query = query,
    body = body,
    raw = raw,
    timeout = timeout
  )
}
