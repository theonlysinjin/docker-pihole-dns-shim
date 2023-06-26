# docker-pihole-dns-shim
Get you dns records into pihole with docker labels

# How To
## To Build
```
docker build -t shim .
```
## To Run
```
docker run -e PIHOLE_TOKEN="" -e PIHOLE_API="http://pi.hole:8080/admin/api.php" -v $PWD:/app/ -v /var/run/docker.sock:/var/run/docker.sock:ro shim
```

# API Endpoints
## A
Add new DNS record
http://ADDRESSOFPIHOLE/admin/api.php?customdns&action=add&ip=IPADDRESS&domain=youdomain&auth=XXX

Delete existing DNS record
http://ADDRESSOFPIHOLE/admin/api.php?customdns&action=delete&ip=IPADDRESS&domain=youdomain&auth=XXX

List existing DNS records
http://ADDRESSOFPIHOLE/admin/api.php?customdns&action=get&auth=XXX

## CNAME
Add new CNAME record
http://ADDRESSOFPIHOLE/admin/api.php?customcname&action=add&domain=YOURCNAME&target=TARGETDOMAIN&auth=XXX

Delete existing CNAME record
http://ADDRESSOFPIHOLE/admin/api.php?customcname&action=delete&domain=YOURCNAME&target=TARGETDOMAIN&auth=XXX

List existing CNAME records
http://ADDRESSOFPIHOLE/admin/api.php?customcname&action=get&auth=XXX
