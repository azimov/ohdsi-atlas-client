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

atlas3PageContent <- function(value) {
  if (is.list(value) && !is.null(value$content)) {
    return(value$content)
  }
  if (is.null(value)) list() else value
}

atlas3Body <- function(value) {
  # Drop NULLs so WebAPI receives the same shape as the Python client.
  if (!is.list(value)) {
    return(value)
  }
  value[!vapply(value, is.null, logical(1))]
}

# Sources ------------------------------------------------------------------

#' @keywords internal
Atlas3Sources <- R6::R6Class(
  "Atlas3Sources",
  public = list(
    initialize = function(client) private$client <- client,
    list = function() private$client$request("GET", "/source/sources"),
    get = function(sourceKey) {
      private$client$request("GET", paste0("/source/", sourceKey))
    },
    priority = function() {
      private$client$request("GET", "/source/daimon/priority")
    },
    priorityVocabulary = function() {
      private$client$request("GET", "/source/priorityVocabulary")
    },
    details = function(sourceId) {
      private$client$request("GET", paste0("/source/details/", sourceId))
    },
    checkConnection = function(sourceKey) {
      private$client$request("GET", paste0("/source/connection/", sourceKey))
    },
    refresh = function() private$client$request("GET", "/source/refresh"),
    setPriority = function(sourceKey, daimonType) {
      private$client$request(
        "POST",
        paste0("/source/", sourceKey, "/daimons/", daimonType, "/set-priority")
      )
    }
  ),
  private = list(client = NULL)
)

# Vocabulary ---------------------------------------------------------------

#' @keywords internal
Atlas3Concepts <- R6::R6Class(
  "Atlas3Concepts",
  public = list(
    initialize = function(client) private$client <- client,

    search = function(sourceKey,
                      query,
                      rows = 100,
                      domain = NULL,
                      vocabulary = NULL,
                      conceptClass = NULL,
                      standardConcept = NULL,
                      invalidReason = NULL,
                      lexical = FALSE) {
      checkmate::assertString(sourceKey, min.chars = 1)
      checkmate::assertString(query, min.chars = 1)
      filters <- !is.null(domain) || !is.null(vocabulary) || !is.null(conceptClass) ||
        !is.null(standardConcept) || !is.null(invalidReason) || isTRUE(lexical)
      if (!filters) {
        value <- private$client$request(
          "GET",
          paste0("/vocabulary/", sourceKey, "/search"),
          query = list(query = query, rows = rows)
        )
      } else {
        body <- list(
          QUERY = query,
          IS_LEXICAL = isTRUE(lexical)
        )
        if (!is.null(domain)) body$DOMAIN_ID <- as.list(domain)
        if (!is.null(vocabulary)) body$VOCABULARY_ID <- as.list(vocabulary)
        if (!is.null(conceptClass)) body$CONCEPT_CLASS_ID <- as.list(conceptClass)
        if (!is.null(standardConcept)) body$STANDARD_CONCEPT <- standardConcept
        if (!is.null(invalidReason)) body$INVALID_REASON <- invalidReason
        value <- private$client$request(
          "POST",
          paste0("/vocabulary/", sourceKey, "/search"),
          body = body
        )
      }
      # WebAPI ignores row limits on these endpoints.
      utils::head(value %||% list(), rows)
    },

    get = function(sourceKey, conceptId) {
      private$client$request(
        "GET",
        paste0("/vocabulary/", sourceKey, "/concept/", conceptId)
      )
    },

    getMany = function(sourceKey, conceptIds) {
      ids <- as.integer(conceptIds)
      if (length(ids) == 0) {
        return(list())
      }
      private$client$request(
        "POST",
        paste0("/vocabulary/", sourceKey, "/lookup/identifiers"),
        body = I(ids)
      )
    },

    related = function(sourceKey, conceptId) {
      private$client$request(
        "GET",
        paste0("/vocabulary/", sourceKey, "/concept/", conceptId, "/related")
      )
    },

    descendants = function(sourceKey, conceptId) {
      private$client$request(
        "GET",
        paste0("/vocabulary/", sourceKey, "/concept/", conceptId, "/descendants")
      )
    },

    ancestorsDescendants = function(sourceKey, conceptId) {
      private$client$request(
        "GET",
        paste0(
          "/vocabulary/", sourceKey, "/concept/", conceptId,
          "/ancestorAndDescendant"
        )
      )
    },

    commonAncestors = function(sourceKey, conceptIds) {
      private$client$request(
        "POST",
        paste0("/vocabulary/", sourceKey, "/commonAncestors"),
        body = I(as.integer(conceptIds))
      )
    },

    recommended = function(sourceKey, conceptIds) {
      private$client$request(
        "POST",
        paste0("/vocabulary/", sourceKey, "/lookup/recommended"),
        body = I(as.integer(conceptIds))
      )
    },

    domains = function(sourceKey) {
      private$client$request("GET", paste0("/vocabulary/", sourceKey, "/domains"))
    },

    vocabularies = function(sourceKey) {
      private$client$request("GET", paste0("/vocabulary/", sourceKey, "/vocabularies"))
    },

    info = function(sourceKey) {
      private$client$request("GET", paste0("/vocabulary/", sourceKey, "/info"))
    },

    resolve = function(sourceKey, expression) {
      private$client$request(
        "POST",
        paste0("/vocabulary/", sourceKey, "/resolveConceptSetExpression"),
        body = expression
      )
    },

    countIncluded = function(sourceKey, expression) {
      private$client$request(
        "POST",
        paste0("/vocabulary/", sourceKey, "/included-concepts/count"),
        body = expression
      )
    },

    expressionSql = function(expression) {
      private$client$request(
        "POST",
        "/vocabulary/conceptSetExpressionSQL",
        body = expression
      )
    },

    counts = function(sourceKey, conceptIds) {
      private$client$cdmResults$conceptCounts(sourceKey, conceptIds)
    }
  ),
  private = list(client = NULL)
)

