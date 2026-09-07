#!/usr/bin/env bash
# Idempotent Cloud Agent install: Python deps plus cached e2e images.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements-dev.txt

sudo service docker start
for _ in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker info >/dev/null

docker compose -f e2e/docker-compose.yml pull
docker pull alpine:3.20

# Builds snapshot disk only; running processes do not carry into agent sessions.
sudo service docker stop || true
