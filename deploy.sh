#!/bin/bash
# Deploy a released OhdsiAtlasClient build.
#
# Copies the built, checked package to the OHDSI drat repository and pushes it.
# Intended to run from CI after a tag is created on `main`; see
# https://ohdsi.github.io/Hades/releaseProcess.html.
#
# Required environment variables:
#   GITHUB_PAT     a token with push access to the OHDSI drat repository
# Optional:
#   PACKAGE_DIR    defaults to OhdsiAtlasClient

set -euo pipefail

PACKAGE_DIR="${PACKAGE_DIR:-OhdsiAtlasClient}"

if [ -z "${GITHUB_PAT:-}" ]; then
  echo "error: GITHUB_PAT must be set to deploy" >&2
  exit 1
fi

STATUS=$(./compare_versions)
if [ "$STATUS" != "new" ]; then
  echo "Nothing to deploy (version status: $STATUS)."
  exit 0
fi

VERSION=$(grep '^Version:' "${PACKAGE_DIR}/DESCRIPTION" | sed 's/Version: *//' | tr -d '\r')
TARBALL="${PACKAGE_DIR}_${VERSION}.tar.gz"

echo "Deploying ${TARBALL}"

R CMD build "${PACKAGE_DIR}"

WORK_DIR=$(mktemp -d)
trap 'rm -rf "${WORK_DIR}"' EXIT

git clone --depth 1 "https://OHDSI:${GITHUB_PAT}@github.com/OHDSI/drat.git" "${WORK_DIR}/drat"
R CMD INSTALL --build --library="${WORK_DIR}/drat" "${TARBALL}"

cd "${WORK_DIR}/drat"
git config user.name "OHDSI Bot"
git config user.email "ohdsi-bot@ohdsi.org"
git add -A
git commit -m "Deploy OhdsiAtlasClient ${VERSION}"
git push origin HEAD:gh-pages

echo "Deployed OhdsiAtlasClient ${VERSION}"
