import core.settings as settings_mod
from conftest import read_config, write_config, post_form

from core import service_ownership as own

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}


def _manual(addr, weight=1, percent=0):
    return {'kind': 'manual', 'address': addr, 'scheme': 'http',
            'weight': weight, 'percent': percent}


def _ref(name, weight=1, percent=0):
    return {'kind': 'service', 'name': name, 'weight': weight, 'percent': percent}


def _save(client, name, children, kind='weighted', **extra):
    body = {'name': name, 'type': kind, 'children': children}
    body.update(extra)
    return client.post('/api/services', json=body, headers=HDR)


def _svc(name=None):
    services = (read_config().get('http') or {}).get('services') or {}
    return services if name is None else services.get(name)


def _ledger():
    return settings_mod.load_settings().get('managed_middlewares') or {}


def test_a_standalone_service_can_be_created(client):
    r = _save(client, 'pool', [_manual('10.0.0.10:80', 9), _manual('10.0.0.11:80', 1)])
    assert r.status_code == 200, r.get_json()
    assert _svc('pool')['weighted']['services'] == [
        {'name': 'pool-backend-1', 'weight': 9},
        {'name': 'pool-backend-2', 'weight': 1},
    ]
    assert _svc('pool-backend-1')['loadBalancer']['servers'] == [{'url': 'http://10.0.0.10:80'}]


def test_a_created_service_is_managed_by_us(client):
    _save(client, 'pool', [_manual('a:80')])
    assert own.ledger_key('pool') in _ledger()
    assert own.is_owned('pool', _svc('pool'), _ledger())


def test_a_created_service_is_offered_to_routes(client):
    _save(client, 'pool', [_manual('a:80')])
    services = client.get('/api/routes').get_json()['services']['http']
    assert 'pool' in services
    assert 'pool-backend-1' in services


def test_mirroring_and_failover_services_can_be_created(client):
    assert _save(client, 'mir', [_manual('a:80'), _ref('shadow', percent=10)],
                 kind='mirroring').status_code == 200
    assert _svc('mir')['mirroring']['mirrors'] == [{'name': 'shadow', 'percent': 10}]
    assert _save(client, 'fo', [_manual('b:80'), _ref('backup')],
                 kind='failover').status_code == 200
    assert _svc('fo')['failover']['fallback'] == 'backup'


def test_a_bad_name_is_refused(client):
    for bad in ('', 'has@provider', 'has/slash', 'has,comma', 'has:colon', 'tpl{{x}}',
                '.', '..', 'x' * 101):
        assert _save(client, bad, [_manual('a:80')]).status_code == 400, bad


def test_a_name_traefik_accepts_is_no_longer_refused(client):
    for good in ('xxx (yyy)', 'has space', '-leading', 'x' * 80, 'caf\u00e9', 'a+b', 'a[1]'):
        r = _save(client, good, [_manual('a:80')], kind='loadBalancer')
        assert r.status_code == 200, (good, r.get_json())
        assert _svc(good) is not None, good


def test_a_service_with_no_backends_is_refused(client):
    assert _save(client, 'empty', []).status_code == 400


def test_an_unsupported_type_is_refused(client):
    for bad in ('highestRandomWeight', 'nonsense', ''):
        assert _save(client, 'pool', [_manual('a:80')], kind=bad).status_code == 400, bad


def test_creating_over_a_service_we_do_not_manage_is_refused(client):
    write_config("""
http:
  routers: {}
  services:
    taken:
      loadBalancer:
        servers:
          - url: http://a:80
""")
    r = _save(client, 'taken', [_manual('b:80')])
    assert r.status_code == 409
    assert _svc('taken')['loadBalancer']['servers'] == [{'url': 'http://a:80'}]


def test_editing_our_own_service_is_allowed(client):
    _save(client, 'pool', [_manual('a:80')])
    r = _save(client, 'pool', [_manual('b:80'), _manual('c:80')], originalName='pool')
    assert r.status_code == 200
    assert len(_svc('pool')['weighted']['services']) == 2


def test_renaming_moves_the_service_and_its_children(client):
    _save(client, 'pool', [_manual('a:80')])
    r = _save(client, 'renamed', [_manual('a:80')], originalName='pool')
    assert r.status_code == 200
    assert _svc('pool') is None
    assert _svc('pool-backend-1') is None
    assert _svc('renamed') is not None
    assert _svc('renamed-backend-1') is not None
    assert own.ledger_key('pool') not in _ledger()


def test_a_service_can_be_deleted(client):
    _save(client, 'pool', [_manual('a:80')])
    r = client.delete('/api/services/pool', headers=HDR)
    assert r.status_code == 200
    assert _svc('pool') is None
    assert _svc('pool-backend-1') is None, 'its owned children go with it'
    assert own.ledger_key('pool') not in _ledger()