# Concept sets -------------------------------------------------------------

#' @keywords internal
Atlas3ConceptSets <- R6::R6Class(
  "Atlas3ConceptSets",
  public = list(
    initialize = function(client) private$client <- client,

    list = function() private$client$request("GET", "/conceptset"),

    get = function(conceptSetId) {
      private$client$request("GET", paste0("/conceptset/", conceptSetId))
    },

    expression = function(conceptSetId, sourceKey = NULL) {
      path <- paste0("/conceptset/", conceptSetId, "/expression")
      if (!is.null(sourceKey)) {
        path <- paste0(path, "/", sourceKey)
      }
      private$client$request("GET", path)
    },

    items = function(conceptSetId) {
      private$client$request("GET", paste0("/conceptset/", conceptSetId, "/items"))
    },

    create = function(name, expression, description = NULL) {
      header <- private$client$request(
        "POST", "/conceptset",
        body = list(name = name, description = description)
      )
      id <- header$id
      if (is.null(id)) {
        abort("WebAPI did not return a concept set ID")
      }
      expression <- private$expressionPayload(expression)
      if (length(expression$items) > 0) {
        private$client$request(
          "PUT",
          paste0("/conceptset/", id, "/items"),
          body = private$itemRows(id, expression)
        )
      }
      header$expression <- expression
      header
    },

    createFromConcepts = function(name,
                                  conceptIds,
                                  sourceKey,
                                  description = NULL,
                                  includeDescendants = FALSE,
                                  includeMapped = FALSE,
                                  exclude = FALSE) {
      ids <- as.integer(conceptIds)
      concepts <- private$client$concepts$getMany(sourceKey, ids)
      if (length(concepts) != length(ids)) {
        missing <- setdiff(ids, vapply(concepts, function(x) as.integer(x$CONCEPT_ID), integer(1)))
        abort(paste0("Concepts not found in source ", sourceKey, ": ",
          paste(missing, collapse = ", ")))
      }
      items <- lapply(concepts, function(concept) {
        list(
          concept = concept,
          isExcluded = isTRUE(exclude),
          includeDescendants = isTRUE(includeDescendants),
          includeMapped = isTRUE(includeMapped)
        )
      })
      self$create(name, list(items = items), description = description)
    },

    update = function(conceptSetId,
                      name = NULL,
                      description = NULL,
                      expression = NULL) {
      if (is.null(name) && is.null(description) && is.null(expression)) {
        abort("Supply at least one of name, description, or expression")
      }
      current <- self$get(conceptSetId)
      body <- list(
        id = conceptSetId,
        name = name %||% current$name,
        description = description %||% current$description
      )
      result <- private$client$request(
        "PUT",
        paste0("/conceptset/", conceptSetId),
        body = body
      )
      expression <- if (is.null(expression)) {
        self$expression(conceptSetId)
      } else {
        private$expressionPayload(expression)
      }
      if (!is.null(expression)) {
        private$client$request(
          "PUT",
          paste0("/conceptset/", conceptSetId, "/items"),
          body = private$itemRows(conceptSetId, expression)
        )
      }
      result$expression <- expression
      result
    },

    delete = function(conceptSetId) {
      private$client$request("DELETE", paste0("/conceptset/", conceptSetId))
    },

    copy = function(conceptSetId) {
      suggestion <- private$client$request(
        "GET", paste0("/conceptset/", conceptSetId, "/copy-name")
      )
      source <- self$get(conceptSetId)
      name <- suggestion$copyName %||% paste0(source$name, " copy")
      self$create(name, self$expression(conceptSetId))
    },

    exists = function(name, conceptSetId = 0) {
      private$client$request(
        "GET",
        paste0("/conceptset/", conceptSetId, "/exists"),
        query = list(name = name)
      )
    },

    check = function(conceptSet) {
      private$client$request("POST", "/conceptset/check", body = conceptSet)
    },

    resolve = function(conceptSetId, sourceKey) {
      private$client$concepts$resolve(sourceKey, self$expression(conceptSetId, sourceKey))
    },

    countIncluded = function(conceptSetId, sourceKey) {
      private$client$concepts$countIncluded(
        sourceKey, self$expression(conceptSetId, sourceKey)
      )
    },

    exportZip = function(conceptSetId, path) {
      bytes <- private$client$request(
        "GET", paste0("/conceptset/", conceptSetId, "/export"), raw = TRUE
      )
      writeBin(bytes, path)
      path
    },

    versions = function(conceptSetId) {
      private$client$request("GET", paste0("/conceptset/", conceptSetId, "/version"))
    },

    version = function(conceptSetId, version) {
      private$client$request(
        "GET", paste0("/conceptset/", conceptSetId, "/version/", version)
      )
    },

    deleteVersion = function(conceptSetId, version) {
      private$client$request(
        "DELETE", paste0("/conceptset/", conceptSetId, "/version/", version)
      )
    },

    byTags = function(tags) {
      private$client$request("POST", "/conceptset/byTags", body = list(tags = as.list(tags)))
    },

    assignTag = function(conceptSetId, tagId) {
      private$client$request(
        "POST", paste0("/conceptset/", conceptSetId, "/tag"), body = as.integer(tagId)
      )
    },

    unassignTag = function(conceptSetId, tagId) {
      private$client$request(
        "DELETE", paste0("/conceptset/", conceptSetId, "/tag/", tagId)
      )
    }
  ),
  private = list(
    client = NULL,
    expressionPayload = function(expression) {
      if (is.character(expression) && length(expression) == 1) {
        expression <- jsonlite::fromJSON(expression, simplifyVector = FALSE)
      }
      if (is.list(expression) && is.null(expression$items) && !is.null(expression$expression)) {
        expression <- expression$expression
      }
      if (!is.list(expression)) {
        abort("A concept set expression must be an object")
      }
      expression$items <- expression$items %||% list()
      if (!is.list(expression$items)) {
        abort("Concept set expression 'items' must be a list")
      }
      expression
    },
    itemRows = function(conceptSetId, expression) {
      lapply(expression$items, function(item) {
        concept <- item$concept %||% list()
        conceptId <- concept$CONCEPT_ID %||% item$conceptId
        if (is.null(conceptId)) {
          abort("A concept set item is missing concept/conceptId")
        }
        list(
          id = 0L,
          conceptSetId = as.integer(conceptSetId),
          conceptId = as.integer(conceptId),
          isExcluded = as.integer(isTRUE(item$isExcluded)),
          includeDescendants = as.integer(isTRUE(item$includeDescendants)),
          includeMapped = as.integer(isTRUE(item$includeMapped))
        )
      })
    }
  )
)

