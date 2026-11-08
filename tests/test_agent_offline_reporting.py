import errno
import os
import re
import ssl

import requests

import core.agents_store as store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _seed():
    store.save_agents_file([{'id': 'a1', 'name': 'alpha',
                             'url': 'https://a1.example.com', 'api_key': 'k1'}])


def test_ssl_error_subclasses_connection_error():
    assert issubclass(requests.exceptions.SSLError, requests.exceptions.ConnectionError), \
        'this is why a TLS failure used to be reported as a refused connection'


def _verify_error(reason):
    err = ssl.SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
                                          '%s (_ssl.c:1032)' % reason)
    err.reason = 'CERTIFICATE_VERIFY_FAILED'
    err.verify_code = 19
    err.verify_message = reason
    return err


def test_health_reports_a_tls_failure_as_a_trust_problem(client, monkeypatch):
    _seed()
    import app as tm
    monkeypatch.setattr(tm.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(
        requests.exceptions.SSLError(_verify_error('self-signed certificate in certificate chain'))))
    d = client.get('/api/agents/a1/health').get_json()
    assert d['ok'] is False
    assert d['error'] == ('TLS verification failed - the agent certificate is not trusted by Traefik Manager '
                          '(self-signed certificate in certificate chain)'), d


def test_health_still_reports_a_refused_connection_plainly(client, monkeypatch):
    _seed()
    import app as tm
    monkeypatch.setattr(tm.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(
        requests.exceptions.ConnectionError(ConnectionRefusedError(errno.ECONNREFUSED, 'Connection refused'))))
    d = client.get('/api/agents/a1/health').get_json()
    assert d['error'] == 'connection refused'


def test_the_tls_branch_is_ordered_before_the_connection_branch():
    src = open(os.path.join(ROOT, 'app.py'), encoding='utf-8').read()
    for block in re.findall(r'except requests\.exceptions\.SSLError.*?except requests\.exceptions\.ConnectionError',
                            src, re.S):
        assert 'SSLError' in block
    for m in re.finditer(r'except requests\.exceptions\.ConnectionError', src):
        before = src[:m.start()]
        assert 'SSLError' in before[-600:], \
            'a ConnectionError handler with no SSLError handler above it will swallow TLS failures'


def test_switching_to_an_offline_agent_explains_why():
    src = open(os.path.join(ROOT, 'templates', 'index.html'), encoding='utf-8').read()
    assert '_warnIfAgentUnreachable' in src
    body = src.split('function _warnIfAgentUnreachable', 1)[1].split('\n}', 1)[0]
    assert 'd.error' in body, 'the toast should name the reason the health check reported'
    assert 'd.status === 401' not in body, (
        'the agent health endpoint is registered outside authMiddleware, so it never '
        'returns 401 and that branch can never run')
    assert 'showToast' in body
    call = src.split('function switchServer', 1)[1].split('\n}', 1)[0]
    assert '_warnIfAgentUnreachable' in call, 'switchServer must actually call it'
