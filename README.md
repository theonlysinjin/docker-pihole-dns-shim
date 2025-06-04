# docker-pihole-dns-shim

Synchronise records founds through docker labels with pihole's custom dns and cname records.  

## NOTE

- This is now configured to work with pihole v6 as the old api is no longer allowed.

## How to get started

### Find your secret pihole token

- Navigate to the [api tab](http://pi.hole:8080/admin/settings/api) in your pihole settings
- Click the `Basic` button to change to `Expert`
- Click the `Configure app password`
- Copy the new app password and save it, NOTE: this will also change your login password to be this app token...
- Click `Replace app password`
- Use this as `PIHOLE_TOKEN`

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
