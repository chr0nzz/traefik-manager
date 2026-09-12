import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACME = {
    'letsencrypt': {
        'Account': {'Email': 'a@b.c', 'PrivateKey': 'zzz', 'Registration': {'uri': 'https://acme/1'}},
        'Certificates': [{'domain': {'main': 'app.example.com', 'sans': []}, 'certificate': '', 'key': ''}],
    },
    'gone': {
        'Account': {'Email': 'a@b.c'},
        'Certificates': [{'domain': {'main': 'old.example.com', 'sans': []}, 'certificate': '', 'key': ''}],
    },
}


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _write_acme(tmp_path, monkeypatch, data=None):
    path = tmp_path / 'acme.json'
    path.write_text(json.dumps(data if data is not None else ACME))
    path.chmod(0o600)
    monkeypatch.setenv('ACME_JSON_PATH', str(path))
    from core import env as env_mod
    env_mod.register_read_path(str(path))
    return path


def test_the_endpoint_answers_for_the_host(client, tmp_path, monkeypatch):
    _write_acme(tmp_path, monkeypatch)
    res = client.get('/api/certs/usage')
    assert res.status_code == 200
    body = res.get_json()
    for key in ('certs', 'unused_known', 'why', 'resolvers_known'):
        assert key in body, f'{key} missing, the tab cannot explain itself without it'


def test_an_unknown_server_is_not_silently_treated_as_the_host(client):
    res = client.get('/api/certs/usage?server=nope')
    assert res.status_code == 404, 'answering for the Host would show the wrong certificates'


def test_it_needs_a_login(anon_client):
    res = anon_client.get('/api/certs/usage')
    assert res.status_code == 401, 'certificate domains are not public'


def test_nothing_is_called_unused_when_traefik_cannot_be_read(client, tmp_path, monkeypatch):
    _write_acme(tmp_path, monkeypatch)
    import app as app_mod
    monkeypatch.setattr(app_mod._trae, '_traefik_request', lambda *a, **k: None)
    body = client.get('/api/certs/usage').get_json()
    assert body['unused_known'] is False
    assert not any(c['unused'] for c in body['certs'])


def test_the_router_reader_reports_truncation():
    src = _read('core', 'traefik.py')
    body = src[src.index('def traefik_api_get_all('):src.index('def _fetch_traefik_routers_and_services')]
    assert 'complete' in body, 'a half-read router list looked complete, so live certs looked unused'
    assert body.count('complete.append(False)') >= 2


def test_the_proto_payload_does_not_call_one_working_protocol_reachable():
    src = _read('app.py')
    body = src[src.index('def _traefik_proto_payload(kind):'):src.index("@app.route('/api/traefik/routers')")]
    assert "out['complete']" in body
    assert 'all(v is not None' in body, 'any() reported reachable when tcp was down'


def test_the_agent_reports_its_tcp_and_udp_errors():
    src = _read('agent', 'handlers.go')
    body = src[src.index('func (a *App) routersHandler('):src.index('func (a *App) servicesHandler(')]
    assert 'tcpErr' in body and 'udpErr' in body, 'a dead tcp endpoint looked like no tcp routers'
    assert '"complete"' in body


def test_tls_domains_survive_for_tcp_and_for_other_providers():
    src = _read('core', 'routes_build.py')
    assert src.count("'tlsDomains'") >= 3, \
        'a route that pre-issues a certificate must be visible for every provider'


def test_the_certs_tab_explains_itself_rather_than_guessing():
    js = _read('static', 'js', 'certs.js')
    assert '_loadCertUsage' in js and '/api/certs/usage' in js
    assert '_certUsage.why' in js, 'the strip must say why it cannot tell'
    assert re.search(r"label: 'unused'", js) and re.search(r"label: 'no resolver'", js)
    assert 'tm-warn' in js, 'chips must use the existing card styling'
