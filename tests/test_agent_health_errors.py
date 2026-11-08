import datetime
import errno
import re
import socket
import ssl
import struct
import threading
import time

import pytest
import requests
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.support import Translations
from urllib3.util import connection as u3conn

import core.agents_store as store
from core import i18n as _i18n

TRUST = 'TLS verification failed - the agent certificate is not trusted by Traefik Manager ('
HEALTH_BODY = b'{"status": "ok", "version": "1.15.0"}'


def _seed(url):
    store.save_agents_file([{'id': 'a1', 'name': 'alpha', 'url': url, 'api_key': 'k1'}])


def _health(client):
    return client.get('/api/agents/a1/health').get_json()


def _assert_no_wrapper(text):
    assert 'ConnectionPool' not in text and 'Max retries' not in text, text


def _closed_port_url(scheme='https'):
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return '%s://127.0.0.1:%d' % (scheme, port)


class _Server:
    def __init__(self, handler, context=None):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.handler = handler
        self.context = context
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            if self.context is not None:
                conn = self.context.wrap_socket(conn, server_side=True)
            self.handler(conn)
        except OSError:
            pass
        finally:
            conn.close()

    def url(self, scheme='http'):
        return '%s://127.0.0.1:%d' % (scheme, self.port)

    def close(self):
        self.sock.close()


@pytest.fixture
def server():
    started = []

    def start(handler, context=None):
        srv = _Server(handler, context)
        started.append(srv)
        return srv
    yield start
    for srv in started:
        srv.close()


def _answer_health(conn):
    conn.recv(4096)
    conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n'
                 b'Content-Length: %d\r\n\r\n%s' % (len(HEALTH_BODY), HEALTH_BODY))


def _reset_after_request(conn):
    conn.recv(4096)
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))


def _never_answer(conn):
    time.sleep(2)


def _plain_http(conn):
    conn.recv(4096)
    conn.sendall(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n')


def _cert(tmp_path, sans):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'agent.example.test')])
    now = datetime.datetime.now(datetime.timezone.utc)
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(ski, critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski), critical=False)
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path = tmp_path / 'agent.crt'
    key_path = tmp_path / 'agent.key'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    return str(cert_path), context


def _ip_sans():
    import ipaddress
    from cryptography import x509
    return [x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]


def _dns_sans(name):
    from cryptography import x509
    return [x509.DNSName(name)]


@pytest.fixture
def connect_fails(monkeypatch):
    def arm(err):
        def raiser(*a, **kw):
            raise err
        monkeypatch.setattr(u3conn, 'create_connection', raiser)
    return arm


def test_a_refused_agent_says_connection_refused_without_the_retry_wrapper(client):
    _seed(_closed_port_url())
    d = _health(client)
    assert d['ok'] is False and d['latency_ms'] == -1, d
    assert d['error'] == 'connection refused', d


def test_an_agent_name_that_does_not_resolve_names_the_host(client, connect_fails):
    connect_fails(socket.gaierror(socket.EAI_NONAME, 'Name or service not known'))
    _seed('https://agent.example.test')
    d = _health(client)
    assert d['error'] == 'DNS name agent.example.test does not resolve', d


def test_an_agent_connect_timeout_is_not_called_refused(client, connect_fails):
    connect_fails(socket.timeout('timed out'))
    _seed('https://agent.example.test')
    assert _health(client)['error'] == 'connection timed out'


def test_no_route_to_the_agent(client, connect_fails):
    connect_fails(OSError(errno.EHOSTUNREACH, 'No route to host'))
    _seed('https://agent.example.test')
    assert _health(client)['error'] == 'no route to host'


def test_an_unmapped_connect_error_keeps_the_innermost_reason(client, connect_fails):
    connect_fails(OSError(errno.EADDRNOTAVAIL, 'Cannot assign requested address'))
    _seed('https://agent.example.test')
    text = _health(client)['error']
    assert text == 'Cannot assign requested address', text
    _assert_no_wrapper(text)


def test_an_agent_that_resets_the_connection(client, server):
    srv = server(_reset_after_request)
    _seed(srv.url())
    assert _health(client)['error'] == 'connection reset'


def test_an_agent_that_never_answers_timed_out_waiting(client, server, monkeypatch):
    srv = server(_never_answer)
    _seed(srv.url())
    real_get = requests.get
    monkeypatch.setattr(requests, 'get', lambda url, **kw: real_get(url, **{**kw, 'timeout': 0.3}))
    d = _health(client)
    assert d['ok'] is False and d['error'] == 'timed out waiting for a response', d


def test_an_https_url_on_a_plain_http_agent_is_a_handshake_failure_not_a_trust_problem(client, server):
    srv = server(_plain_http)
    _seed(srv.url('https'))
    text = _health(client)['error']
    assert text.startswith('TLS handshake failed (') and text.endswith(')'), text
    assert '_ssl.c' not in text and '[SSL' not in text, text
    assert 'not trusted' not in text
    _assert_no_wrapper(text)


def test_a_self_signed_agent_certificate_names_the_verify_reason(client, server, tmp_path):
    _path, context = _cert(tmp_path, _ip_sans())
    srv = server(_answer_health, context)
    _seed(srv.url('https'))
    d = _health(client)
    assert d['ok'] is False, d
    text = d['error']
    assert text.startswith(TRUST) and text.endswith(')'), text
    assert re.search(r'self[- ]signed certificate', text[len(TRUST):]), text
    _assert_no_wrapper(text)
    assert 'CERTIFICATE_VERIFY_FAILED' not in text and '_ssl.c' not in text, text


def test_a_trusted_certificate_for_another_name_names_the_mismatch(client, server, tmp_path, monkeypatch):
    path, context = _cert(tmp_path, _dns_sans('other.example.test'))
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', path)
    srv = server(_answer_health, context)
    _seed(srv.url('https'))
    text = _health(client)['error']
    assert text.startswith(TRUST), text
    assert 'mismatch' in text.lower() and '127.0.0.1' in text, text
    _assert_no_wrapper(text)


def test_a_trusted_agent_certificate_is_healthy(client, server, tmp_path, monkeypatch):
    path, context = _cert(tmp_path, _ip_sans())
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', path)
    srv = server(_answer_health, context)
    _seed(srv.url('https'))
    d = _health(client)
    assert d['ok'] is True and d['status'] == 200 and d['version'] == '1.15.0', d


def test_a_hand_edited_url_without_a_scheme_keeps_the_whole_requests_message(client):
    _seed('agent.example.test')
    text = _health(client)['error']
    assert 'No scheme supplied' in text and text.endswith('https://agent.example.test/health?'), text


def test_the_reason_is_shown_in_the_requester_language(client, monkeypatch, tmp_path):
    catalog = Catalog(locale='de')
    catalog.add('connection refused', 'Verbindung abgelehnt', context='check failure')
    target = tmp_path / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)
    german = Translations.load(str(tmp_path), ['de'], 'messages')
    monkeypatch.setattr(_i18n, '_request_translations', lambda: german)
    _seed(_closed_port_url())
    assert _health(client)['error'] == 'Verbindung abgelehnt'
