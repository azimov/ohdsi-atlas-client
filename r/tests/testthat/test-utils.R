test_that("URL normalisation adds a scheme and strips suffixes", {
  expect_equal(atlas3NormalizeUrl("atlas.example.org/atlas/"), "https://atlas.example.org/atlas")
  expect_equal(atlas3NormalizeUrl("http://host:8080/WebAPI/"), "http://host:8080/WebAPI")
  expect_error(atlas3NormalizeUrl(""))
  expect_error(atlas3NormalizeUrl("ftp://host"), "Invalid URL")
})

test_that("candidate WebAPI roots cover ATLAS layouts", {
  expect_equal(
    atlas3CandidateApiBases("https://host/atlas"),
    c("https://host/WebAPI", "https://host/webapi", "https://host", "https://host/atlas/WebAPI")
  )
  expect_equal(atlas3CandidateApiBases("https://host/WebAPI/"), "https://host/WebAPI")
  expect_equal(atlas3CandidateApiBases("https://host/atlas/index.html")[[1]], "https://host/WebAPI")
})

test_that("versions are parsed and compared", {
  expect_equal(atlas3ParseVersion("3.0.0"), c(3L, 0L, 0L))
  expect_equal(atlas3ParseVersion("v3.1"), c(3L, 1L, 0L))
  expect_equal(atlas3ParseVersion("3.0.0-SNAPSHOT"), c(3L, 0L, 0L))
  expect_true(atlas3VersionAtLeast("3.0.1"))
  expect_false(atlas3VersionAtLeast("2.15.0"))
  expect_error(atlas3ParseVersion("nope"))
})

test_that("keys are redacted", {
  expect_equal(atlas3RedactKey(NULL), "<none>")
  expect_equal(atlas3RedactKey("short"), "***")
  expect_match(atlas3RedactKey("wa_1234567890abcdef"), "^wa_1234")
})

test_that("stable hashes are order independent", {
  expect_equal(
    atlas3StableHash(list(a = 1, b = 2)),
    atlas3StableHash(list(b = 2, a = 1))
  )
  expect_false(identical(atlas3StableHash(list(a = 1)), atlas3StableHash(list(a = 2))))
})

test_that("unique names are deterministic", {
  expect_equal(atlas3UniqueName("x", character()), "x")
  expect_equal(atlas3UniqueName("x", "x"), "x (imported)")
  expect_equal(atlas3UniqueName("x", c("x", "x (imported)")), "x (imported) 2")
})
