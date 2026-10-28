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

#' @noRd
Atlas3 <- R6::R6Class(
  "Atlas3",
  public = list(
    url = NULL,
    apiUrl = NULL,
    atlasUrl = NULL,
    version = NULL,
    discovery = NULL,
    apiKey = NULL,
    bearerToken = NULL,
    timeout = 60,
    sources = NULL,
    concepts = NULL,
    conceptSets = NULL,
    cohorts = NULL,
    cohortSets = NULL,
    cdmResults = NULL,
    jobs = NULL,
    cohortCharacterizations = NULL,
    featureAnalyses = NULL,
    incidenceRates = NULL,
    pathways = NULL,
    reusable = NULL,
    tags = NULL,
    auth = NULL,
    tools = NULL,
    notifications = NULL,
    cache = NULL,
    sqlrender = NULL,
    ddl = NULL,
    evidence = NULL,
    statistic = NULL,

    initialize = function(url,
                          apiKey = NULL,
                          bearerToken = NULL,
                          profile = "default",
                          timeout = 60,
                          discovery = NULL,
                          credentialStore = NULL,
                          useKeyring = TRUE,
                          autoLogin = FALSE,
                          username = NULL,
                          password = NULL) {
      checkmate::assertString(url, min.chars = 1)
      self$url <- atlas3NormalizeUrl(url)
      self$timeout <- timeout
      self$discovery <- if (is.null(discovery)) {
        discoverAtlas(self$url, timeout = min(timeout, 15))
      } else if (inherits(discovery, "atlas3_discovery")) {
        discovery
      } else {
        atlas3DiscoveryFromList(discovery)
      }
      self$apiUrl <- self$discovery$apiUrl
      self$atlasUrl <- self$discovery$atlasUrl
      self$version <- self$discovery$version

      private$credentialStore <- credentialStore %||%
        Atlas3CredentialStore$new(profile = profile, useKeyring = useKeyring)
      apiKey <- apiKey %||% Sys.getenv("ATLAS3_API_KEY", unset = NA_character_)
      if (identical(apiKey, NA_character_) || !nzchar(apiKey)) {
        apiKey <- NULL
      }
      if (is.null(apiKey) && is.null(bearerToken)) {
        stored <- private$credentialStore$get(self$apiUrl)
        if (!is.null(stored$apiKey)) {
          apiKey <- stored$apiKey
          private$credential <- stored
        }
      }
      self$apiKey <- apiKey
      self$bearerToken <- bearerToken

      if (isTRUE(autoLogin) && is.null(apiKey) && is.null(bearerToken)) {
        self$login()
      }

      self$sources <- Atlas3Sources$new(self)
      self$concepts <- Atlas3Concepts$new(self)
      self$conceptSets <- Atlas3ConceptSets$new(self)
      self$cohorts <- Atlas3Cohorts$new(self)
      self$cohortSets <- Atlas3CohortSets$new(self)
      self$cdmResults <- Atlas3CdmResults$new(self)
      self$jobs <- Atlas3Jobs$new(self)
      self$cohortCharacterizations <- Atlas3Analyses$new(
        self, "/cohort-characterization", copyMethod = "post",
        importPath = "/import", exportPath = "/{id}/export",
        generateMethod = "post", generatePath = "/{id}/generation/{sourceKey}",
        cancelMethod = "delete", generationPath = "/{id}/generation",
        versions = TRUE, tags = TRUE
      )
      self$featureAnalyses <- Atlas3FeatureAnalyses$new(self)
      self$incidenceRates <- Atlas3IncidenceRates$new(self)
      self$pathways <- Atlas3Analyses$new(
        self, "/pathway-analysis", copyMethod = "post",
        importPath = "/import", exportPath = "/{id}/export",
        generateMethod = "post", generatePath = "/{id}/generation/{sourceKey}",
        cancelMethod = "delete", generationPath = "/{id}/generation",
        versions = TRUE, tags = TRUE
      )
      self$reusable <- Atlas3Analyses$new(
        self, "/reusable", copyMethod = "post", importPath = "",
        exportPath = "/{id}", generateMethod = NULL, versions = TRUE,
        tags = TRUE
      )
      self$tags <- Atlas3Tags$new(self)
      self$auth <- Atlas3Auth$new(self)
      self$tools <- Atlas3Tools$new(self)
      self$notifications <- Atlas3Notifications$new(self)
      self$cache <- Atlas3Cache$new(self)
      self$sqlrender <- Atlas3SqlRender$new(self)
      self$ddl <- Atlas3Ddl$new(self)
      self$evidence <- Atlas3Evidence$new(self)
      self$statistic <- Atlas3Statistic$new(self)

      if (!is.null(username) || !is.null(password)) {
        self$login(username, password)
      }
      invisible(self)
    },

    login = function(username = NULL,
                     password = NULL,
                     keyName = "atlas3-r",
                     description = NULL,
                     expiresInDays = NULL,
                     store = TRUE,
                     createApiKey = TRUE) {
      username <- username %||% Sys.getenv("ATLAS3_USERNAME", unset = NA_character_)
      password <- password %||% Sys.getenv("ATLAS3_PASSWORD", unset = NA_character_)
      if (is.na(username) || !nzchar(username)) {
        if (!interactive()) {
          abort("No username supplied and ATLAS3_USERNAME is not set",
            class = "atlas3_configuration_error"
          )
        }
        username <- readline("ATLAS3 username: ")
      }
      if (is.na(password) || !nzchar(password)) {
        if (!interactive()) {
          abort("No password supplied and ATLAS3_PASSWORD is not set",
            class = "atlas3_configuration_error"
          )
        }
        password <- if (requireNamespace("askpass", quietly = TRUE)) {
          askpass::askpass("ATLAS3 password: ")
        } else {
          readline("ATLAS3 password: ")
        }
      }

      provider <- private$databaseProvider()
      loginPath <- provider$url %||% "user/login/db"
      loginPath <- sub("^/+", "", loginPath)
      result <- private$rawRequest(
        "POST", paste0("/", loginPath),
        form = list(login = username, password = password)
      )
      jwt <- result$jwt
      if (is.null(jwt) || !nzchar(jwt)) {
        abort(
          "WebAPI did not return a JWT. Check that database authentication is enabled and the credentials are correct.",
          class = "atlas3_authentication_error"
        )
      }

      if (isTRUE(createApiKey)) {
        key <- private$rawRequest(
          "POST", "/user/apikeys",
          body = list(
            name = keyName,
            description = description,
            expiresInDays = expiresInDays
          ),
          bearerToken = jwt
        )
        rawKey <- key$rawKey
        if (is.null(rawKey) || !nzchar(rawKey)) {
          abort("WebAPI created an API key but did not return it",
            class = "atlas3_authentication_error"
          )
        }
        self$apiKey <- rawKey
        self$bearerToken <- NULL
        private$credential <- list(
          apiKey = rawKey,
          apiUrl = self$apiUrl,
          login = result$login %||% username,
          keyIdentifier = key$keyIdentifier,
          createdAt = atlas3NowIso()
        )
        if (isTRUE(store)) {
          private$credentialStore$set(
            self$apiUrl,
            rawKey,
            login = private$credential$login,
            keyIdentifier = key$keyIdentifier
          )
        }
      } else {
        self$bearerToken <- jwt
        self$apiKey <- NULL
      }
      private$currentUser <- NULL
      self$whoami()
      invisible(self)
    },

    loginWithJwt = function(jwt,
                            createApiKey = FALSE,
                            keyName = "atlas3-r",
                            description = NULL,
                            expiresInDays = NULL,
                            store = TRUE) {
      checkmate::assertString(jwt, min.chars = 1)
      if (!isTRUE(createApiKey)) {
        self$bearerToken <- jwt
        self$apiKey <- NULL
        private$currentUser <- NULL
        self$whoami()
        return(invisible(self))
      }
      key <- private$rawRequest(
        "POST", "/user/apikeys",
        body = list(
          name = keyName,
          description = description,
          expiresInDays = expiresInDays
        ),
        bearerToken = jwt
      )
      self$apiKey <- key$rawKey
      self$bearerToken <- NULL
      private$credential <- list(
        apiKey = self$apiKey,
        apiUrl = self$apiUrl,
        keyIdentifier = key$keyIdentifier,
        createdAt = atlas3NowIso()
      )
      if (isTRUE(store)) {
        private$credentialStore$set(
          self$apiUrl, self$apiKey,
          keyIdentifier = key$keyIdentifier
        )
      }
      private$currentUser <- NULL
      self$whoami()
      invisible(self)
    },

    logout = function(revoke = TRUE) {
      if (isTRUE(revoke) && !is.null(private$credential$keyIdentifier)) {
        tryCatch(
          self$auth$revokeApiKey(private$credential$keyIdentifier, remove = TRUE),
          error = function(e) NULL
        )
      }
      private$credentialStore$delete(self$apiUrl)
      private$credential <- NULL
      private$currentUser <- NULL
      self$apiKey <- NULL
      self$bearerToken <- NULL
      invisible(self)
    },

    whoami = function(force = FALSE) {
      if (is.null(private$currentUser) || isTRUE(force)) {
        private$currentUser <- self$request("GET", "/user/me")
      }
      private$currentUser
    },

    permissions = function() {
      self$whoami()$authz$permissions %||% character()
    },

    hasPermission = function(permission) {
      permissions <- self$permissions()
      if ("*" %in% permissions || permission %in% permissions) {
        return(TRUE)
      }
      prefix <- strsplit(permission, ":", fixed = TRUE)[[1]][1]
      paste0(prefix, ":*") %in% permissions
    },

    request = function(method, path, query = list(), body = NULL, form = NULL,
                       raw = FALSE, timeout = NULL) {
      atlas3Request(
        self, method, path,
        query = query, body = body, form = form, raw = raw, timeout = timeout
      )
    },

    call = function(operationId, ...) {
      atlas3CallEndpoint(self, operationId, ...)
    },

    endpoints = function(group = NULL, method = NULL, pathContains = NULL) {
      atlas3Endpoints(self, group = group, method = method, pathContains = pathContains)
    },

    close = function() {
      invisible(self)
    },

    print = function(...) {
      user <- tryCatch(self$whoami()$user$login, error = function(e) "unknown")
      cat("<Atlas3 client>\n")
      cat("  WebAPI: ", self$apiUrl, "\n", sep = "")
      cat("  Version:", self$version, "\n", sep = " ")
      cat("  User:   ", user, "\n", sep = "")
      cat("  Key:    ", atlas3RedactKey(self$apiKey), "\n", sep = "")
      invisible(self)
    }
  ),
  private = list(
    credentialStore = NULL,
    credential = NULL,
    currentUser = NULL,
    databaseProvider = function() {
      providers <- self$discovery$authProviders
      for (provider in providers) {
        if (identical(tolower(provider$name), "db") ||
          grepl("login/db", provider$url %||% "", fixed = TRUE)) {
          return(provider)
        }
      }
      abort(
        "This WebAPI does not advertise database authentication. Supply a personal API key or JWT instead.",
        class = "atlas3_authentication_error"
      )
    },
    rawRequest = function(method, path, body = NULL, form = NULL, bearerToken = NULL) {
      url <- atlas3HttpUrl(self, path)
      request <- httr2::request(url)
      request <- httr2::req_method(request, method)
      headers <- list(Accept = "application/json")
      if (!is.null(bearerToken)) {
        headers[["Authorization"]] <- paste("Bearer", bearerToken)
      }
      request <- do.call(httr2::req_headers, c(list(request), headers))
      request <- httr2::req_timeout(request, self$timeout)
      request <- httr2::req_error(request, is_error = function(resp) FALSE)
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
      response <- tryCatch(
        httr2::req_perform(request),
        error = function(error) {
          abort(
            paste0("Could not reach WebAPI: ", conditionMessage(error)),
            class = "atlas3_connection_error"
          )
        }
      )
      if (httr2::resp_status(response) >= 400L) {
        atlas3HttpError(response, method, url)
      }
      httr2::resp_body_json(response, simplifyVector = FALSE)
    }
  )
)