# Cohort definitions -------------------------------------------------------

#' @keywords internal
Atlas3Cohorts <- R6::R6Class(
  "Atlas3Cohorts",
  public = list(
    initialize = function(client) private$client <- client,

    list = function() private$client$request("GET", "/cohortdefinition"),

    get = function(cohortId) {
      private$parseCohort(
        private$client$request("GET", paste0("/cohortdefinition/", cohortId))
      )
    },

    raw = function(cohortId) {
      private$client$request("GET", paste0("/cohortdefinition/", cohortId))
    },

    expression = function(cohortId) self$get(cohortId)$expression,

    create = function(name, expression, description = NULL,
                      expressionType = "SIMPLE_EXPRESSION") {
      private$parseCohort(private$client$request(
        "POST", "/cohortdefinition",
        body = list(
          name = name,
          description = description,
          expression = expression,
          expressionType = expressionType
        )
      ))
    },

    update = function(cohortId, name = NULL, description = NULL,
                      expression = NULL, expressionType = NULL) {
      if (is.null(name) && is.null(description) && is.null(expression) &&
        is.null(expressionType)) {
        abort("Supply at least one field to update")
      }
      current <- self$get(cohortId)
      private$parseCohort(private$client$request(
        "PUT", paste0("/cohortdefinition/", cohortId),
        body = list(
          id = cohortId,
          name = name %||% current$name,
          description = description %||% current$description,
          expression = expression %||% current$expression,
          expressionType = expressionType %||% current$expressionType %||% "SIMPLE_EXPRESSION"
        )
      ))
    },

    delete = function(cohortId) {
      private$client$request("DELETE", paste0("/cohortdefinition/", cohortId))
    },

    copy = function(cohortId) {
      private$parseCohort(
        private$client$request("GET", paste0("/cohortdefinition/", cohortId, "/copy"))
      )
    },

    exists = function(name, cohortId = 0) {
      private$client$request(
        "GET", paste0("/cohortdefinition/", cohortId, "/exists"),
        query = list(name = name)
      )
    },

    sql = function(expression, options = NULL) {
      body <- list(expression = expression)
      if (!is.null(options)) body$options <- options
      result <- private$client$request("POST", "/cohortdefinition/sql", body = body)
      result$templateSql %||% result
    },

    check = function(expression, v2 = FALSE) {
      path <- if (isTRUE(v2)) "/cohortdefinition/checkV2" else "/cohortdefinition/check"
      private$client$request("POST", path, body = expression)
    },

    generate = function(cohortId, sourceKey, demographic = FALSE) {
      private$client$request(
        "GET",
        paste0("/cohortdefinition/", cohortId, "/generate/", sourceKey),
        query = list(demographic = isTRUE(demographic))
      )
    },

    cancel = function(cohortId, sourceKey) {
      private$client$request(
        "GET", paste0("/cohortdefinition/", cohortId, "/cancel/", sourceKey)
      )
    },

    generationInfo = function(cohortId) {
      private$client$request("GET", paste0("/cohortdefinition/", cohortId, "/info"))
    },

    inclusionReport = function(cohortId, sourceKey, mode = 0) {
      private$client$request(
        "GET",
        paste0("/cohortdefinition/", cohortId, "/report/", sourceKey, "/inclusion"),
        query = list(mode = mode)
      )
    },

    demographicsReport = function(cohortId, sourceKey, ccGenerateId = NULL) {
      private$client$request(
        "GET",
        paste0("/cohortdefinition/", cohortId, "/report/", sourceKey, "/demographics"),
        query = list(ccGenerateId = ccGenerateId)
      )
    },

    exportConceptSetsZip = function(cohortId, path) {
      bytes <- private$client$request(
        "GET",
        paste0("/cohortdefinition/", cohortId, "/export/conceptset"),
        raw = TRUE
      )
      writeBin(bytes, path)
      path
    },

    printFriendly = function(expression) {
      private$client$request(
        "POST", "/cohortdefinition/printfriendly/cohort", body = expression
      )
    },

    versions = function(cohortId) {
      private$client$request("GET", paste0("/cohortdefinition/", cohortId, "/version"))
    },

    version = function(cohortId, version) {
      private$client$request(
        "GET", paste0("/cohortdefinition/", cohortId, "/version/", version)
      )
    },

    deleteVersion = function(cohortId, version) {
      private$client$request(
        "DELETE", paste0("/cohortdefinition/", cohortId, "/version/", version)
      )
    },

    byTags = function(tags) {
      private$client$request(
        "POST", "/cohortdefinition/byTags", body = list(tags = as.list(tags))
      )
    },

    assignTag = function(cohortId, tagId) {
      private$client$request(
        "POST", paste0("/cohortdefinition/", cohortId, "/tag"), body = as.integer(tagId)
      )
    },

    unassignTag = function(cohortId, tagId) {
      private$client$request(
        "DELETE", paste0("/cohortdefinition/", cohortId, "/tag/", tagId)
      )
    }
  ),
  private = list(
    client = NULL,
    parseCohort = function(value) {
      if (is.character(value$expression) && length(value$expression) == 1) {
        value$rawExpression <- value$expression
        value$expression <- jsonlite::fromJSON(value$expression, simplifyVector = FALSE)
      }
      value
    }
  )
)

