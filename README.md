# docker-pihole-dns-shim
Syncronise records founds through docker labels with pihole's custom dns and cname records.

[![Build & Push](https://github.com/theonlysinjin/docker-pihole-dns-shim/actions/workflows/build-push.yml/badge.svg?branch=main)](https://github.com/theonlysinjin/docker-pihole-dns-shim/actions/workflows/build-push.yml)
# How to get started
## Label
Add records to pihole by labelling your docker containers, you can add as many labels(records) to individual containers as you need.  
An example of the (json-encoded) label is as follows:
```yaml
pihole.custom-record:
  - ["pihole-dns-shim.lan", "127.0.0.1"]
  - ["pihole-dns-shim.lan", "www.google.com"]
```
as a docker label:
```
"pihole.custom-record=[[\"pihole-dns-shim.lan\", \"127.0.0.1\"] [\"pihole-dns-shim.lan\", \"www.google.com\"]]"
```
## Run
cli
```bash
docker run \
  -l "pihole.custom-record=[[\"pihole-dns-shim.lan\", \"127.0.0.1\"]]" \
  -e PIHOLE_TOKEN="" \
  -e PIHOLE_API="http://pi.hole:8080/admin/api.php" \
  -e STATE_FILE="/state/pihole.state" \
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
      - "pihole.custom-record=[[\"pihole-dns-shim.lan\", \"127.0.0.1\"]]"
    environment:
      PIHOLE_TOKEN: "${PIHOLE_TOKEN}"
      PIHOLE_API: "${PIHOLE_API}"
      # STATE_FILE: "/state/pihole.state"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
```

## API Endpoints
Make a _GET_ request to the following endpoints.  
Replace the parts of the url that are in uppercase.
### Manage A Records
Add new DNS record  
http://pi.hole:8080/admin/api.php?customdns&action=add&ip=IPADDRESS&domain=DOMAIN&auth=XXX

Delete existing DNS record  
http://pi.hole:8080/admin/api.php?customdns&action=delete&ip=IPADDRESS&domain=DOMAIN&auth=XXX

List existing DNS records  
http://pi.hole:8080/admin/api.php?customdns&action=get&auth=XXX

### Manage CNAME Records
Add new CNAME record  
http://pi.hole:8080/admin/api.php?customcname&action=add&domain=DOMAIN&target=TARGET&auth=XXX

Delete existing CNAME record  
http://pi.hole:8080/admin/api.php?customcname&action=delete&domain=DOMAIN&target=TARGET&auth=XXX

List existing CNAME records  
http://pi.hole:8080/admin/api.php?customcname&action=get&auth=XXX
