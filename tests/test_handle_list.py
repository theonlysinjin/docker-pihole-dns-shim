import sys, types, importlib


def import_shim_with_docker_stub():
	sys.modules.pop('shim', None)
	docker_stub = types.SimpleNamespace(DockerClient=lambda base_url: object())
	sys.modules['docker'] = docker_stub
	return importlib.import_module('shim')


def test_handleList_adds_new_records_and_flushes(monkeypatch):
	shim = import_shim_with_docker_stub()
	# Isolate globals
	shim.globalList = set()
	shim.globalLastSeen = {}

	# Freeze time for determinism
	monkeypatch.setattr(shim.time, 'time', lambda: 2000000000)
	shim.reapSeconds = 3600

	created = []

	def fake_addObject(obj, existingRecords):
		created.append(obj)
		shim.globalList.add(obj)
		shim.globalLastSeen[obj] = 2000000000

	calls = {"flushed": False}

	def fake_flushList():
		calls["flushed"] = True

	monkeypatch.setattr(shim, 'addObject', fake_addObject)
	monkeypatch.setattr(shim, 'flushList', fake_flushList)

	newGlobalList = {("new.example", "10.0.0.10")}
	existing = {"dns": set(), "cname": set()}

	shim.handleList(newGlobalList, existing)

	assert created == [("new.example", "10.0.0.10")]
	assert ("new.example", "10.0.0.10") in shim.globalList
	assert calls["flushed"] is True


def test_handleList_reaps_old_records_and_defers_recent(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = set()
	shim.globalLastSeen = {}

	# Set reap window to 100 seconds
	shim.reapSeconds = 100

	# Two records: one old, one recent
	old_rec = ("old.example", "10.0.0.20")
	recent_rec = ("recent.example", "10.0.0.21")
	shim.globalList.update({old_rec, recent_rec})
	shim.globalLastSeen[old_rec] = 1000  # very old
	# recent record seen 50s ago, which is < reapSeconds, so it should be deferred
	shim.globalLastSeen[recent_rec] = 2050

	# Now is 2100: old should be reaped (age 110), recent deferred (age 50)
	monkeypatch.setattr(shim.time, 'time', lambda: 2100)

	removed = []

	def fake_removeObject(obj, existing):
		removed.append(obj)
		shim.globalList.remove(obj)

	# Prevent addObject from calling out to API during sync phase
	monkeypatch.setattr(shim, 'addObject', lambda obj, existing: None)
	monkeypatch.setattr(shim, 'removeObject', fake_removeObject)
	monkeypatch.setattr(shim, 'flushList', lambda: None)

	# No currently labeled items
	newGlobalList = set()
	existing = {"dns": set(), "cname": set()}

	shim.handleList(newGlobalList, existing)

	assert old_rec in removed
	assert recent_rec not in removed
	assert old_rec not in shim.globalList
	assert recent_rec in shim.globalList


def test_handleList_syncs_missing_records(monkeypatch):
	shim = import_shim_with_docker_stub()
	shim.globalList = {("synced.example", "10.0.0.30"), ("alias.example", "host.example")}

	added = []

	def fake_addObject(obj, existing):
		added.append(obj)

	monkeypatch.setattr(shim, 'addObject', fake_addObject)
	monkeypatch.setattr(shim, 'flushList', lambda: None)

	# existing records are missing both entries → should be re-added via addObject
	newGlobalList = shim.globalList.copy()
	existing = {"dns": set(), "cname": set()}

	shim.handleList(newGlobalList, existing)

	assert {("synced.example", "10.0.0.30"), ("alias.example", "host.example")} <= set(added)


