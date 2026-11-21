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

test_that("live ATLAS 3.0 workflows", {
  url <- Sys.getenv("OHDSI_ATLAS_CLIENT_TEST_URL", unset = "")
  skip_if(!nzchar(url), "OHDSI_ATLAS_CLIENT_TEST_URL is not set")
  skip_on_cran()

  apiKey <- Sys.getenv("OHDSI_ATLAS_CLIENT_TEST_API_KEY", unset = "")
  skip_if(!nzchar(apiKey), "OHDSI_ATLAS_CLIENT_TEST_API_KEY is not set")
  sourceKey <- Sys.getenv("OHDSI_ATLAS_CLIENT_TEST_SOURCE", unset = "EUNOMIA")
  store <- OhdsiAtlasClientCredentialStore$new(
    configDir = tempfile("ohdsi-atlas-client-live-"), useKeyring = FALSE
  )
  atlas <- connectAtlas(url, apiKey = apiKey, credentialStore = store, useKeyring = FALSE)
  atlas$login(apiKey, store = FALSE)
  expect_true(ohdsiAtlasClientVersionAtLeast(atlas$version))
  sources <- atlas$sources$list()
  expect_true(length(sources) >= 1)
  counts <- atlas$concepts$counts(sourceKey, c(1124300))
  expect_true(length(counts) >= 1)
  concepts <- atlas$concepts$search(sourceKey, "diclofenac", rows = 3)
  expect_true(length(concepts) <= 3)

  name <- paste0("ohdsi-atlas-client-r-test-", sample.int(1e8, 1))
  conceptSet <- atlas$conceptSets$createFromConcepts(
    name, c(1124300), sourceKey = sourceKey, includeDescendants = TRUE
  )
  on.exit(if (exists("conceptSet")) atlas$conceptSets$delete(conceptSet$id), add = TRUE)
  expression <- atlas$conceptSets$expression(conceptSet$id)
  expect_true(length(expression$items) == 1)

  cohortName <- paste0("ohdsi-atlas-client-r-cohort-", sample.int(1e8, 1))
  cohort <- atlas$cohorts$create(cohortName, atlas$cohorts$expression(1))
  on.exit(if (exists("cohort")) atlas$cohorts$delete(cohort$id), add = TRUE)
  expect_equal(atlas$cohorts$get(cohort$id)$name, cohortName)
  sql <- atlas$cohorts$sql(atlas$cohorts$expression(cohort$id))
  expect_true(grepl("CONCEPT", toupper(sql)))

  bundle <- atlas$cohortSets$export(1)
  expect_true(length(bundle$cohorts) >= 1)
  plan <- atlas$cohortSets$import(bundle, onConflict = "rename", dryRun = TRUE)
  expect_true(length(plan$createdCohorts) >= 1)

  # DDL endpoints return SQL text and need the text Accept header.
  resultsDdl <- atlas$ddl$results(dialect = "postgresql", schema = "results")
  expect_match(toupper(resultsDdl), "CREATE TABLE", fixed = TRUE)
  achillesDdl <- atlas$ddl$achilles(dialect = "postgresql", schema = "results")
  expect_match(toupper(achillesDdl), "CREATE TABLE", fixed = TRUE)

  # The documented concept-count alias agrees with the canonical method.
  canonical <- atlas$cdmResults$conceptCounts(sourceKey, c(1124300))
  alias <- atlas$concepts$counts(sourceKey, c(1124300))
  expect_equal(alias[[1]]$values, canonical[[1]]$values)
})
