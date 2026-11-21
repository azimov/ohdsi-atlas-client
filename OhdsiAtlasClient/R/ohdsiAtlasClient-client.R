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

#' @noRd
OhdsiAtlasClient <- R6::R6Class(
  "OhdsiAtlasClient",
  public = list(
    url = NULL,
    apiUrl = NULL,
    atlasUrl = NULL,
    version = NULL,
    discovery = NULL,
    apiKey = NULL,
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
                          profile = "default",
                          timeout = 60,
                          discovery = NULL,
                          credentialStore = NULL,
                          useKeyring = TRUE) {
      checkmate::assertString(url, min.chars = 1)
      self$url <- ohdsiAtlasClientNormalizeUrl(url)
      self$timeout <- timeout
      self$discovery <- if (is.null(discovery)) {
        discoverAtlas(self$url, timeout = min(timeout, 15))
      } else if (inherits(discovery, "ohdsi_atlas_client_discovery")) {
        discovery
      } else {
        ohdsiAtlasClientDiscoveryFromList(discovery)
      }
      self$apiUrl <- self$discovery$apiUrl
      self$atlasUrl <- self$discovery$atlasUrl
      self$version <- self$discovery$version

      private$credentialStore <- credentialStore %||%
        OhdsiAtlasClientCredentialStore$new(profile = profile, useKeyring = useKeyring)
      apiKey <- apiKey %||% Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY", unset = NA_character_)
      if (identical(apiKey, NA_character_) || !nzchar(apiKey)) {
        apiKey <- NULL
      }
      if (is.null(apiKey)) {
        stored <- private$credentialStore$get(self$apiUrl)
        if (!is.null(stored$apiKey)) {
          apiKey <- stored$apiKey
          private$credential <- stored
        }
      }
      self$apiKey <- apiKey

      self$sources <- OhdsiAtlasClientSources$new(self)
      self$concepts <- OhdsiAtlasClientConcepts$new(self)
      self$conceptSets <- OhdsiAtlasClientConceptSets$new(self)
      self$cohorts <- OhdsiAtlasClientCohorts$new(self)
      self$cohortSets <- OhdsiAtlasClientCohortSets$new(self)
      self$cdmResults <- OhdsiAtlasClientCdmResults$new(self)
      self$jobs <- OhdsiAtlasClientJobs$new(self)
      self$cohortCharacterizations <- OhdsiAtlasClientAnalyses$new(
        self, "/cohort-characterization", copyMethod = "post",
        importPath = "/import", exportPath = "/{id}/export",
        generateMethod = "post", generatePath = "/{id}/generation/{sourceKey}",
        cancelMethod = "delete", generationPath = "/{id}/generation",
        versions = TRUE, tags = TRUE
      )
      self$featureAnalyses <- OhdsiAtlasClientFeatureAnalyses$new(self)
      self$incidenceRates <- OhdsiAtlasClientIncidenceRates$new(self)
      self$pathways <- OhdsiAtlasClientAnalyses$new(
        self, "/pathway-analysis", copyMethod = "post",
        importPath = "/import", exportPath = "/{id}/export",
        generateMethod = "post", generatePath = "/{id}/generation/{sourceKey}",
        cancelMethod = "delete", generationPath = "/{id}/generation",
        versions = TRUE, tags = TRUE
      )
      self$reusable <- OhdsiAtlasClientAnalyses$new(
        self, "/reusable", copyMethod = "post", importPath = "",
        exportPath = "/{id}", generateMethod = NULL, versions = TRUE,
        tags = TRUE
      )
      self$tags <- OhdsiAtlasClientTags$new(self)
      self$auth <- OhdsiAtlasClientAuth$new(self)
      self$tools <- OhdsiAtlasClientTools$new(self)
      self$notifications <- OhdsiAtlasClientNotifications$new(self)
      self$cache <- OhdsiAtlasClientCache$new(self)
      self$sqlrender <- OhdsiAtlasClientSqlRender$new(self)
      self$ddl <- OhdsiAtlasClientDdl$new(self)
      self$evidence <- OhdsiAtlasClientEvidence$new(self)
      self$statistic <- OhdsiAtlasClientStatistic$new(self)
      invisible(self)
    },

    login = function(apiKey, store = TRUE) {
      checkmate::assertString(apiKey, min.chars = 1)
      previous <- self$apiKey
      self$apiKey <- apiKey
      private$currentUser <- NULL
      tryCatch(
        self$whoami(force = TRUE),
        error = function(error) {
          self$apiKey <- previous
          private$currentUser <- NULL
          stop(error)
        }
      )
      identifier <- ohdsiAtlasClientKeyIdentifier(apiKey)
      private$credential <- list(
        apiKey = apiKey,
        apiUrl = self$apiUrl,
        keyIdentifier = identifier,
        createdAt = ohdsiAtlasClientNowIso()
      )
      if (isTRUE(store)) {
        private$credentialStore$set(self$apiUrl, apiKey, keyIdentifier = identifier)
      }
      invisible(self)
    },

    logout = function(revoke = TRUE) {
      identifier <- private$credential$keyIdentifier %||% ohdsiAtlasClientKeyIdentifier(self$apiKey)
      if (isTRUE(revoke) && !is.null(identifier)) {
        tryCatch(
          self$auth$revokeApiKey(identifier, remove = TRUE),
          error = function(e) NULL
        )
      }
      private$credentialStore$delete(self$apiUrl)
      private$credential <- NULL
      private$currentUser <- NULL
      self$apiKey <- NULL
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
                       headers = NULL, raw = FALSE, timeout = NULL) {
      ohdsiAtlasClientRequest(
        self, method, path,
        query = query, body = body, form = form, headers = headers,
        raw = raw, timeout = timeout
      )
    },

    call = function(operationId, ...) {
      ohdsiAtlasClientCallEndpoint(self, operationId, ...)
    },

    endpoints = function(group = NULL, method = NULL, pathContains = NULL) {
      ohdsiAtlasClientEndpoints(self, group = group, method = method, pathContains = pathContains)
    },

    close = function() {
      invisible(self)
    },

    print = function(...) {
      user <- tryCatch(self$whoami()$user$login, error = function(e) "unknown")
      cat("<OhdsiAtlasClient client>\n")
      cat("  WebAPI: ", self$apiUrl, "\n", sep = "")
      cat("  Version:", self$version, "\n", sep = " ")
      cat("  User:   ", user, "\n", sep = "")
      cat("  Key:    ", ohdsiAtlasClientRedactKey(self$apiKey), "\n", sep = "")
      invisible(self)
    }
  ),
  private = list(
    credentialStore = NULL,
    credential = NULL,
    currentUser = NULL
  )
)

