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
  bundle <- atlas3BundleFromCohorts(list(cohortPayload()), atlas = list(url = "https://x"))
  expect_s3_class(bundle, "atlas3_cohort_set_bundle")
  expect_equal(length(bundle$cohorts), 1)
  expect_equal(bundle$cohorts[[1]]$conceptSetIds, 0L)
  expect_equal(length(bundle$conceptSets), 1)
  expect_equal(bundle$conceptSets[[1]]$name, "diclofenac")
  expect_true(nzchar(bundle$integrity$digest))
})

test_that("duplicate embedded concept sets are deduplicated", {
  bundle <- atlas3BundleFromCohorts(list(cohortPayload(), cohortPayload("Second")))
  expect_equal(length(bundle$conceptSets), 1)
})

test_that("bundles round-trip JSON, ZIP, and directories", {
  bundle <- atlas3BundleFromCohorts(list(cohortPayload()))
  jsonPath <- tempfile(fileext = ".json")
  atlas3BundleSave(bundle, jsonPath)
  loaded <- atlas3BundleLoad(jsonPath)
  expect_equal(loaded$cohorts[[1]]$name, "Demo")
  expect_equal(loaded$integrity$digest, bundle$integrity$digest)

  zipPath <- tempfile(fileext = ".zip")
  atlas3BundleSave(bundle, zipPath)
  expect_equal(atlas3BundleLoad(zipPath)$cohorts[[1]]$name, "Demo")

  directory <- tempfile("bundle-")
  atlas3BundleSave(bundle, directory)
  expect_true(file.exists(file.path(directory, "cohort-set.json")))
  expect_true(dir.exists(file.path(directory, "cohorts")))
  expect_equal(atlas3BundleLoad(directory)$cohorts[[1]]$name, "Demo")
})

test_that("integrity tampering is detected", {
  bundle <- atlas3BundleFromCohorts(list(cohortPayload()))
  bundle$cohorts[[1]]$name <- "Tampered"
  expect_error(atlas3BundleValidate(bundle), "integrity")
})

test_that("duplicate cohort names are rejected", {
  bundle <- atlas3BundleFromCohorts(list(cohortPayload(), cohortPayload()))
  expect_error(atlas3BundleValidate(bundle), "Duplicate cohort names")
})