def test_a_service_a_route_still_uses_cannot_be_deleted(client):
    _save(client, 'pool', [_manual('a:80')])
    post_form(client, "/save", serviceName='web', subdomain='web.example.com', protocol='http',
              scheme='http', certResolver='letsencrypt', serviceRef='pool')
    r = client.delete('/api/services/pool', headers=HDR)
    assert r.status_code == 409
    assert _svc('pool') is not None


def test_a_service_that_is_a_backend_of_another_cannot_be_deleted(client):
    _save(client, 'leaf', [_manual('a:80')])
    _save(client, 'parent', [_ref('leaf')])
    r = client.delete('/api/services/leaf', headers=HDR)
    assert r.status_code == 409
    assert _svc('leaf') is not None


def test_a_service_we_do_not_manage_cannot_be_deleted(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      weighted:
        services:
          - name: a-svc
            weight: 1
""")
    r = client.delete('/api/services/theirs', headers=HDR)
    assert r.status_code == 403
    assert _svc('theirs') is not None


def test_deleting_something_that_does_not_exist_is_a_404(client):
    assert client.delete('/api/services/nope', headers=HDR).status_code == 404


def test_creating_a_service_requires_the_csrf_token(client):
    r = client.post('/api/services', json={'name': 'x', 'type': 'weighted',
                                           'children': [_manual('a:80')]},
                    headers={'X-Requested-With': 'fetch'})
    assert r.status_code >= 400


def test_a_plain_load_balancer_service_can_be_created(client):
    r = _save(client, 'plainsvc', [_manual('10.0.0.5:80'), _manual('10.0.0.6:80')],
              kind='loadBalancer')
    assert r.status_code == 200, r.get_json()
    assert _svc('plainsvc')['loadBalancer']['servers'] == [
        {'url': 'http://10.0.0.5:80'}, {'url': 'http://10.0.0.6:80'}]
    assert _svc('plainsvc-backend-1') is None, 'a plain load balancer owns no child services'


def test_editing_a_hand_written_load_balancer_keeps_its_other_settings(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      loadBalancer:
        servers:
          - url: http://old:80
        passHostHeader: false
        healthCheck:
          path: /up
      middlewares:
        - secure@file
""")
    r = _save(client, 'theirs', [_manual('new:80')], kind='loadBalancer')
    assert r.status_code == 200, r.get_json()
    svc = _svc('theirs')
    assert svc['loadBalancer']['servers'] == [{'url': 'http://new:80'}]
    assert svc['loadBalancer']['passHostHeader'] is False
    assert svc['loadBalancer']['healthCheck'] == {'path': '/up'}
    assert svc['middlewares'] == ['secure@file']


def test_a_plain_load_balancer_is_not_claimed_in_the_ledger(client):
    _save(client, 'plainsvc', [_manual('a:80')], kind='loadBalancer')
    assert own.ledger_key('plainsvc') not in _ledger()


def test_an_unknown_config_file_is_refused_not_silently_redirected(client):
    r = _save(client, 'pool', [_manual('a:80')], configFile='does-not-exist.yml')
    assert r.status_code == 400
    assert _svc('pool') is None


def test_failover_refuses_a_third_backend(client):
    r = _save(client, 'fo', [_manual('a:80'), _manual('b:80'), _manual('c:80')], kind='failover')
    assert r.status_code == 400
    assert 'two backends' in r.get_json()['error']
    assert _svc('fo') is None
    assert _svc('fo-backend-3') is None, 'a rejected save must leave nothing behind'


def test_failover_with_two_backends_creates_exactly_two_children(client):
    assert _save(client, 'fo', [_manual('a:80'), _manual('b:80')], kind='failover').status_code == 200
    assert _svc('fo')['failover'] == {'service': 'fo-backend-1', 'fallback': 'fo-backend-2'}
    assert _svc('fo-backend-1') is not None and _svc('fo-backend-2') is not None
    assert _svc('fo-backend-3') is None


def test_a_load_balancer_we_created_can_be_deleted(client):
    r = _save(client, 'plainsvc', [_manual('10.0.0.5:80')], kind='loadBalancer')
    assert r.status_code == 200, r.get_json()
    r = client.delete('/api/services/plainsvc', headers=HDR)
    assert r.status_code == 200, r.get_json()
    assert _svc('plainsvc') is None


def test_a_hand_written_load_balancer_can_be_deleted(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      loadBalancer:
        servers:
          - url: http://10.0.0.9:80
""")
    r = client.delete('/api/services/theirs', headers=HDR)
    assert r.status_code == 200, r.get_json()
    assert _svc('theirs') is None


def test_a_composite_we_do_not_manage_still_cannot_be_deleted(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      weighted:
        services:
          - name: a
            weight: 1
    a:
      loadBalancer:
        servers:
          - url: http://10.0.0.9:80
""")
    r = client.delete('/api/services/theirs', headers=HDR)
    assert r.status_code == 403
    assert _svc('theirs') is not None


