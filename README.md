# docker-pihole-dns-shim

Easily synchronise records found through docker labels with pihole's custom dns and cname records.  


> ⚠️ **Breaking Change Notice:**  
> The `latest` image now targets Pi-hole v6 and uses the new API.  
> If you need Pi-hole v5 support, see the "Legacy (v5) Configuration" section after the setup instructions below.


## How to get started

### Find your secret pihole token

**Create an application password**
- Find System / Settings in the left hand panel,
- Navigate to the [Web interface / API](http://pi.hole:8080/admin/settings/api) tab in your pihole settings
- Click the `Basic` button to change to `Expert`
- Click the `Configure app password`
- Copy the new app password and save it, this is your last chance
- Click `Replace app password`
- Use this as `PIHOLE_TOKEN`

**Allow the application password to make changes**
- Under System / Settings,
- Navigate to [All settings](http://pi.hole:8080/admin/settings/all)
- Select the "Webserver and API" tab
- Find and enable `webserver.api.app_sudo` 

**OR**
- Use your admin login password for `PIHOLE_TOKEN`

### Run

cli

```bash
docker run \
  -l "pihole.custom-record=[[\"pihole-dns-shim.lan\", \"127.0.0.1\"]]" \
  -e PIHOLE_TOKEN="" \
  -e PIHOLE_API="http://pi.hole:8080/api" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  theonlysinjin/docker-pihole-dns-shim
```

docker-compose.yml

```docker
services:
  pihole-dns-shim:
    container_name: "pihole-dns-shim"
    image: theonlysinjin/docker-pihole-dns-shim
    restart: unless-stopped
    labels:
      - pihole.custom-record=[["pihole-dns-shim.lan", "127.0.0.1"]]
    environment:
      PIHOLE_TOKEN: "${PIHOLE_TOKEN}"
      PIHOLE_API: "${PIHOLE_API}"
      # LOGGING_LEVEL: "DEBUG"
      # STATE_FILE: "/state/pihole.state"
      # INTERVAL_SECONDS: "10"            # full sync cadence
      # SYNC_MODE: "interval"             # one of: interval, events
      # EVENT_BATCH_INTERVAL_MS: "500"    # process queued containers every N ms
      # DOCKER_EVENT_ACTIONS: "start,stop,die,create,unpause,oom,kill" # filter actions
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
```

### Label

Add records to pihole by labelling your docker containers, you can add as many labels(records) to individual containers as you need.  
An example of the (json-encoded) label is as follows:

```yaml
pihole.custom-record:
  - ["pihole-dns-shim.lan", "127.0.0.1"]
  - ["pihole-dns-shim.lan", "www.google.com"]
```

as a docker label:

```
"pihole.custom-record=[[\"pihole-dns-shim.lan\", \"127.0.0.1\"], [\"pihole-dns-shim.lan\", \"www.google.com\"]]"
```

## Development

### Debug

You can turn on extra logging by setting the log level to DEBUG,  
Set an env variable in the container with `LOGGING_LEVEL="DEBUG"`

### Sync modes

The shim can synchronize in two ways:

- interval: Performs a full scan and sync every `INTERVAL_SECONDS` (default 10s).
- events: On startup performs one full sync, continues running periodic full syncs on `INTERVAL_SECONDS`, and between intervals listens to Docker events and performs incremental, per-container updates batched every `EVENT_BATCH_INTERVAL_MS`.

Configuration via environment variables:

- `SYNC_MODE` (default: `interval`): `interval` or `events`.
- `INTERVAL_SECONDS` (default: `10`): Full sync cadence for both modes.
- `EVENT_BATCH_INTERVAL_MS` (default: `500`): Batch interval for incremental per-container processing in events mode.
- `DOCKER_EVENT_ACTIONS` (optional): Comma-separated list of actions to listen for; defaults to common lifecycle events like `create,start,stop,restart,die,kill,oom,pause,unpause,destroy,rename`.

Event reference: see Docker events for containers in the docs: [Docker events — Containers](https://docs.docker.com/reference/cli/docker/system/events/#containers)

### API Endpoints

Uses the v6 rest api
[Api Docs](http://pi.hole:8080/api/docs)

## Legacy (v5) Configuration

If you are still using Pi-hole v5, use the `theonlysinjin/docker-pihole-dns-shim:pihole-v5` image tag and refer to the previous configuration instructions [here](https://github.com/theonlysinjin/docker-pihole-dns-shim/tree/pihole-v5).

## Upgrading from v5 to v6

- Official Pi-hole v6 upgrade guide: [https://docs.pi-hole.net/docker/upgrading/v5-v6/](https://docs.pi-hole.net/docker/upgrading/v5-v6/)
- **TL;DR of what's changed:**
  - Pi-hole v6 introduces a new REST API and changes to authentication.
  - This project now uses the v6 API and requires an app password or admin password.
  - The old API is no longer supported in the latest image.

## Acknowledgements

Special thanks to [@phyzical](https://github.com/phyzical) for his support and contributions to code changes!
