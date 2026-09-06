import json
import os
import re

import core.settings as settings_mod
from conftest import read_config, write_config
from test_service_authoring import HDR, _manual, _ref, _save

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _http():
    return read_config().get('http') or {}


def _ledger():
    return settings_mod.load_settings().get('managed_middlewares') or {}


def _delete(client, name, force=False):
    return client.delete('/api/services/%s%s' % (name, '?force=1' if force else ''), headers=HDR)


ROUTER_AND_PARENT = """
http:
  routers:
    web:
      rule: Host(`web.example.com`)
      service: pool
  services:
    pool:
      loadBalancer:
        servers:
          - url: http://10.0.0.1:80
    leaf:
      loadBalancer:
        servers:
          - url: http://10.0.0.2:80
    wrap:
      weighted:
        services:
          - name: pool
            weight: 1
          - name: leaf
            weight: 1
"""


def test_the_refusal_names_the_routers_and_the_parents(client):
    write_config(ROUTER_AND_PARENT)
    r = _delete(client, 'pool')
    assert r.status_code == 409, r.get_json()
    body = r.get_json()
    assert body.get('inUseBy') == ['web'], body
    assert body.get('parents') == ['wrap'], body


def test_force_deletes_the_dependent_router_and_its_transport(client):
    write_config("""
http:
  routers:
    web:
      rule: Host(`web.example.com`)
      service: pool
  services:
    pool:
      loadBalancer:
        serversTransport: pool-transport
        servers:
          - url: http://10.0.0.1:80
  serversTransports:
    pool-transport:
      insecureSkipVerify: true
""")
    s = settings_mod.load_settings()
    ledger = dict(s.get('managed_middlewares') or {})
    ledger['tp::pool-transport'] = {'kind': 'transport'}
    settings_mod.save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'], traefik_api_url=s['traefik_api_url'],
        auth_enabled=s['auth_enabled'], password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        managed_middlewares=ledger)

    r = _delete(client, 'pool', force=True)
    assert r.status_code == 200, r.get_json()
    h = _http()
    assert 'web' not in (h.get('routers') or {}), 'the dependent router survived a forced delete'
    assert 'pool' not in (h.get('services') or {})
    assert 'pool-transport' not in (h.get('serversTransports') or {}), \
        'the router transport was left behind, so the shared cleanup was not used'
    assert 'tp::pool-transport' not in _ledger(), 'stale transport ledger entry'


def test_force_strips_the_child_from_a_parent_that_still_has_others(client):
    write_config(ROUTER_AND_PARENT)
    r = _delete(client, 'pool', force=True)
    assert r.status_code == 200, r.get_json()
    wrap = _http()['services'].get('wrap')
    assert wrap, 'a parent with another child left must survive'
    kids = [c['name'] for c in wrap['weighted']['services']]
    assert kids == ['leaf'], kids


def test_force_removes_a_parent_left_empty_and_cascades_upward(client):
    write_config("http:\n  routers: {}\n  services: {}\n")
    assert _save(client, 'pool', [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]).status_code == 200
    assert _save(client, 'wrap', [_ref('pool')]).status_code == 200
    assert _save(client, 'gp', [_ref('wrap')]).status_code == 200

    r = _delete(client, 'pool', force=True)
    assert r.status_code == 200, r.get_json()
    svcs = _http().get('services') or {}
    assert 'wrap' not in svcs, 'a parent left with no children is invalid and must go too'
    assert 'gp' not in svcs, 'the grandparent then had no children either'
    assert not [k for k in _ledger() if k.startswith('svc::')], 'stale ledger entries: %r' % sorted(_ledger())


def test_force_leaves_a_child_another_service_still_uses(client):
    write_config("http:\n  routers: {}\n  services: {}\n")
    assert _save(client, 'pool', [_manual('10.0.0.1:80'), _manual('10.0.0.2:80')]).status_code == 200
    assert _save(client, 'other', [_ref('pool-backend-1'), _manual('10.0.0.9:80')]).status_code == 200

    r = _delete(client, 'pool', force=True)
    assert r.status_code == 200, r.get_json()
    svcs = _http().get('services') or {}
    assert 'pool-backend-1' in svcs, 'a child another service uses must not be deleted'
    assert 'pool-backend-2' not in svcs, 'an unused child should go with its parent'


