import glob
import json
import os
import re

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from flask_babel import get_domain

from core import agent_errors, i18n
from tests.conftest import tm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch', 'Accept-Language': 'de'}
AGENT = {'id': 'a1', 'name': 'edge', 'url': 'http://agent.invalid:8090', 'api_key': 'k'}
SAMPLE = {'detail': 'boom', 'file': 'routes.yml', 'url': 'http://traefik:8080', 'path': '/logs/access.log', 'removed': 2, 'name': 'chain-no-auth'}


def _agent_codes():
    codes = set()
    for path in glob.glob(os.path.join(ROOT, 'agent', '*.go')):
        if path.endswith('_test.go'):
            continue
        src = open(path, encoding='utf-8').read()
        codes |= set(re.findall(r'jsonErrorCode\(w, "(\w+)"', src))
        codes |= set(re.findall(r'"code": "(\w+)"', src))
        codes |= set(re.findall(r'reasonCode = "[^"]*", "(\w+)"', src))
    return codes


def test_every_agent_code_has_a_message_and_none_are_stale():
    codes = _agent_codes()
    assert len(codes) > 50
    assert codes == set(agent_errors.MESSAGES)


def test_every_message_formats_with_the_params_the_agent_sends():
    with tm.app.test_request_context('/'):
        for code, fn in agent_errors.MESSAGES.items():
            text = fn(SAMPLE)
            assert text and '%(' not in text, code


@pytest.fixture
def german(tmp_path, monkeypatch):
    catalog = Catalog(locale='de')
    catalog.add('Invalid YAML: %(error)s', 'Ungültiges YAML: %(error)s')
    catalog.add('The agent refused the API key', 'Der Agent hat den API-Schlüssel abgelehnt')
    catalog.add(('Removed %(num)d certificate, then stopped at %(file)s: %(detail)s',
                 'Removed %(num)d certificates, then stopped at %(file)s: %(detail)s'),
                ('%(num)d Zertifikat entfernt, dann bei %(file)s angehalten: %(detail)s',
                 '%(num)d Zertifikate entfernt, dann bei %(file)s angehalten: %(detail)s'))
    catalog.add('acme.json is mounted read only on this agent', 'acme.json ist auf diesem Agenten schreibgeschützt')
    target = tmp_path / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)
    app = tm.app
    monkeypatch.setattr(app.extensions['babel'], 'translation_directories', [str(tmp_path)])
    monkeypatch.setattr(i18n, 'available_tags', lambda locale_dir=None: ('en', 'de'))
    with app.test_request_context('/'):
        monkeypatch.setattr(get_domain(), 'cache', {})
    return app


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self.content = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = {'content-type': 'application/json'}
        self.ok = status < 400

    def json(self):
        return json.loads(self.content)


@pytest.fixture
def agent_reply(monkeypatch):
    reply = {}
    monkeypatch.setattr(tm, '_agent_by_id', lambda agent_id: AGENT if agent_id == 'a1' else None)
    monkeypatch.setattr(tm, '_agent_request', lambda agent, method, path, **kw: reply['resp'])
    return reply


def test_a_coded_agent_error_is_translated_for_a_german_session(german, client, agent_reply):
    agent_reply['resp'] = _Resp(400, {'error': 'invalid YAML: line 3', 'code': 'invalid_yaml',
                                      'params': {'detail': 'line 3'}, 'ok': False})
    r = client.post('/api/agents/proxy/a1/static', json={'content': 'x'}, headers=HDR)
    assert r.status_code == 400
    body = r.get_json()
    assert body['error'] == 'Ungültiges YAML: line 3'
    assert body['code'] == 'invalid_yaml' and body['params'] == {'detail': 'line 3'}


def test_the_partial_certificate_error_uses_the_plural(german, client, agent_reply):
    agent_reply['resp'] = _Resp(500, {'error': 'removed 1 certificate(s), then stopped at acme.json: x',
                                      'code': 'certs_partial', 'params': {'removed': 1, 'file': 'acme.json', 'detail': 'x'},
                                      'removed': 1, 'partial': True})
    r = client.post('/api/agents/proxy/a1/traefik/certs/delete', json={}, headers=HDR)
    assert r.get_json()['error'] == '1 Zertifikat entfernt, dann bei acme.json angehalten: x'


def test_english_sessions_get_the_agent_bytes_unchanged(german, client, agent_reply):
    raw = b'{"error":"unauthorized","code":"unauthorized","ok":false}\n'
    agent_reply['resp'] = _Resp(401, raw)
    r = client.get('/api/agents/proxy/a1/configs', headers={k: v for k, v in HDR.items() if k != 'Accept-Language'})
    assert r.status_code == 401
    assert r.get_data() == raw


def test_an_old_agent_without_codes_passes_through(german, client, agent_reply):
    raw = b'{"error":"invalid YAML: line 3","ok":false}\n'
    agent_reply['resp'] = _Resp(400, raw)
    r = client.post('/api/agents/proxy/a1/static', json={}, headers=HDR)
    assert r.get_data() == raw


def test_a_success_body_is_never_rewritten(german, client, agent_reply):
    raw = b'{"routers":[{"name":"a","code":"x"}],"total":1.0}\n'
    agent_reply['resp'] = _Resp(200, raw)
    r = client.get('/api/agents/proxy/a1/traefik/routers', headers=HDR)
    assert r.get_data() == raw


def test_unknown_codes_and_bad_params_fall_back_to_the_agent_text(german):
    with tm.app.test_request_context('/', headers={'Accept-Language': 'de'}):
        assert agent_errors.text('from_a_newer_agent', {}, 'english') == 'english'
        assert agent_errors.text('invalid_yaml', {}, 'english') == 'english'
        assert agent_errors.text('invalid_yaml', 'not a dict', 'english') == 'english'
        assert agent_errors.text('certs_partial', {'removed': 'many', 'file': 'f', 'detail': 'd'}, 'english') == 'english'
        assert agent_errors.text(['invalid_yaml'], {'detail': 'x'}, 'english') == 'english'


def test_the_cert_status_reason_is_translated(german, client, agent_reply):
    agent_reply['resp'] = _Resp(200, {'available': False, 'writable': False, 'restart_method': '',
                                      'reason': 'acme.json is mounted read only on this agent',
                                      'reason_code': 'acme_read_only', 'paths': []})
    r = client.get('/api/certs/manage?server=a1', headers=HDR)
    assert r.get_json()['reason'] == 'acme.json ist auf diesem Agenten schreibgeschützt'
