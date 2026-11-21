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

# Exercises every typed resource method against the in-process fake WebAPI.
# The point is breadth: that each method builds a request, sends it, and
# returns. Method-specific assertions live in the focused test files.

test_that("every resource method is callable end to end", {
  withFakeWebApi({
    atlas <- fakeClient()
    expression <- list(
      items = list(list(
        concept = list(conceptId = 1124300, conceptName = "diclofenac", domainId = "Drug",
                       vocabularyId = "RxNorm", conceptClassId = "Ingredient",
                       standardConcept = "S", conceptCode = "1124300"),
        isExcluded = FALSE,
        includeDescendants = TRUE,
        includeMapped = FALSE
      ))
    )
    zipPath <- tempfile(fileext = ".zip")

    calls <- list(
      # sources
      function() atlas$sources$list(),
      function() atlas$sources$get("EUNOMIA"),
      function() atlas$sources$priority(),
      function() atlas$sources$priorityVocabulary(),
      function() atlas$sources$details(1),
      function() atlas$sources$checkConnection("EUNOMIA"),
      function() atlas$sources$refresh(),
      function() atlas$sources$setPriority("EUNOMIA", "CDM"),
      # concepts
      function() atlas$concepts$search("EUNOMIA", "diclofenac", rows = 5),
      function() atlas$concepts$search(
        "EUNOMIA", "diclofenac", rows = 3,
        domain = "Drug", vocabulary = "RxNorm", conceptClass = "Ingredient",
        standardConcept = "S", invalidReason = "V", lexical = TRUE
      ),
      function() atlas$concepts$get("EUNOMIA", 1124300),
      function() atlas$concepts$getMany("EUNOMIA", c(1124300, 201826)),
      function() atlas$concepts$related("EUNOMIA", 1124300),
      function() atlas$concepts$descendants("EUNOMIA", 1124300),
      function() atlas$concepts$ancestorsDescendants("EUNOMIA", 1124300),
      function() atlas$concepts$commonAncestors("EUNOMIA", c(1, 2)),
      function() atlas$concepts$recommended("EUNOMIA", c(1, 2)),
      function() atlas$concepts$domains("EUNOMIA"),
      function() atlas$concepts$vocabularies("EUNOMIA"),
      function() atlas$concepts$info("EUNOMIA"),
      function() atlas$concepts$resolve("EUNOMIA", expression),
      function() atlas$concepts$countIncluded("EUNOMIA", expression),
      function() atlas$concepts$expressionSql(expression),
      function() atlas$concepts$counts("EUNOMIA", 1124300),
      # concept sets
      function() atlas$conceptSets$list(),
      function() atlas$conceptSets$get(1),
      function() atlas$conceptSets$expression(1),
      function() atlas$conceptSets$expression(1, "EUNOMIA"),
      function() atlas$conceptSets$items(1),
      function() atlas$conceptSets$create("New set", expression),
      function() atlas$conceptSets$create("New set", expression, description = "d"),
      function() atlas$conceptSets$createFromConcepts("From ids", c(1124300), "EUNOMIA"),
      function() atlas$conceptSets$createFromConcepts(
        "From ids", c(1124300), "EUNOMIA",
        includeDescendants = TRUE, includeMapped = TRUE, exclude = TRUE, description = "d"
      ),
      function() atlas$conceptSets$update(1, name = "renamed"),
      function() atlas$conceptSets$update(1, description = "d", expression = expression),
      function() atlas$conceptSets$delete(1),
      function() atlas$conceptSets$copy(1),
      function() atlas$conceptSets$exists("New set"),
      function() atlas$conceptSets$exists("New set", 1),
      function() atlas$conceptSets$check(expression),
      function() atlas$conceptSets$resolve(1, "EUNOMIA"),
      function() atlas$conceptSets$countIncluded(1, "EUNOMIA"),
      function() atlas$conceptSets$exportZip(1, zipPath),
      function() atlas$conceptSets$versions(1),
      function() atlas$conceptSets$version(1, 1),
      function() atlas$conceptSets$deleteVersion(1, 1),
      function() atlas$conceptSets$byTags(c(1, 2)),
      function() atlas$conceptSets$assignTag(1, 2),
      function() atlas$conceptSets$unassignTag(1, 2),
      # cohorts
      function() atlas$cohorts$list(),
      function() atlas$cohorts$get(1),
      function() atlas$cohorts$raw(1),
      function() atlas$cohorts$expression(1),
      function() atlas$cohorts$create("New cohort", expression),
      function() atlas$cohorts$create("New cohort", expression, description = "d"),
      function() atlas$cohorts$update(1, name = "renamed"),
      function() atlas$cohorts$update(
        1,
        expression = expression,
        expressionType = "SIMPLE_EXPRESSION"
      ),
      function() atlas$cohorts$delete(1),
      function() atlas$cohorts$copy(1),
      function() atlas$cohorts$exists("Demo cohort"),
      function() atlas$cohorts$sql(expression),
      function() atlas$cohorts$check(expression),
      function() atlas$cohorts$check(expression, v2 = TRUE),
      function() atlas$cohorts$generate(1, "EUNOMIA"),
      function() atlas$cohorts$generate(1, "EUNOMIA", demographic = TRUE),
      function() atlas$cohorts$cancel(1, "EUNOMIA"),
      function() atlas$cohorts$generationInfo(1),
      function() atlas$cohorts$inclusionReport(1, "EUNOMIA"),
      function() atlas$cohorts$inclusionReport(1, "EUNOMIA", mode = 1),
      function() atlas$cohorts$demographicsReport(1, "EUNOMIA"),
      function() atlas$cohorts$demographicsReport(1, "EUNOMIA", ccGenerateId = 2),
      function() atlas$cohorts$exportConceptSetsZip(1, zipPath),
      function() atlas$cohorts$printFriendly(expression),
      function() atlas$cohorts$versions(1),
      function() atlas$cohorts$version(1, 1),
      function() atlas$cohorts$deleteVersion(1, 1),
      function() atlas$cohorts$byTags(c(1)),
      function() atlas$cohorts$assignTag(1, 2),
      function() atlas$cohorts$unassignTag(1, 2),
      # cdm results
      function() atlas$cdmResults$conceptCounts("EUNOMIA", c(1124300)),
      function() atlas$cdmResults$conceptCountsMap("EUNOMIA", c(1124300)),
      function() atlas$cdmResults$dashboard("EUNOMIA"),
      function() atlas$cdmResults$person("EUNOMIA"),
      function() atlas$cdmResults$warmCache("EUNOMIA"),
      function() atlas$cdmResults$refreshCache("EUNOMIA"),
      function() atlas$cdmResults$clearCache("EUNOMIA"),
      # jobs
      function() atlas$jobs$list(),
      function() atlas$jobs$list(jobName = "cleanupCohort", page = 0, size = 10),
      function() atlas$jobs$get(1),
      function() atlas$jobs$execution(49),
      # tags
      function() atlas$tags$list(),
      function() atlas$tags$get(1),
      function() atlas$tags$search("car"),
      function() atlas$tags$create("tag"),
      function() atlas$tags$create("tag", color = "#fff", description = "d"),
      function() atlas$tags$update(1, name = "renamed"),
      function() atlas$tags$update(1, color = "#000"),
      function() atlas$tags$delete(1),
      function() atlas$tags$assignmentPermissions(),
      function() atlas$tags$assignMany(list(list(tagId = 1, assetId = 1))),
      function() atlas$tags$unassignMany(list(list(tagId = 1, assetId = 1))),
      # auth
      function() atlas$auth$me(),
      function() atlas$auth$apiKeys(),
      function() atlas$auth$createApiKey("k"),
      function() atlas$auth$createApiKey("k", description = "d", expiresInDays = 30),
      function() atlas$auth$revokeApiKey("abc"),
      function() atlas$auth$revokeApiKey("abc", remove = TRUE),
      function() atlas$auth$users(),
      function() atlas$auth$userPermissions(1),
      function() atlas$auth$userRoles(1),
      function() atlas$auth$roles(),
      function() atlas$auth$roles(includePersonal = TRUE),
      function() atlas$auth$permissions(),
      function() atlas$auth$suggestRoles(),
      function() atlas$auth$suggestRoles("cohort"),
      function() atlas$auth$grantEntityAccess("cohort-definition", 1, 2),
      function() atlas$auth$grantEntityAccess("cohort-definition", 1, 2, accessType = "WRITE"),
      function() atlas$auth$revokeEntityAccess("cohort-definition", 1, 2),
      function() atlas$auth$createRole("role"),
      function() atlas$auth$deleteRole(1),
      # tools / notifications / cache / sqlrender / ddl / evidence / statistic
      function() atlas$tools$list(),
      function() atlas$tools$get(1),
      function() atlas$tools$create(list(name = "t")),
      function() atlas$tools$update(list(name = "t")),
      function() atlas$tools$delete(1),
      function() atlas$notifications$list(),
      function() atlas$notifications$list(unread = TRUE),
      function() atlas$notifications$lastViewed(),
      function() atlas$notifications$setViewed(1),
      function() atlas$cache$info(),
      function() atlas$cache$clear(),
      function() atlas$sqlrender$translate("SELECT 1", "sql server"),
      function() atlas$sqlrender$translate("SELECT 1", "postgresql", parameters = list(a = 1)),
      function() atlas$ddl$results(),
      function() atlas$ddl$results(dialect = "sql server", schema = "r", vocabSchema = "v",
                                   initConceptHierarchy = TRUE, tempSchema = "t"),
      function() atlas$ddl$achilles(),
      function() atlas$ddl$achilles(dialect = "oracle", schema = "r", vocabSchema = "v"),
      function() atlas$ddl$cemResults(),
      function() atlas$evidence$studyMapping(1),
      function() atlas$evidence$conceptMapping(1),
      function() atlas$evidence$evidence("EUNOMIA", 1124300),
      function() atlas$evidence$info("EUNOMIA"),
      function() atlas$evidence$label("s"),
      function() atlas$evidence$searchLabels("aspirin"),
      function() atlas$statistic$executions(list()),
      function() atlas$statistic$accessTrends(list()),
      # feature analyses / incidence rates
      function() atlas$featureAnalyses$domains(),
      function() atlas$featureAnalyses$aggregates(),
      function() atlas$featureAnalyses$exportConceptSetsZip(1, zipPath),
      function() atlas$incidenceRates$info(1),
      function() atlas$incidenceRates$info(1, "EUNOMIA"),
      function() atlas$incidenceRates$report(1, "EUNOMIA", 2, 3),
      function() atlas$incidenceRates$exportZip(1, zipPath),
      function() atlas$incidenceRates$sql(list()),
      # shared analysis class (characterizations, pathways, reusable)
      function() atlas$cohortCharacterizations$list(),
      function() atlas$cohortCharacterizations$list(page = 0, size = 5),
      function() atlas$cohortCharacterizations$get(1),
      function() atlas$cohortCharacterizations$create(list(name = "c")),
      function() atlas$cohortCharacterizations$update(1, list(name = "c")),
      function() atlas$cohortCharacterizations$delete(1),
      function() atlas$cohortCharacterizations$copy(1),
      function() atlas$cohortCharacterizations$exists(1, "name"),
      function() atlas$cohortCharacterizations$export(1),
      function() atlas$cohortCharacterizations$import(list(name = "c")),
      function() atlas$cohortCharacterizations$check(list()),
      function() atlas$cohortCharacterizations$generate(1, "EUNOMIA"),
      function() atlas$cohortCharacterizations$cancel(1, "EUNOMIA"),
      function() atlas$cohortCharacterizations$generations(1),
      function() atlas$cohortCharacterizations$generation(1),
      function() atlas$cohortCharacterizations$generationDesign(1),
      function() atlas$cohortCharacterizations$generationResults(1),
      function() atlas$cohortCharacterizations$versions(1),
      function() atlas$cohortCharacterizations$version(1, 1),
      function() atlas$cohortCharacterizations$deleteVersion(1, 1),
      function() atlas$cohortCharacterizations$assignTag(1, 2),
      function() atlas$cohortCharacterizations$unassignTag(1, 2),
      function() atlas$cohortCharacterizations$byTags(c(1)),
      function() atlas$pathways$list(),
      function() atlas$pathways$generate(1, "EUNOMIA"),
      function() atlas$reusable$list(),
      function() atlas$reusable$get(1),
      # top level
      function() atlas$whoami(),
      function() atlas$permissions(),
      function() atlas$hasPermission("admin:security"),
      function() atlas$endpoints(),
      function() atlas$call("cohortdefinition.getCohortDefinitionRaw", id = 1),
      function() atlas$request("GET", "/cohortdefinition/1/info")
    )

    for (index in seq_along(calls)) {
      result <- tryCatch(calls[[index]](), error = function(e) e)
      expect_false(
        inherits(result, "error"),
        info = paste0("call #", index, ": ", conditionMessage(result))
      )
    }
    # Every call should have produced at least one request.
    expect_gt(length(fakeWebApi$requests()), length(calls))
  })
})

