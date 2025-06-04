import docker, time, requests, json, socket, os, sys, logging

dockerUrl = os.getenv('DOCKER_URL', "unix://var/run/docker.sock")

client = docker.DockerClient(base_url=dockerUrl)

token = os.getenv('PIHOLE_TOKEN', "")
piholeAPI = os.getenv('PIHOLE_API', "http://pi.hole:8080/api")
statePath = os.getenv('STATE_FILE', "/state/pihole.state")
intervalSeconds = int(os.getenv('INTERVAL_SECONDS', "10"))

loggingLevel = logging.getLevelName(os.getenv('LOGGING_LEVEL', "INFO"))
logging.basicConfig(
    level=loggingLevel,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

global globalList
globalList = set()

endpoints = {
    "createAuth": {
      "type": "post",
      "endpoint": "/auth",
      "payloadKeys": ["session", "sid"]
    },
    "getAuths": {
      "type": "get",
      "endpoint": "/auth/sessions",
      "payloadKeys": ["sessions"]
    },
    "deleteAuth": {
      "type": "delete",
      "endpoint": "/auth/session",
      "payloadKeys": []
    },
    "dns": {
      "type": "get",
      "endpoint": "/config/dns/hosts",
      "payloadKeys": ["config", "dns", "hosts"]
    },
    "createDns": {
      "type": "put",
      "endpoint": "/config/dns/hosts",
      "payloadKeys": []
    },
    "deleteDns": {
      "type": "delete",
      "endpoint": "/config/dns/hosts",
      "payloadKeys": []
    },
    "cname": {
      "type": "get",
      "endpoint": "/config/dns/cnameRecords",
      "payloadKeys": ["config", "dns", "cnameRecords"]
    },
    "createCname": {
      "type": "put",
      "endpoint": "/config/dns/cnameRecords",
      "payloadKeys": []
    },
    "deleteCname": {
      "type": "delete",
      "endpoint": "/config/dns/cnameRecords",
      "payloadKeys": []
    },
}

def ipTest(ip):
  is_ip = False
  try:
   socket.inet_aton(ip)
   is_ip = True
  except Exception as ex:
    template = "An exception of type {0} occurred. Arguments:\n{1!r}"
    message = template.format(type(ex).__name__, ex.args)
    logger.debug(message)

  return is_ip, ip

def flushList():
  jsonObject = json.dumps(list(globalList), indent=2)
  with open(statePath, "w") as outfile:
    outfile.write(jsonObject)

def readState():
  fileExists = os.path.exists(statePath)
  if fileExists:
    logger.info("Loading existing state...")
    with open(statePath, 'r') as openfile:
      readList = json.load(openfile)
      for obj in readList:
        logger.info("From file (%s): %s" %(type(obj), obj))
        globalList.add(tuple(obj))
  else:
    logger.info("Loading skipped, no db found.")

def printState():
  logger.debug("State")
  logger.debug("-----------")
  for obj in globalList:
    logger.debug(obj)
  logger.debug("-----------")

def extract_from_response(response, key_sequence):
    value = response
    for key in key_sequence:
        value = value[key]
    return value

sid = None

def apiCall(endpointKey, payload=None):
  endpointDict = endpoints[endpointKey]
  payloadKeys = endpointDict["payloadKeys"]
  type = endpointDict["type"]
  endpoint = "%s%s" %(piholeAPI, endpointDict["endpoint"])
  headers = {
    "sid": sid,
    "User-Agent": "docker-pihole-dns-shim",
  }
  if type == "get":
    response = requests.get(endpoint, params=payload, headers=headers)
  elif type == "post":
    response = requests.post(endpoint, json=payload, headers=headers)
  elif type == "delete":
    response = requests.delete("%s/%s" %(endpoint, payload), headers=headers)
  elif type == "put":
    response = requests.put("%s/%s" %(endpoint, payload), headers=headers)

  logger.debug("Response code: %s" %(response.status_code))

  extractedResponse = None

  if response.status_code == 200 :
    success = True
    extractedResponse =  extract_from_response(response.json(), payloadKeys)
    logger.debug("Extracted Response: %s", extractedResponse)
  elif response.status_code == 204:
    success = True
  else:
    success = False

  return(success, extractedResponse)

def auth():
  logger.debug("Authenticating with pihole API...")
  success, response = apiCall("createAuth", payload={"password": token})
  if not success:
    logger.error("Authentication failed: %s" %(response))
    sys.exit(1)
  logger.debug("done")
  return response

def cleanSessions():
  logger.debug("Removing old sessions...")
  success, sessions = apiCall("getAuths")
  if not success:
    logger.error("Failed to fetch sessions: %s" %(sessions))
    return
  for session in sessions:
    if session["current_session"] == False and session["user_agent"] == "docker-pihole-dns-shim":
      logger.debug("Removing session: %s" %(session["id"]))
      success, response = apiCall("deleteAuth", payload=session["id"])
      if not success:
        logger.error("Failed to delete session %s: %s" %(session, response))
  logger.debug("done")

def listExisting():
  logger.debug("Fetching current records...")

  dnsSuccess, dnsResult = apiCall("dns")
  dns = set(tuple(item.split(" ", 1)[::-1]) for item in dnsResult)
  logger.debug("DNS Records: %s" %(dns))

  cnameSuccess, cnameResult = apiCall("cname")
  cname = set(tuple(item.split(" ", 1)[::-1]) for item in cnameResult)
  logger.debug("CName Records: %s" %(cname))

  logger.debug("done")
  return({"dns": dns, "cname": cname})

def addObject(obj, existingRecords):
  domain = False
  logger.info("Adding: " + str(obj))
  domain = obj[0]
  is_ip, target = ipTest(obj[1])
  logger.debug("domain (%s): %s" %(type(domain), domain))
  logger.debug("target (%s): %s" %(type(target), target))
  logger.debug("is_ip: %s" %(str(is_ip)))
  payload="%s %s" %(target, domain)

  if is_ip:
    if obj in existingRecords["dns"]:
      success = True
    else:
      success, result = apiCall("createDns", payload=payload)
  else:
    if obj in existingRecords["cname"]:
      success = True
    else:
      success, result = apiCall("createCname", payload=payload)

  if success or ("error" in result and "message" in result["error"] and result["error"]["message"] == "Item already present"):
    globalList.add(obj)
    logger.info("Added to global list after success: %s" %(str(obj)))
  else:
    logger.error("Failed to add to list: %s" %(str(result)))

def removeObject(obj, existingRecords):
  logger.info("Removing: " + str(obj))
  domain = obj[0]
  is_ip, target = ipTest(obj[1])
  logger.debug("domain (%s): %s" %(type(domain), domain))
  logger.debug("target (%s): %s" %(type(target), target))
  logger.debug("is_ip: %s" %(str(is_ip)))
  payload="%s %s" %(target, domain)

  if is_ip:
    if obj not in existingRecords["dns"]:
      success = True
    else:
      success, result = apiCall("deleteDns",payload=payload)
  else:
    if obj not in existingRecords["cname"]:
      success = True
    else:
      success, result = apiCall("deleteCname",payload=payload)

  if success:
    globalList.remove(obj)
    logger.info("Removed from global list after success: %s" %(str(obj)))
  else:
    logger.error("Failed to remove from list: %s" %(str(result)))

def handleList(newGlobalList, existingRecords):
  toAdd = set([x for x in newGlobalList if x not in globalList])
  toRemove = set([x for x in globalList if x not in newGlobalList])
  toSync = set([x for x in globalList if ((x not in existingRecords["dns"]) and (x not in existingRecords["cname"]))])

  logger.debug("These are labels to add: %s" %(toAdd))
  if len(toAdd) > 0:
    for add in toAdd:
      addObject(add, existingRecords)

  logger.debug("These are labels to remove: %s" %(toRemove))
  if len(toRemove) > 0:
    for remove in toRemove:
      removeObject(remove, existingRecords)

  logger.debug("These are labels to sync: %s" %(toSync))
  if len(toSync) > 0:
    for sync in (toSync-toAdd-toRemove):
      addObject(sync, existingRecords)

  printState()
  flushList()

if __name__ == "__main__":
  if token == "":
    logger.warning("pihole token is blank, Set a token environment variable PIHOLE_TOKEN")
    sys.exit(1)

  else:
    readState()
    sid = auth()
    cleanSessions()

    while True:
      logger.info("Running sync")
      logger.debug("Listing containers...")
      containers = client.containers.list()
      globalListBefore = globalList.copy()
      newGlobalList = set()
      existingRecords = listExisting()
      for container in containers:
        customRecordsLabel = container.labels.get("pihole.custom-record")
        if customRecordsLabel:
          customRecords = json.loads(customRecordsLabel)
          for cr in customRecords:
            newGlobalList.add(tuple(cr))

      handleList(newGlobalList, existingRecords)
      logger.info("Sleeping for %s" %(intervalSeconds))
      time.sleep(intervalSeconds)
