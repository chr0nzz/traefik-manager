import json

import core.agents_store as store
import core.settings as settings_mod
from core import service_ownership as own

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
AGENT = {'id': 'a1', 'name': 'edge', 'url': 'http://a1:8090', 'api_key': 'k'}


class _FakeAgent:

    def __init__(self):
        self.files = {'dynamic.yml': {'http': {'routers': {}, 'services': {}}}}
        self.writes = []

    def load(self, agent):
        import copy
        return copy.deepcopy(self.files)

    def write(self, agent, filename, cfg):
        import copy
        self.files[filename] = copy.deepcopy(cfg)
        self.writes.append(filename)


def _install(monkeypatch):
    store.save_agents_file([AGENT])
    fake = _FakeAgent()
    import app as A
    monkeypatch.setattr(A, '_agent_load_configs', fake.load)
    monkeypatch.setattr(A, '_agent_write_config', fake.write)
    return fake


def _svcs(fake):
    return sorted((fake.files['dynamic.yml'].get('http') or {}).get('services') or {})


def _manual(addr, weight=1):
    return {'kind': 'manual', 'address': addr, 'scheme': 'http', 'weight': weight, 'percent': 0}


def _ledger():
    return settings_mod.load_settings().get('managed_middlewares') or {}


def test_a_service_can_be_created_on_an_agent(client, monkeypatch):
    fake = _install(monkeypatch)
    r = client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})
    assert r.status_code == 200, r.get_json()
    assert _svcs(fake) == ['pool', 'pool-backend-1', 'pool-backend-2'], \
        'the service was not written to the agent'
    assert fake.writes, 'nothing was pushed to the agent'


def test_agent_ownership_is_recorded_under_the_agent_namespace(client, monkeypatch):
    _install(monkeypatch)
    client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})
    keys = _ledger()
    assert own.ledger_key('pool', 'a1') in keys, \
        'the agent ledger entry must be namespaced: %r' % sorted(keys)
    assert own.ledger_key('pool') not in keys, \
        'an agent service must not claim the Host key'


def test_a_service_can_be_deleted_on_an_agent(client, monkeypatch):
    fake = _install(monkeypatch)
    client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})
    r = client.delete('/api/services/pool?agent_id=a1', headers=HDR)
    assert r.status_code == 200, r.get_json()
    assert _svcs(fake) == [], 'the service was not removed from the agent'
    assert own.ledger_key('pool', 'a1') not in _ledger()


def test_an_agent_service_can_be_adopted(client, monkeypatch):
    fake = _install(monkeypatch)
    fake.files['dynamic.yml']['http']['services'] = {
        'theirs': {'weighted': {'services': [{'name': 'a', 'weight': 1}]}},
        'a': {'loadBalancer': {'servers': [{'url': 'http://10.0.0.9:80'}]}},
    }
    r = client.post('/api/services/theirs/ownership?agent_id=a1', headers=HDR,
                    json={'adopt': True})
    assert r.status_code == 200, r.get_json()
    assert own.ledger_key('theirs', 'a1') in _ledger()


def test_the_host_is_untouched_when_authoring_on_an_agent(client, monkeypatch):
    from conftest import read_config
    _install(monkeypatch)
    before = json.dumps(read_config(), sort_keys=True, default=str)
    client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})
    assert json.dumps(read_config(), sort_keys=True, default=str) == before, \
        'authoring on an agent wrote to the Host config'


def test_an_agent_route_reports_its_service_as_owned(client, monkeypatch):
    fake = _install(monkeypatch)
    client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})
    fake.files['dynamic.yml']['http']['routers'] = {
        'web': {'rule': 'Host(`web.example.com`)', 'service': 'pool'}}

    import app as A
    monkeypatch.setattr(A, '_agent_request', lambda *a, **k: _StubResp())
    r = client.get('/api/agents/a1/routes')
    assert r.status_code == 200, r.get_data(as_text=True)
    apps = r.get_json().get('apps') or []
    web = [a for a in apps if a.get('name') == 'web']
    assert web, 'the agent route was not returned: %r' % [a.get('name') for a in apps]
    assert web[0].get('serviceOwned') is True, \
        'ownership is recorded under agent_a1::svc::pool but checked without the namespace'


class _StubResp:
    ok = True
    status_code = 200
    text = '{}'

    def json(self):
        return {}


