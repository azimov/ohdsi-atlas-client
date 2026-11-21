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

test_that("a client reports its own state", {
  withFakeWebApi({
    atlas <- fakeClient()
    printed <- utils::capture.output(print(atlas))
    expect_true(any(grepl("OhdsiAtlasClient", printed)))
    expect_output(print(atlas$discovery), "WebAPI")
  })
})

test_that("login validates the key and stores it", {
  withFakeWebApi({
    store <- OhdsiAtlasClient:::OhdsiAtlasClientCredentialStore$new(
      configDir = tempfile("login-"),
      useKeyring = FALSE
    )
    atlas <- connectAtlas(
      "https://fake.example.org",
      useKeyring = FALSE,
      credentialStore = store
    )
    atlas$login("good-key")
    expect_equal(atlas$apiKey, "good-key")
    expect_equal(store$get(atlas$apiUrl)$apiKey, "good-key")

    # A rejected key must not be adopted.
    expect_error(atlas$login("bad-key"), class = "ohdsi_atlas_client_authentication_error")
    expect_equal(atlas$apiKey, "good-key")
  })
})

test_that("logout clears the key and optionally revokes it", {
  withFakeWebApi({
    store <- OhdsiAtlasClient:::OhdsiAtlasClientCredentialStore$new(
      configDir = tempfile("logout-"),
      useKeyring = FALSE
    )
    atlas <- connectAtlas(
      "https://fake.example.org",
      apiKey = "test-key",
      useKeyring = FALSE,
      credentialStore = store
    )
    atlas$login("test-key")
    atlas$logout(revoke = FALSE)
    expect_null(atlas$apiKey)
    expect_null(store$get(atlas$apiUrl)$apiKey)
  })
})

test_that("permissions are queryable", {
  withFakeWebApi({
    atlas <- fakeClient()
    expect_true(atlas$hasPermission("admin:security"))
    expect_false(atlas$hasPermission("admin:nonexistent"))
    expect_true(length(atlas$permissions()) >= 1)
  })
})

test_that("HTTP errors map to typed conditions", {
  withFakeWebApi({
    atlas <- fakeClient()
    expect_error(atlas$request("GET", "/forbidden"), class = "ohdsi_atlas_client_permission_error")
    expect_error(atlas$request("GET", "/missing"), class = "ohdsi_atlas_client_not_found_error")
    expect_error(atlas$request("GET", "/broken"), class = "ohdsi_atlas_client_server_error")
  })
})

test_that("an unreachable server raises a connection error", {
  # The real transport is restored here; nothing listens on port 9.
  expect_error(
    connectAtlas("http://127.0.0.1:9/WebAPI", useKeyring = FALSE),
    "Could not discover"
  )
})

test_that("discovery rejects pre-3.0 servers", {
  withFakeWebApi({
    fakeWebApi$register("/info$", function(...) {
      fakeWebApi$respond(200L, list(version = "2.14.0"))
    })
    expect_error(
      connectAtlas("https://fake.example.org", useKeyring = FALSE),
      class = "ohdsi_atlas_client_unsupported_version_error"
    )
  })
})

test_that("discovery reports what it tried when nothing answers", {
  withFakeWebApi({
    fakeWebApi$register(".*", function(...) fakeWebApi$respond(404L, list(message = "nope")))
    expect_error(
      connectAtlas("https://fake.example.org", useKeyring = FALSE),
      class = "ohdsi_atlas_client_discovery_error"
    )
  })
})

test_that("credentials round-trip through a file store", {
  directory <- tempfile("credentials-")
  store <- OhdsiAtlasClient:::OhdsiAtlasClientCredentialStore$new(
    configDir = directory,
    useKeyring = FALSE
  )
  expect_null(store$get("https://a.example.org/WebAPI"))
  store$set("https://a.example.org/WebAPI", "k1")
  expect_equal(store$get("https://a.example.org/WebAPI")$apiKey, "k1")
  expect_true(any(grepl("a.example.org", store$urls())))

  # A different profile does not leak into the default one.
  other <- OhdsiAtlasClient:::OhdsiAtlasClientCredentialStore$new(
    configDir = directory,
    useKeyring = FALSE,
    profile = "other"
  )
  expect_null(other$get("https://a.example.org/WebAPI"))

  store$delete("https://a.example.org/WebAPI")
  expect_null(store$get("https://a.example.org/WebAPI"))
})

test_that("the API key is never echoed in full", {
  expect_false(grepl("SECRETSECRET", ohdsiAtlasClientRedactKey("wa_1234567890abcdef_SECRETSECRET")))
  expect_equal(ohdsiAtlasClientRedactKey(NULL), "<none>")
})

test_that("URL normalisation and version comparison behave", {
  expect_equal(ohdsiAtlasClientNormalizeUrl("https://x.org/atlas/"), "https://x.org/atlas")
  expect_true(ohdsiAtlasClientVersionAtLeast("3.0.0", "3.0.0"))
  expect_true(ohdsiAtlasClientVersionAtLeast("3.1.2", "3.0.0"))
  expect_false(ohdsiAtlasClientVersionAtLeast("2.9.9", "3.0.0"))
  expect_true(length(ohdsiAtlasClientCandidateApiBases("https://x.org/atlas")) >= 2)
})

test_that("endpoint listing can be filtered and called", {
  withFakeWebApi({
    atlas <- fakeClient()
    all <- atlas$endpoints()
    expect_gt(length(all), 300)
    filtered <- atlas$endpoints(group = "cohortdefinition")
    groups <- vapply(filtered, function(x) identical(x$group, "cohortdefinition"), logical(1))
    expect_true(all(groups))
    expect_true(length(atlas$endpoints(method = "GET")) > 0)
    expect_true(length(atlas$endpoints(pathContains = "generate")) > 0)

    atlas$call("cohortdefinition.getCohortDefinitionRaw", id = 1)
    expect_match(fakeWebApi$last()$path, "/cohortdefinition/1$")
    expect_error(atlas$call("no.such.operation"), class = "ohdsi_atlas_client_endpoint_error")
    expect_error(
      atlas$call("cohortdefinition.getCohortDefinitionRaw", bogus = 1),
      class = "ohdsi_atlas_client_endpoint_error"
    )
  })
})

test_that("job waiting gives up after the timeout", {
  withFakeWebApi({
    atlas <- fakeClient()
    fakeWebApi$register("/job/execution/", function(...) {
      fakeWebApi$respond(200L, list(executionId = 49, status = "RUNNING"))
    })
    expect_error(
      atlas$jobs$wait(49, timeout = 0.1, pollInterval = 0.02),
      class = "ohdsi_atlas_client_job_timeout"
    )
  })
})

test_that("a failed job surfaces as a job failure", {
  withFakeWebApi({
    atlas <- fakeClient()
    fakeWebApi$register("/job/execution/", function(...) {
      fakeWebApi$respond(200L, list(executionId = 49, status = "FAILED", exitStatus = "FAILED"))
    })
    expect_error(atlas$jobs$wait(49, timeout = 2, pollInterval = 0.02),
                 class = "ohdsi_atlas_client_job_failed")
  })
})

test_that("analysis import posts the design", {
  withFakeWebApi({
    atlas <- fakeClient()
    atlas$cohortCharacterizations$import(list(name = "design"))
    request <- fakeWebApi$last()
    expect_equal(request$method, "POST")
    expect_match(request$path, "/cohort-characterization/import$")
    expect_match(as.character(request$body), "design")
  })
})
