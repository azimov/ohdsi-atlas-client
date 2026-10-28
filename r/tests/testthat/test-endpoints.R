test_that("the endpoint catalog contains the full WebAPI surface", {
  catalog <- Atlas3:::atlas3Catalog()
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
  atlas3CallEndpoint(
    client, "cohortdefinition.generateCohort",
    id = 1, sourceKey = "EUNOMIA", demographic = FALSE
  )
  expect_equal(calls[[1]]$method, "GET")
  expect_equal(calls[[1]]$path, "/cohortdefinition/1/generate/EUNOMIA")
  expect_equal(calls[[1]]$query, list(demographic = FALSE))
})

test_that("unknown operations fail with a helpful class", {
  expect_error(atlas3CallEndpoint(list(request = function(...) NULL), "nope"),
    class = "atlas3_endpoint_error"
  )
})
