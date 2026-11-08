import os

import pytest
from ruamel.yaml import YAML

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}

FORM = {'address': ':443', 'redirect_to': '', 'underscore_headers': '', 'trusted_ips': '',
        'forwarded_insecure': False, 'proxy_trusted_ips': '', 'proxy_insecure': False,
        'middlewares': '', 'tls_enabled': False, 'tls_cert_resolver': '', 'tls_options': '',
        'as_default': False, 'read_timeout': '60s', 'write_timeout': '', 'idle_timeout': ''}

WITH_PORT = ("entryPoints:\n  websecure:\n    address: ':443'\n"
             "    http3:\n      advertisedPort: 8443\n")
BARE_KEY = "entryPoints:\n  websecure:\n    address: ':443'\n    http3:\n"
NO_HTTP3 = "entryPoints:\n  websecure:\n    address: ':443'\n"


@pytest.fixture
def static_file():
    path = os.environ['STATIC_CONFIG_PATH']
    with open(path) as fh:
        original = fh.read()
    yield path
    with open(path, 'w') as fh:
        fh.write(original)


def _save(client, path, raw, http3):
    res = client.post('/api/static/section', headers=HDR, json={
        'action': 'edit', 'section': 'entrypoints', 'name': 'websecure', 'old_name': 'websecure',
        'data': dict(FORM, http3=http3), 'current_raw': raw})
    assert res.status_code == 200, res.data
    saved = client.post('/api/static/config', headers=HDR, json={'content': res.get_json()['raw']})
    assert saved.status_code == 200, saved.data
    with open(path) as fh:
        return YAML(typ='safe').load(fh)['entryPoints']['websecure']


def test_save_keeps_http3_advertised_port(client, static_file):
    ep = _save(client, static_file, WITH_PORT, True)
    assert ep['http3'] == {'advertisedPort': 8443}
    assert ep['transport']['respondingTimeouts']['readTimeout'] == '60s'


def test_ticking_http3_writes_empty_block(client, static_file):
    assert _save(client, static_file, NO_HTTP3, True)['http3'] == {}


def test_ticking_http3_replaces_bare_key(client, static_file):
    assert _save(client, static_file, BARE_KEY, True)['http3'] == {}


def test_unticking_http3_removes_block(client, static_file):
    assert 'http3' not in _save(client, static_file, WITH_PORT, False)