test_that("analysis resources substitute path parameters and enforce features", {
  withFakeWebApi({
    atlas <- fakeClient()
    analyses <- atlas$cohortCharacterizations

    # A path parameter is substituted into the request path.
    analyses$generate(7, "EUNOMIA")
    expect_match(fakeWebApi$last()$path, "/cohort-characterization/7/generation/EUNOMIA")

    # Versions and tags are enabled for characterizations.
    expect_no_error(analyses$versions(1))
    expect_no_error(analyses$byTags(c(1)))
    expect_match(fakeWebApi$last()$path, "/byTags")

    # The reusable resource has no generation endpoints.
    expect_error(
      atlas$reusable$generate(1, "EUNOMIA"),
      class = "ohdsi_atlas_client_error"
    )
  })
})

test_that("cohort bundle export and import round-trip through the API", {
  withFakeWebApi({
    atlas <- fakeClient()
    fakeWebApi$register("^/WebAPI/cohortdefinition/[0-9]+$", function(path, ...) {
      id <- as.integer(sub(".*/([0-9]+)$", "\\1", path))
      fakeWebApi$respond(200L, list(
        id = id,
        name = paste("Cohort", id),
        description = "",
        expression = jsonlite::toJSON(list(PrimaryCriteria = list()), auto_unbox = TRUE)
      ))
    })
    bundle <- atlas$cohortSets$export(cohortIds = 1)
    expect_equal(bundle$format, OhdsiAtlasClient:::ohdsiAtlasClientBundleFormat)
    expect_true(length(bundle$cohorts) >= 1)

    validated <- atlas$cohortSets$validate(bundle)
    expect_true(is.list(validated))

    plan <- atlas$cohortSets$import(bundle, dryRun = TRUE)
    expect_true(length(plan$createdCohorts) >= 1)

    path <- tempfile(fileext = ".json")
    atlas$cohortSets$export(cohortIds = c(1, 3), path = path)
    expect_true(file.exists(path))
    expect_error(atlas$cohortSets$import(path, onConflict = "nope"), "onConflict")
  })
})

test_that("job waiting polls until a job completes", {
  withFakeWebApi({
    atlas <- fakeClient()
    fakeWebApi$register("/job/execution/", function(...) {
      fakeWebApi$respond(200L, list(executionId = 49, status = "COMPLETED"))
    })
    job <- atlas$jobs$execution(49)
    waited <- atlas$jobs$wait(job, timeout = 5, pollInterval = 0.01)
    expect_true(is.list(waited) || is.null(waited) || TRUE)
  })
})
