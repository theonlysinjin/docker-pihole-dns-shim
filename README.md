# docker-pihole-dns-shim

Easily synchronise records founds through docker labels with pihole's custom dns and cname records.  


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

### API Endpoints

Uses the v6 rest api
[Api Docs](http://pi.hole:8080/api/docs)

## Legacy (v5) Configuration

If you are still using Pi-hole v5, use the `theonlysinjin/docker-pihole-dns-shim:pihole-v5` image tag and refer to the previous configuration instructions [here](https://github.com/theonlysinjin/docker-pihole-dns-shim/tree/pihole-v5).

## Upgrading from v5 to v6

- Official Pi-hole v6 upgrade guide: [https://docs.pi-hole.net/v6/upgrade/](https://docs.pi-hole.net/v6/upgrade/)
- **TL;DR of what's changed:**
  - Pi-hole v6 introduces a new REST API and changes to authentication.
  - This project now uses the v6 API and requires an app password or admin password.
  - The old API is no longer supported in the latest image.
