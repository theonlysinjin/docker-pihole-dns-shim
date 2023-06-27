# docker-pihole-dns-shim
Syncronise records founds through docker labels with pihole's custom dns and cname records.  
# How to get started
## Label
Add records to pihole by labelling your docker containers, you can add as many labels(records) to individual containers as you need.  
An example of the (json-encoded) label is as follows:
```
"pihole.custom-record=[[\"pihole-shim.lan\", \"127.0.0.1\"]]"
```
## Build
```
docker build -t pihole-shim .
```
## Run
```bash
docker run \
  -l "pihole.custom-record=[[\"pihole-shim.lan\", \"127.0.0.1\"]]" \
  -e PIHOLE_TOKEN="" \
  -e PIHOLE_API="http://pi.hole:8080/admin/api.php" \
  -e STATE_FILE="/state/pihole.state" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro pihole-shim
```
docker-compose.yml
```docker
services:
  pihole-shim:
    container_name: "pihole-shim"
    image: pihole-shim
    restart: unless-stopped
    labels:
      - "pihole.custom-record=[[\"pihole-shim.lan\", \"127.0.0.1\"]]"
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
