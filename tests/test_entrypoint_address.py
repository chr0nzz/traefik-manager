import json

import pytest

RAW = "entryPoints:\n  web:\n    address: ':80'\n"

EP_BASE = {'address': ':443', 'redirect_to': '', 'http3': False, 'underscore_headers': '',
           'trusted_ips': '', 'forwarded_insecure': False, 'proxy_trusted_ips': '',
           'proxy_insecure': False, 'middlewares': '', 'tls_enabled': False,
           'tls_cert_resolver': '', 'tls_options': '', 'as_default': False,
           'read_timeout': '', 'write_timeout': '', 'idle_timeout': ''}


def _static_section(client, raw, section, action, name, data):
    return client.post('/api/static/section',
                       data=json.dumps({'action': action, 'section': section, 'name': name,
                                        'old_name': name, 'data': data, 'current_raw': raw}),
                       content_type='application/json',
                       headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})


@pytest.mark.parametrize('typed, saved', [
    ('8080', ':8080'),
    ('8443/udp', ':8443/udp'),
    ('51820/UDP', ':51820/udp'),
    (':443', ':443'),
    ('0.0.0.0:80', '0.0.0.0:80'),
    ('[::]:443', '[::]:443'),
    ('localhost:9000/tcp', 'localhost:9000/tcp'),
])
def test_entrypoint_address_saved_in_traefik_format(client, typed, saved):
    res = _static_section(client, RAW, 'entrypoints', 'edit', 'web', dict(EP_BASE, address=typed))
    assert res.status_code == 200, res.data
    assert res.get_json()['parsed']['entryPoints']['web']['address'] == saved


@pytest.mark.parametrize('typed', ['abc', 'myhost', ':0', ':70000', '80/sctp', 'http://:80', ':80:81'])
def test_entrypoint_address_refused_when_invalid(client, typed):
    res = _static_section(client, RAW, 'entrypoints', 'add', 'other', dict(EP_BASE, address=typed))
    assert res.status_code == 400
    assert 'Entrypoint address' in json.loads(res.data)['error']


def test_entrypoint_empty_address_keeps_existing(client):
    res = _static_section(client, RAW, 'entrypoints', 'edit', 'web', dict(EP_BASE, address=''))
    assert res.status_code == 200, res.data
    assert res.get_json()['parsed']['entryPoints']['web']['address'] == ':80'
