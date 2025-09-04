import sys, types, importlib, json


def import_shim_with_docker_stub():
	# Fresh import for clean globals
	sys.modules.pop('shim', None)
	# Minimal docker stub to satisfy import
	docker_stub = types.SimpleNamespace(DockerClient=lambda base_url: object())
	sys.modules['docker'] = docker_stub
	return importlib.import_module('shim')


def test_readState_parses_legacy_list_format(tmp_path, monkeypatch):
	shim = import_shim_with_docker_stub()
	# Freeze time so last_seen is deterministic
	monkeypatch.setattr(shim.time, 'time', lambda: 1700000000)
	shim.globalList = set()
	shim.globalLastSeen = {}

	state_file = tmp_path / 'pihole.state'
	legacy = [
		["example.lan", "10.0.0.1"],
		["alias.lan", "app.lan"],
	]
	state_file.write_text(json.dumps(legacy))
	shim.statePath = str(state_file)

	shim.readState()

	expected = {("example.lan", "10.0.0.1"), ("alias.lan", "app.lan")}
	assert shim.globalList == expected
	for tup in expected:
		assert shim.globalLastSeen.get(tup) == 1700000000


def test_readState_parses_v1_owned_sets_last_seen_now(tmp_path, monkeypatch):
	shim = import_shim_with_docker_stub()
	monkeypatch.setattr(shim.time, 'time', lambda: 1800000000)
	shim.globalList = set()
	shim.globalLastSeen = {}

	state_file = tmp_path / 'pihole.state'
	v1 = {
		"version": 1,
		"owned": [["v1.lan", "10.0.0.2"], ["v1alias.lan", "v1target.lan"]],
	}
	state_file.write_text(json.dumps(v1))
	shim.statePath = str(state_file)

	shim.readState()

	expected = {("v1.lan", "10.0.0.2"), ("v1alias.lan", "v1target.lan")}
	assert shim.globalList == expected
	for tup in expected:
		assert shim.globalLastSeen.get(tup) == 1800000000


def test_readState_parses_v2_owned_and_last_seen(tmp_path):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()
	shim.globalLastSeen = {}

	state_file = tmp_path / 'pihole.state'
	v2 = {
		"version": 2,
		"owned": [["v2.lan", "10.0.0.3"], ["v2alias.lan", "v2target.lan"]],
		"last_seen": [["v2.lan", "10.0.0.3", 1900000000]],
	}
	state_file.write_text(json.dumps(v2))
	shim.statePath = str(state_file)

	shim.readState()

	assert shim.globalList == {("v2.lan", "10.0.0.3"), ("v2alias.lan", "v2target.lan")}
	assert shim.globalLastSeen.get(("v2.lan", "10.0.0.3")) == 1900000000
	# Entry without last_seen provided should be absent from map
	assert ("v2alias.lan", "v2target.lan") not in shim.globalLastSeen