# CDM results --------------------------------------------------------------

#' @keywords internal
Atlas3CdmResults <- R6::R6Class(
  "Atlas3CdmResults",
  public = list(
    initialize = function(client) private$client <- client,

    conceptCounts = function(sourceKey, conceptIds, batchSize = 500) {
      ids <- unique(as.integer(conceptIds))
      if (length(ids) == 0) {
        return(list())
      }
      batches <- atlas3Chunk(ids, batchSize)
      result <- list()
      for (batch in batches) {
        value <- private$client$request(
          "POST",
          paste0("/cdmresults/", sourceKey, "/conceptRecordCount"),
          body = I(as.integer(batch))
        )
        for (entry in value %||% list()) {
          for (name in names(entry)) {
            values <- as.integer(entry[[name]])
            result[[length(result) + 1L]] <- structure(
              list(
                conceptId = as.integer(name),
                values = values,
                recordCount = if (length(values) >= 1) values[[1]] else NULL,
                descendantRecordCount = if (length(values) >= 2) values[[2]] else NULL,
                personCount = if (length(values) >= 3) values[[3]] else NULL,
                descendantPersonCount = if (length(values) >= 4) values[[4]] else NULL
              ),
              class = c("atlas3_concept_count", "list")
            )
          }
        }
      }
      result
    },

    conceptCountsMap = function(sourceKey, conceptIds, batchSize = 500) {
      values <- self$conceptCounts(sourceKey, conceptIds, batchSize)
      names(values) <- vapply(values, function(x) as.character(x$conceptId), character(1))
      values
    },

    dashboard = function(sourceKey) {
      private$client$request("GET", paste0("/cdmresults/", sourceKey, "/dashboard"))
    },

    person = function(sourceKey) {
      private$client$request("GET", paste0("/cdmresults/", sourceKey, "/person"))
    },

    warmCache = function(sourceKey) {
      private$client$request("GET", paste0("/cdmresults/", sourceKey, "/warmCache"))
    },

    refreshCache = function(sourceKey) {
      private$client$request("GET", paste0("/cdmresults/", sourceKey, "/refreshCache"))
    },

    clearCache = function(sourceKey) {
      private$client$request("POST", paste0("/cdmresults/", sourceKey, "/clearCache"))
    }
  ),
  private = list(client = NULL)
)

# Cohort definition sets ---------------------------------------------------

