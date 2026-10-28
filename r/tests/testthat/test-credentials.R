test_that("credentials round-trip through the file backend", {
  directory <- tempfile("atlas3-creds-")
  store <- Atlas3CredentialStore$new(
    configDir = directory, useKeyring = FALSE
  )
  store$set("https://example.org/WebAPI", "wa_test_key",
    login = "user", keyIdentifier = "abc"
  )
  value <- store$get("https://example.org/WebAPI")
  expect_equal(value$apiKey, "wa_test_key")
  expect_equal(value$login, "user")
  expect_equal(value$keyIdentifier, "abc")
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
    configuration = list(),
    authProviders = list(list(name = "DB", url = "user/login/db"))
  )
  atlas <- connectAtlas(
    "https://example.org/atlas",
    apiKey = "wa_test_key",
    discovery = discovery,
    credentialStore = Atlas3CredentialStore$new(
      configDir = tempfile("atlas3-creds-"), useKeyring = FALSE
    )
  )
  expect_equal(atlas$apiUrl, "https://example.org/WebAPI")
  expect_equal(atlas$version, "3.0.0")
  expect_equal(atlas$apiKey, "wa_test_key")
  expect_s3_class(atlas$cohorts, "Atlas3Cohorts")
  expect_s3_class(atlas$cohortSets, "Atlas3CohortSets")
})
