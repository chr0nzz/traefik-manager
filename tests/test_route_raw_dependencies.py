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


ROUTE_ONLY = textwrap.dedent('''\
    http:
      routers:
        plex-rtr:
          rule: "Host(`plex.example.com`)"
          entryPoints: [websecure]
          middlewares:
            - chain-no-auth@file
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
    ''')

SHARED = textwrap.dedent('''\
    http:
      middlewares:
        chain-no-auth:
          chain:
            middlewares: [sec-headers]
      serversTransports:
        plex-transport:
          forwardingTimeouts:
            dialTimeout: 30s
    tls:
      options:
        tls-opts:
          minVersion: VersionTLS12
    ''')


@pytest.fixture
def route_config(config_path):
    config_path.write_text(CONFIG)
    return config_path


@pytest.fixture
def split_config(config_path, tmp_path, monkeypatch):
    from core import env as core_env
    shared = tmp_path / 'shared.yml'
    shared.write_text(SHARED)
    config_path.write_text(ROUTE_ONLY)
    monkeypatch.setattr(core_env, 'CONFIG_PATHS', [str(config_path), str(shared)])
    return shared


def _payload(client, route='plex-rtr'):
    res = client.get(f'/api/routes/{route}/raw')
    assert res.status_code == 200, res.data[:200]
    return res.get_json()


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


def test_the_api_names_the_file_each_dependency_lives_in(client, split_config):
    origins = _payload(client)['origins']
    assert origins['http']['middlewares']['chain-no-auth'] == 'shared.yml'
    assert origins['http']['serversTransports']['plex-transport'] == 'shared.yml'
    assert origins['tls']['options']['tls-opts'] == 'shared.yml'


def test_a_dependency_in_the_route_own_file_is_reported_there(client, route_config):
    origins = _payload(client)['origins']
    own = route_config.name
    assert origins['http']['middlewares']['chain-no-auth'] == own
    assert origins['http']['serversTransports']['plex-transport'] == own
    assert origins['tls']['options']['tls-opts'] == own


def test_a_route_with_no_dependencies_reports_no_origins(client, config_path):
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
    assert _payload(client, 'plain-rtr')['origins'] == {}


def test_a_definition_from_another_file_is_shown_in_the_editor(client, split_config):
    raw = _payload(client)['raw']
    assert 'chain-no-auth:' in raw, 'the middleware the route uses belongs in its YAML, file aside'
    assert 'dialTimeout: 30s' in raw, 'the transport arrives with its settings'
    assert 'minVersion: VersionTLS12' in raw, 'so do the TLS options the router names'


def test_an_untouched_definition_from_another_file_is_not_copied_in(client, split_config,
                                                                   config_path):
    raw = _payload(client)['raw']
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    text = config_path.read_text()
    assert 'chain-no-auth:' not in text, 'the middleware belongs to shared.yml and must stay there'
    assert 'dialTimeout' not in text, 'the transport definition must not be duplicated'
    assert 'minVersion' not in text, 'nor the TLS options'
    assert 'chain-no-auth' in split_config.read_text(), 'the other file keeps its definition'


def test_reordering_or_reformatting_a_shared_definition_is_not_a_change(client, split_config,
                                                                       config_path):
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', "dialTimeout: '30s'")
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    assert 'dialTimeout' not in config_path.read_text()


def test_editing_a_definition_from_another_file_asks_first(client, split_config, config_path):
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    assert res.status_code == 409, res.data[:200]
    body = res.get_json()
    assert body['needsConfirm'] is True
    change = body['sharedChanges'][0]
    assert change['name'] == 'plex-transport' and change['file'] == 'shared.yml'
    assert 'dialTimeout: 30s' in split_config.read_text(), 'nothing is written before the confirm'


def test_the_prompt_says_how_many_routes_the_change_reaches(client, split_config, config_path):
    config_path.write_text(config_path.read_text().replace(
        '  services:',
        '    sonarr-rtr:\n      rule: "Host(`sonarr.example.com`)"\n'
        '      service: plex-svc\n  services:'))
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    used = res.get_json()['sharedChanges'][0]['usedBy']
    assert used['count'] == 2, 'both routes share the service that names this transport'
    assert 'sonarr-rtr' in used['routes'] and 'plex-rtr' in used['routes']


