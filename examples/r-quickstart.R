# End-to-end R example against a live ATLAS 3.0 deployment.
#
#   # OHDSI_ATLAS_CLIENT_API_KEY must be set in the environment (or a secret manager).
#   export OHDSI_ATLAS_CLIENT_URL=https://atlas.example.org
#   export OHDSI_ATLAS_CLIENT_SOURCE=EUNOMIA
#   Rscript examples/r-quickstart.R

library(OhdsiAtlasClient)

url <- Sys.getenv("OHDSI_ATLAS_CLIENT_URL")
if (!nzchar(url)) {
  stop("Set OHDSI_ATLAS_CLIENT_URL")
}
sourceKey <- Sys.getenv("OHDSI_ATLAS_CLIENT_SOURCE", unset = "EUNOMIA")

atlas <- connectAtlas(url, apiKey = Sys.getenv("OHDSI_ATLAS_CLIENT_API_KEY"))

cat("Connected to", atlas$apiUrl, "(WebAPI", atlas$version, ")\n")
print(atlas$whoami()$user)
print(vapply(atlas$sources$list(), `[[`, "", "sourceKey"))

concepts <- atlas$concepts$search(sourceKey, "diclofenac", rows = 5)
print(vapply(concepts, `[[`, "", "CONCEPT_NAME"))

counts <- atlas$cdmResults$conceptCounts(sourceKey, c(1124300))
print(counts[[1]]$values)

demo <- atlas$cohorts$get(1)
cat("Demo cohort:", demo$name, "concept sets:", length(demo$expression$ConceptSets), "\n")

bundle <- atlas$cohortSets$export(c(1), path = tempfile(fileext = ".zip"))
plan <- atlas$cohortSets$import(bundle, onConflict = "rename", dryRun = TRUE)
cat("Cohort-set dry run:", length(plan$createdCohorts), "cohorts would be created\n")
