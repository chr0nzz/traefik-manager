import textwrap

import pytest

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}

CONFIG = textwrap.dedent('''\
    http:
      routers:
        plex-rtr:
          rule: "Host(`plex.example.com`)"
          entryPoints: [websecure]
          middlewares:
            - chain-no-auth@file
            - crowdsec@docker
          service: plex-svc
          tls:
            certResolver: cloudflare
            options: tls-opts
      services:
        plex-svc:
          loadBalancer:
            servers:
              - url: "http://192.168.1.105:32400"
            serversTransport: plex-transport
        other-svc:
          loadBalancer:
            servers:
              - url: "http://10.0.0.9:80"
            serversTransport: plex-transport
      middlewares:
        chain-no-auth:
          chain:
            middlewares: [sec-headers]
        unrelated:
          headers:
            customRequestHeaders:
              X-Test: "1"
      serversTransports:
        plex-transport:
          forwardingTimeouts:
            dialTimeout: 30s
    tls:
      options:
        tls-opts:
          minVersion: VersionTLS12
        other-opts:
          minVersion: VersionTLS13
    ''')


@pytest.fixture
def route_config(config_path):
    config_path.write_text(CONFIG)
    return config_path


def _raw(client, route='plex-rtr'):
    res = client.get(f'/api/routes/{route}/raw')
    assert res.status_code == 200, res.data[:200]
    return res.get_json()['raw']


def test_the_raw_yaml_carries_what_the_route_depends_on(client, route_config):
    raw = _raw(client)
    assert 'serversTransports:' in raw and 'plex-transport:' in raw, \
        'the service names a transport, so its definition belongs in the route YAML'
    assert 'dialTimeout: 30s' in raw, 'the transport must arrive with its settings, not just its name'
    assert 'chain-no-auth:' in raw, 'a middleware defined in this file is part of the route'
    assert 'minVersion: VersionTLS12' in raw, 'the TLS options the router names belong here too'


def test_the_raw_yaml_leaves_other_routes_definitions_out(client, route_config):
    raw = _raw(client)
    assert 'unrelated:' not in raw, 'a middleware this route does not use must not appear'
    assert 'other-opts:' not in raw, 'only the TLS options this router names'
    assert 'other-svc:' not in raw, 'another route service must not be dragged in'


def test_a_middleware_from_another_provider_is_not_invented(client, config_path):
    config_path.write_text(CONFIG.replace('            - chain-no-auth@file\n', ''))
    raw = _raw(client)
    assert 'crowdsec' in raw, 'the router keeps its own middleware list'
    assert 'middlewares:\n    crowdsec' not in raw, \
        'a Docker middleware is not defined in this file, so there is nothing to include'


def test_editing_a_transport_in_the_editor_is_saved(client, route_config):
    edited = _raw(client).replace('dialTimeout: 30s', 'dialTimeout: 99s')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': edited}, headers=HDR)
    assert res.status_code == 200 and res.get_json().get('ok'), res.data[:200]
    text = route_config.read_text()
    assert 'dialTimeout: 99s' in text, \
        'the save reported success and dropped the edit, which is worse than not showing it'


def test_editing_the_tls_options_in_the_editor_is_saved(client, route_config):
    edited = _raw(client).replace('minVersion: VersionTLS12', 'minVersion: VersionTLS13')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': edited}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    after = route_config.read_text()
    assert 'VersionTLS13' in after.split('tls-opts:')[1][:80]


def test_saving_keeps_the_definitions_other_routes_use(client, route_config):
    edited = _raw(client).replace('dialTimeout: 30s', 'dialTimeout: 45s')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': edited}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    text = route_config.read_text()
    for kept in ('unrelated:', 'other-opts:', 'other-svc:'):
        assert kept in text, f'{kept} belongs to another route and must survive this save'


def test_a_route_without_dependencies_is_unchanged(client, config_path):
    config_path.write_text(textwrap.dedent('''\
        http:
          routers:
            plain-rtr:
              rule: "Host(`plain.example.com`)"
              service: plain-svc
          services:
            plain-svc:
              loadBalancer:
                servers:
                  - url: "http://10.0.0.5:80"
        '''))
    raw = _raw(client, 'plain-rtr')
    assert 'serversTransports' not in raw and 'middlewares' not in raw and 'tls:' not in raw, \
        'a route with no dependencies gets the YAML it always got'
