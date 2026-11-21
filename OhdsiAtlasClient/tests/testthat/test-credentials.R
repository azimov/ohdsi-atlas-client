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

test_that("credentials round-trip through the file backend", {
  directory <- tempfile("ohdsi-atlas-client-creds-")
  store <- OhdsiAtlasClientCredentialStore$new(
    configDir = directory, useKeyring = FALSE
  )
  store$set("https://example.org/WebAPI", "wa_1234567890abcdef_secret")
  value <- store$get("https://example.org/WebAPI")
  expect_equal(value$apiKey, "wa_1234567890abcdef_secret")
  expect_equal(value$keyIdentifier, "1234567890abcdef")
  expect_true(file.exists(store$path))
  store$delete("https://example.org/WebAPI")
  expect_null(store$get("https://example.org/WebAPI"))
})

test_that("the client can be constructed without network access", {
  discovery <- list(
    inputUrl = "https://example.org/atlas",
    apiUrl = "https://example.org/WebAPI",
    atlasUrl = "https://example.org/atlas",
    version = "3.0.0",
    buildInfo = list(),
    configuration = list()
  )
  atlas <- connectAtlas(
    "https://example.org/atlas",
    apiKey = "wa_1234567890abcdef_secret",
    discovery = discovery,
    credentialStore = OhdsiAtlasClientCredentialStore$new(
      configDir = tempfile("ohdsi-atlas-client-creds-"), useKeyring = FALSE
    )
  )
  expect_equal(atlas$apiUrl, "https://example.org/WebAPI")
  expect_equal(atlas$version, "3.0.0")
  expect_equal(atlas$apiKey, "wa_1234567890abcdef_secret")
  expect_s3_class(atlas$cohorts, "OhdsiAtlasClientCohorts")
  expect_s3_class(atlas$cohortSets, "OhdsiAtlasClientCohortSets")
})