#' @keywords internal
Atlas3CohortSets <- R6::R6Class(
  "Atlas3CohortSets",
  public = list(
    initialize = function(client) private$client <- client,

    export = function(cohortIds = NULL, path = NULL, includeConceptSets = TRUE) {
      if (is.null(cohortIds)) {
        cohortIds <- vapply(
          private$client$cohorts$list(),
          function(cohort) as.integer(cohort$id),
          integer(1)
        )
      }
      cohortIds <- unique(as.integer(cohortIds))
      if (length(cohortIds) == 0) {
        abort("No cohorts selected for export", class = "atlas3_bundle_error")
      }
      payloads <- lapply(cohortIds, private$client$cohorts$raw)
      bundle <- atlas3BundleFromCohorts(
        payloads,
        atlas = list(
          url = private$client$url,
          apiUrl = private$client$apiUrl,
          webApiVersion = private$client$version
        )
      )
      if (!isTRUE(includeConceptSets)) {
        bundle$conceptSets <- list()
      }
      bundle <- atlas3BundleWithIntegrity(bundle)
      if (!is.null(path)) {
        atlas3BundleSave(bundle, path)
      }
      bundle
    },

    import = function(bundle, onConflict = "rename", dryRun = FALSE) {
      if (!onConflict %in% c("error", "skip", "rename", "update")) {
        abort("onConflict must be one of 'error', 'skip', 'rename', 'update'")
      }
      if (is.character(bundle) && length(bundle) == 1) {
        bundle <- atlas3BundleLoad(bundle)
      }
      atlas3BundleValidate(bundle)
      result <- structure(
        list(
          createdCohorts = list(),
          updatedCohorts = list(),
          skippedCohorts = list(),
          createdConceptSets = list(),
          updatedConceptSets = list(),
          skippedConceptSets = list(),
          conceptSetMap = list(),
          warnings = character(),
          dryRun = isTRUE(dryRun)
        ),
        class = c("atlas3_import_result", "list")
      )

      existingConceptSets <- private$namedById(private$client$conceptSets$list())
      takenConceptSetNames <- names(existingConceptSets)
      for (conceptEntry in bundle$conceptSets %||% list()) {
        existing <- existingConceptSets[[conceptEntry$name]]
        if (!is.null(existing)) {
          if (identical(onConflict, "error")) {
            abort(
              paste0("Concept set '", conceptEntry$name, "' already exists"),
              class = "atlas3_conflict_error"
            )
          }
          if (identical(onConflict, "skip")) {
            result$skippedConceptSets[[length(result$skippedConceptSets) + 1L]] <-
              list(name = conceptEntry$name, id = existing$id)
            result$conceptSetMap[[conceptEntry$name]] <- as.integer(existing$id)
            next
          }
          if (identical(onConflict, "update")) {
            if (isTRUE(dryRun)) {
              result$updatedConceptSets[[length(result$updatedConceptSets) + 1L]] <-
                list(name = conceptEntry$name, id = existing$id, dryRun = TRUE)
            } else {
              updated <- private$client$conceptSets$update(
                as.integer(existing$id),
                description = conceptEntry$description,
                expression = conceptEntry$expression
              )
              result$updatedConceptSets[[length(result$updatedConceptSets) + 1L]] <-
                list(name = conceptEntry$name, id = updated$id)
            }
            result$conceptSetMap[[conceptEntry$name]] <- as.integer(existing$id)
            next
          }
          newName <- atlas3UniqueName(conceptEntry$name, takenConceptSetNames)
          takenConceptSetNames <- c(takenConceptSetNames, newName)
          if (isTRUE(dryRun)) {
            result$createdConceptSets[[length(result$createdConceptSets) + 1L]] <-
              list(name = newName, originalName = conceptEntry$name, dryRun = TRUE)
            result$conceptSetMap[[conceptEntry$name]] <- 0L
          } else {
            created <- private$client$conceptSets$create(
              newName, conceptEntry$expression,
              description = conceptEntry$description
            )
            result$createdConceptSets[[length(result$createdConceptSets) + 1L]] <-
              list(name = newName, originalName = conceptEntry$name, id = created$id)
            result$conceptSetMap[[conceptEntry$name]] <- as.integer(created$id)
          }
          next
        }
        takenConceptSetNames <- c(takenConceptSetNames, conceptEntry$name)
        if (isTRUE(dryRun)) {
          result$createdConceptSets[[length(result$createdConceptSets) + 1L]] <-
            list(name = conceptEntry$name, dryRun = TRUE)
          result$conceptSetMap[[conceptEntry$name]] <- 0L
        } else {
          created <- private$client$conceptSets$create(
            conceptEntry$name, conceptEntry$expression,
            description = conceptEntry$description
          )
          result$createdConceptSets[[length(result$createdConceptSets) + 1L]] <-
            list(name = conceptEntry$name, id = created$id)
          result$conceptSetMap[[conceptEntry$name]] <- as.integer(created$id)
        }
      }

      existingCohorts <- private$namedById(private$client$cohorts$list())
      takenCohortNames <- names(existingCohorts)
      for (cohortEntry in bundle$cohorts) {
        existing <- existingCohorts[[cohortEntry$name]]
        if (!is.null(existing)) {
          if (identical(onConflict, "error")) {
            abort(
              paste0("Cohort '", cohortEntry$name, "' already exists"),
              class = "atlas3_conflict_error"
            )
          }
          if (identical(onConflict, "skip")) {
            result$skippedCohorts[[length(result$skippedCohorts) + 1L]] <-
              list(name = cohortEntry$name, id = existing$id)
            next
          }
          if (identical(onConflict, "update")) {
            if (isTRUE(dryRun)) {
              result$updatedCohorts[[length(result$updatedCohorts) + 1L]] <-
                list(name = cohortEntry$name, id = existing$id, dryRun = TRUE)
            } else {
              updated <- private$client$cohorts$update(
                as.integer(existing$id),
                name = cohortEntry$name,
                description = cohortEntry$description,
                expression = cohortEntry$expression,
                expressionType = cohortEntry$expressionType
              )
              result$updatedCohorts[[length(result$updatedCohorts) + 1L]] <-
                list(name = cohortEntry$name, id = updated$id)
            }
            next
          }
          newName <- atlas3UniqueName(cohortEntry$name, takenCohortNames)
          takenCohortNames <- c(takenCohortNames, newName)
          if (isTRUE(dryRun)) {
            result$createdCohorts[[length(result$createdCohorts) + 1L]] <-
              list(name = newName, originalName = cohortEntry$name, dryRun = TRUE)
          } else {
            created <- private$client$cohorts$create(
              newName, cohortEntry$expression,
              description = cohortEntry$description,
              expressionType = cohortEntry$expressionType
            )
            result$createdCohorts[[length(result$createdCohorts) + 1L]] <-
              list(name = newName, originalName = cohortEntry$name, id = created$id)
          }
          next
        }
        takenCohortNames <- c(takenCohortNames, cohortEntry$name)
        if (isTRUE(dryRun)) {
          result$createdCohorts[[length(result$createdCohorts) + 1L]] <-
            list(name = cohortEntry$name, dryRun = TRUE)
        } else {
          created <- private$client$cohorts$create(
            cohortEntry$name, cohortEntry$expression,
            description = cohortEntry$description,
            expressionType = cohortEntry$expressionType
          )
          result$createdCohorts[[length(result$createdCohorts) + 1L]] <-
            list(name = cohortEntry$name, id = created$id)
        }
      }
      result
    },

    validate = function(bundle) {
      if (is.character(bundle) && length(bundle) == 1) {
        bundle <- atlas3BundleLoad(bundle)
      }
      atlas3BundleValidate(bundle)
      atlas3BundleSummary(bundle)
    }
  ),
  private = list(
    client = NULL,
    namedById = function(values) {
      result <- list()
      for (value in values %||% list()) {
        result[[value$name]] <- value
      }
      result
    }
  )
)

# Jobs ---------------------------------------------------------------------

