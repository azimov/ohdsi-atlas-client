test_that("live ATLAS 3.0 workflows", {
  url <- Sys.getenv("ATLAS3_TEST_URL", unset = "")
  skip_if(!nzchar(url), "ATLAS3_TEST_URL is not set")
  skip_on_cran()

  apiKey <- Sys.getenv("ATLAS3_TEST_API_KEY", unset = "")
  skip_if(!nzchar(apiKey), "ATLAS3_TEST_API_KEY is not set")
  sourceKey <- Sys.getenv("ATLAS3_TEST_SOURCE", unset = "EUNOMIA")
  store <- Atlas3CredentialStore$new(
    configDir = tempfile("atlas3-live-"), useKeyring = FALSE
  )
  atlas <- connectAtlas(url, apiKey = apiKey, credentialStore = store, useKeyring = FALSE)
  atlas$login(apiKey, store = FALSE)
  expect_true(atlas3VersionAtLeast(atlas$version))
  sources <- atlas$sources$list()
  expect_true(length(sources) >= 1)
  counts <- atlas$concepts$counts(sourceKey, c(1124300))
  expect_true(length(counts) >= 1)
  concepts <- atlas$concepts$search(sourceKey, "diclofenac", rows = 3)
  expect_true(length(concepts) <= 3)

  name <- paste0("atlas3-r-test-", sample.int(1e8, 1))
  conceptSet <- atlas$conceptSets$createFromConcepts(
    name, c(1124300), sourceKey = sourceKey, includeDescendants = TRUE
  )
  on.exit(if (exists("conceptSet")) atlas$conceptSets$delete(conceptSet$id), add = TRUE)
  expression <- atlas$conceptSets$expression(conceptSet$id)
  expect_true(length(expression$items) == 1)

  cohortName <- paste0("atlas3-r-cohort-", sample.int(1e8, 1))
  cohort <- atlas$cohorts$create(cohortName, atlas$cohorts$expression(1))
  on.exit(if (exists("cohort")) atlas$cohorts$delete(cohort$id), add = TRUE)
  expect_equal(atlas$cohorts$get(cohort$id)$name, cohortName)
  sql <- atlas$cohorts$sql(atlas$cohorts$expression(cohort$id))
  expect_true(grepl("CONCEPT", toupper(sql)))

  bundle <- atlas$cohortSets$export(1)
  expect_true(length(bundle$cohorts) >= 1)
  plan <- atlas$cohortSets$import(bundle, onConflict = "rename", dryRun = TRUE)
  expect_true(length(plan$createdCohorts) >= 1)
})
