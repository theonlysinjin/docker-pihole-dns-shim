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