def test_nothing_on_disk_references_the_service_after_force(client):
    write_config(ROUTER_AND_PARENT)
    assert _delete(client, 'pool', force=True).status_code == 200
    h = _http()
    for rname, rdata in (h.get('routers') or {}).items():
        assert rdata.get('service') != 'pool', rname
    for sname, sdef in (h.get('services') or {}).items():
        for kind in ('weighted', 'mirroring', 'failover'):
            for c in ((sdef.get(kind) or {}).get('services') or []):
                assert c.get('name') != 'pool', sname


def test_the_response_says_what_was_deleted(client):
    write_config(ROUTER_AND_PARENT)
    body = _delete(client, 'pool', force=True).get_json()
    assert body.get('ok') is True
    assert body.get('deleted', {}).get('routers') == ['web'], body
    assert 'pool' in body.get('deleted', {}).get('services', []), body


def test_force_on_an_agent_deletes_the_router_and_strips_the_parent(client, monkeypatch):
    from test_agent_service_authoring import _install
    fake = _install(monkeypatch)
    fake.files['dynamic.yml'] = {'http': {
        'routers': {'web': {'rule': 'Host(`w.example.com`)', 'service': 'pool'}},
        'services': {
            'pool': {'loadBalancer': {'servers': [{'url': 'http://10.0.0.1:80'}]}},
            'leaf': {'loadBalancer': {'servers': [{'url': 'http://10.0.0.2:80'}]}},
            'wrap': {'weighted': {'services': [{'name': 'pool', 'weight': 1}, {'name': 'leaf', 'weight': 1}]}},
        }}}
    before = json.dumps(read_config(), sort_keys=True, default=str)

    r = client.delete('/api/services/pool?agent_id=a1&force=1', headers=HDR)
    assert r.status_code == 200, r.get_json()
    h = fake.files['dynamic.yml']['http']
    assert 'web' not in h['routers'], 'the agent router survived'
    assert 'pool' not in h['services']
    assert [c['name'] for c in h['services']['wrap']['weighted']['services']] == ['leaf']
    assert json.dumps(read_config(), sort_keys=True, default=str) == before, 'the Host config was touched'


def _client_fn(name):
    with open(os.path.join(ROOT, 'static', 'js', 'services.js'), encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'async function ' + name + r'\(.*?\n\}', src, re.S)
    assert m, 'the %s helper moved' % name
    return m.group(0)


def test_the_client_never_forces_on_the_first_attempt():
    body = _client_fn('deleteServiceFromModal')
    assert '_sendServiceDelete(name, false)' in body, 'the first attempt must not force'


def test_the_client_offers_the_dialog_on_a_refusal():
    body = _client_fn('_sendServiceDelete')
    assert 'res.status === 409' in body
    assert 'inUseBy' in body and 'parents' in body, 'the dialog must know both kinds of dependant'
    assert '_sendServiceDelete(name, true)' in body, 'confirming must retry with force'


def test_the_dialog_says_routes_will_be_deleted():
    body = _client_fn('_sendServiceDelete')
    assert re.search(r'[Dd]elete', body) and 'route' in body, \
        'a forced service delete removes routes, and the dialog must say so plainly'


def test_every_touched_file_is_backed_up_before_a_forced_delete(client, monkeypatch, tmp_path):
    import glob
    from core import env
    bk = tmp_path / 'bk'
    bk.mkdir()
    monkeypatch.setattr(env, 'BACKUP_DIR', str(bk))
    write_config(ROUTER_AND_PARENT)
    assert _delete(client, 'pool', force=True).status_code == 200
    fresh = glob.glob(os.path.join(str(bk), '*.bak'))
    assert fresh, 'a forced delete rewrote the config with no backup taken first'
    names = {os.path.basename(f).split('.')[0] for f in fresh}
    assert os.path.basename(env.CONFIG_PATH).split('.')[0] in names, \
        'the backup must be of the file that was rewritten: %r' % sorted(fresh)
