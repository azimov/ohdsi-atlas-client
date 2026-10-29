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

Atlas3CredentialStore <- R6::R6Class(
  "Atlas3CredentialStore",
  public = list(
    directory = NULL,
    path = NULL,
    profile = "default",
    useKeyring = TRUE,

    initialize = function(configDir = NULL,
                          profile = "default",
                          useKeyring = TRUE) {
      self$profile <- profile
      self$directory <- configDir %||% tools::R_user_dir("Atlas3", "config")
      self$path <- file.path(self$directory, "credentials.json")
      self$useKeyring <- isTRUE(useKeyring) &&
        requireNamespace("keyring", quietly = TRUE)
      invisible(self)
    },

    get = function(apiUrl) {
      key <- private$key(apiUrl)
      if (self$useKeyring) {
        value <- tryCatch(
          keyring::key_get("atlas3", key),
          error = function(e) NULL
        )
        if (!is.null(value) && nzchar(value)) {
          return(tryCatch(jsonlite::fromJSON(value, simplifyVector = FALSE),
            error = function(e) NULL
          ))
        }
      }
      entries <- private$read()
      entry <- entries[[key]]
      if (is.null(entry) || is.null(entry$apiKey)) {
        return(NULL)
      }
      entry
    },

    set = function(apiUrl, apiKey, keyIdentifier = NULL) {
      checkmate::assertString(apiKey, min.chars = 1)
      key <- private$key(apiUrl)
      entry <- list(
        apiKey = apiKey,
        apiUrl = apiUrl,
        keyIdentifier = keyIdentifier %||% atlas3KeyIdentifier(apiKey),
        createdAt = atlas3NowIso()
      )
      if (self$useKeyring) {
        stored <- tryCatch(
          {
            keyring::key_set_with_value("atlas3", key, jsonlite::toJSON(entry, auto_unbox = TRUE))
            TRUE
          },
          error = function(e) FALSE
        )
        if (stored) {
          return(invisible(entry))
        }
      }
      entries <- private$read()
      entries[[key]] <- entry
      private$write(entries)
      invisible(entry)
    },

    delete = function(apiUrl) {
      key <- private$key(apiUrl)
      if (self$useKeyring) {
        tryCatch(keyring::key_delete("atlas3", key), error = function(e) NULL)
      }
      entries <- private$read()
      if (!is.null(entries[[key]])) {
        entries[[key]] <- NULL
        private$write(entries)
      }
      invisible(self)
    },

    urls = function() {
      sub("^[^|]*\\|", "", names(private$read()))
    }
  ),
  private = list(
    key = function(apiUrl) {
      paste0(self$profile, "|", sub("/+$", "", apiUrl))
    },
    read = function() {
      if (!file.exists(self$path)) {
        return(list())
      }
      value <- tryCatch(
        jsonlite::fromJSON(self$path, simplifyVector = FALSE),
        error = function(e) list()
      )
      if (is.list(value)) value else list()
    },
    write = function(entries) {
      dir.create(self$directory, recursive = TRUE, showWarnings = FALSE)
      atlas3WriteJson(entries, self$path)
      tryCatch(Sys.chmod(self$path, mode = "0600"), error = function(e) NULL)
      invisible(self)
    }
  )
)
