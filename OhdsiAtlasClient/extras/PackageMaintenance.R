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

# Package maintenance for a HADES release.
#
# Run from the package root:  Rscript extras/PackageMaintenance.R
#
# This follows the HADES release process:
# https://ohdsi.github.io/Hades/releaseProcess.html
# It is developer tooling only; it is excluded from the built package by
# .Rbuildignore.

options(width = 100)

## Version and metadata ------------------------------------------------------

# Bump the version before running the release steps. HADES uses three digits:
#   micro (x.y.Z) bug fixes only,   minor (x.Y.0) new functionality,
#   major (X.0.0) breaking changes.
ensureVersionUpdated <- function() {
  required <- "OhdsiAtlasClient"
  description <- read.dcf("DESCRIPTION")
  cat("Current version:", description[1, "Version"], "\n")
  cat("Current date:   ", description[1, "Date"], "\n")
  if (!"Date" %in% colnames(description) ||
      is.na(description[1, "Date"]) ||
      as.Date(description[1, "Date"]) < Sys.Date()) {
    message("Update the Date field in DESCRIPTION to today's date before releasing.")
  }
  if (!"Remotes" %in% colnames(description)) {
    # Nothing to check: every dependency is on CRAN.
    return(invisible(TRUE))
  }
  remotes <- description[1, "Remotes"]
  if (grepl("develop", remotes)) {
    stop("The Remotes section must not reference a 'develop' branch in a release.")
  }
  invisible(TRUE)
}

## Documentation -------------------------------------------------------------

regenerateDocumentation <- function() {
  roxygen2::roxygenise()
  devtools::document()
  # A spellcheck failure is a release blocker for HADES packages.
  devtools::spellcheck()
  invisible(TRUE)
}

## Tests and checks ----------------------------------------------------------

runTests <- function() {
  devtools::test()
  invisible(TRUE)
}

runCheck <- function() {
  # HADES requires R CMD check without warnings on Windows, macOS, and Linux.
  # This runs the local check; CI covers the other platforms.
  results <- devtools::check(
    args = c("--no-manual", "--as-cran"),
    error_on = "warning"
  )
  if (length(results$notes) > 0) {
    message(length(results$notes), " note(s); review 00check.log before releasing.")
  }
  invisible(results)
}

checkCoverage <- function(threshold = 80) {
  if (!requireNamespace("covr", quietly = TRUE)) {
    message("covr is not installed; skipping the coverage check.")
    return(invisible(NA_real_))
  }
  coverage <- covr::package_coverage(type = "tests", quiet = TRUE)
  percent <- covr::percent_coverage(coverage)
  cat("Test coverage:", round(percent, 1), "%\n")
  if (percent < threshold) {
    warning("Coverage is below the HADES guideline of ", threshold, "%.", call. = FALSE)
  }
  invisible(percent)
}

## Website -------------------------------------------------------------------

buildWebsite <- function() {
  if (!requireNamespace("pkgdown", quietly = TRUE)) {
    message("pkgdown is not installed; skipping the website build.")
    return(invisible(FALSE))
  }
  pkgdown::build_site(preview = FALSE)
  invisible(TRUE)
}

## Full release --------------------------------------------------------------

release <- function() {
  ensureVersionUpdated()
  regenerateDocumentation()
  runTests()
  checkCoverage()
  runCheck()
  buildWebsite()
  cat(
    "\nRelease checklist remaining (per HADES release process):\n",
    "  1. Confirm R CMD check is clean on Windows, macOS, and Linux in CI.\n",
    "  2. Merge 'develop' into 'main' with the new version in DESCRIPTION.\n",
    "  3. The tag and drat push are created automatically by CI.\n",
    "  4. Announce the release on the OHDSI forums HADES thread.\n",
    sep = ""
  )
  invisible(TRUE)
}

# Uncomment to run the full sequence:
# release()
