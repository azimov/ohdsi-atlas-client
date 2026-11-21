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

# Single seam for performing a request. Tests replace this to exercise the
# client without a live server; production code always goes through httr2.
ohdsiAtlasClientPerform <- function(request) {
  httr2::req_perform(request)
}

ohdsiAtlasClientHttpUrl <- function(client, path) {
  if (grepl("^https?://", path)) {
    return(path)
  }
  paste0(sub("/+$", "", client$apiUrl), "/", sub("^/+", "", path))
}

ohdsiAtlasClientHttpHeaders <- function(client) {
  headers <- list(Accept = "application/json")
  if (!is.null(client$apiKey) && nzchar(client$apiKey)) {
    headers[["X-API-KEY"]] <- client$apiKey
  }
  headers
}

ohdsi_atlas_clientErrorMessage <- function(response) {
  body <- tryCatch(
    httr2::resp_body_json(response, simplifyVector = FALSE),
    error = function(e) NULL
  )
  if (is.list(body)) {
    message <- body$message %||% body$error %||% body$detail
    if (!is.null(message)) {
      return(as.character(message))
    }
  }
  text <- tryCatch(httr2::resp_body_string(response), error = function(e) "")
  if (nzchar(text)) {
    return(substr(text, 1, 2000))
  }
  httr2::resp_status_desc(response)
}

ohdsiAtlasClientHttpError <- function(response, method, url) {
  status <- httr2::resp_status(response)
  message <- ohdsi_atlas_clientErrorMessage(response)
  if (status == 401L) {
    abort(
      paste0(
        "WebAPI rejected the API key: ", message,
        ". Supply a valid key with connectAtlas(apiKey = ...) or $login(apiKey)."
      ),
      class = c("ohdsi_atlas_client_authentication_error", "ohdsi_atlas_client_http_error"),
      status = status,
      method = method,
      url = url
    )
  }
  if (status == 403L) {
    abort(
      paste0("Permission denied: ", message, "."),
      class = c("ohdsi_atlas_client_permission_error", "ohdsi_atlas_client_http_error"),
      status = status,
      method = method,
      url = url
    )
  }
  if (status == 404L) {
    abort(
      message,
      class = c("ohdsi_atlas_client_not_found_error", "ohdsi_atlas_client_http_error"),
      status = status,
      method = method,
      url = url
    )
  }
  if (status >= 500L) {
    abort(
      message,
      class = c("ohdsi_atlas_client_server_error", "ohdsi_atlas_client_http_error"),
      status = status,
      method = method,
      url = url
    )
  }
  abort(
    message,
    class = c("ohdsi_atlas_client_http_error"),
    status = status,
    method = method,
    url = url
  )
}

ohdsiAtlasClientRequest <- function(client,
                          method,
                          path,
                          query = list(),
                          body = NULL,
                          form = NULL,
                          headers = NULL,
                          raw = FALSE,
                          timeout = NULL) {
  method <- toupper(method)
  url <- ohdsiAtlasClientHttpUrl(client, path)
  request <- httr2::request(url)
  request <- httr2::req_method(request, method)
  requestHeaders <- ohdsiAtlasClientHttpHeaders(client)
  if (length(headers) > 0) {
    requestHeaders[names(headers)] <- headers
  }
  request <- do.call(httr2::req_headers, c(list(request), requestHeaders))
  request <- httr2::req_user_agent(
    request,
    paste0("ohdsi-atlas-client-r/", utils::packageVersion("OhdsiAtlasClient"))
  )
  request <- httr2::req_timeout(request, timeout %||% client$timeout)
  request <- httr2::req_error(request, is_error = function(resp) FALSE)
  if (length(query) > 0) {
    query <- query[!vapply(query, is.null, logical(1))]
    if (length(query) > 0) {
      request <- do.call(httr2::req_url_query, c(list(request), query))
    }
  }
  if (!is.null(body)) {
    request <- httr2::req_body_raw(
      request,
      jsonlite::toJSON(body, auto_unbox = TRUE, null = "null", na = "null", digits = NA),
      type = "application/json"
    )
  }
  if (!is.null(form)) {
    request <- do.call(httr2::req_body_form, c(list(request), form))
  }
  maxTries <- if (method %in% c("GET", "HEAD", "OPTIONS", "PUT", "DELETE")) 3L else 1L
  request <- httr2::req_retry(
    request,
    max_tries = maxTries,
    is_transient = function(resp) httr2::resp_status(resp) %in% c(429L, 500L, 502L, 503L, 504L)
  )

  response <- tryCatch(
    ohdsiAtlasClientPerform(request),
    error = function(error) {
      abort(
        paste0("Could not reach WebAPI: ", conditionMessage(error)),
        class = c("ohdsi_atlas_client_connection_error", "ohdsi_atlas_client_http_error"),
        method = method,
        url = url
      )
    }
  )

  status <- httr2::resp_status(response)
  if (status >= 400L) {
    ohdsiAtlasClientHttpError(response, method, url)
  }
  body <- tryCatch(httr2::resp_body_raw(response), error = function(e) raw(0))
  if (length(body) == 0) {
    return(NULL)
  }
  if (raw) {
    return(body)
  }
  contentType <- httr2::resp_content_type(response)
  if (grepl("json", contentType, fixed = TRUE)) {
    return(httr2::resp_body_json(response, simplifyVector = FALSE))
  }
  text <- httr2::resp_body_string(response)
  if (grepl("^[[:space:]]*[\\[{]", text)) {
    return(tryCatch(
      jsonlite::fromJSON(text, simplifyVector = FALSE),
      error = function(e) text
    ))
  }
  text
}
