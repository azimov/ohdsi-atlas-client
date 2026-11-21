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

test_that("URL normalisation adds a scheme and strips suffixes", {
  expect_equal(
    ohdsiAtlasClientNormalizeUrl("atlas.example.org/atlas/"),
    "https://atlas.example.org/atlas"
  )
  expect_equal(ohdsiAtlasClientNormalizeUrl("http://host:8080/WebAPI/"), "http://host:8080/WebAPI")
  expect_error(ohdsiAtlasClientNormalizeUrl(""))
  expect_error(ohdsiAtlasClientNormalizeUrl("ftp://host"), "Invalid URL")
})

test_that("candidate WebAPI roots cover ATLAS layouts", {
  expect_equal(
    ohdsiAtlasClientCandidateApiBases("https://host/atlas"),
    c("https://host/WebAPI", "https://host/webapi", "https://host", "https://host/atlas/WebAPI")
  )
  expect_equal(ohdsiAtlasClientCandidateApiBases("https://host/WebAPI/"), "https://host/WebAPI")
  expect_equal(
    ohdsiAtlasClientCandidateApiBases("https://host/atlas/index.html")[[1]],
    "https://host/WebAPI"
  )
})

test_that("versions are parsed and compared", {
  expect_equal(ohdsiAtlasClientParseVersion("3.0.0"), c(3L, 0L, 0L))
  expect_equal(ohdsiAtlasClientParseVersion("v3.1"), c(3L, 1L, 0L))
  expect_equal(ohdsiAtlasClientParseVersion("3.0.0-SNAPSHOT"), c(3L, 0L, 0L))
  expect_true(ohdsiAtlasClientVersionAtLeast("3.0.1"))
  expect_false(ohdsiAtlasClientVersionAtLeast("2.15.0"))
  expect_error(ohdsiAtlasClientParseVersion("nope"))
})

test_that("keys are redacted", {
  expect_equal(ohdsiAtlasClientRedactKey(NULL), "<none>")
  expect_equal(ohdsiAtlasClientRedactKey("short"), "***")
  expect_match(ohdsiAtlasClientRedactKey("wa_1234567890abcdef"), "^wa_1234")
})

test_that("stable hashes are order independent", {
  expect_equal(
    ohdsiAtlasClientStableHash(list(a = 1, b = 2)),
    ohdsiAtlasClientStableHash(list(b = 2, a = 1))
  )
  expect_false(
    identical(
      ohdsiAtlasClientStableHash(list(a = 1)),
      ohdsiAtlasClientStableHash(list(a = 2))
    )
  )
})

test_that("unique names are deterministic", {
  expect_equal(ohdsiAtlasClientUniqueName("x", character()), "x")
  expect_equal(ohdsiAtlasClientUniqueName("x", "x"), "x (imported)")
  expect_equal(ohdsiAtlasClientUniqueName("x", c("x", "x (imported)")), "x (imported) 2")
})


test_that("API key identifiers are extracted", {
  expect_equal(ohdsiAtlasClientKeyIdentifier("wa_1234567890abcdef_secret"), "1234567890abcdef")
  expect_null(ohdsiAtlasClientKeyIdentifier("not-a-key"))
  expect_null(ohdsiAtlasClientKeyIdentifier(NULL))
})
