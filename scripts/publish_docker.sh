#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: publish_docker.sh <version>}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY env not set}"

IMAGE="ghcr.io/${GITHUB_REPOSITORY}"

docker build \
  --build-arg APP_VERSION="${VERSION}" \
  -t "${IMAGE}:${VERSION}" \
  -t "${IMAGE}:latest" \
  .

docker push "${IMAGE}:${VERSION}"
docker push "${IMAGE}:latest"
