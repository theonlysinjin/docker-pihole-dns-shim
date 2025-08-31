import docker, time, requests, json, socket, os, sys, logging, threading

dockerUrl = os.getenv('DOCKER_URL', "unix://var/run/docker.sock")

client = docker.DockerClient(base_url=dockerUrl)

token = os.getenv('PIHOLE_TOKEN', "")
piholeAPI = os.getenv('PIHOLE_API', "http://pi.hole:8080/api")
statePath = os.getenv('STATE_FILE', "/state/pihole.state")
intervalSeconds = int(os.getenv('INTERVAL_SECONDS', "10"))
syncMode = os.getenv('SYNC_MODE', "interval").lower()
eventBatchIntervalMs = int(os.getenv('EVENT_BATCH_INTERVAL_MS', "500"))
eventActionsEnv = os.getenv('DOCKER_EVENT_ACTIONS')
if eventActionsEnv:
  eventActions = set([a.strip() for a in eventActionsEnv.split(',') if a.strip() != ""])
else:
  # Default set of container actions that can affect running state or configuration
  eventActions = set([
    "create", "start", "stop", "restart", "die", "kill", "oom",
    "pause", "unpause", "destroy", "rename"
  ])

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
sync_lock = threading.Lock()
containerRecords = {}
pending_containers = set()
pending_containers_lock = threading.Lock()

