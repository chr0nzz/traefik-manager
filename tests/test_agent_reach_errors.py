import os
import re
import socket
import time

import pytest
import requests
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.support import Translations

from core import i18n as _i18n
from test_agent_health_errors import (TRUST, _assert_no_wrapper, _cert, _closed_port_url, _ip_sans, _plain_http,
                                      _seed, connect_fails, server)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
API_TRUST = 'TLS verification failed - the API certificate is not trusted. '
API_CONN = 'Connection error - check the URL and network. ('

__all__ = ['connect_fails', 'server']


def _routes(client):
    r = client.get('/api/agents/a1/routes')
    return r.status_code, r.get_json()['error']


def _proxy(client):
    r = client.get('/api/agents/proxy/a1/keys', headers=HDR)
    return r.status_code, r.get_json()['error']


def _api_test(client, url):
    return client.post('/api/settings/test-connection', json={'url': url}, headers=HDR).get_json()


def _answer_json(conn):
    conn.recv(4096)
    body = b'{"Version": "3.7.17"}'
    conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n'
                 b'Content-Length: %d\r\n\r\n%s' % (len(body), body))


def _slow(conn):
    conn.recv(4096)
    time.sleep(2)


@pytest.fixture
def api_ssrf(monkeypatch):
    import app as tm
    monkeypatch.setattr(tm, '_ssrf_ok', lambda u: True)


def test_agent_routes_name_a_refused_connection(client):
    _seed(_closed_port_url())
    code, text = _routes(client)
    assert code == 502 and text == 'Cannot reach agent (connection refused)', text


def test_agent_routes_name_an_unresolvable_host(client, connect_fails):
    connect_fails(socket.gaierror(socket.EAI_NONAME, 'Name or service not known'))
    _seed('https://agent.example.test')
    code, text = _routes(client)
    assert code == 502 and text == 'Cannot reach agent (DNS name agent.example.test does not resolve)', text


def test_agent_routes_on_a_plain_http_agent_name_the_handshake_not_trust(client, server):
    srv = server(_plain_http)
    _seed(srv.url('https'))
    code, text = _routes(client)
    assert code == 502 and text.startswith('Cannot reach agent (TLS handshake failed (') and text.endswith('))'), text
    assert '_ssl.c' not in text and '[SSL' not in text, text
    assert 'not trusted' not in text


def test_agent_routes_with_a_self_signed_certificate_keep_the_trust_wording(client, server, tmp_path):
    _path, context = _cert(tmp_path, _ip_sans())
    srv = server(_answer_json, context)
    _seed(srv.url('https'))
    code, text = _routes(client)
    assert code == 502 and text.startswith(TRUST) and text.endswith(')'), text
    assert re.search(r'self[- ]signed certificate', text[len(TRUST):]), text
    _assert_no_wrapper(text)


def test_agent_routes_that_time_out_answer_504(client, server, monkeypatch):
    srv = server(_slow)
    _seed(srv.url())
    real = requests.request
    monkeypatch.setattr(requests, 'request', lambda m, u, **kw: real(m, u, **{**kw, 'timeout': 0.3}))
    code, text = _routes(client)
    assert code == 504 and text == 'Agent timed out', text


def test_agent_proxy_names_a_refused_connection(client):
    _seed(_closed_port_url())
    code, text = _proxy(client)
    assert code == 502 and text == 'Cannot reach agent (connection refused)', text


def test_agent_proxy_names_a_connect_timeout(client, connect_fails):
    connect_fails(socket.timeout('timed out'))
    _seed('https://agent.example.test')
    code, text = _proxy(client)
    assert code == 502 and text == 'Cannot reach agent (connection timed out)', text


def test_agent_proxy_with_a_self_signed_certificate_keeps_the_trust_wording(client, server, tmp_path):
    _path, context = _cert(tmp_path, _ip_sans())
    srv = server(_answer_json, context)
    _seed(srv.url('https'))
    code, text = _proxy(client)
    assert code == 502 and text.startswith(TRUST), text
    assert re.search(r'self[- ]signed certificate', text), text
    _assert_no_wrapper(text)


def test_the_reason_is_shown_in_the_requester_language(client, monkeypatch, tmp_path, api_ssrf):
    catalog = Catalog(locale='de')
    catalog.add('connection refused', 'Verbindung abgelehnt', context='check failure')
    catalog.add('Cannot reach agent (%(reason)s)', 'Agent nicht erreichbar (%(reason)s)', flags=['python-format'])
    catalog.add('Connection error - check the URL and network. (%(error)s)',
                'Verbindungsfehler (%(error)s)', flags=['python-format'])
    target = tmp_path / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)
    german = Translations.load(str(tmp_path), ['de'], 'messages')
    monkeypatch.setattr(_i18n, '_request_translations', lambda: german)
    _seed(_closed_port_url())
    assert _routes(client) == (502, 'Agent nicht erreichbar (Verbindung abgelehnt)')
    assert _api_test(client, _closed_port_url('http'))['error'] == 'Verbindungsfehler (Verbindung abgelehnt)'


def test_traefik_api_test_names_a_refused_connection(client, api_ssrf):
    d = _api_test(client, _closed_port_url('http'))
    assert d['ok'] is False and d['error'] == API_CONN + 'connection refused)', d


def test_traefik_api_test_on_a_plain_http_api_names_the_handshake(client, server, api_ssrf):
    srv = server(_plain_http)
    d = _api_test(client, srv.url('https'))
    assert d['error'].startswith(API_CONN + 'TLS handshake failed (') and d['error'].endswith('))'), d
    assert '_ssl.c' not in d['error'] and '[SSL' not in d['error'], d
    assert 'not trusted' not in d['error']


def test_traefik_api_test_with_a_self_signed_certificate_names_the_verify_reason(client, server, tmp_path,
                                                                                  api_ssrf):
    _path, context = _cert(tmp_path, _ip_sans())
    srv = server(_answer_json, context)
    d = _api_test(client, srv.url('https'))
    text = d['error']
    assert text.startswith(API_TRUST) and text.endswith(')'), text
    assert re.search(r'\(self[- ]signed certificate\)$', text), text
    _assert_no_wrapper(text)


def test_traefik_api_test_with_a_trusted_certificate_connects(client, server, tmp_path, monkeypatch, api_ssrf):
    path, context = _cert(tmp_path, _ip_sans())
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', path)
    srv = server(_answer_json, context)
    d = _api_test(client, srv.url('https'))
    assert d == {'ok': True, 'version': '3.7.17'}, d


def test_the_ui_shows_the_server_reason_for_a_502():
    src = open(os.path.join(ROOT, 'static', 'js', 'core.js'), encoding='utf-8').read()
    body = src.split('async function _errText', 1)[1].split('\n}', 1)[0]
    branch = body.split('res.status === 502', 1)[1].split('res.status === 401', 1)[0]
    assert 'data.error' in branch, 'a 502 from Traefik Manager carries the reason in its JSON body'
    assert branch.index('data.error') < branch.index('Cannot reach the agent'), branch
