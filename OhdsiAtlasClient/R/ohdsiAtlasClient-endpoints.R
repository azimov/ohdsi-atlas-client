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

ohdsiAtlasClientCatalog <- local({
  cache <- NULL
  function() {
    if (is.null(cache)) {
      path <- system.file("extdata", "endpoints.json", package = "OhdsiAtlasClient")
      if (!nzchar(path) || !file.exists(path)) {
        abort("The bundled endpoint catalog is missing", class = "ohdsi_atlas_client_error")
      }
      cache <<- jsonlite::fromJSON(path, simplifyVector = FALSE)
    }
    cache
  }
})

ohdsiAtlasClientEndpoint <- function(operationId) {
  catalog <- ohdsiAtlasClientCatalog()
  matches <- Filter(
    function(endpoint) identical(endpoint$operationId, operationId),
    catalog$endpoints
  )
  if (length(matches) == 0) {
    abort(
      paste0("Unknown WebAPI operation '", operationId, "'"),
      class = "ohdsi_atlas_client_endpoint_error"
    )
  }
  matches[[1]]
}

#' List the WebAPI endpoint catalog
#'
#' @param client An [OhdsiAtlasClient] client.
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
ohdsiAtlasClientEndpoints <- function(client, group = NULL, method = NULL, pathContains = NULL) {
  catalog <- ohdsiAtlasClientCatalog()
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
#' @param client An [OhdsiAtlasClient] client.
#' @param operationId The catalog operation ID.
#' @param ... Path/query parameters, or `body`, `query`, `raw`, `timeout`.
#' @param query Either a list of extra query-string parameters, or the value
#'   for WebAPI's own `query` search parameter (for example on
#'   `/vocabulary/{sourceKey}/search`). A list is always treated as the extra
#'   parameters; any other value is sent as `?query=`.
#' @return The parsed response.
#' @export
#' @examples
#' \dontrun{
#' atlas <- connectAtlas("https://atlas.example.org")
#' atlas$call("cohortdefinition.getCohortDefinitionRaw", id = 1)
#' }
ohdsiAtlasClientCallEndpoint <- function(client, operationId, ..., query = NULL) {
  endpoint <- ohdsiAtlasClientEndpoint(operationId)
  dots <- list(...)

  # `query` may mean two things:
  #   * a plain list: extra query-string parameters, e.g. query = list(rows = 5)
  #   * a single value for WebAPI's own `query` search parameter, e.g.
  #     query = "aspirin" on /vocabulary/{sourceKey}/search
  # A list is always the override. A non-list value is the `query` parameter,
  # which is how every caller writes it.
  if (is.list(query)) {
    extraQuery <- query
    queryParameter <- NULL
  } else {
    extraQuery <- list()
    queryParameter <- query
  }

  pathParams <- dots$path_params %||% list()
  dots$path_params <- NULL
  body <- dots$body %||% NULL
  dots$body <- NULL
  raw <- isTRUE(dots$raw)
  dots$raw <- NULL
  timeout <- dots$timeout %||% NULL
  dots$timeout <- NULL

  # Anything named like an operation parameter belongs to the operation.
  filters <- list(query = queryParameter)
  for (name in names(dots)) {
    value <- dots[[name]]
    dots[[name]] <- NULL
    if (is.null(value)) next
    filters[[name]] <- value
  }

  for (parameter in endpoint$parameters) {
    if (!identical(parameter[["in"]], "path")) next
    name <- parameter$name
    if (!is.null(filters[[name]])) {
      pathParams[[name]] <- filters[[name]]
      filters[[name]] <- NULL
    }
    if (is.null(pathParams[[name]])) {
      abort(
        paste0(operationId, " requires path parameter '", name, "'"),
        class = "ohdsi_atlas_client_endpoint_error"
      )
    }
  }

  queryString <- extraQuery
  for (parameter in endpoint$parameters) {
    if (!identical(parameter[["in"]], "query")) next
    name <- parameter$name
    if (!is.null(filters[[name]])) {
      queryString[[name]] <- filters[[name]]
      filters[[name]] <- NULL
    }
  }
  filters <- filters[!vapply(filters, is.null, logical(1))]

  if (length(filters) > 0) {
    abort(
      paste0(
        "Unexpected arguments for ", operationId, ": ",
        paste(names(filters), collapse = ", ")
      ),
      class = "ohdsi_atlas_client_endpoint_error"
    )
  }

  path <- endpoint$path
  for (name in names(pathParams)) {
    path <- gsub(paste0("{", name, "}"), as.character(pathParams[[name]]), path, fixed = TRUE)
  }
  client$request(
    endpoint$method,
    path,
    query = queryString,
    body = body,
    raw = raw,
    timeout = timeout
  )
}
