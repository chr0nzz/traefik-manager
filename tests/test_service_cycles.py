import json

from conftest import post_form, read_config, write_config
from test_service_authoring import HDR, _manual, _ref, _save, _svc


def _all_services():
    return (read_config().get('http') or {}).get('services') or {}


def test_a_service_cannot_reference_itself(client):
    r = _save(client, 'pihole', [_ref('pihole')])
    assert r.status_code == 400, r.get_json()
    assert 'itself' in (r.get_json() or {}).get('error', '').lower(), r.get_json()
    assert _svc('pihole') is None, 'the self-referential service was written to disk'


def test_a_service_cannot_reference_itself_alongside_real_backends(client):
    r = _save(client, 'pihole', [_manual('10.0.0.1:80'), _ref('pihole')])
    assert r.status_code == 400, r.get_json()
    assert _svc('pihole') is None


def test_a_two_hop_cycle_is_refused(client):
    write_config("""
http:
  routers: {}
  services:
    leaf:
      loadBalancer:
        servers:
          - url: http://10.0.0.9:80
""")
    r = _save(client, 'a', [_ref('leaf')])
    assert r.status_code == 200, r.get_json()
    r = _save(client, 'b', [_ref('a')])
    assert r.status_code == 200, r.get_json()

    r = _save(client, 'a', [_ref('b')], originalName='a')
    assert r.status_code == 400, 'a -> b -> a was written: %r' % r.get_json()
    assert 'cycle' in (r.get_json() or {}).get('error', '').lower() or \
           'itself' in (r.get_json() or {}).get('error', '').lower(), r.get_json()
    kids = [c['name'] for c in _svc('a')['weighted']['services']]
    assert kids == ['leaf'], 'the original wiring must survive a refused save: %r' % kids


def test_a_legitimate_chain_still_saves(client):
    write_config("""
http:
  routers: {}
  services:
    leaf:
      loadBalancer:
        servers:
          - url: http://10.0.0.9:80
""")
    assert _save(client, 'a', [_ref('leaf')]).status_code == 200
    assert _save(client, 'b', [_ref('a')]).status_code == 200
    assert _save(client, 'c', [_ref('b'), _ref('leaf')]).status_code == 200


def test_the_route_form_cannot_point_a_service_at_itself(client):
    write_config("http:\n  routers: {}\n  services: {}\n")
    r = post_form(client, '/save', serviceName='pihole', subdomain='pihole.example.com',
                  protocol='http', scheme='http', certResolver='letsencrypt',
                  targetIp='10.0.0.1', targetPort='8080',
                  backendsJsonHttp=json.dumps({'compositeType': 'weighted', 'children': [
                      {'kind': 'service', 'name': 'pihole-service', 'weight': 1, 'percent': 0}]}))
    assert r.status_code >= 400, \
        'the route form wrote a service that references itself: %r' % r.get_json()
    svcs = _all_services()
    for name, block in svcs.items():
        for kind in ('weighted', 'mirroring', 'failover'):
            for child in ((block.get(kind) or {}).get('services') or []):
                assert child.get('name') != name, 'self reference on disk: %s' % name


def test_an_agent_service_cannot_reference_itself(client, monkeypatch):
    from test_agent_service_authoring import _install, _svcs
    fake = _install(monkeypatch)
    r = client.post('/api/services', headers=HDR, json={
        'name': 'pihole', 'type': 'weighted', 'agent_id': 'a1',
        'children': [{'kind': 'service', 'name': 'pihole', 'weight': 1, 'percent': 0}]})
    assert r.status_code == 400, r.get_json()
    assert _svcs(fake) == [], 'the self-referential service was written to the agent'
    assert fake.writes == [], 'nothing should have been pushed to the agent'


def test_an_agent_two_hop_cycle_is_refused(client, monkeypatch):
    from test_agent_service_authoring import _install
    fake = _install(monkeypatch)
    fake.files['dynamic.yml']['http']['services'] = {
        'leaf': {'loadBalancer': {'servers': [{'url': 'http://10.0.0.9:80'}]}},
        'a': {'weighted': {'services': [{'name': 'leaf', 'weight': 1}]}},
        'b': {'weighted': {'services': [{'name': 'a', 'weight': 1}]}},
    }
    client.post('/api/services/a/ownership?agent_id=a1', headers=HDR, json={'adopt': True})
    r = client.post('/api/services', headers=HDR, json={
        'name': 'a', 'type': 'weighted', 'originalName': 'a', 'agent_id': 'a1',
        'children': [{'kind': 'service', 'name': 'b', 'weight': 1, 'percent': 0}]})
    assert r.status_code == 400, 'a -> b -> a was written to the agent: %r' % r.get_json()
    kids = [c['name'] for c in fake.files['dynamic.yml']['http']['services']['a']['weighted']['services']]
    assert kids == ['leaf'], 'the agent config must be untouched after a refused save: %r' % kids
