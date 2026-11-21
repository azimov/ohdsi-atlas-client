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

# In-process fake of WebAPI 3.0.
#
# Rather than opening a socket, the fake replaces `ohdsiAtlasClientPerform()`,
# the single seam every request goes through. Real httr2 requests are built and
# real httr2_response objects are returned, so discovery, authentication, header
# handling, status mapping, JSON/text decoding, retries, and every resource
# method are exercised for real. The fake records each request so tests can
# assert on the path, query string, body, and headers that were actually sent.
#
# Routes are matched in registration order, so a test can override any default.
# Anything unmatched falls through to a plausible default for that path shape.

fakeWebApi <- local({
  routes <- list()
  entries <- list()

  register <- function(pattern, handler) {
    routes[[length(routes) + 1L]] <<- list(pattern = pattern, handler = handler)
    invisible(NULL)
  }

  reset <- function() {
    routes <<- list()
    entries <<- list()
    invisible(NULL)
  }

  requests <- function() entries

  last <- function() {
    if (length(entries) == 0L) {
      return(NULL)
    }
    entries[[length(entries)]]
  }

  respond <- function(status = 200L, body = NULL, type = NULL) {
    text <- if (is.null(body)) {
      ""
    } else if (is.character(body) && length(body) == 1L) {
      body
    } else {
      as.character(jsonlite::toJSON(body, auto_unbox = TRUE, null = "null", digits = NA))
    }
    if (is.null(type)) {
      # A real server sends JSON for structured data and text/plain for SQL.
      looksJson <- nzchar(text) && grepl("^[[:space:]]*[\\[{]", text)
      type <- if (looksJson) "application/json" else "text/plain"
    }
    httr2::response(
      url = "http://fake/WebAPI",
      status = status,
      headers = list("Content-Type" = type),
      body = charToRaw(text)
    )
  }

  defaultBody <- function(path, method) {
    # Text responses first: these must not be mistaken for JSON payloads.
    if (grepl("/ddl/", path)) {
      return("CREATE TABLE IF NOT EXISTS results.cohort (cohort_definition_id int);")
    }
    if (grepl("/export", path)) {
      return("PK-fake-zip")
    }
    if (grepl("/sql$", path)) {
      # WebAPI returns the rendered SQL in a `templateSql` field.
      return(list(templateSql = "SELECT 1;", requiredParameters = list(), parameters = list()))
    }
    if (grepl("/check", path)) {
      return(list(warnings = list()))
    }
    if (grepl("/info$", path)) {
      return(list(
        version = "3.0.0",
        buildInfo = list(artifactVersion = "WebAPI 3.0.0-TEST"),
        configuration = list(person = list(viewDatesPermitted = FALSE))
      ))
    }
    if (grepl("/user/me$", path)) {
      return(list(
        user = list(id = 1, login = "tester", name = "Tester"),
        authz = list(permissions = c("read:cohort-definition", "admin:security"))
      ))
    }
    catalogue <- "/(domains|vocabularies|information|info|daimons|permissions|roles|details)$"
    if (grepl(catalogue, path)) {
      return(list())
    }
    if (grepl("/search", path)) {
      return(list(
        list(conceptId = 1124300, conceptName = "diclofenac", domainId = "Drug",
             vocabularyId = "RxNorm", standardConcept = "S"),
        list(conceptId = 201826, conceptName = "Type 2 diabetes mellitus",
             domainId = "Condition", vocabularyId = "SNOMED", standardConcept = "S")
      ))
    }
    if (grepl("/conceptRecordCount$", path)) {
      return(list(list(`1124300` = list(830, 830, 830, 830))))
    }
    if (grepl("/job/execution", path)) {
      return(list(
        content = list(list(executionId = 49, status = "COMPLETED",
                            jobInstance = list(name = "cleanupCohort"))),
        page = list(size = 20, number = 0, totalElements = 1, totalPages = 1)
      ))
    }
    if (grepl("^/WebAPI/source/sources$", path)) {
      return(list(
        list(sourceId = 1, sourceKey = "EUNOMIA", sourceName = "Eunomia",
             sourceDialect = "postgresql", priority = 0),
        list(sourceId = 2, sourceKey = "SYNTH", sourceName = "Synthetic",
             sourceDialect = "sql server", priority = 1)
      ))
    }
    if (grepl("^/WebAPI/conceptset/[0-9]+(/|$)", path)) {
      return(list(id = 1, name = "Set", expression = list(items = list())))
    }
    if (grepl("^/WebAPI/cohortdefinition$", path)) {
      if (identical(method, "POST")) {
        return(list(id = 42, name = "New cohort", expression = list()))
      }
      return(list(
        list(id = 1, name = "Demo cohort", description = "demo"),
        list(id = 2, name = "Another cohort", description = "")
      ))
    }
    if (grepl("^/WebAPI/cohortdefinition/[0-9]+$", path)) {
      return(list(
        id = 1,
        name = "Demo cohort",
        description = "demo",
        expression = jsonlite::toJSON(list(PrimaryCriteria = list()), auto_unbox = TRUE)
      ))
    }
    if (grepl("/generate/", path)) {
      return(list(executionId = 49, status = "PENDING"))
    }
    if (grepl("^/WebAPI/(cohortdefinition|ir)/[0-9]+/info$", path)) {
      return(list(list(id = list(cohortDefinitionId = 1, sourceId = 1),
                       status = "COMPLETE", personCount = 830)))
    }
    if (grepl("/report/.*/inclusion", path)) {
      return(list(summary = list(list(id = -1, name = "All", count = 830))))
    }
    if (grepl("/person$", path)) {
      return(list(person = list(1)))
    }
    if (grepl("/permission", path)) {
      return(list())
    }
    if (grepl("/evidence", path)) {
      return(list())
    }
    if (grepl("^/WebAPI/conceptset$", path)) {
      if (identical(method, "POST")) {
        return(list(id = 42, name = "New concept set"))
      }
      return(list(
        list(id = 1, name = "Existing set"),
        list(id = 2, name = "Another set")
      ))
    }
    if (grepl("/(tag|tool|role|user)", path)) {
      if (identical(method, "GET")) {
        return(list())
      }
      return(list(id = 1, name = "created"))
    }
    if (grepl("^/WebAPI/[a-z-]+$", path) && identical(method, "GET")) {
      return(list(list(id = 1, name = "item")))
    }
    if (identical(method, "GET")) {
      return(list())
    }
    list(id = 1)
  }

  perform <- function(request) {
    parsed <- httr2::url_parse(request$url)
    path <- parsed$path
    query <- parsed$query
    body <- request$body$data
    if (is.raw(body)) {
      body <- rawToChar(body)
    }
    method <- request$method
    entries[[length(entries) + 1L]] <<- list(
      method = method,
      path = path,
      query = query,
      body = body,
      headers = request$headers
    )

    key <- request$headers[["X-API-KEY"]]
    if (is.null(key)) {
      key <- request$headers[["x-api-key"]]
    }
    if (!is.null(key) && identical(as.character(key), "bad-key")) {
      return(respond(401L, list(message = "Unauthorized")))
    }
    if (grepl("/forbidden", path)) {
      return(respond(403L, list(message = "Access Denied")))
    }
    if (grepl("/missing", path)) {
      return(respond(404L, list(message = "Resource not found")))
    }
    if (grepl("/broken", path)) {
      return(respond(500L, list(message = "boom")))
    }

    for (route in routes) {
      if (grepl(route$pattern, path)) {
        return(route$handler(path = path, query = query, request = request))
      }
    }
    respond(200L, defaultBody(path, method))
  }

  list(
    register = register,
    reset = reset,
    requests = requests,
    last = last,
    respond = respond,
    perform = perform
  )
})

# Install the fake for the duration of `code`, then restore the real transport.
withFakeWebApi <- function(code) {
  original <- get("ohdsiAtlasClientPerform", envir = asNamespace("OhdsiAtlasClient"))
  fakeWebApi$reset()
  assignInNamespace("ohdsiAtlasClientPerform", fakeWebApi$perform, ns = "OhdsiAtlasClient")
  on.exit(
    assignInNamespace("ohdsiAtlasClientPerform", original, ns = "OhdsiAtlasClient"),
    add = TRUE
  )
  force(code)
}

# A connected client pointed at the fake. No network access is needed.
fakeClient <- function(apiKey = "test-key", url = "https://fake.example.org") {
  connectAtlas(
    url,
    apiKey = apiKey,
    useKeyring = FALSE,
    credentialStore = OhdsiAtlasClient:::OhdsiAtlasClientCredentialStore$new(
      configDir = tempfile("fake-"),
      useKeyring = FALSE
    )
  )
}