def test_a_tcp_service_name_is_refused_by_the_save_endpoint(client):
    write_config("""
http:
  routers: {}
  services: {}
tcp:
  routers: {}
  services:
    postgres:
      loadBalancer:
        servers:
          - address: 10.0.0.9:5432
""")
    r = _save(client, 'postgres', [_manual('10.0.0.5:80')], kind='loadBalancer')
    assert r.status_code == 400
    assert 'TCP' in r.get_json()['error']
    assert _svc('postgres') is None, 'no http service is written over the tcp one'


def test_a_udp_service_name_is_refused_by_the_save_endpoint(client):
    write_config("""
http:
  routers: {}
  services: {}
udp:
  routers: {}
  services:
    wireguard:
      loadBalancer:
        servers:
          - address: 10.0.0.9:51820
""")
    r = _save(client, 'wireguard', [_manual('10.0.0.5:80')], kind='loadBalancer')
    assert r.status_code == 400
    assert 'UDP' in r.get_json()['error']


def test_an_unrelated_http_name_is_still_accepted(client):
    write_config("""
http:
  routers: {}
  services: {}
tcp:
  routers: {}
  services:
    postgres:
      loadBalancer:
        servers:
          - address: 10.0.0.9:5432
""")
    r = _save(client, 'webpool', [_manual('10.0.0.5:80')], kind='loadBalancer')
    assert r.status_code == 200, r.get_json()


def _hc(**over):
    hc = {'enabled': True, 'path': '/up'}
    hc.update(over)
    return hc


def test_a_health_check_is_written_with_every_field_traefik_takes(client):
    r = _save(client, 'pool', [_manual('a:80'), _manual('b:80')], kind='loadBalancer',
              healthCheck=_hc(interval='10s', timeout='3s', unhealthyInterval='1m30s',
                              method='HEAD', status='204', scheme='https', port='8080',
                              hostname='probe.local', mode='grpc', followRedirects=False,
                              headers={'X-Probe': 'tm', '': 'dropped'}))
    assert r.status_code == 200, r.get_json()
    hc = _svc('pool')['loadBalancer']['healthCheck']
    assert hc == {'path': '/up', 'interval': '10s', 'timeout': '3s', 'unhealthyInterval': '1m30s',
                  'scheme': 'https', 'mode': 'grpc', 'hostname': 'probe.local', 'method': 'HEAD',
                  'port': 8080, 'status': 204, 'followRedirects': False,
                  'headers': {'X-Probe': 'tm'}}, hc


def test_turning_the_health_check_off_removes_it(client):
    _save(client, 'pool', [_manual('a:80')], kind='loadBalancer', healthCheck=_hc())
    assert _svc('pool')['loadBalancer']['healthCheck']['path'] == '/up'
    r = _save(client, 'pool', [_manual('a:80')], kind='loadBalancer',
              healthCheck={'enabled': False, 'path': '/up'})
    assert r.status_code == 200, r.get_json()
    assert 'healthCheck' not in _svc('pool')['loadBalancer'], _svc('pool')


def test_a_health_check_without_a_path_probes_the_server_root(client):
    r = _save(client, 'pool', [_manual('a:80')], kind='loadBalancer',
              healthCheck={'enabled': True, 'path': '  ', 'interval': '10s', 'timeout': '3s'})
    assert r.status_code == 200, r.get_json()
    hc = _svc('pool')['loadBalancer']['healthCheck']
    assert hc == {'interval': '10s', 'timeout': '3s'}, \
        'Traefik gates on the healthCheck block, not on the path, so a pathless check is valid: %r' % (hc,)


def test_a_client_that_sends_no_health_check_still_keeps_the_existing_one(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      loadBalancer:
        servers:
          - url: http://old:80
        healthCheck:
          path: /up
          method: HEAD
""")
    r = _save(client, 'theirs', [_manual('new:80')], kind='loadBalancer')
    assert r.status_code == 200, r.get_json()
    assert _svc('theirs')['loadBalancer']['healthCheck'] == {'path': '/up', 'method': 'HEAD'}


def test_a_health_check_field_we_do_not_know_survives_an_edit(client):
    write_config("""
http:
  routers: {}
  services:
    theirs:
      loadBalancer:
        servers:
          - url: http://old:80
        healthCheck:
          path: /up
          somethingTraefikAddedLater: keepme
""")
    r = _save(client, 'theirs', [_manual('new:80')], kind='loadBalancer', healthCheck=_hc(path='/hz'))
    assert r.status_code == 200, r.get_json()
    hc = _svc('theirs')['loadBalancer']['healthCheck']
    assert hc['path'] == '/hz', 'the editor owns the fields it shows'
    assert hc['somethingTraefikAddedLater'] == 'keepme', \
        'a field the editor does not show must not be dropped: %r' % (hc,)
