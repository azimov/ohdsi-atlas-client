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

cohortPayload <- function(name = "Demo") {
  list(
    id = 1,
    name = name,
    description = "A demo",
    expressionType = "SIMPLE_EXPRESSION",
    expression = jsonlite::toJSON(list(
      ConceptSets = list(list(
        id = 0,
        name = "diclofenac",
        expression = list(items = list(list(
          concept = list(CONCEPT_ID = 1124300, CONCEPT_NAME = "Diclofenac"),
          isExcluded = FALSE,
          includeDescendants = TRUE,
          includeMapped = FALSE
        )))
      )),
      PrimaryCriteria = list(
        CriteriaList = list(list(DrugEra = list(CodesetId = 0))),
        ObservationWindow = list(PriorDays = 365, PostDays = 0),
        PrimaryCriteriaLimit = list(Type = "First")
      )
    ), auto_unbox = TRUE, null = "null")
  )
}

test_that("bundles collect cohorts and embedded concept sets", {
  bundle <- ohdsiAtlasClientBundleFromCohorts(
    list(cohortPayload()),
    atlas = list(url = "https://x")
  )
  expect_s3_class(bundle, "ohdsi_atlas_client_cohort_set_bundle")
  expect_equal(length(bundle$cohorts), 1)
  expect_equal(bundle$cohorts[[1]]$conceptSetIds, 0L)
  expect_equal(length(bundle$conceptSets), 1)
  expect_equal(bundle$conceptSets[[1]]$name, "diclofenac")
  expect_true(nzchar(bundle$integrity$digest))
})

test_that("duplicate embedded concept sets are deduplicated", {
  bundle <- ohdsiAtlasClientBundleFromCohorts(list(cohortPayload(), cohortPayload("Second")))
  expect_equal(length(bundle$conceptSets), 1)
})

test_that("bundles round-trip JSON, ZIP, and directories", {
  bundle <- ohdsiAtlasClientBundleFromCohorts(list(cohortPayload()))
  jsonPath <- tempfile(fileext = ".json")
  ohdsiAtlasClientBundleSave(bundle, jsonPath)
  loaded <- ohdsiAtlasClientBundleLoad(jsonPath)
  expect_equal(loaded$cohorts[[1]]$name, "Demo")
  expect_equal(loaded$integrity$digest, bundle$integrity$digest)

  zipPath <- tempfile(fileext = ".zip")
  ohdsiAtlasClientBundleSave(bundle, zipPath)
  expect_equal(ohdsiAtlasClientBundleLoad(zipPath)$cohorts[[1]]$name, "Demo")

  directory <- tempfile("bundle-")
  ohdsiAtlasClientBundleSave(bundle, directory)
  expect_true(file.exists(file.path(directory, "cohort-set.json")))
  expect_true(dir.exists(file.path(directory, "cohorts")))
  expect_equal(ohdsiAtlasClientBundleLoad(directory)$cohorts[[1]]$name, "Demo")
})

test_that("integrity tampering is detected", {
  bundle <- ohdsiAtlasClientBundleFromCohorts(list(cohortPayload()))
  bundle$cohorts[[1]]$name <- "Tampered"
  expect_error(ohdsiAtlasClientBundleValidate(bundle), "integrity")
})

test_that("duplicate cohort names are rejected", {
  bundle <- ohdsiAtlasClientBundleFromCohorts(list(cohortPayload(), cohortPayload()))
  expect_error(ohdsiAtlasClientBundleValidate(bundle), "Duplicate cohort names")
})
