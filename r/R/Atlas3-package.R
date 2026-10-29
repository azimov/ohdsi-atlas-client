# Copyright 2026 Observational Health Data Sciences and Informatics
#
# This file is part of Atlas3
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

#' Atlas3: a client for OHDSI ATLAS 3.0 and WebAPI 3.0
#'
#' `Atlas3` connects to an ATLAS 3.0 deployment from its URL, discovers the
#' WebAPI root and version, and provides typed access to
#' sources, vocabularies, concept sets, cohort definitions, cohort definition
#' sets, CDM results, jobs, and analysis resources.
#'
#' @section Quick start:
#' ```r
#' library(Atlas3)
#' atlas <- connectAtlas("https://atlas.example.org", apiKey = "wa_...")
#' atlas$sources$list()
#' atlas$concepts$search("EUNOMIA", "diclofenac")
#' ```
#'
#' @section ATLAS version:
#' Both clients require ATLAS/WebAPI 3.0.0 or newer. WebAPI 2.x is rejected
#' during discovery.
#'
#' @keywords internal
"_PACKAGE"

#' @importFrom R6 R6Class
#' @importFrom rlang abort
NULL