def test_confirming_writes_the_change_to_the_file_that_owns_it(client, split_config, config_path):
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    res = client.post('/api/routes/plex-rtr/raw',
                      json={'content': raw, 'applyShared': True}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    assert 'dialTimeout: 99s' in split_config.read_text(), 'the edit belongs in the file it came from'
    assert 'dialTimeout' not in config_path.read_text(), 'and must not be duplicated into the route'


def test_confirming_also_saves_the_route_itself(client, split_config, config_path):
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    raw = raw.replace('Host(`plex.example.com`)', 'Host(`new.example.com`)')
    res = client.post('/api/routes/plex-rtr/raw',
                      json={'content': raw, 'applyShared': True}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    assert 'new.example.com' in config_path.read_text()
    assert 'dialTimeout: 99s' in split_config.read_text()


def test_cancelling_leaves_the_other_file_byte_identical(client, split_config, config_path):
    before = split_config.read_text()
    raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    assert res.status_code == 409
    assert split_config.read_text() == before


def test_a_read_only_file_is_refused_before_anything_is_written(client, split_config, config_path):
    import os
    before = config_path.read_text()
    os.chmod(split_config, 0o444)
    try:
        raw = _payload(client)['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
        res = client.post('/api/routes/plex-rtr/raw',
                          json={'content': raw, 'applyShared': True}, headers=HDR)
    finally:
        os.chmod(split_config, 0o644)
    assert res.status_code == 409, res.data[:200]
    assert res.get_json()['readOnly'] == 'shared.yml'
    assert 'read-only' in res.get_json()['error']
    assert config_path.read_text() == before, 'the route must not be written either'


def test_a_file_that_changed_on_disk_aborts_the_whole_save(client, split_config, config_path):
    payload = _payload(client)
    raw = payload['raw'].replace('dialTimeout: 30s', 'dialTimeout: 99s')
    split_config.write_text(split_config.read_text().replace('30s', '31s'))
    res = client.post('/api/routes/plex-rtr/raw',
                      json={'content': raw, 'applyShared': True,
                            'fingerprints': payload['fingerprints']}, headers=HDR)
    assert res.status_code == 409, res.data[:200]
    assert res.get_json()['stale'] == 'shared.yml'
    assert '31s' in split_config.read_text(), 'the file that moved underneath is left as it is'


def test_the_fingerprints_cover_every_file_the_route_touches(client, split_config, config_path):
    prints = _payload(client)['fingerprints']
    assert set(prints) == {config_path.name, 'shared.yml'}
    assert all(prints.values()), 'each file needs a fingerprint to compare against'


def test_renaming_a_shared_definition_is_refused(client, split_config, config_path):
    raw = _payload(client)['raw'].replace('    plex-transport:', '    plex-transport-x:')
    res = client.post('/api/routes/plex-rtr/raw',
                      json={'content': raw, 'applyShared': True}, headers=HDR)
    assert res.status_code == 409, res.data[:200]
    body = res.get_json()
    assert body['renamed'] == 'plex-transport'
    assert 'shared.yml' in body['error']
    assert 'plex-transport-x' not in config_path.read_text(), 'no orphan is created'
    assert 'plex-transport:' in split_config.read_text(), 'the original keeps its name'


def test_a_new_definition_still_lands_in_the_route_own_file(client, split_config, config_path):
    raw = _payload(client)['raw']
    anchor = next(line for line in raw.splitlines() if line.strip() == 'plex-transport:')
    pad = anchor[:len(anchor) - len(anchor.lstrip())]
    raw = raw.replace(anchor, f'{pad}brand-new:\n{pad}  insecureSkipVerify: true\n{anchor}')
    res = client.post('/api/routes/plex-rtr/raw', json={'content': raw}, headers=HDR)
    assert res.status_code == 200, res.data[:200]
    assert 'brand-new:' in config_path.read_text(), \
        'a definition that exists nowhere else is this route file to write'
    assert 'brand-new' not in split_config.read_text(), 'and it does not reach the other file'