#' Connect to an ATLAS 3.0 deployment
#'
#' Discovers the WebAPI root, checks that the server is ATLAS/WebAPI 3.0 or
#' newer, and returns an [Atlas3] client. Supply an `apiKey` to skip credential
#' lookup, or call `$login()` afterwards to create and store one.
#'
#' @param url ATLAS UI URL, WebAPI URL, or bare host name.
#' @param apiKey Optional personal API key (`wa_...`).
#' @param bearerToken Optional JWT.
#' @param profile Credential-store profile name.
#' @param timeout Request timeout in seconds.
#' @param discovery Optional pre-built discovery result (used in tests).
#' @param credentialStore Optional `Atlas3CredentialStore`.
#' @param useKeyring Prefer the OS keyring when the `keyring` package is
#'   installed.
#' @param autoLogin Log in with `ATLAS3_USERNAME` / `ATLAS3_PASSWORD` when no
#'   credential is available.
#' @param username Optional login name; when supplied, the client logs in and
#'   provisions an API key immediately.
#' @param password Optional password used only for that login.
#' @return An Atlas3 client object.
#' @export
#' @examples
#' \dontrun{
#' atlas <- connectAtlas("https://atlas.example.org")
#' atlas$sources$list()
#' }
connectAtlas <- function(url,
                         apiKey = NULL,
                         bearerToken = NULL,
                         profile = "default",
                         timeout = 60,
                         discovery = NULL,
                         credentialStore = NULL,
                         useKeyring = TRUE,
                         autoLogin = FALSE,
                         username = NULL,
                         password = NULL) {
  Atlas3$new(
    url = url,
    apiKey = apiKey,
    bearerToken = bearerToken,
    profile = profile,
    timeout = timeout,
    discovery = discovery,
    credentialStore = credentialStore,
    useKeyring = useKeyring,
    autoLogin = autoLogin,
    username = username,
    password = password
  )
}