#' @keywords internal
Atlas3Jobs <- R6::R6Class(
  "Atlas3Jobs",
  public = list(
    initialize = function(client) private$client <- client,

    list = function(jobName = NULL, page = NULL, size = NULL) {
      private$client$request(
        "GET", "/job/execution",
        query = list(jobName = jobName, page = page, size = size)
      )
    },

    get = function(jobId) {
      private$client$request("GET", paste0("/job/", jobId))
    },

    execution = function(executionId) {
      private$client$request("GET", paste0("/job/execution/", executionId))
    },

    wait = function(job, timeout = 600, pollInterval = 2, raiseOnFailure = TRUE) {
      executionId <- if (is.list(job)) job$executionId else as.integer(job)
      if (is.null(executionId) || length(executionId) == 0) {
        abort("Job has no executionId; cannot poll it")
      }
      deadline <- Sys.time() + timeout
      latest <- if (is.list(job)) job else self$execution(executionId)
      finished <- function(value) {
        toupper(value$status %||% "") %in% c("COMPLETED", "FAILED", "ABANDONED", "STOPPED")
      }
      while (!finished(latest)) {
        if (Sys.time() >= deadline) {
          abort(
            paste0(
              "Job execution ", executionId, " did not finish within ", timeout,
              " seconds (last status: ", latest$status %||% "unknown", ")"
            ),
            class = "atlas3_job_timeout"
          )
        }
        Sys.sleep(pollInterval)
        latest <- self$execution(executionId)
      }
      succeeded <- toupper(latest$status %||% "") == "COMPLETED" &&
        toupper(latest$exitStatus %||% "COMPLETED") == "COMPLETED"
      if (isTRUE(raiseOnFailure) && !succeeded) {
        abort(
          paste0(
            "Job execution ", executionId, " finished with status ",
            latest$status %||% "unknown", ": ", latest$failMessage %||% ""
          ),
          class = "atlas3_job_failed"
        )
      }
      latest
    }
  ),
  private = list(client = NULL)
)

# Analyses -----------------------------------------------------------------

#' @keywords internal
Atlas3Analyses <- R6::R6Class(
  "Atlas3Analyses",
  public = list(
    initialize = function(client,
                          path,
                          copyMethod = "get",
                          importPath = "/import",
                          exportPath = "/{id}/export",
                          generateMethod = "post",
                          generatePath = "/{id}/generation/{sourceKey}",
                          cancelMethod = "delete",
                          cancelPath = "/{id}/generation/{sourceKey}",
                          generationPath = "/{id}/generation",
                          versions = TRUE,
                          tags = TRUE,
                          tagParam = FALSE) {
      private$client <- client
      private$path <- path
      private$copyMethod <- copyMethod
      private$importPath <- importPath
      private$exportPath <- exportPath
      private$generateMethod <- generateMethod
      private$generatePath <- generatePath
      private$cancelMethod <- cancelMethod
      private$cancelPath <- cancelPath
      private$generationPath <- generationPath
      private$versionsEnabled <- versions
      private$tagsEnabled <- tags
      private$tagParam <- tagParam
    },

    list = function(page = NULL, size = NULL) {
      value <- private$client$request(
        "GET", private$path,
        query = list(page = page, size = size)
      )
      atlas3PageContent(value)
    },

    get = function(analysisId) {
      private$client$request("GET", paste0(private$path, "/", analysisId))
    },

    create = function(analysis) {
      private$client$request("POST", private$path, body = analysis)
    },

    update = function(analysisId, analysis) {
      private$client$request("PUT", paste0(private$path, "/", analysisId), body = analysis)
    },

    delete = function(analysisId) {
      private$client$request("DELETE", paste0(private$path, "/", analysisId))
    },

    copy = function(analysisId) {
      if (identical(private$copyMethod, "get")) {
        private$client$request("GET", paste0(private$path, "/", analysisId, "/copy"))
      } else {
        private$client$request("POST", paste0(private$path, "/", analysisId))
      }
    },

    exists = function(analysisId, name) {
      private$client$request(
        "GET", paste0(private$path, "/", analysisId, "/exists"),
        query = list(name = name)
      )
    },

    export = function(analysisId) {
      path <- private$formatPath(private$exportPath, analysisId)
      private$client$request("GET", paste0(private$path, path))
    },

    import = function(design) {
      if (!nzchar(private$importPath)) {
        abort("This resource has no import endpoint")
      }
      private$client$request(
        "POST", paste0(private$path, private$importPath), body = design
      )
    },

    check = function(analysis) {
      private$client$request("POST", paste0(private$path, "/check"), body = analysis)
    },

    generate = function(analysisId, sourceKey) {
      if (is.null(private$generateMethod)) {
        abort("This resource has no execution endpoint")
      }
      path <- private$formatPath(private$generatePath, analysisId, sourceKey)
      if (identical(private$generateMethod, "get")) {
        private$client$request("GET", paste0(private$path, path))
      } else {
        private$client$request("POST", paste0(private$path, path))
      }
    },

    cancel = function(analysisId, sourceKey) {
      path <- private$formatPath(private$cancelPath, analysisId, sourceKey)
      if (identical(private$cancelMethod, "get")) {
        private$client$request("GET", paste0(private$path, path))
      } else {
        private$client$request("DELETE", paste0(private$path, path))
      }
    },

    generations = function(analysisId) {
      private$client$request(
        "GET", paste0(private$path, private$formatPath(private$generationPath, analysisId))
      )
    },

    generation = function(generationId) {
      private$client$request(
        "GET", paste0(private$path, "/generation/", generationId)
      )
    },

    generationDesign = function(generationId) {
      private$client$request(
        "GET", paste0(private$path, "/generation/", generationId, "/design")
      )
    },

    generationResults = function(generationId) {
      private$client$request(
        "GET", paste0(private$path, "/generation/", generationId, "/result")
      )
    },

    versions = function(analysisId) {
      private$require(private$versionsEnabled, "versions")
      private$client$request("GET", paste0(private$path, "/", analysisId, "/version"))
    },

    version = function(analysisId, version) {
      private$require(private$versionsEnabled, "versions")
      private$client$request(
        "GET", paste0(private$path, "/", analysisId, "/version/", version)
      )
    },

    deleteVersion = function(analysisId, version) {
      private$require(private$versionsEnabled, "versions")
      private$client$request(
        "DELETE", paste0(private$path, "/", analysisId, "/version/", version)
      )
    },

    assignTag = function(analysisId, tagId) {
      private$require(private$tagsEnabled, "tags")
      if (isTRUE(private$tagParam)) {
        private$client$request(
          "POST", paste0(private$path, "/", analysisId, "/tag"),
          query = list(tagId = tagId)
        )
      } else {
        private$client$request(
          "POST", paste0(private$path, "/", analysisId, "/tag"),
          body = as.integer(tagId)
        )
      }
    },

    unassignTag = function(analysisId, tagId) {
      private$require(private$tagsEnabled, "tags")
      private$client$request(
        "DELETE", paste0(private$path, "/", analysisId, "/tag/", tagId)
      )
    },

    byTags = function(tags) {
      private$require(private$tagsEnabled, "tags")
      private$client$request(
        "POST", paste0(private$path, "/byTags"), body = list(tags = as.list(tags))
      )
    }
  ),
  private = list(
    client = NULL,
    path = NULL,
    copyMethod = "get",
    importPath = "/import",
    exportPath = "/{id}/export",
    generateMethod = "post",
    generatePath = "/{id}/generation/{sourceKey}",
    cancelMethod = "delete",
    cancelPath = "/{id}/generation/{sourceKey}",
    generationPath = "/{id}/generation",
    versionsEnabled = TRUE,
    tagsEnabled = TRUE,
    tagParam = FALSE,
    formatPath = function(template, analysisId, sourceKey = NULL) {
      path <- gsub("{id}", as.character(analysisId), template, fixed = TRUE)
      if (!is.null(sourceKey)) {
        path <- gsub("{sourceKey}", as.character(sourceKey), path, fixed = TRUE)
      }
      path
    },
    require = function(enabled, feature) {
      if (!isTRUE(enabled)) {
        abort(paste0("This resource does not support ", feature))
      }
    }
  )
)

