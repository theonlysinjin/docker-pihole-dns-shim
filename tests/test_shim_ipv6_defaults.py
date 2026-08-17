import sys, types, importlib


def import_shim_with_docker_stub():
	# Ensure fresh import each time for isolated globals
	sys.modules.pop('shim', None)
	docker_stub = types.SimpleNamespace(DockerClient=lambda base_url: object())
	sys.modules['docker'] = docker_stub
	return importlib.import_module('shim')


def test_ipTest_ipv6_true():
	shim = import_shim_with_docker_stub()
	is_ip, target = shim.ipTest('2001:db8::1')
	assert is_ip is True
	assert target == '2001:db8::1'

	is_ip2, target2 = shim.ipTest('::1')
	assert is_ip2 is True
	assert target2 == '::1'


def test_ipTest_still_rejects_hostnames():
	shim = import_shim_with_docker_stub()
	is_ip, _ = shim.ipTest('not.an.ip')
	assert is_ip is False


def test_parseCustomRecords_single_element_uses_defaults(monkeypatch):
	shim = import_shim_with_docker_stub()
	monkeypatch.setattr(shim, 'defaultTargetV4', '10.0.0.11')
	monkeypatch.setattr(shim, 'defaultTargetV6', '2001:db8::11')

	result = shim.parseCustomRecords([["app.lan"]])

	assert result == {
		("app.lan", "10.0.0.11"),
		("app.lan", "2001:db8::11"),
	}


def test_parseCustomRecords_two_element_entry_unaffected_by_defaults(monkeypatch):
	shim = import_shim_with_docker_stub()
	monkeypatch.setattr(shim, 'defaultTargetV4', '10.0.0.11')
	monkeypatch.setattr(shim, 'defaultTargetV6', '2001:db8::11')

	result = shim.parseCustomRecords([["app.lan", "10.0.0.99"]])

	assert result == {("app.lan", "10.0.0.99")}


def test_parseCustomRecords_single_element_with_only_v4_default_set(monkeypatch):
	shim = import_shim_with_docker_stub()
	monkeypatch.setattr(shim, 'defaultTargetV4', '10.0.0.11')
	monkeypatch.setattr(shim, 'defaultTargetV6', '')

	result = shim.parseCustomRecords([["app.lan"]])

	assert result == {("app.lan", "10.0.0.11")}


def test_parseCustomRecords_mixed_entries_in_one_label(monkeypatch):
	shim = import_shim_with_docker_stub()
	monkeypatch.setattr(shim, 'defaultTargetV4', '10.0.0.11')
	monkeypatch.setattr(shim, 'defaultTargetV6', '2001:db8::11')

	result = shim.parseCustomRecords([["old.lan", "10.0.0.5"], ["new.lan"]])

	assert result == {
		("old.lan", "10.0.0.5"),
		("new.lan", "10.0.0.11"),
		("new.lan", "2001:db8::11"),
	}


def test_addObject_uses_createDns_for_ipv6_target(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()
	shim.globalLastSeen = {}

	captured = {}

	def fake_api_call(endpoint_key, payload=None):
		captured['endpoint_key'] = endpoint_key
		captured['payload'] = payload
		return True, None

	monkeypatch.setattr(shim, 'apiCall', fake_api_call)

	obj = ("app.lan", "2001:db8::11")
	existing = {"dns": set(), "cname": set()}

	shim.addObject(obj, existing)

	assert captured['endpoint_key'] == 'createDns'
	assert captured['payload'] == '2001:db8::11 app.lan'
	assert obj in shim.globalList
