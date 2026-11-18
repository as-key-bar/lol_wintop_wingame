#!/usr/bin/env bash
# Pull the latest code and rebuild/restart the stack. Run from the repo root on the server.
set -euo pipefail

cd "$(dirname "$0")/.."
git pull --ff-only
export APP_VERSION="$(tr -d '[:space:]' < VERSION)"
export APP_COMMIT="$(git rev-parse --short HEAD)"
echo "Deploying version ${APP_VERSION} (${APP_COMMIT})"
docker compose -f compose.prod.yaml --env-file deploy/.env up -d --build
docker image prune -f
docker compose -f compose.prod.yaml --env-file deploy/.env ps