#' @keywords internal
Atlas3FeatureAnalyses <- R6::R6Class(
  "Atlas3FeatureAnalyses",
  inherit = Atlas3Analyses,
  public = list(
    initialize = function(client) {
      super$initialize(
        client,
        path = "/feature-analysis",
        copyMethod = "get",
        importPath = "",
        exportPath = "/{id}/export/conceptset",
        generateMethod = NULL,
        versions = FALSE,
        tags = FALSE
      )
    },
    domains = function() {
      private$client$request("GET", "/feature-analysis/domains")
    },
    aggregates = function() {
      private$client$request("GET", "/feature-analysis/aggregates")
    },
    exportConceptSetsZip = function(analysisId, path) {
      bytes <- private$client$request(
        "GET", paste0("/feature-analysis/", analysisId, "/export/conceptset"),
        raw = TRUE
      )
      writeBin(bytes, path)
      path
    }
  )
)

#' @keywords internal
Atlas3IncidenceRates <- R6::R6Class(
  "Atlas3IncidenceRates",
  inherit = Atlas3Analyses,
  public = list(
    initialize = function(client) {
      super$initialize(
        client,
        path = "/ir",
        copyMethod = "get",
        importPath = "/design",
        exportPath = "/{id}/design",
        generateMethod = "get",
        generatePath = "/{id}/execute/{sourceKey}",
        cancelMethod = "delete",
        cancelPath = "/{id}/execute/{sourceKey}",
        generationPath = "/{id}/info",
        versions = TRUE,
        tags = TRUE,
        tagParam = TRUE
      )
    },
    info = function(analysisId, sourceKey = NULL) {
      path <- paste0("/ir/", analysisId, "/info")
      if (!is.null(sourceKey)) path <- paste0(path, "/", sourceKey)
      private$client$request("GET", path)
    },
    report = function(analysisId, sourceKey, targetId, outcomeId) {
      private$client$request(
        "GET", paste0("/ir/", analysisId, "/report/", sourceKey),
        query = list(targetId = targetId, outcomeId = outcomeId)
      )
    },
    exportZip = function(analysisId, path) {
      bytes <- private$client$request(
        "GET", paste0("/ir/", analysisId, "/export"), raw = TRUE
      )
      writeBin(bytes, path)
      path
    },
    sql = function(request) {
      result <- private$client$request("POST", "/ir/sql", body = request)
      result$templateSql %||% result
    }
  )
)

# Tags ---------------------------------------------------------------------

#' @keywords internal
Atlas3Tags <- R6::R6Class(
  "Atlas3Tags",
  public = list(
    initialize = function(client) private$client <- client,
    list = function() private$client$request("GET", "/tag"),
    get = function(tagId) private$client$request("GET", paste0("/tag/", tagId)),
    search = function(namePart) {
      private$client$request("GET", "/tag/search", query = list(namePart = namePart))
    },
    create = function(name, color = NULL, description = NULL) {
      private$client$request(
        "POST", "/tag",
        body = list(name = name, color = color, description = description)
      )
    },
    update = function(tagId, name = NULL, color = NULL, description = NULL) {
      current <- self$get(tagId)
      private$client$request(
        "PUT", paste0("/tag/", tagId),
        body = list(
          id = tagId,
          name = name %||% current$name,
          color = color %||% current$color,
          description = description %||% current$description
        )
      )
    },
    delete = function(tagId) private$client$request("DELETE", paste0("/tag/", tagId)),
    assignmentPermissions = function() {
      private$client$request("GET", "/tag/assignmentPermissions")
    },
    assignMany = function(assignment) {
      private$client$request("POST", "/tag/multiAssign", body = assignment)
    },
    unassignMany = function(assignment) {
      private$client$request("POST", "/tag/multiUnassign", body = assignment)
    }
  ),
  private = list(client = NULL)
)

# Authentication and users -------------------------------------------------

