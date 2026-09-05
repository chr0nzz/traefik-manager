import json

from conftest import post_form, read_config, write_config

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}

BASE = """
http:
  routers:
    web:
      rule: Host(`web.example.com`)
      service: web-svc
      middlewares: [auth, compress]
    api:
      rule: Host(`api.example.com`)
      service: web-svc
      middlewares: [auth]
  services:
    web-svc:
      loadBalancer:
        servers:
          - url: http://10.0.0.1:80
  middlewares:
    auth:
      basicAuth:
        users: ["u:$2y$05$abc"]
    compress:
      compress: {}
"""


def _mws(router):
    return ((read_config().get('http') or {}).get('routers') or {}).get(router, {}).get('middlewares')


def _names():
    return sorted((read_config().get('http') or {}).get('middlewares') or {})


def test_deleting_a_used_middleware_is_refused(client):
    write_config(BASE)
    r = client.post('/delete-middleware/auth', data={'csrf_token': 'testtoken'}, headers=HDR)
    assert r.status_code == 409, r.get_data(as_text=True)
    body = r.get_json() or {}
    assert 'web' in (body.get('message') or '') and 'api' in (body.get('message') or ''), \
        'the refusal must name the routers still using it: %r' % body
    assert 'auth' in _names(), 'the middleware was deleted despite being in use'


def test_deleting_an_unused_middleware_still_works(client):
    write_config(BASE)
    r = client.post('/delete-middleware/compress',
                    data={'csrf_token': 'testtoken', 'force': 'true'}, headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)


def test_force_deleting_strips_the_middleware_from_its_routers(client):
    write_config(BASE)
    r = client.post('/delete-middleware/auth',
                    data={'csrf_token': 'testtoken', 'force': 'true'}, headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in _names()
    assert _mws('web') == ['compress'], 'the reference was left behind: %r' % _mws('web')
    assert not _mws('api'), 'the reference was left behind: %r' % _mws('api')


def test_renaming_a_middleware_moves_its_routers_with_it(client):
    write_config(BASE)
    r = post_form(client, '/save-middleware', middlewareName='authelia',
                  isMwEdit='true', originalMwId='auth', mwProtocol='http',
                  originalMwProtocol='http',
                  middlewareContent='basicAuth:\n  users: ["u:$2y$05$abc"]\n')
    assert r.status_code in (200, 302), r.get_data(as_text=True)
    assert 'authelia' in _names() and 'auth' not in _names()
    assert _mws('web') == ['authelia', 'compress'], \
        'the router still points at the old name: %r' % _mws('web')
    assert _mws('api') == ['authelia'], _mws('api')


def _svc_manual(addr):
    return {'kind': 'manual', 'address': addr, 'scheme': 'http', 'weight': 1, 'percent': 0}


def test_renaming_a_service_moves_its_routers_with_it(client):
    write_config("http:\n  routers: {}\n  services: {}\n")
    r = client.post('/api/services', headers=HDR, json={
        'name': 'pool', 'type': 'weighted',
        'children': [_svc_manual('10.0.0.1:80'), _svc_manual('10.0.0.2:80')]})
    assert r.status_code == 200, r.get_json()

    cfg = read_config()
    cfg['http']['routers'] = {'web': {'rule': 'Host(`w.example.com`)', 'service': 'pool'}}
    write_config(json.dumps(cfg))

    r = client.post('/api/services', headers=HDR, json={
        'name': 'renamed', 'type': 'weighted', 'originalName': 'pool',
        'children': [_svc_manual('10.0.0.1:80'), _svc_manual('10.0.0.2:80')]})
    assert r.status_code == 200, r.get_json()

    http = read_config().get('http') or {}
    target = (http.get('routers') or {}).get('web', {}).get('service')
    assert target == 'renamed', 'the router still points at the old name: %r' % target
    assert target in (http.get('services') or {}), 'the router points at a service that does not exist'


TLS_BASE = """
http:
  routers:
    web:
      rule: Host(`web.example.com`)
      service: web-svc
      tls:
        options: strict
  services:
    web-svc:
      loadBalancer:
        servers:
          - url: http://10.0.0.1:80
tls:
  options:
    strict:
      minVersion: VersionTLS13
"""


def _tls_names():
    return sorted(((read_config().get('tls') or {}).get('options') or {}))


def test_deleting_a_used_tls_profile_is_refused(client):
    write_config(TLS_BASE)
    r = client.delete('/api/tls-options/strict', headers=HDR)
    assert r.status_code == 409, r.get_data(as_text=True)
    assert 'web' in ((r.get_json() or {}).get('message') or ''), \
        'the refusal must name the routers using it: %r' % r.get_json()
    assert 'strict' in _tls_names(), 'the profile was deleted despite being in use'


def test_an_unused_tls_profile_still_deletes(client):
    write_config(TLS_BASE.replace('      tls:\n        options: strict\n', ''))
    r = client.delete('/api/tls-options/strict', headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert _tls_names() == []


def test_renaming_a_tls_profile_moves_its_routers_with_it(client):
    write_config(TLS_BASE)
    r = client.post('/api/tls-options', headers=HDR, json={
        'name': 'modern', 'originalName': 'strict', 'minVersion': 'VersionTLS13'})
    assert r.status_code == 200, r.get_data(as_text=True)

    cfg = read_config()
    assert _tls_names() == ['modern'], 'the old profile was left behind: %r' % _tls_names()
    used = ((cfg.get('http') or {}).get('routers') or {}).get('web', {}).get('tls', {}).get('options')
    assert used == 'modern', 'the router still points at the old profile: %r' % used


def test_renaming_a_tls_profile_leaves_other_routers_alone(client):
    write_config(TLS_BASE.replace(
        '    web:', '    other:\n      rule: Host(`o.example.com`)\n      service: web-svc\n'
                    '      tls:\n        options: different\n    web:'))
    client.post('/api/tls-options', headers=HDR, json={
        'name': 'modern', 'originalName': 'strict', 'minVersion': 'VersionTLS13'})
    routers = (read_config().get('http') or {}).get('routers') or {}
    assert routers['other']['tls']['options'] == 'different', \
        'an unrelated router was retargeted: %r' % routers['other']
