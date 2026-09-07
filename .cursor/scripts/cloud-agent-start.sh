#!/usr/bin/env bash
# Start Docker and the API-only Pi-hole fixture for live e2e checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

sudo service docker start
for _ in $(seq 1 30); do
  if [[ -S /var/run/docker.sock ]]; then
    break
  fi
  sleep 1
done

# Group membership from the image may not apply to this session yet.
if [[ -S /var/run/docker.sock ]]; then
  sudo chmod 666 /var/run/docker.sock || true
fi

for _ in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker info >/dev/null

E2E_KEEP_PIHOLE=1 bash e2e/run.sh --up-only
