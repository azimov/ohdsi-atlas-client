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

# Regression tests for the DDL resource.
#
# The DDL endpoints were originally called as `GET /ddl/cdm` with CDM-shaped
# parameters. WebAPI 3.0 has no such endpoint (404) and the three that exist
# take a results `schema`. They also return plain SQL text, so a request that
# only advertises `Accept: application/json` makes WebAPI return HTTP 500.

test_that("DDL methods target the real endpoints with the real parameters", {
  calls <- list()
  client <- list(
    request = function(method, path, query = list(), body = NULL, form = NULL,
                       headers = NULL, raw = FALSE, timeout = NULL) {
      calls[[length(calls) + 1L]] <<- list(
        method = method, path = path, query = query, headers = headers
      )
      "CREATE TABLE IF NOT EXISTS results.cohort (cohort_definition_id int);"
    }
  )
  ddl <- OhdsiAtlasClient:::OhdsiAtlasClientDdl$new(client)

  sql <- ddl$results(dialect = "postgresql", schema = "cdm_results", vocabSchema = "vocab")
  expect_true(grepl("CREATE TABLE", sql))
  expect_equal(calls[[1]]$method, "GET")
  expect_equal(calls[[1]]$path, "/ddl/results")
  expect_equal(calls[[1]]$query$schema, "cdm_results")
  expect_equal(calls[[1]]$query$vocabSchema, "vocab")
  expect_null(calls[[1]]$query$cdmSchema)
  expect_null(calls[[1]]$query$resultsSchema)
  expect_null(calls[[1]]$query$cdmVersion)

  ddl$achilles(dialect = "postgresql", schema = "results", vocabSchema = "vocab")
  expect_equal(calls[[2]]$path, "/ddl/achilles")
  expect_equal(calls[[2]]$query$schema, "results")
  expect_null(calls[[2]]$query$resultsSchema)

  ddl$cemResults(dialect = "postgresql", schema = "results")
  expect_equal(calls[[3]]$path, "/ddl/cemresults")
  expect_equal(calls[[3]]$query$schema, "results")

  # SQL endpoints must advertise that they accept text.
  for (call in calls) {
    expect_match(call$headers$Accept, "text/plain", fixed = TRUE)
  }
})

test_that("the DDL calls are all present in the endpoint catalog", {
  catalog <- OhdsiAtlasClient:::ohdsiAtlasClientCatalog()
  paths <- vapply(catalog$endpoints, function(endpoint) endpoint$path, character(1))
  expect_true("/ddl/results" %in% paths)
  expect_true("/ddl/achilles" %in% paths)
  expect_true("/ddl/cemresults" %in% paths)
  expect_false("/ddl/cdm" %in% paths)
})

test_that("the CDM DDL convenience method is gone", {
  client <- list(request = function(...) NULL)
  ddl <- OhdsiAtlasClient:::OhdsiAtlasClientDdl$new(client)
  expect_false("cdm" %in% names(ddl))
  expect_true(all(c("results", "achilles", "cemResults") %in% names(ddl)))
})