endpoints = {
    "createAuth": {
      "type": "post",
      "endpoint": "/auth",
      "payloadExtractor": lambda payload: payload["session"]["sid"],
    },
    "getAuths": {
      "type": "get",
      "endpoint": "/auth/sessions",
      "payloadExtractor": lambda payload: payload["sessions"],
    },
    "deleteAuth": {
      "type": "delete",
      "endpoint": "/auth/session",
    },
    "dns": {
      "type": "get",
      "endpoint": "/config/dns/hosts",
      "payloadExtractor": lambda payload: payload["config"]["dns"]["hosts"],
    },
    "createDns": {
      "type": "put",
      "endpoint": "/config/dns/hosts",
    },
    "deleteDns": {
      "type": "delete",
      "endpoint": "/config/dns/hosts",
    },
    "cname": {
      "type": "get",
      "endpoint": "/config/dns/cnameRecords",
      "payloadExtractor": lambda payload: payload["config"]["dns"]["cnameRecords"],
    },
    "createCname": {
      "type": "put",
      "endpoint": "/config/dns/cnameRecords",
    },
    "deleteCname": {
      "type": "delete",
      "endpoint": "/config/dns/cnameRecords",
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

sid = None

def apiCall(endpointKey, payload=None):
  endpointDict = endpoints[endpointKey]
  payloadExtractor = endpointDict.get("payloadExtractor", lambda x: x)
  http_method = endpointDict["type"]
  endpoint = "%s%s" %(piholeAPI, endpointDict["endpoint"])
  headers = {
    "sid": sid,
    "User-Agent": "docker-pihole-dns-shim",
  }
  if http_method == "get":
    response = requests.get(endpoint, params=payload, headers=headers)
  elif http_method == "post":
    response = requests.post(endpoint, json=payload, headers=headers)
  elif http_method == "delete":
    response = requests.delete("%s/%s" %(endpoint, payload), headers=headers)
  elif http_method == "put":
    response = requests.put("%s/%s" %(endpoint, payload), headers=headers)

  logger.debug("Response code: %s" %(response.status_code))

  extractedResponse = None

  if response.status_code == 200:
    success = True
    extractedResponse = payloadExtractor(response.json())
    logger.debug("Extracted Response: %s", extractedResponse)
  elif response.status_code == 204 or response.status_code == 201:
    success = True
  else:
    extractedResponse = response.json()
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
  cname = set(tuple(item.split(",", 1)) for item in cnameResult)
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

  if is_ip:
    if obj in existingRecords["dns"]:
      success = True
    else:
      success, result = apiCall("createDns", payload="%s %s" %(target, domain))
  else:
    if obj in existingRecords["cname"]:
      success = True
    else:
      success, result = apiCall("createCname", payload="%s,%s" %(domain,target))

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
  if is_ip:
    if obj not in existingRecords["dns"]:
      success = True
    else:
      success, result = apiCall("deleteDns",payload="%s %s" %(target, domain))
  else:
    if obj not in existingRecords["cname"]:
      success = True
    else:
      success, result = apiCall("deleteCname",payload="%s,%s" %(domain, target))

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

def sync_once():
  with sync_lock:
    logger.info("Running sync")
    logger.debug("Listing containers...")
    containers = client.containers.list()
    newGlobalList = set()
    newContainerRecords = {}
    existingRecords = listExisting()
    for container in containers:
      try:
        customRecordsLabel = container.labels.get("pihole.custom-record")
      except Exception as ex:
        logger.debug("Error reading labels from container %s: %s" % (getattr(container, 'name', 'unknown'), ex))
        continue
      if customRecordsLabel:
        try:
          customRecords = json.loads(customRecordsLabel)
        except Exception as ex:
          logger.error("Invalid JSON in label for container %s: %s" % (getattr(container, 'name', 'unknown'), ex))
          continue
        for cr in customRecords:
          try:
            newGlobalList.add(tuple(cr))
          except Exception as ex:
            logger.error("Invalid record %s on container %s: %s" % (cr, getattr(container, 'name', 'unknown'), ex))
        try:
          newContainerRecords[container.id] = set(tuple(cr) for cr in customRecords)
        except Exception as ex:
          logger.debug("Error building per-container record set for %s: %s" % (getattr(container, 'name', 'unknown'), ex))
    handleList(newGlobalList, existingRecords)
    # Refresh per-container mapping after successful reconciliation
    global containerRecords
    containerRecords = newContainerRecords

def interval_loop(stop_event: threading.Event):
  while not stop_event.is_set():
    sync_once()
    logger.info("Sleeping for %s" % (intervalSeconds))
    # Use event wait to allow timely shutdowns
    stop_event.wait(intervalSeconds)

def events_loop(stop_event: threading.Event):
  logger.info("Starting Docker events listener with actions: %s" % (sorted(list(eventActions))))
  # Build filters for Docker events API
  filters = {"type": "container"}
  if eventActions:
    filters["event"] = list(eventActions)
  while not stop_event.is_set():
    try:
      for event in client.events(decode=True, filters=filters):
        if stop_event.is_set():
          break
        try:
          # docker-py may provide either 'Action' or 'status'
          action = event.get('Action') or event.get('status') or ''
          if action and (not eventActions or action in eventActions):
            container_name = (event.get('Actor') or {}).get('Attributes', {}).get('name', 'unknown')
            container_id = event.get('id') or (event.get('Actor') or {}).get('ID')
            if container_id:
              with pending_containers_lock:
                pending_containers.add(container_id)
              logger.debug("Event '%s' for '%s' queued for incremental sync" % (action, container_name))
        except Exception as inner_ex:
          logger.debug("Error handling event: %s" % (inner_ex))
    except Exception as ex:
      logger.error("Docker events stream error: %s" % (ex))
      # Backoff before retrying the event stream
      time.sleep(5)

def _find_mapping_key_by_prefix(container_id_prefix):
  for key in list(containerRecords.keys()):
    try:
      if key.startswith(container_id_prefix):
        return key
    except Exception:
      continue
  return None

def _get_container_if_running(container_id):
  try:
    container = client.containers.get(container_id)
  except Exception:
    return None
  try:
    running = container.attrs.get('State', {}).get('Running', False)
  except Exception:
    running = False
  return container if running else None

def _get_records_from_label(label_value):
  records = set()
  try:
    if not label_value:
      return records
    parsed = json.loads(label_value)
    for cr in parsed:
      records.add(tuple(cr))
  except Exception as ex:
    logger.error("Invalid JSON in label: %s" % (ex))
  return records

def process_containers_batch(container_ids):
  with sync_lock:
    if not container_ids:
      return
    logger.info("Processing %s container(s) from event queue" % (len(container_ids)))
    existingRecords = listExisting()
    for cid in container_ids:
      # Normalize to full id if we already know it
      mapped_key = _find_mapping_key_by_prefix(cid)
      key_to_use = mapped_key if mapped_key else cid
      container = _get_container_if_running(cid)
      if container is None:
        # Treat as removal of previously contributed records (if any)
        oldRecords = containerRecords.get(key_to_use, set())
        if len(oldRecords) == 0:
          continue
        for rec in list(oldRecords):
          # Only remove if no other container still references this record
          referenced_elsewhere = any((rec in recs) for k, recs in containerRecords.items() if k != key_to_use)
          if not referenced_elsewhere:
            removeObject(rec, existingRecords)
        # Cleanup mapping entry
        if key_to_use in containerRecords:
          del containerRecords[key_to_use]
        continue

      # Running container: add/update records based on label
      try:
        label_value = container.labels.get("pihole.custom-record")
      except Exception as ex:
        logger.debug("Error reading labels from container %s: %s" % (getattr(container, 'name', 'unknown'), ex))
        continue
      if not label_value:
        # No label -> do nothing for running container
        continue
      newRecords = _get_records_from_label(label_value)
      oldRecords = containerRecords.get(container.id, set())

      # Additions: records that are new relative to global list
      for rec in (newRecords - globalList):
        addObject(rec, existingRecords)

      # Removals: records that this container no longer has, and not referenced by others
      for rec in (oldRecords - newRecords):
        referenced_elsewhere = any((rec in recs) for k, recs in containerRecords.items() if k != container.id)
        if not referenced_elsewhere:
          removeObject(rec, existingRecords)

      # Update mapping and global state for this container
      containerRecords[container.id] = newRecords

    flushList()

def events_scheduler_loop(stop_event: threading.Event):
  logger.info("Starting events batch scheduler (interval=%dms)" % (eventBatchIntervalMs))
  interval_seconds = max(eventBatchIntervalMs, 50) / 1000.0
  while not stop_event.is_set():
    # Wait a short interval to check flags while still allowing prompt shutdown
    stop_event.wait(interval_seconds)
    if stop_event.is_set():
      break
    with pending_containers_lock:
      if len(pending_containers) == 0:
        continue
      # Drain the current set
      batch = list(pending_containers)
      pending_containers.clear()
    try:
      process_containers_batch(batch)
    except Exception as ex:
      logger.error("Error during incremental sync batch: %s" % (ex))

if __name__ == "__main__":
  if token == "":
    logger.warning("pihole token is blank, Set a token environment variable PIHOLE_TOKEN")
    sys.exit(1)
  else:
    readState()
    sid = auth()
    cleanSessions()

    logger.info("Sync mode: %s" % (syncMode))

    stop_event = threading.Event()
    threads = []

    # Validate sync mode: only 'interval' or 'events'
    if syncMode not in ["interval", "events"]:
      logger.warning("Unknown SYNC_MODE '%s'. Falling back to 'interval'." % (syncMode))
      syncMode = "interval"

    if syncMode in ["interval"]:
      t = threading.Thread(target=interval_loop, args=(stop_event,), daemon=True)
      threads.append(t)
      t.start()

    if syncMode in ["events"]:
      # Full sync on startup to establish state
      sync_once()
      # Start interval full sync to keep things fresh
      t = threading.Thread(target=interval_loop, args=(stop_event,), daemon=True)
      threads.append(t)
      t.start()
      t = threading.Thread(target=events_loop, args=(stop_event,), daemon=True)
      threads.append(t)
      t.start()
      s = threading.Thread(target=events_scheduler_loop, args=(stop_event,), daemon=True)
      threads.append(s)
      s.start()

    # If no valid mode provided, default to interval for backward compatibility
    if len(threads) == 0:
      logger.warning("Unknown SYNC_MODE '%s'. Falling back to 'interval' mode." % (syncMode))
      t = threading.Thread(target=interval_loop, args=(stop_event,), daemon=True)
      threads.append(t)
      t.start()

    # Keep the main thread alive
    try:
      while True:
        time.sleep(1)
    except KeyboardInterrupt:
      logger.info("Shutdown requested, stopping threads...")
      stop_event.set()
      for t in threads:
        t.join(timeout=3)
