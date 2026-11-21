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

test_that("the endpoint catalog contains the full WebAPI surface", {
  catalog <- OhdsiAtlasClient:::ohdsiAtlasClientCatalog()
  expect_equal(catalog$endpointCount, 344)
  expect_equal(length(catalog$endpoints), 344)
  ids <- vapply(catalog$endpoints, function(endpoint) endpoint$operationId, character(1))
  expect_true("cohortdefinition.generateCohort" %in% ids)
  expect_true("cdmresults.getConceptRecordCount" %in% ids)
  expect_true("vocabulary.executeSearch.3" %in% ids)
})

test_that("call substitutes path and query parameters", {
  calls <- list()
  client <- list(
    request = function(method, path, query = list(), body = NULL, raw = FALSE, timeout = NULL) {
      calls[[length(calls) + 1L]] <<- list(
        method = method, path = path, query = query, body = body
      )
      list(ok = TRUE)
    }
  )
  ohdsiAtlasClientCallEndpoint(
    client, "cohortdefinition.generateCohort",
    id = 1, sourceKey = "EUNOMIA", demographic = FALSE
  )
  expect_equal(calls[[1]]$method, "GET")
  expect_equal(calls[[1]]$path, "/cohortdefinition/1/generate/EUNOMIA")
  expect_equal(calls[[1]]$query, list(demographic = FALSE))
})

test_that("unknown operations fail with a helpful class", {
  expect_error(ohdsiAtlasClientCallEndpoint(list(request = function(...) NULL), "nope"),
    class = "ohdsi_atlas_client_endpoint_error"
  )
})

test_that("a parameter named query is sent, not swallowed", {
  calls <- list()
  client <- list(
    request = function(method, path, query = list(), body = NULL, raw = FALSE, timeout = NULL) {
      calls[[length(calls) + 1L]] <<- list(path = path, query = query)
      NULL
    }
  )
  ohdsiAtlasClientCallEndpoint(
    client, "vocabulary.executeSearch.3",
    sourceKey = "EUNOMIA", query = "aspirin", rows = 5
  )
  expect_equal(calls[[1]]$path, "/vocabulary/EUNOMIA/search")
  expect_equal(calls[[1]]$query$query, "aspirin")
  expect_equal(calls[[1]]$query$rows, 5)
})

test_that("a list passed as query is an extra-query override", {
  calls <- list()
  client <- list(
    request = function(method, path, query = list(), body = NULL, raw = FALSE, timeout = NULL) {
      calls[[length(calls) + 1L]] <<- list(path = path, query = query)
      NULL
    }
  )
  ohdsiAtlasClientCallEndpoint(client, "cohortdefinition.getCohortDefinitionRaw", id = 1,
                     query = list(extra = 2))
  expect_equal(calls[[1]]$path, "/cohortdefinition/1")
  expect_equal(calls[[1]]$query$extra, 2)
})

test_that("unknown arguments are rejected", {
  client <- list(request = function(...) NULL)
  expect_error(
    ohdsiAtlasClientCallEndpoint(
      client, "cohortdefinition.getCohortDefinitionRaw",
      id = 1, bogus = 2
    ),
    class = "ohdsi_atlas_client_endpoint_error"
  )
})