#' Extract a concept ID from an expression item
#'
#' Concept IDs appear as `concept$conceptId` in Circe expressions and in
#' WebAPI concept objects, but inline expressions copied from older tooling
#' sometimes carry the database column name `CONCEPT_ID`. Accept either.
#'
#' @param item One concept set expression item.
#' @return An integer concept ID, or `NULL` when none is present.
#' @noRd
ohdsiAtlasClientConceptId <- function(item) {
  concept <- item$concept
  if (is.list(concept)) {
    for (field in c("conceptId", "CONCEPT_ID", "concept_id")) {
      if (!is.null(concept[[field]])) {
        return(as.integer(concept[[field]]))
      }
    }
  } else if (length(concept) == 1 && !is.na(concept)) {
    return(as.integer(concept))
  }
  for (field in c("conceptId", "CONCEPT_ID", "concept_id")) {
    if (!is.null(item[[field]])) {
      return(as.integer(item[[field]]))
    }
  }
  NULL
}

#' Connect to an ATLAS 3.0 deployment
#'
#' Discovers the WebAPI root, checks that the server is ATLAS/WebAPI 3.0 or
#' newer, and returns an [OhdsiAtlasClient] client. Supply an `apiKey` to skip credential
#' lookup, or call `$login(apiKey)` afterwards to validate and store one.
#'
#' @param url ATLAS UI URL, WebAPI URL, or bare host name.
#' @param apiKey Personal API key. If omitted, `OHDSI_ATLAS_CLIENT_API_KEY` or a stored key
#'   is used.
#' @param profile Credential-store profile name.
#' @param timeout Request timeout in seconds.
#' @param discovery Optional pre-built discovery result (used in tests).
#' @param credentialStore Optional credential store.
#' @param useKeyring Prefer the OS keyring when the `keyring` package is
#'   installed.
#' @return An OhdsiAtlasClient client object.
#' @export
#' @examples
#' \dontrun{
#' atlas <- connectAtlas(
#'   "https://atlas.example.org",
#'   apiKey = Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY")
#' )
#' atlas$sources$list()
#' }

connectAtlas <- function(url,
                         apiKey = NULL,
                         profile = "default",
                         timeout = 60,
                         discovery = NULL,
                         credentialStore = NULL,
                         useKeyring = TRUE) {
  OhdsiAtlasClient$new(
    url = url,
    apiKey = apiKey,
    profile = profile,
    timeout = timeout,
    discovery = discovery,
    credentialStore = credentialStore,
    useKeyring = useKeyring
  )
}
