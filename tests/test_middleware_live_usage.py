import os
import shutil
import subprocess

import pytest

from conftest import read_config, write_config

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}

BASE = """
http:
  routers:
    web:
      rule: Host(`web.example.com`)
      service: web-svc
      middlewares: [compress]
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
tcp:
  middlewares:
    tcp-allow:
      ipAllowList:
        sourceRange: ["10.0.0.0/8"]
"""

AGENT = {'id': 'a1', 'name': 'edge', 'url': 'http://agent.invalid', 'key': 'k'}


def _names(section='http'):
    return sorted((read_config().get(section) or {}).get('middlewares') or {})


def _live(monkeypatch, app_module, http=None, tcp=None):
    calls = []

    def fake(path, complete=None):
        calls.append(path)
        if path.startswith('/api/http/middlewares'):
            return http
        if path.startswith('/api/tcp/middlewares'):
            return tcp
        return None
    monkeypatch.setattr(app_module, 'traefik_api_get_all', fake)
    return calls


def _delete(client, name, **extra):
    return client.post('/delete-middleware/' + name, data={'csrf_token': 'testtoken', **extra}, headers=HDR)


def test_a_middleware_used_only_by_docker_labels_is_refused(client, monkeypatch, app_module):
    write_config(BASE)
    _live(monkeypatch, app_module, http=[
        {'name': 'auth@file', 'provider': 'file', 'usedBy': ['whoami@docker']},
        {'name': 'compress@file', 'provider': 'file', 'usedBy': ['web@file']},
    ], tcp=[])
    r = _delete(client, 'auth')
    assert r.status_code == 409, r.get_data(as_text=True)
    body = r.get_json() or {}
    assert body.get('inUseBy') == ['whoami@docker'], body
    assert body.get('externalUsers') == ['whoami@docker'], body
    assert 'whoami@docker' in (body.get('message') or ''), body
    assert 'auth' in _names(), 'a middleware Docker routers still use was deleted'


def test_file_routers_and_other_providers_are_both_named(client, monkeypatch, app_module):
    write_config(BASE.replace('middlewares: [compress]', 'middlewares: [compress, auth]'))
    _live(monkeypatch, app_module, http=[
        {'name': 'auth@file', 'provider': 'file', 'usedBy': ['web@file', 'whoami@docker', 'api@kubernetescrd']},
    ], tcp=[])
    body = _delete(client, 'auth').get_json() or {}
    assert body.get('inUseBy') == ['web', 'api@kubernetescrd', 'whoami@docker'], body
    assert body.get('externalUsers') == ['api@kubernetescrd', 'whoami@docker'], body


def test_force_deletes_without_asking_traefik(client, monkeypatch, app_module):
    write_config(BASE)
    calls = _live(monkeypatch, app_module, http=[
        {'name': 'auth@file', 'provider': 'file', 'usedBy': ['whoami@docker']},
    ], tcp=[])
    r = _delete(client, 'auth', force='true')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in _names()
    assert not [c for c in calls if 'middlewares' in c], calls


def test_an_unreachable_traefik_falls_back_to_the_files(client, monkeypatch, app_module):
    write_config(BASE)
    _live(monkeypatch, app_module, http=None, tcp=None)
    r = _delete(client, 'auth')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in _names()


def test_a_same_named_middleware_from_another_provider_does_not_count(client, monkeypatch, app_module):
    write_config(BASE)
    _live(monkeypatch, app_module, http=[
        {'name': 'auth@docker', 'provider': 'docker', 'usedBy': ['whoami@docker']},
        {'name': 'auth@file', 'provider': 'file', 'usedBy': []},
    ], tcp=[])
    r = _delete(client, 'auth')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in _names()


def test_a_tcp_middleware_used_by_another_provider_is_refused(client, monkeypatch, app_module):
    write_config(BASE)
    _live(monkeypatch, app_module, http=[], tcp=[
        {'name': 'tcp-allow@file', 'provider': 'file', 'usedBy': ['db@docker']},
    ])
    r = _delete(client, 'tcp-allow')
    assert r.status_code == 409, r.get_data(as_text=True)
    assert (r.get_json() or {}).get('inUseBy') == ['db@docker']
    assert 'tcp-allow' in _names('tcp')


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload

    def json(self):
        return self._payload


def _agent(monkeypatch, app_module, reply):
    written = {}
    paths = []
    configs = {'dynamic.yml': read_config()}

    def fake_request(agent, method, path, **kw):
        paths.append((method, path))
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(app_module, '_agent_by_id', lambda i: AGENT if i == 'a1' else None)
    monkeypatch.setattr(app_module, '_agent_load_configs', lambda a: configs)
    monkeypatch.setattr(app_module, '_agent_write_config', lambda a, f, c: written.__setitem__(f, c))
    monkeypatch.setattr(app_module, '_agent_request', fake_request)
    monkeypatch.setattr(app_module, '_git_push_agent_if_enabled', lambda *a, **k: None)
    monkeypatch.setattr(app_module, 'traefik_api_get_all',
                        lambda *a, **k: pytest.fail('an agent delete must ask the agent, not the hub Traefik'))
    return written, paths


def test_an_agent_middleware_used_by_docker_labels_is_refused(client, monkeypatch, app_module):
    write_config(BASE)
    written, paths = _agent(monkeypatch, app_module, _Resp(200, {
        'http': [{'name': 'auth@file', 'provider': 'file', 'usedBy': ['whoami@docker']}], 'tcp': []}))
    r = _delete(client, 'auth', agent_id='a1')
    assert r.status_code == 409, r.get_data(as_text=True)
    assert (r.get_json() or {}).get('inUseBy') == ['whoami@docker']
    assert ('GET', '/api/traefik/middlewares') in paths
    assert not written, 'the agent config was written despite the refusal'


@pytest.mark.parametrize('reply', [_Resp(404, {'error': 'not found'}), _Resp(502, {}), ConnectionError('down')])
def test_an_agent_without_live_usage_still_deletes(client, monkeypatch, app_module, reply):
    write_config(BASE)
    written, _ = _agent(monkeypatch, app_module, reply)
    r = _delete(client, 'auth', agent_id='a1')
    assert r.status_code == 200, r.get_data(as_text=True)
    assert 'auth' not in ((written.get('dynamic.yml') or {}).get('http') or {}).get('middlewares', {})


def test_the_browser_counts_other_providers():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_mw_live_usage.mjs where it is')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([node, os.path.join(root, 'scripts', 'test_mw_live_usage.mjs')],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