#' @keywords internal
Atlas3Auth <- R6::R6Class(
  "Atlas3Auth",
  public = list(
    initialize = function(client) private$client <- client,
    me = function() private$client$request("GET", "/user/me"),
    apiKeys = function() private$client$request("GET", "/user/apikeys"),
    createApiKey = function(name, description = NULL, expiresInDays = NULL) {
      private$client$request(
        "POST", "/user/apikeys",
        body = list(
          name = name, description = description, expiresInDays = expiresInDays
        )
      )
    },
    revokeApiKey = function(keyIdentifier, remove = FALSE) {
      private$client$request(
        "DELETE", paste0("/user/apikeys/", keyIdentifier),
        query = if (isTRUE(remove)) list(remove = "true") else list()
      )
    },
    users = function() private$client$request("GET", "/user"),
    userPermissions = function(userId) {
      private$client$request("GET", paste0("/user/", userId, "/permissions"))
    },
    userRoles = function(userId) {
      private$client$request("GET", paste0("/user/", userId, "/roles"))
    },
    roles = function(includePersonal = FALSE) {
      private$client$request(
        "GET", "/role", query = list(include_personal = isTRUE(includePersonal))
      )
    },
    permissions = function() private$client$request("GET", "/permission"),
    suggestRoles = function(search = NULL) {
      private$client$request(
        "GET", "/permission/access/suggest", query = list(roleSearch = search)
      )
    },
    grantEntityAccess = function(entityType, entityId, roleId, accessType = "READ") {
      private$client$request(
        "POST",
        paste0("/permission/access/", entityType, "/", entityId, "/role/", roleId),
        body = list(accessType = accessType)
      )
    },
    revokeEntityAccess = function(entityType, entityId, roleId) {
      private$client$request(
        "DELETE",
        paste0("/permission/access/", entityType, "/", entityId, "/role/", roleId)
      )
    },
    createRole = function(name) {
      private$client$request("POST", "/role", body = list(name = name))
    },
    deleteRole = function(roleId) {
      private$client$request("DELETE", paste0("/role/", roleId))
    }
  ),
  private = list(client = NULL)
)

# Smaller resources --------------------------------------------------------

#' @keywords internal
Atlas3Tools <- R6::R6Class(
  "Atlas3Tools",
  public = list(
    initialize = function(client) private$client <- client,
    list = function() private$client$request("GET", "/tool"),
    get = function(toolId) private$client$request("GET", paste0("/tool/", toolId)),
    create = function(tool) private$client$request("POST", "/tool", body = tool),
    update = function(tool) private$client$request("PUT", "/tool", body = tool),
    delete = function(toolId) private$client$request("DELETE", paste0("/tool/", toolId))
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3Notifications <- R6::R6Class(
  "Atlas3Notifications",
  public = list(
    initialize = function(client) private$client <- client,
    list = function(...) private$client$request("GET", "/notifications", query = list(...)),
    lastViewed = function() private$client$request("GET", "/notifications/viewed"),
    setViewed = function(stamp) {
      private$client$request("POST", "/notifications/viewed", body = stamp)
    }
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3Cache <- R6::R6Class(
  "Atlas3Cache",
  public = list(
    initialize = function(client) private$client <- client,
    info = function() private$client$request("GET", "/cache"),
    clear = function() private$client$request("GET", "/cache/clear")
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3SqlRender <- R6::R6Class(
  "Atlas3SqlRender",
  public = list(
    initialize = function(client) private$client <- client,
    translate = function(sql, targetDialect, parameters = list(), oracleTempSchema = NULL) {
      private$client$request(
        "POST", "/sqlrender/translate",
        body = list(
          SQL = sql,
          targetdialect = targetDialect,
          parameters = parameters,
          oracleTempSchema = oracleTempSchema
        )
      )
    }
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3Ddl <- R6::R6Class(
  "Atlas3Ddl",
  public = list(
    initialize = function(client) private$client <- client,
    cdm = function(dialect = NULL, cdmVersion = NULL, cdmSchema = NULL, resultsSchema = NULL) {
      private$client$request(
        "GET", "/ddl/cdm",
        query = list(
          dialect = dialect, cdmVersion = cdmVersion,
          cdmSchema = cdmSchema, resultsSchema = resultsSchema
        )
      )
    },
    achilles = function(dialect = NULL, cdmVersion = NULL, cdmSchema = NULL,
                        resultsSchema = NULL, vocabSchema = NULL) {
      private$client$request(
        "GET", "/ddl/achilles",
        query = list(
          dialect = dialect, cdmVersion = cdmVersion, cdmSchema = cdmSchema,
          resultsSchema = resultsSchema, vocabSchema = vocabSchema
        )
      )
    }
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3Evidence <- R6::R6Class(
  "Atlas3Evidence",
  public = list(
    initialize = function(client) private$client <- client,
    studyMapping = function(cohortId) {
      private$client$request("GET", paste0("/evidence/study/", cohortId))
    },
    conceptMapping = function(conceptId) {
      private$client$request("GET", paste0("/evidence/mapping/", conceptId))
    },
    evidence = function(sourceKey, conceptId) {
      private$client$request("GET", paste0("/evidence/", sourceKey, "/", conceptId))
    },
    info = function(sourceKey) {
      private$client$request("GET", paste0("/evidence/", sourceKey, "/info"))
    },
    label = function(setId) {
      private$client$request("GET", paste0("/evidence/label/", setId))
    },
    searchLabels = function(term) {
      private$client$request("GET", paste0("/evidence/labelsearch/", term))
    }
  ),
  private = list(client = NULL)
)

#' @keywords internal
Atlas3Statistic <- R6::R6Class(
  "Atlas3Statistic",
  public = list(
    initialize = function(client) private$client <- client,
    executions = function(request) {
      private$client$request("POST", "/statistic/executions", body = request)
    },
    accessTrends = function(request) {
      private$client$request("POST", "/statistic/accesstrends", body = request)
    }
  ),
  private = list(client = NULL)
)
