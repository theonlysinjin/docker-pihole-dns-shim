## Technical Specifications

### Overview

`docker-pihole-dns-shim` synchronizes Docker container labels into Pi-hole's custom DNS and CNAME records using the Pi-hole v6 REST API. It watches running containers, reads the JSON-encoded label `pihole.custom-record`, and ensures those entries exist in Pi-hole. It also removes entries when labels disappear. State is persisted on disk to reconcile across restarts.

### Components

- **Runtime process**: `shim.py` (Python)
  - Uses Docker SDK to list containers and read labels
  - Uses `requests` to interact with the Pi-hole v6 REST API
  - Maintains an in-memory and on-disk set of synchronized records
- **Container image**: Built from `alpine:latest` with Python and dependencies, entrypoint `python /app/shim.py`.
- **Release workflow**: GitHub Action tags Docker Hub and GHCR images on releases.

### Data Model

- **Label format**: Docker label key `pihole.custom-record` with a JSON array of pairs.
  - Each pair: `[domain, target]`
  - If `target` is an IPv4 address → A/hosts entry (domain → IP)
  - If `target` is a hostname → CNAME record (domain → target)

### Configuration (Environment Variables)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `PIHOLE_TOKEN` | Yes | — | Pi-hole app password (preferred) or admin password used to authenticate. |
| `PIHOLE_API` | No | `http://pi.hole:8080/api` | Base URL for the Pi-hole v6 REST API. |
| `DOCKER_URL` | No | `unix://var/run/docker.sock` | Docker socket URL used by the shim to read container labels. |
| `STATE_FILE` | No | `/state/pihole.state` | Path to the persisted state file inside the container. |
| `INTERVAL_SECONDS` | No | `10` | Polling interval for sync loop in seconds. |
| `REAP_SECONDS` | No | `600` (10m) | Grace period before removing records that are no longer labeled. |
| `LOGGING_LEVEL` | No | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

### External Interfaces

- **Docker**: Reads container labels via Docker Engine API.
- **Pi-hole v6 REST API**:
  - `POST /auth` → returns session `sid` used in header `sid`
  - `GET /auth/sessions` and `DELETE /auth/session/{id}` → cleanup old sessions for this User-Agent
  - `GET /config/dns/hosts` → returns host entries (rendered as strings "IP host")
  - `PUT /config/dns/hosts/{IP host}` and `DELETE /config/dns/hosts/{IP host}`
  - `GET /config/dns/cnameRecords` → returns CNAME entries ("domain,target")
  - `PUT /config/dns/cnameRecords/{domain,target}` and `DELETE /config/dns/cnameRecords/{domain,target}`

### Authentication & Session Management

- Authenticates once per start using `PIHOLE_TOKEN` to obtain `sid` via `POST /auth`.
- Sets headers for all API calls: `sid` and `User-Agent: docker-pihole-dns-shim`.
- Fetches all sessions and deletes prior stale sessions for this User-Agent (not the current session).

### Operation & Sync Algorithm

1. Validate `PIHOLE_TOKEN` exists; exit if missing.
2. Load previous state from `STATE_FILE` into an in-memory set (`globalList`).
3. Authenticate to Pi-hole and clean old sessions.
4. Loop every `INTERVAL_SECONDS` seconds:
   - List running Docker containers.
   - Build `newGlobalList` from all container labels `pihole.custom-record` (parsed JSON, coerced to tuples).
   - Update per-record `last_seen` for all currently labeled tuples.
   - Fetch current Pi-hole records (hosts and CNAME) and normalize to sets of tuples.
   - Compute:
     - `toAdd`: labels in `newGlobalList` but not in `globalList`.
     - `toRemove`: subset of labels in `globalList` but not in `newGlobalList` whose `last_seen` age >= `REAP_SECONDS`.
     - `toSync`: labels in `globalList` missing from Pi-hole (drift correction).
   - Apply changes:
     - For each tuple `(domain, target)`:
       - If `target` is IPv4, manage via hosts endpoints; else via CNAME endpoints.
       - Treat "already present" responses as success.
   - Update `globalList`, write to `STATE_FILE`, then sleep.

### Record Ownership

- If a labeled record `(domain, target)` already exists in Pi-hole at sync time, the shim treats it as present and adopts it into its managed state.
- Once adopted, the record is considered owned by the shim: if the corresponding label is later removed from containers, the record will be deleted from Pi-hole on the next sync.
- Ownership is at the exact tuple level `(domain, target)`; other Pi-hole entries are not modified unless they are also labeled and adopted.
  - With reaping enabled, deletion only occurs after a record has been unseen for `REAP_SECONDS`.

### Persistence & State

- State file stores the set of synchronized label tuples and last-seen timestamps.
- On startup, the set is restored and used to determine adds/removes and to reconcile drift.
  - v2 format extends the state with last-seen timestamps to support reaping:
    - `{ "owned": [[domain, target], ...], "last_seen": [[domain, target, epochSeconds], ...], "version": 2 }`
    - Legacy list format is still accepted and upgraded in-memory with current timestamps.

### Logging & Observability

- Structured console logs with level controlled by `LOGGING_LEVEL`.
- No metrics/health endpoint; rely on container logs and exit codes.

### Containerization

- Requires Docker socket mounted read-only (example: `-v /var/run/docker.sock:/var/run/docker.sock:ro`).
- Suggested volume for state: mount a writable path to `/state` if persistence is desired.

### Constraints & Assumptions

- Pi-hole v6 API must be reachable at `PIHOLE_API`.
- `pihole.custom-record` label must be valid JSON; invalid JSON will prevent records from being parsed.
- Only IPv4 addresses are treated as A/hosts entries; all other non-IP targets are treated as CNAMEs.
- Sync scope is limited to records declared via labels; it does not prune unrelated Pi-hole records.

### Security Considerations

- `PIHOLE_TOKEN` grants API write access; keep it secret.
- Docker socket access is required for read-only container metadata; mount as read-only and scope access appropriately.

### Compatibility

- Designed for Pi-hole v6. For v5, use the legacy image tag referenced in the README.

### Example Usage

```bash
docker run \
  -l 'pihole.custom-record=[["app.lan","10.0.0.10"],["alias.lan","app.lan"]]' \
  -e PIHOLE_TOKEN=... \
  -e PIHOLE_API='http://pi.hole:8080/api' \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  theonlysinjin/docker-pihole-dns-shim
```


