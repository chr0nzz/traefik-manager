import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

URL_FOR = re.compile(r"""url_for\(\s*['"]([^'"]+)['"]""")


def _sources():
    files = [os.path.join(ROOT, 'app.py')]
    for sub in ('core', 'templates', 'static/js'):
        base = os.path.join(ROOT, sub)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ('vendor', '__pycache__')]
            for fn in filenames:
                if fn.endswith(('.py', '.html', '.js')):
                    files.append(os.path.join(dirpath, fn))
    return files


def _targets():
    found = {}
    for path in _sources():
        try:
            text = open(path, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            continue
        for m in URL_FOR.finditer(text):
            found.setdefault(m.group(1), set()).add(os.path.relpath(path, ROOT))
    return found


def test_every_url_for_target_is_registered(app_module):
    registered = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    missing = {t: sorted(src) for t, src in _targets().items() if t not in registered}
    assert not missing, (
        'url_for() targets that do not resolve to a registered endpoint '
        '(a redirect using one of these raises BuildError at runtime):\n  '
        + '\n  '.join('%s  <- %s' % (t, ', '.join(s)) for t, s in sorted(missing.items()))
    )


def test_core_route_set_is_present(app_module):
    rules = {r.rule for r in app_module.app.url_map.iter_rules()}
    for rule in ('/', '/login', '/logout', '/save', '/save-middleware',
                 '/api/routes', '/api/routes/all', '/api/configs', '/api/health',
                 '/api/agents', '/api/backups', '/api/settings'):
        assert rule in rules, 'route %s disappeared' % rule


def test_no_duplicate_rules(app_module):
    seen = {}
    for r in app_module.app.url_map.iter_rules():
        for method in (r.methods or set()) - {'HEAD', 'OPTIONS'}:
            key = (r.rule, method)
            assert key not in seen, (
                'duplicate route: %s %s registered by both %s and %s'
                % (method, r.rule, seen[key], r.endpoint))
            seen[key] = r.endpoint


def test_dashboard_override_url_scheme_is_validated(client):
    payload = {'custom_groups': [], 'route_overrides': {
        'good':   {'url': 'https://app.example.com/admin', 'display_name': 'Good'},
        'evil':   {'url': 'javascript:alert(1)', 'display_name': 'Evil'},
        'data':   {'url': 'data:text/html,x'},
        'blank':  {'url': '   '},
    }}
    r = client.post('/api/dashboard/config', json=payload,
                    headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code == 200

    cfg = client.get('/api/dashboard/config').get_json()
    ov = cfg['route_overrides']
    assert ov['good']['url'] == 'https://app.example.com/admin'
    assert 'url' not in ov['evil']
    assert 'url' not in ov['data']
    assert 'url' not in ov['blank']
    assert ov['evil']['display_name'] == 'Evil'


def test_agent_visible_tabs_follow_the_hub(client):
    from core import agents_store
    agents_store.save_agents_file([
        {'id': 'ag1', 'name': 'Test Agent', 'url': 'http://10.0.0.5:8280', 'api_key': 'k'},
    ])
    r = client.put('/api/agents/ag1',
                   json={'visible_tabs': {'logs': True, 'certs': 0, 'bogus': True, 'docker': 'yes'}},
                   headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code == 200

    agents = client.get('/api/agents').get_json()['agents']
    ag = next(a for a in agents if a['id'] == 'ag1')
    assert ag['visible_tabs'] == {'logs': True, 'certs': False, 'docker': True}

    reloaded = agents_store.load_agents()
    assert reloaded[0]['visible_tabs'] == {'logs': True, 'certs': False, 'docker': True}


def test_toast_messages_are_recorded_in_the_drawer(client):
    r = client.post('/api/notifications/log',
                    json={'message': 'Route gone deleted', 'type': 'error'},
                    headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code == 200 and r.get_json()['stored'] is True

    entries = client.get('/api/notifications').get_json()
    assert any(e['msg'] == 'Route gone deleted' and e['type'] == 'error' for e in entries)


def test_the_same_message_is_not_recorded_twice(client):
    payload = {'message': 'Saved app1', 'type': 'success'}
    hdrs = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
    assert client.post('/api/notifications/log', json=payload, headers=hdrs).get_json()['stored'] is True
    assert client.post('/api/notifications/log', json=payload, headers=hdrs).get_json()['stored'] is False

    entries = client.get('/api/notifications').get_json()
    assert sum(1 for e in entries if e['msg'] == 'Saved app1') == 1


def test_empty_toast_messages_are_rejected(client):
    r = client.post('/api/notifications/log', json={'message': '   '},
                    headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code == 400


def test_recording_a_toast_requires_a_session(anon_client):
    r = anon_client.post('/api/notifications/log', json={'message': 'hi'},
                         headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code in (302, 401, 403)


def _static_providers_roundtrip(client, raw, payload):
    import json
    res = client.post('/api/static/section',
                      data=json.dumps({'action': 'set', 'section': 'providers',
                                       'name': '', 'data': payload, 'current_raw': raw}),
                      content_type='application/json',
                      headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert res.status_code == 200, res.data
    body = res.get_json()
    assert body.get('ok'), body
    return body['raw'], body.get('parsed') or {}


BARE_DOCKER = "providers:\n  docker: {}\n"


def test_turning_off_expose_by_default_is_written_to_the_file(client):
    raw, parsed = _static_providers_roundtrip(client, BARE_DOCKER, {
        'docker': True, 'dockerEndpoint': '', 'dockerExposedByDefault': False,
        'dockerWatch': True, 'file': False,
    })
    assert parsed['providers']['docker'].get('exposedByDefault') is False, (
        'Traefik defaults exposedByDefault to true, so turning it off must write the key.\n'
        'Leaving it out leaves every container auto-exposed.\n' + raw)
    assert 'exposedByDefault: false' in raw


def test_leaving_expose_by_default_on_does_not_write_the_key(client):
    raw, parsed = _static_providers_roundtrip(client, BARE_DOCKER, {
        'docker': True, 'dockerEndpoint': '', 'dockerExposedByDefault': True,
        'dockerWatch': True, 'file': False,
    })
    assert 'exposedByDefault' not in (parsed['providers']['docker'] or {}), raw


def _cs_lapi_stub(monkeypatch, capi_count, local_ip, local_origin='crowdsec', stream=True):
    import app as tm
    from core import crowdsec as cs
    pool = [{'id': i + 1, 'origin': 'CAPI', 'value': f'10.0.{i // 256}.{i % 256}',
             'type': 'ban', 'scenario': 'capi', 'until': '2099-01-01T00:00:00Z'}
            for i in range(capi_count)]
    pool.append({'id': 999999, 'origin': local_origin, 'value': local_ip, 'type': 'ban',
                 'scenario': 'crowdsecurity/http-probing', 'until': '2099-01-01T00:00:00Z'})

    calls = []

    def fake(method, path, **kw):
        calls.append(path)
        if '/v1/decisions/stream' in path:
            if not stream:
                raise cs.CrowdSecUnavailable(f'LAPI answered HTTP 404 on {path}')
            return {'new': list(pool), 'deleted': []}
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(path).query)
        limit = int(q.get('limit', ['100'])[0])
        id_gt = int(q.get('id_gt', ['0'])[0])
        rows = sorted((d for d in pool if d['id'] > id_gt), key=lambda d: d['id'])
        return rows[:limit]

    cs.cs_stream_reset()
    monkeypatch.setattr(tm, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(tm, '_cs_api_key', lambda: 'key')
    monkeypatch.setattr(cs, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(cs, '_cs_api_key', lambda: 'key')
    monkeypatch.setattr(tm, '_cs_request', fake)
    monkeypatch.setattr(tm, '_cs_request_strict', fake)
    monkeypatch.setattr(cs, '_cs_request_strict', fake)
    return calls


def test_local_decisions_survive_the_pagination_cap(client, monkeypatch):
    ip = '45.148.10.125'
    _cs_lapi_stub(monkeypatch, capi_count=6000, local_ip=ip)

    res = client.get('/api/crowdsec/decisions')
    assert res.status_code == 200, res.data
    values = [d['value'] for d in res.get_json()]
    assert ip in values, (
        'A local decision sitting past the old cap was dropped, so the UI could '
        'never find it. See issue #130.')


def test_manually_added_decisions_are_found(client, monkeypatch):
    ip = '198.51.100.7'
    _cs_lapi_stub(monkeypatch, capi_count=6000, local_ip=ip, local_origin='manual')

    res = client.get('/api/crowdsec/decisions')
    values = [d['value'] for d in res.get_json()]
    assert ip in values, 'a ban added from the UI past the cap was dropped'


def test_every_decision_is_returned(client, monkeypatch):
    _cs_lapi_stub(monkeypatch, capi_count=6000, local_ip='45.148.10.125')

    res = client.get('/api/crowdsec/decisions')
    assert len(res.get_json()) == 6001, 'the cursor walk stopped short of the full set'


def test_local_decisions_are_not_duplicated(client, monkeypatch):
    _cs_lapi_stub(monkeypatch, capi_count=3, local_ip='45.148.10.125')

    res = client.get('/api/crowdsec/decisions')
    ids = [d['id'] for d in res.get_json()]
    assert len(ids) == len(set(ids)), 'the cursor walk returned a decision twice'
    assert ids.count(999999) == 1


def test_unreachable_lapi_is_not_reported_as_zero_decisions(client, monkeypatch):
    import app as tm
    from core.crowdsec import CrowdSecUnavailable

    def boom(method, path, **kw):
        raise CrowdSecUnavailable('CrowdSec LAPI unreachable: connection refused')

    monkeypatch.setattr(tm, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(tm, '_cs_api_key', lambda: 'key')
    monkeypatch.setattr(tm, '_cs_request_strict', boom)

    res = client.get('/api/crowdsec/decisions')
    assert res.status_code == 502, res.data
    assert 'error' in res.get_json()


def test_decisions_without_a_bouncer_key_say_why(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(tm, '_cs_api_key', lambda: '')

    res = client.get('/api/crowdsec/decisions')
    assert res.status_code == 503
    assert 'bouncer' in res.get_json()['error'].lower()


def test_geoip_lookup_no_longer_truncates(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm, '_geoip_enabled', lambda: True)
    monkeypatch.setattr(tm, '_geoip_reader', lambda: object())
    monkeypatch.setattr(tm, '_geoip_lookup',
                        lambda ip, reader: {'country_code': 'US', 'country': 'United States'})

    ips = ['10.0.%d.%d' % (i // 256, i % 256) for i in range(2500)]
    res = client.post('/api/geoip/lookup', json={'ips': ips},
                      headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert res.status_code == 200
    assert len(res.get_json()['results']) == 2500, 'lookups are being silently dropped'


def test_geoip_aggregate_returns_counts_and_codes(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm, '_geoip_enabled', lambda: True)
    monkeypatch.setattr(tm, '_geoip_reader', lambda: object())

    def geo(ip, reader):
        return ({'country_code': 'US', 'country': 'United States'} if ip.startswith('10.')
                else {'country_code': 'DE', 'country': 'Germany'})
    monkeypatch.setattr(tm, '_geoip_lookup', geo)

    ips = ['10.0.0.%d' % i for i in range(30)] + ['8.8.8.%d' % i for i in range(12)]
    res = client.post('/api/geoip/lookup', json={'ips': ips, 'aggregate': True},
                      headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    body = res.get_json()

    assert body['counts']['US']['count'] == 30
    assert body['counts']['DE']['count'] == 12
    assert body['counts']['US']['country'] == 'United States'
    assert 'results' not in body, 'aggregate mode should not ship per-IP objects'
    assert body['codes']['10.0.0.5'] == 'US', 'the country filter needs per-IP codes'
    assert body['codes']['8.8.8.5'] == 'DE'


def _static_section(client, raw, section, action, name, data, old_name=None):
    import json
    res = client.post('/api/static/section',
                      data=json.dumps({'action': action, 'section': section, 'name': name,
                                       'old_name': old_name or name, 'data': data, 'current_raw': raw}),
                      content_type='application/json',
                      headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    return res


RESOLVER_RAW = """certificatesResolvers:
  cf:
    acme:
      email: a@b.co
      storage: /acme.json
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory
      preferredChain: ISRG Root X1
      eab:
        kid: k1
        hmacEncoded: h1
      dnsChallenge:
        provider: cloudflare
        resolvers:
          - 1.1.1.1:53
"""


def test_resolver_edit_preserves_keys_the_form_does_not_manage(client):
    res = _static_section(client, RESOLVER_RAW, 'resolvers', 'edit', 'cf', {
        'email': 'new@b.co', 'storage': '/acme.json', 'challenge_type': 'dnsChallenge',
        'provider': 'cloudflare', 'http_entrypoint': '',
        'ca_server': 'https://acme-staging-v02.api.letsencrypt.org/directory',
        'key_type': '', 'eab_kid': 'k1', 'eab_hmac': 'h1',
        'dns_resolvers': '1.1.1.1:53', 'dns_delay': '', 'dns_disable_checks': False,
    })
    assert res.status_code == 200, res.data
    acme = res.get_json()['parsed']['certificatesResolvers']['cf']['acme']
    assert acme['email'] == 'new@b.co'
    assert acme['preferredChain'] == 'ISRG Root X1', 'unmanaged keys must survive a form edit'
    assert acme['caServer'].endswith('/directory')
    assert acme['eab'] == {'kid': 'k1', 'hmacEncoded': 'h1'}
    assert acme['dnsChallenge']['resolvers'] == ['1.1.1.1:53']


EP_BASE = {'address': ':443', 'redirect_to': '', 'http3': False, 'underscore_headers': '',
           'trusted_ips': '', 'forwarded_insecure': False, 'proxy_trusted_ips': '',
           'proxy_insecure': False, 'middlewares': '', 'tls_enabled': False,
           'tls_cert_resolver': '', 'tls_options': '', 'as_default': False,
           'read_timeout': '', 'write_timeout': '', 'idle_timeout': ''}


def test_entrypoint_form_writes_trust_tls_and_timeouts(client):
    raw = "entryPoints:\n  websecure:\n    address: ':443'\n"
    res = _static_section(client, raw, 'entrypoints', 'edit', 'websecure', dict(EP_BASE, **{
        'trusted_ips': '173.245.48.0/20\n10.0.0.0/8',
        'middlewares': 'secure@file, rl@file',
        'tls_enabled': True, 'tls_cert_resolver': 'cf',
        'as_default': True, 'read_timeout': '60s', 'idle_timeout': '180',
    }))
    assert res.status_code == 200, res.data
    ep = res.get_json()['parsed']['entryPoints']['websecure']
    assert ep['forwardedHeaders']['trustedIPs'] == ['173.245.48.0/20', '10.0.0.0/8']
    assert ep['http']['middlewares'] == ['secure@file', 'rl@file']
    assert ep['http']['tls']['certResolver'] == 'cf'
    assert ep['asDefault'] is True
    assert ep['transport']['respondingTimeouts']['readTimeout'] == '60s'
    assert ep['transport']['respondingTimeouts']['idleTimeout'] == 180


def test_entrypoint_rejects_bad_cidr_and_duration(client):
    raw = "entryPoints:\n  web:\n    address: ':80'\n"
    bad_ip = _static_section(client, raw, 'entrypoints', 'edit', 'web',
                             dict(EP_BASE, trusted_ips='not-an-ip'))
    assert bad_ip.status_code == 400
    bad_dur = _static_section(client, raw, 'entrypoints', 'edit', 'web',
                              dict(EP_BASE, read_timeout='banana'))
    assert bad_dur.status_code == 400


def test_entrypoint_edit_preserves_unmanaged_keys(client):
    raw = ("entryPoints:\n  web:\n    address: ':80'\n"
           "    reusePort: true\n    http2:\n      maxConcurrentStreams: 250\n")
    res = _static_section(client, raw, 'entrypoints', 'edit', 'web', dict(EP_BASE, address=':80'))
    assert res.status_code == 200, res.data
    ep = res.get_json()['parsed']['entryPoints']['web']
    assert ep['reusePort'] is True
    assert ep['http2']['maxConcurrentStreams'] == 250


LOG_BASE = {'level': 'ERROR', 'log_format': '', 'log_file': '', 'log_max_size': '',
            'log_max_backups': '', 'log_max_age': '', 'log_compress': False,
            'accessLog': False, 'accessLogPath': '', 'al_format': '', 'al_buffering': '',
            'al_status_codes': '', 'al_min_duration': '', 'al_retry': False, 'al_headers_mode': ''}


def test_log_editor_writes_file_rotation_and_access_filters(client):
    res = _static_section(client, 'log:\n  level: ERROR\n', 'log', 'set', '', dict(LOG_BASE, **{
        'level': 'INFO', 'log_format': 'json', 'log_file': '/logs/traefik.log',
        'log_max_size': '50', 'log_max_backups': '3', 'log_compress': True,
        'accessLog': True, 'accessLogPath': '/logs/access.log', 'al_format': 'json',
        'al_buffering': '100', 'al_status_codes': '400-499, 500', 'al_min_duration': '200ms',
        'al_headers_mode': 'keep',
    }))
    assert res.status_code == 200, res.data
    parsed = res.get_json()['parsed']
    log = parsed['log']
    assert log == {'level': 'INFO', 'format': 'json', 'filePath': '/logs/traefik.log',
                   'maxSize': 50, 'maxBackups': 3, 'compress': True}
    al = parsed['accessLog']
    assert al['filePath'] == '/logs/access.log' and al['format'] == 'json'
    assert al['bufferingSize'] == 100
    assert al['filters'] == {'statusCodes': ['400-499', '500'], 'minDuration': '200ms'}
    assert al['fields'] == {'headers': {'defaultMode': 'keep'}}


def test_log_edit_preserves_unmanaged_keys(client):
    raw = ("log:\n  level: INFO\n  noColor: true\n"
           "accessLog:\n  filePath: /logs/a.log\n  addInternals: true\n"
           "  fields:\n    names:\n      StartUTC: drop\n")
    res = _static_section(client, raw, 'log', 'set', '', dict(LOG_BASE, **{
        'level': 'DEBUG', 'accessLog': True, 'accessLogPath': '/logs/a.log',
    }))
    assert res.status_code == 200, res.data
    parsed = res.get_json()['parsed']
    assert parsed['log']['noColor'] is True, 'unmanaged log keys must survive'
    assert parsed['accessLog']['addInternals'] is True
    assert parsed['accessLog']['fields']['names'] == {'StartUTC': 'drop'}, 'per-field names must survive'


def test_log_editor_rejects_bad_values(client):
    assert _static_section(client, '', 'log', 'set', '', dict(LOG_BASE,
        log_file='/l.log', log_max_size='big')).status_code == 400
    assert _static_section(client, '', 'log', 'set', '', dict(LOG_BASE,
        accessLog=True, al_status_codes='4xx')).status_code == 400
    assert _static_section(client, '', 'log', 'set', '', dict(LOG_BASE,
        accessLog=True, al_min_duration='fast')).status_code == 400


OBS_BASE = {'ping': False, 'prometheus': False, 'prom_ep_labels': True, 'prom_router_labels': False,
            'prom_svc_labels': True, 'tracing': False, 'trace_service': '', 'trace_sample': '',
            'trace_endpoint': ''}


def test_observability_editor_writes_ping_prometheus_and_tracing(client):
    res = _static_section(client, '', 'observability', 'set', '', dict(OBS_BASE, **{
        'ping': True, 'prometheus': True, 'prom_router_labels': True, 'prom_svc_labels': False,
        'tracing': True, 'trace_service': 'edge', 'trace_sample': '0.5',
        'trace_endpoint': 'http://collector:4318/v1/traces',
    }))
    assert res.status_code == 200, res.data
    parsed = res.get_json()['parsed']
    assert parsed['ping'] == {}
    assert parsed['metrics']['prometheus'] == {'addRoutersLabels': True, 'addServicesLabels': False}
    assert parsed['tracing'] == {'serviceName': 'edge', 'sampleRate': 0.5,
                                 'otlp': {'http': {'endpoint': 'http://collector:4318/v1/traces'}}}


def test_observability_preserves_other_metrics_backends(client):
    raw = "metrics:\n  datadog:\n    address: dd:8125\n  prometheus: {}\n"
    res = _static_section(client, raw, 'observability', 'set', '',
                          dict(OBS_BASE, prometheus=False))
    assert res.status_code == 200, res.data
    parsed = res.get_json()['parsed']
    assert parsed['metrics'] == {'datadog': {'address': 'dd:8125'}}, \
        'disabling prometheus must not touch other metrics backends'
    bad = _static_section(client, '', 'observability', 'set', '',
                          dict(OBS_BASE, tracing=True, trace_sample='5'))
    assert bad.status_code == 400


def test_system_editor_writes_global_and_core(client):
    res = _static_section(client, '', 'system', 'set', '', {
        'check_new_version': False, 'send_usage': True, 'rule_syntax': 'v2'})
    assert res.status_code == 200, res.data
    parsed = res.get_json()['parsed']
    assert parsed['global'] == {'checkNewVersion': False, 'sendAnonymousUsage': True}
    assert parsed['core'] == {'defaultRuleSyntax': 'v2'}
    back = _static_section(client, res.get_json()['raw'], 'system', 'set', '', {
        'check_new_version': True, 'send_usage': False, 'rule_syntax': ''})
    parsed2 = back.get_json()['parsed']
    assert 'global' not in parsed2 and 'core' not in parsed2, 'defaults must remove the blocks'


def test_local_plugins_are_managed_separately(client):
    raw = "experimental:\n  plugins:\n    remote1:\n      moduleName: github.com/a/b\n      version: v1\n"
    res = _static_section(client, raw, 'plugins', 'add', 'dev-plugin',
                          {'moduleName': 'github.com/me/dev', 'version': '', 'local': True})
    assert res.status_code == 200, res.data
    exp = res.get_json()['parsed']['experimental']
    assert exp['localPlugins'] == {'dev-plugin': {'moduleName': 'github.com/me/dev'}}
    assert 'dev-plugin' not in exp['plugins']
    res2 = _static_section(client, res.get_json()['raw'], 'plugins', 'edit', 'dev-plugin',
                           {'moduleName': 'github.com/me/dev', 'version': 'v2', 'local': False})
    exp2 = res2.get_json()['parsed']['experimental']
    assert 'localPlugins' not in exp2, 'switching to remote must drop the local entry'
    assert exp2['plugins']['dev-plugin'] == {'moduleName': 'github.com/me/dev', 'version': 'v2'}


def test_providers_throttle_duration_roundtrip(client):
    raw, parsed = _static_providers_roundtrip(client, BARE_DOCKER, {
        'docker': True, 'dockerEndpoint': '', 'dockerExposedByDefault': True,
        'dockerWatch': True, 'file': False, 'providers_throttle': '5s',
    })
    assert parsed['providers']['providersThrottleDuration'] == '5s'
    raw2, parsed2 = _static_providers_roundtrip(client, raw, {
        'docker': True, 'dockerEndpoint': '', 'dockerExposedByDefault': True,
        'dockerWatch': True, 'file': False, 'providers_throttle': '',
    })
    assert 'providersThrottleDuration' not in parsed2['providers']


def test_servers_transport_defaults_roundtrip(client):
    res = _static_section(client, '', 'system', 'set', '', {
        'check_new_version': True, 'send_usage': False, 'rule_syntax': '',
        'st_insecure': True, 'st_root_cas': '/certs/ca.pem', 'st_max_idle': '100',
        'st_dial': '10s', 'st_resp_header': '', 'st_idle_conn': '90',
    })
    assert res.status_code == 200, res.data
    st = res.get_json()['parsed']['serversTransport']
    assert st == {'insecureSkipVerify': True, 'rootCAs': ['/certs/ca.pem'],
                  'maxIdleConnsPerHost': 100,
                  'forwardingTimeouts': {'dialTimeout': '10s', 'idleConnTimeout': 90}}
    bad = _static_section(client, '', 'system', 'set', '', {
        'check_new_version': True, 'send_usage': False, 'rule_syntax': '',
        'st_insecure': False, 'st_root_cas': '', 'st_max_idle': 'lots',
        'st_dial': '', 'st_resp_header': '', 'st_idle_conn': '',
    })
    assert bad.status_code == 400


def test_dashboard_config_is_scoped_per_server(client):
    hdrs = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
    host = {'custom_groups': [{'name': 'Host Work'}],
            'route_overrides': {'r1': {'group': 'Host Work'}}}
    assert client.post('/api/dashboard/config', json=host, headers=hdrs).status_code == 200

    agent = {'custom_groups': [{'name': 'Agent Media'}],
             'route_overrides': {'r1': {'group': 'Agent Media'}}, 'server': 'agent-abc'}
    assert client.post('/api/dashboard/config?server=agent-abc', json=agent,
                       headers=hdrs).status_code == 200

    got_host = client.get('/api/dashboard/config').get_json()
    assert [g['name'] for g in got_host['custom_groups']] == ['Host Work'], \
        'an agent group must not appear on the host'
    assert got_host['route_overrides']['r1']['group'] == 'Host Work'

    got_agent = client.get('/api/dashboard/config?server=agent-abc').get_json()
    assert [g['name'] for g in got_agent['custom_groups']] == ['Agent Media']
    assert got_agent['route_overrides']['r1']['group'] == 'Agent Media', \
        'same route id on two servers must not share an override'

    other = client.get('/api/dashboard/config?server=agent-zzz').get_json()
    assert other['custom_groups'] == [] and other['route_overrides'] == {}, \
        'a server with no config of its own starts empty, not with another servers groups'


def test_routers_and_services_report_traefik_reachability(client, app_module, monkeypatch):
    for path in ('/api/traefik/routers', '/api/traefik/services'):
        body = client.get(path).get_json()
        assert body['reachable'] is False, \
            path + ' must say the API is unreachable, not answer 200 with empty lists'
        assert body['http'] == [] and body['tcp'] == [] and body['udp'] == []

    monkeypatch.setattr(app_module, 'traefik_api_get_all', lambda p, complete=None: [])
    for path in ('/api/traefik/routers', '/api/traefik/services'):
        body = client.get(path).get_json()
        assert body['reachable'] is True, \
            'an estate with genuinely zero routers is reachable, not blind'
        assert body['complete'] is True, \
            'every protocol answered, so the list is whole'


def test_one_protocol_failing_is_not_a_complete_router_list(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, 'traefik_api_get_all',
                        lambda p, complete=None: [] if '/http/' in p else None)
    body = client.get('/api/traefik/routers').get_json()
    assert body['reachable'] is True, 'http answered, so Traefik is up'
    assert body['complete'] is False, \
        'tcp never answered, so an unlisted tcp router would look like it does not exist'


def test_dashboard_config_read_drops_a_hand_written_javascript_link(client, app_module):
    with open(app_module.GROUPS_CONFIG_FILE, 'w') as f:
        f.write('custom_groups: []\n'
                'route_overrides:\n'
                '  evil:\n'
                "    url: 'javascript:alert(1)'\n"
                '  fine:\n'
                "    url: 'https://ok.example'\n")
    got = client.get('/api/dashboard/config').get_json()
    with open(app_module.GROUPS_CONFIG_FILE, 'w') as f:
        f.write('custom_groups: []\nroute_overrides: {}\n')
    assert 'url' not in got['route_overrides']['evil'], \
        'a non http link written straight into the file must not be served back'
    assert got['route_overrides']['fine']['url'] == 'https://ok.example'


def test_tls_options_are_not_shown_for_agents(client, monkeypatch, app_module):
    host = client.get('/api/tls-options').get_json()
    assert isinstance(host, list)

    monkeypatch.setattr(app_module, '_agent_by_id', lambda i: {'id': i, 'name': i, 'url': 'http://x'})
    monkeypatch.setattr(app_module, '_agent_load_configs', lambda a: {'dynamic.yml': {}})
    agent = client.get('/api/tls-options?server=agent-abc').get_json()
    assert agent == [], 'an agent with no tls options must not show the hosts profiles'

    monkeypatch.setattr(app_module, '_agent_load_configs',
                        lambda a: {'dynamic.yml': {'tls': {'options': {'agentonly': {'minVersion': 'VersionTLS13'}}}}})
    agent2 = client.get('/api/tls-options?server=agent-abc').get_json()
    assert [o['name'] for o in agent2] == ['agentonly']


def test_paged_fallback_still_returns_every_decision(client, monkeypatch):
    ip = '203.0.113.9'
    calls = _cs_lapi_stub(monkeypatch, capi_count=6000, local_ip=ip, stream=False)

    res = client.get('/api/crowdsec/decisions')
    assert res.status_code == 200, res.data
    values = [d['value'] for d in res.get_json()]
    assert ip in values, (
        'On a LAPI with no /v1/decisions/stream the paged walk must still find every '
        'decision, including one past the old cap. See issue #130.')
    assert any('stream' in c for c in calls), 'the stream endpoint should be tried first'
    assert any('id_gt=' in c for c in calls), 'it should fall back to the paged walk'


def test_stream_is_preferred_and_pages_only_once(client, monkeypatch):
    calls = _cs_lapi_stub(monkeypatch, capi_count=6000, local_ip='198.51.100.4')

    res = client.get('/api/crowdsec/decisions')
    assert res.status_code == 200
    assert len(res.get_json()) == 6001
    assert len(calls) == 1, f'the stream should need one call, got {calls[:5]}'
    assert 'startup=true' in calls[0]


def test_second_read_uses_a_delta_not_a_full_resync(client, monkeypatch):
    calls = _cs_lapi_stub(monkeypatch, capi_count=10, local_ip='198.51.100.5')

    client.get('/api/crowdsec/decisions')
    client.get('/api/crowdsec/decisions')
    assert 'startup=true' in calls[0]
    assert 'startup=true' not in calls[1], 'the second read must be an incremental delta'
