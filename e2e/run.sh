#!/usr/bin/env bash
# Live e2e: label a container, run the shim once, assert Pi-hole's text config.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/e2e/docker-compose.yml")
PIHOLE_CONTAINER="${PIHOLE_CONTAINER:-shim-e2e-pihole}"
LABELED_CONTAINER="${LABELED_CONTAINER:-shim-e2e-labeled}"
E2E_DOMAIN_A="${E2E_DOMAIN_A:-e2e-shim.lan}"
E2E_IP="${E2E_IP:-10.10.10.42}"
E2E_DOMAIN_CNAME="${E2E_DOMAIN_CNAME:-e2e-cname.lan}"
PIHOLE_TOKEN="${PIHOLE_TOKEN:-e2e-only-not-a-secret}"
PIHOLE_API="${PIHOLE_API:-http://127.0.0.1:18080/api}"
STATE_FILE="${STATE_FILE:-$ROOT/tmp/e2e.pihole.state}"
WAIT_SECONDS="${WAIT_SECONDS:-120}"
MODE="${1:-}"

HOST_RECORD="${E2E_IP} ${E2E_DOMAIN_A}"
CNAME_RECORD="${E2E_DOMAIN_CNAME},${E2E_DOMAIN_A}"
LABEL_JSON="[[\"${E2E_DOMAIN_A}\", \"${E2E_IP}\"], [\"${E2E_DOMAIN_CNAME}\", \"${E2E_DOMAIN_A}\"]]"

python_bin() {
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT/.venv/bin/python"
  else
    printf '%s\n' "python3"
  fi
}

wait_for_pihole() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  local code
  echo "Waiting for Pi-hole API at ${PIHOLE_API} ..."
  while (( SECONDS < deadline )); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' \
      -X POST "${PIHOLE_API}/auth" \
      -H 'Content-Type: application/json' \
      -d "{\"password\":\"${PIHOLE_TOKEN}\"}" || true)"
    if [[ "$code" == "200" ]]; then
      echo "Pi-hole API is ready."
      return 0
    fi
    sleep 2
  done
  echo "Pi-hole API did not become ready within ${WAIT_SECONDS}s (last HTTP ${code:-none})." >&2
  docker logs "$PIHOLE_CONTAINER" 2>&1 | tail -n 80 >&2 || true
  return 1
}

dump_pihole_config() {
  echo "----- /etc/pihole/pihole.toml (dns.hosts / dns.cnameRecords) -----"
  docker exec "$PIHOLE_CONTAINER" sh -c \
    'pihole-FTL --config dns.hosts; echo; pihole-FTL --config dns.cnameRecords; echo; cat /etc/pihole/pihole.toml' \
    || true
  echo "----- /etc/pihole/hosts -----"
  docker exec "$PIHOLE_CONTAINER" sh -c 'ls -la /etc/pihole/hosts 2>/dev/null; cat /etc/pihole/hosts/* 2>/dev/null' \
    || true
}

up_only() {
  "${COMPOSE[@]}" up -d
  wait_for_pihole
}

cleanup_labeled() {
  docker rm -f "$LABELED_CONTAINER" >/dev/null 2>&1 || true
}

run_sync_and_assert() {
  up_only
  cleanup_labeled

  docker run -d --name "$LABELED_CONTAINER" \
    --label "pihole.custom-record=${LABEL_JSON}" \
    alpine:3.20 sleep 3600 >/dev/null

  mkdir -p "$(dirname "$STATE_FILE")"
  rm -f "$STATE_FILE"

  echo "Running shim --run-once ..."
  PIHOLE_TOKEN="$PIHOLE_TOKEN" \
  PIHOLE_API="$PIHOLE_API" \
  STATE_FILE="$STATE_FILE" \
  SHIM_INSTANCE_ID="e2e" \
  LOGGING_LEVEL="${LOGGING_LEVEL:-DEBUG}" \
    "$(python_bin)" "$ROOT/shim.py" --run-once --no-remove

  # FTL writes pihole.toml (the v6 text config) and may materialize /etc/pihole/hosts/*.
  local deadline=$((SECONDS + 30))
  local toml hosts_dir ftl_hosts ftl_cnames
  local hosts_ok=0 cname_ok=0 generated_ok=0
  while (( SECONDS < deadline )); do
    ftl_hosts="$(docker exec "$PIHOLE_CONTAINER" pihole-FTL --config dns.hosts 2>/dev/null || true)"
    ftl_cnames="$(docker exec "$PIHOLE_CONTAINER" pihole-FTL --config dns.cnameRecords 2>/dev/null || true)"
    toml="$(docker exec "$PIHOLE_CONTAINER" cat /etc/pihole/pihole.toml 2>/dev/null || true)"
    hosts_dir="$(docker exec "$PIHOLE_CONTAINER" sh -c 'cat /etc/pihole/hosts/* /etc/pihole/custom.list 2>/dev/null' || true)"

    grep -F -q -- "$HOST_RECORD" <<<"${ftl_hosts}${toml}" && hosts_ok=1 || hosts_ok=0
    grep -F -q -- "$CNAME_RECORD" <<<"${ftl_cnames}${toml}" && cname_ok=1 || cname_ok=0
    if [[ -n "$hosts_dir" ]] && grep -F -q -- "$HOST_RECORD" <<<"$hosts_dir"; then
      generated_ok=1
    fi
    if (( hosts_ok == 1 && cname_ok == 1 && generated_ok == 1 )); then
      break
    fi
    sleep 1
  done

  local failed=0
  if (( hosts_ok != 1 )); then
    echo "FAIL: A record '${HOST_RECORD}' missing from pihole.toml / dns.hosts" >&2
    failed=1
  else
    echo "OK: A record '${HOST_RECORD}' present in Pi-hole dns.hosts / pihole.toml"
  fi
  if (( cname_ok != 1 )); then
    echo "FAIL: CNAME '${CNAME_RECORD}' missing from pihole.toml / dns.cnameRecords" >&2
    failed=1
  else
    echo "OK: CNAME '${CNAME_RECORD}' present in Pi-hole dns.cnameRecords / pihole.toml"
  fi
  if (( generated_ok == 1 )); then
    echo "OK: A record '${HOST_RECORD}' present in generated hosts file"
  elif (( hosts_ok == 1 )); then
    echo "WARN: generated /etc/pihole/hosts file did not include '${HOST_RECORD}' yet; pihole.toml is the v6 text config."
  fi

  if (( failed != 0 )); then
    dump_pihole_config
    cleanup_labeled
    return 1
  fi

  cleanup_labeled
  if [[ "${E2E_KEEP_PIHOLE:-}" != "1" ]]; then
    "${COMPOSE[@]}" down
  fi
  echo "e2e passed."
}

case "$MODE" in
  --up-only)
    up_only
    ;;
  --help|-h)
    echo "Usage: e2e/run.sh [--up-only]"
    echo "  (default) start Pi-hole, sync a labeled container, assert text config"
    echo "  --up-only  start Pi-hole and wait for the API"
    ;;
  "")
    run_sync_and_assert
    ;;
  *)
    echo "Unknown argument: $MODE" >&2
    exit 2
    ;;
esac