def test_the_client_sends_the_agent_id_rather_than_proxying():
    import os
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, 'static', 'js', 'services.js'), encoding='utf-8').read()

    for call in re.findall(r"agentFetch\('/api/services[^']*'", src):
        raise AssertionError(
            'service authoring must go to the Host with an agent_id, not proxy to the '
            'agent, which has no such endpoint: %s' % call)

    save = src[src.index("fetch('/api/services'"):][:600]
    assert 'agent_id' in save, 'the save body must carry the selected agent'
    assert '_csrfHeaders()' in save, 'the save lost its CSRF header when it left agentFetch'

    for name in ('_setServiceOwnership', 'deleteServiceFromModal'):
        body = re.search(r'async function ' + name + r'\(.*?\n\}', src, re.S).group(0)
        assert '_svcApiPath(' in body, '%s must pass the agent id' % name
        assert '_csrfHeaders()' in body, '%s lost its CSRF header' % name


def test_the_services_list_reports_ownership_for_an_agent(client, monkeypatch):
    _install(monkeypatch)
    client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted', 'agent_id': 'a1',
        'children': [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]})

    import app as A
    monkeypatch.setattr(A, '_agent_request', lambda *a, **k: _StubResp())
    r = client.get('/api/traefik/services?agent_id=a1')
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert 'pool' in (body.get('ownedServices') or []), \
        'the agent list must report what is managed there: %r' % body.get('ownedServices')
    assert 'pool-backend-1' in (body.get('ownedChildren') or []), \
        'generated children must be reported so the list can fold them into their parent'


def test_the_client_lists_services_through_the_host():
    import os
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, 'static', 'js', 'services.js'), encoding='utf-8').read()
    assert "agentFetch('/api/traefik/services')" not in src, (
        'proxying the list to the agent loses ownership, since the ledger lives on the Host')
    assert re.search(r"fetch\(_svcApiPath\('/api/traefik/services'\)", src), \
        'the list must be fetched from the Host with the agent id'


def test_a_middleware_rename_cascades_on_an_agent(client, monkeypatch):
    fake = _install(monkeypatch)
    fake.files['dynamic.yml']['http']['middlewares'] = {'auth': {'basicAuth': {'users': ['u:x']}}}
    fake.files['other.yml'] = {'http': {'routers': {
        'web': {'rule': 'Host(`w.example.com`)', 'service': 'x', 'middlewares': ['auth']}}}}

    r = client.post('/save-middleware', data={
        'csrf_token': 'testtoken', 'agent_id': 'a1', 'middlewareName': 'authelia',
        'isMwEdit': 'true', 'originalMwId': 'auth', 'mwProtocol': 'http',
        'originalMwProtocol': 'http', 'configFile': 'dynamic.yml',
        'middlewareContent': "basicAuth:\n  users: ['u:x']\n"}, headers=HDR)
    assert r.status_code in (200, 302), r.get_data(as_text=True)

    mws = fake.files['other.yml']['http']['routers']['web'].get('middlewares')
    assert mws == ['authelia'], \
        'the agent router in another file kept the old name: %r' % mws


def test_deleting_a_used_middleware_on_an_agent_is_refused(client, monkeypatch):
    fake = _install(monkeypatch)
    fake.files['dynamic.yml']['http']['middlewares'] = {'auth': {'basicAuth': {'users': ['u:x']}}}
    fake.files['dynamic.yml']['http']['routers'] = {
        'web': {'rule': 'Host(`w.example.com`)', 'service': 'x', 'middlewares': ['auth']}}

    r = client.post('/delete-middleware/auth',
                    data={'csrf_token': 'testtoken', 'agent_id': 'a1'}, headers=HDR)
    assert r.status_code == 409, r.get_data(as_text=True)
    assert 'auth' in (fake.files['dynamic.yml']['http'].get('middlewares') or {}), \
        'the middleware was deleted on the agent despite being in use'


def test_force_deleting_on_an_agent_strips_the_reference(client, monkeypatch):
    fake = _install(monkeypatch)
    fake.files['dynamic.yml']['http']['middlewares'] = {'auth': {'basicAuth': {'users': ['u:x']}}}
    fake.files['dynamic.yml']['http']['routers'] = {
        'web': {'rule': 'Host(`w.example.com`)', 'service': 'x', 'middlewares': ['auth']}}

    r = client.post('/delete-middleware/auth',
                    data={'csrf_token': 'testtoken', 'agent_id': 'a1', 'force': 'true'},
                    headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in (fake.files['dynamic.yml']['http'].get('middlewares') or {})
    assert not fake.files['dynamic.yml']['http']['routers']['web'].get('middlewares'), \
        'the agent router kept a reference to a middleware that no longer exists'
