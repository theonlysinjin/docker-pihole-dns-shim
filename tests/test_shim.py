import sys, types, importlib
import time


def import_shim_with_docker_stub():
	# Ensure fresh import each time for isolated globals
	sys.modules.pop('shim', None)
	# Provide a minimal docker stub so importing shim doesn't require docker SDK
	docker_stub = types.SimpleNamespace(DockerClient=lambda base_url: object())
	sys.modules['docker'] = docker_stub
	return importlib.import_module('shim')


def test_ipTest_ipv4_true_and_invalid_false():
	shim = import_shim_with_docker_stub()
	is_ip, target = shim.ipTest('10.0.0.11')
	assert is_ip is True
	assert target == '10.0.0.11'

	is_ip2, _ = shim.ipTest('not.an.ip')
	assert is_ip2 is False


def test_addObject_uses_createDns_for_ip_and_formats_payload(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()
	shim.globalLastSeen = {}

	captured = {}

	def fake_api_call(endpoint_key, payload=None):
		captured['endpoint_key'] = endpoint_key
		captured['payload'] = payload
		return True, None

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	obj = ("speedtest.example.com", "10.0.0.11")
	existing = {"dns": set(), "cname": set()}

	shim.addObject(obj, existing)

	assert captured['endpoint_key'] == 'createDns'
	assert captured['payload'] == '10.0.0.11 speedtest.example.com'
	assert obj in shim.globalList
	assert obj in shim.globalLastSeen
	assert isinstance(shim.globalLastSeen[obj], int)


def test_addObject_uses_createCname_for_hostname_and_formats_payload(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()
	shim.globalLastSeen = {}

	captured = {}

	def fake_api_call(endpoint_key, payload=None):
		captured['endpoint_key'] = endpoint_key
		captured['payload'] = payload
		return True, None

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	obj = ("alias.lan", "app.lan")
	existing = {"dns": set(), "cname": set()}

	shim.addObject(obj, existing)

	assert captured['endpoint_key'] == 'createCname'
	assert captured['payload'] == 'alias.lan,app.lan'
	assert obj in shim.globalList
	assert obj in shim.globalLastSeen
	assert isinstance(shim.globalLastSeen[obj], int)


def test_listExisting_parses_dns_and_cname_sets(monkeypatch):
	shim = import_shim_with_docker_stub()

	def fake_api_call(endpoint_key, payload=None):
		if endpoint_key == 'dns':
			return True, [
				'10.0.0.11 speedtest.example.com',
				'1.2.3.4 a.example'
			]
		elif endpoint_key == 'cname':
			return True, [
				'alias.lan,app.lan'
			]
		else:
			assert False, f"Unexpected endpoint {endpoint_key}"

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	result = shim.listExisting()
	assert result["dns"] == {
		("speedtest.example.com", "10.0.0.11"),
		("a.example", "1.2.3.4"),
	}
	assert result["cname"] == {("alias.lan", "app.lan")}


def test_removeObject_calls_delete_for_ip_and_cname(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()

	calls = []

	def fake_api_call(endpoint_key, payload=None):
		calls.append((endpoint_key, payload))
		return True, None

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	# IP/A record deletion
	ip_obj = ("host.lan", "10.0.0.9")
	shim.globalList.add(ip_obj)
	existing = {"dns": {ip_obj}, "cname": set()}
	shim.removeObject(ip_obj, existing)
	assert ("deleteDns", "10.0.0.9 host.lan") in calls
	assert ip_obj not in shim.globalList

	# CNAME deletion
	calls.clear()
	cname_obj = ("alias.lan", "app.lan")
	shim.globalList.add(cname_obj)
	existing2 = {"dns": set(), "cname": {cname_obj}}
	shim.removeObject(cname_obj, existing2)
	assert ("deleteCname", "alias.lan,app.lan") in calls
	assert cname_obj not in shim.globalList


def test_main_run_once_calls_sync_once_and_exits(monkeypatch):
	shim = import_shim_with_docker_stub()

	# Bypass env-based config requirements
	shim.token = "token"

	# Avoid touching disk/network during the test
	monkeypatch.setattr(shim, 'readState', lambda: None)
	monkeypatch.setattr(shim, 'auth', lambda: "sid")
	monkeypatch.setattr(shim, 'cleanSessions', lambda: None)

	called = []
	monkeypatch.setattr(shim, 'sync_once', lambda allow_remove=True: called.append(allow_remove))
	monkeypatch.setattr(shim.time, 'sleep', lambda _: (_ for _ in ()).throw(AssertionError("sleep should not be called in --run-once")))

	rc = shim.main(["--run-once"])
	assert rc == 0
	assert called == [True]


def test_main_run_once_no_remove_sets_allow_remove_false(monkeypatch):
	shim = import_shim_with_docker_stub()

	shim.token = "token"
	monkeypatch.setattr(shim, 'readState', lambda: None)
	monkeypatch.setattr(shim, 'auth', lambda: "sid")
	monkeypatch.setattr(shim, 'cleanSessions', lambda: None)

	called = []
	monkeypatch.setattr(shim, 'sync_once', lambda allow_remove=True: called.append(allow_remove))

	rc = shim.main(["--run-once", "--no-remove"])
	assert rc == 0
	assert called == [False]


def test_userAgent_without_instance_id():
	shim = import_shim_with_docker_stub()
	shim.instanceId = ""
	assert shim.userAgent() == "docker-pihole-dns-shim"


def test_userAgent_with_instance_id():
	shim = import_shim_with_docker_stub()
	shim.instanceId = "abc-123"
	assert shim.userAgent() == "docker-pihole-dns-shim/abc-123"


def test_readState_returns_persisted_instance_id(tmp_path):
	import json
	shim = import_shim_with_docker_stub()
	state_file = tmp_path / "pihole.state"
	state_file.write_text(json.dumps({
		"version": 2,
		"owned": [["app.lan", "10.0.0.1"]],
		"last_seen": [["app.lan", "10.0.0.1", 1700000000]],
		"instance_id": "test-instance-99",
	}))
	shim.statePath = str(state_file)
	returned = shim.readState()
	assert returned == "test-instance-99"
	assert ("app.lan", "10.0.0.1") in shim.globalList


def test_readState_returns_none_when_no_instance_id(tmp_path):
	import json
	shim = import_shim_with_docker_stub()
	state_file = tmp_path / "pihole.state"
	state_file.write_text(json.dumps({
		"version": 2,
		"owned": [],
		"last_seen": [],
	}))
	shim.statePath = str(state_file)
	returned = shim.readState()
	assert returned is None


def test_readState_legacy_list_returns_none(tmp_path):
	import json
	shim = import_shim_with_docker_stub()
	state_file = tmp_path / "pihole.state"
	state_file.write_text(json.dumps([["app.lan", "10.0.0.1"]]))
	shim.statePath = str(state_file)
	returned = shim.readState()
	assert returned is None
	assert ("app.lan", "10.0.0.1") in shim.globalList


def test_cleanSessions_only_removes_own_agent_sessions(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.instanceId = "my-instance"

	sessions = [
		{"id": "s1", "current_session": False, "user_agent": "docker-pihole-dns-shim/my-instance"},
		{"id": "s2", "current_session": True,  "user_agent": "docker-pihole-dns-shim/my-instance"},
		{"id": "s3", "current_session": False, "user_agent": "docker-pihole-dns-shim/other-instance"},
		{"id": "s4", "current_session": False, "user_agent": "docker-pihole-dns-shim"},
	]

	deleted = []

	def fake_api_call(endpoint_key, payload=None):
		if endpoint_key == "getAuths":
			return True, sessions
		if endpoint_key == "deleteAuth":
			deleted.append(payload)
			return True, None
		return True, None

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	shim.cleanSessions()

	# Only s1 should be deleted: not current, matches own user agent
	assert deleted == ["s1"]


def test_main_instance_id_resolution_prefers_env(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.token = "token"
	shim.shimInstanceIdEnv = "env-id"

	monkeypatch.setattr(shim, 'readState', lambda: "persisted-id")
	monkeypatch.setattr(shim, 'auth', lambda: "sid")
	monkeypatch.setattr(shim, 'cleanSessions', lambda: None)
	monkeypatch.setattr(shim, 'sync_once', lambda allow_remove=True: None)

	shim.main(["--run-once"])
	assert shim.instanceId == "env-id"


def test_main_instance_id_resolution_uses_persisted_over_generated(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.token = "token"
	shim.shimInstanceIdEnv = ""

	monkeypatch.setattr(shim, 'readState', lambda: "persisted-id")
	monkeypatch.setattr(shim, 'auth', lambda: "sid")
	monkeypatch.setattr(shim, 'cleanSessions', lambda: None)
	monkeypatch.setattr(shim, 'sync_once', lambda allow_remove=True: None)

	shim.main(["--run-once"])
	assert shim.instanceId == "persisted-id"


def test_main_instance_id_generated_when_nothing_persisted(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.token = "token"
	shim.shimInstanceIdEnv = ""

	monkeypatch.setattr(shim, 'readState', lambda: None)
	monkeypatch.setattr(shim, 'auth', lambda: "sid")
	monkeypatch.setattr(shim, 'cleanSessions', lambda: None)
	monkeypatch.setattr(shim, 'sync_once', lambda allow_remove=True: None)

	shim.main(["--run-once"])
	assert shim.instanceId != ""
	# Should look like a UUID
	import uuid
	uuid.UUID(shim.instanceId)  # raises if invalid

