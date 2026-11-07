import errno
import socket
import ssl
import struct
import threading
import time

import pytest
import requests
from urllib3 import exceptions as u3exc
from urllib3.util import connection as u3conn

from core import i18n
from core import reachability

pytestmark = pytest.mark.filterwarnings('ignore::urllib3.exceptions.InsecureRequestWarning')


class _Raw:
    def __init__(self, handler):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.handler = handler
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
            self.handler(conn)
        except OSError:
            pass
        finally:
            conn.close()

    def url(self, scheme='http'):
        return '%s://127.0.0.1:%d/' % (scheme, self.port)

    def close(self):
        self.sock.close()


def _close_after_request(conn):
    conn.recv(4096)


def _reset_after_request(conn):
    conn.recv(4096)
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))


def _never_answer(conn):
    time.sleep(2)


def _plain_http(conn):
    conn.recv(4096)
    conn.sendall(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n')


def _closed_port_url(scheme='http'):
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return '%s://127.0.0.1:%d/' % (scheme, port)


def _failure(url, timeout=2):
    try:
        requests.head(url, timeout=timeout, allow_redirects=False, verify=False)
    except requests.exceptions.RequestException as exc:
        return exc
    raise AssertionError('%s answered, the test needs it to fail' % url)


@pytest.fixture
def connect_fails(monkeypatch):
    def arm(err):
        def raiser(*a, **kw):
            raise err
        monkeypatch.setattr(u3conn, 'create_connection', raiser)
    return arm


def _text(exc, url):
    return str(reachability.failure_reason(exc, url))


def _assert_no_wrapper(text):
    assert 'ConnectionPool' not in text and 'Max retries' not in text, text


def test_a_refused_connection_names_the_cause_not_the_retry_wrapper():
    url = _closed_port_url('https')
    exc = _failure(url)
    assert 'Max retries exceeded' in str(exc)[:80], 'the cut used to keep only this wrapper'
    text = _text(exc, url)
    assert text == 'connection refused'
    _assert_no_wrapper(text)


def test_a_name_that_does_not_resolve_says_so_and_names_the_host(connect_fails):
    connect_fails(socket.gaierror(socket.EAI_NONAME, 'Name or service not known'))
    url = 'https://app.example.test/'
    assert _text(_failure(url), url) == 'DNS name app.example.test does not resolve'


def test_a_temporary_dns_failure_on_musl_is_a_dns_failure(connect_fails):
    connect_fails(socket.gaierror(socket.EAI_AGAIN, 'Try again'))
    url = 'https://app.example.test/'
    assert _text(_failure(url), url) == 'DNS name app.example.test does not resolve'


def test_a_dns_failure_without_an_address_still_says_dns(connect_fails):
    connect_fails(socket.gaierror(socket.EAI_NONAME, 'Name or service not known'))
    assert _text(_failure('https://app.example.test/'), '') == 'DNS name does not resolve'


def test_no_route_to_host(connect_fails):
    connect_fails(OSError(errno.EHOSTUNREACH, 'No route to host'))
    url = 'https://app.example.test/'
    assert _text(_failure(url), url) == 'no route to host'


def test_network_unreachable(connect_fails):
    connect_fails(OSError(errno.ENETUNREACH, 'Network is unreachable'))
    url = 'https://app.example.test/'
    assert _text(_failure(url), url) == 'network unreachable'


def test_a_connect_timeout_is_reported_even_past_the_old_cut(connect_fails):
    connect_fails(socket.timeout('timed out'))
    url = 'https://a-rather-long-hostname-for-a-route.example.test/'
    exc = _failure(url)
    assert 'timeout' not in str(exc)[:80].lower(), 'the old check only looked at the first 80 characters'
    assert _text(exc, url) == 'connection timed out'


def test_a_kernel_connect_timeout_is_a_timeout(connect_fails):
    connect_fails(TimeoutError(errno.ETIMEDOUT, 'Connection timed out'))
    url = 'https://app.example.test/'
    assert _text(_failure(url), url) == 'connection timed out'


def test_an_unmapped_connect_error_is_not_mistaken_for_a_timeout(connect_fails):
    connect_fails(OSError(errno.EADDRNOTAVAIL, 'Cannot assign requested address'))
    url = 'https://app.example.test/'
    text = _text(_failure(url), url)
    assert text == 'Cannot assign requested address', 'NewConnectionError subclasses ConnectTimeoutError in urllib3'
    _assert_no_wrapper(text)


def test_a_server_that_never_answers_timed_out_waiting():
    srv = _Raw(_never_answer)
    try:
        url = srv.url()
        assert _text(_failure(url, timeout=0.3), url) == 'timed out waiting for a response'
    finally:
        srv.close()


def test_tls_to_a_plain_http_port_names_the_ssl_reason():
    srv = _Raw(_plain_http)
    try:
        url = srv.url('https')
        text = _text(_failure(url), url)
        assert text.startswith('TLS handshake failed (') and text.endswith(')'), text
        assert '_ssl.c' not in text and '[SSL' not in text, text
        _assert_no_wrapper(text)
    finally:
        srv.close()


def test_a_tls_error_without_an_ssl_reason_keeps_the_detail():
    exc = requests.exceptions.SSLError('certificate rejected')
    assert _text(exc, 'https://a.example.test/') == 'TLS handshake failed (certificate rejected)'


def test_an_ssl_error_python_cannot_name_drops_the_openssl_noise():
    err = ssl.SSLError(1, '[SSL] record layer failure (_ssl.c:1018)')
    pool = u3exc.MaxRetryError(None, '/', reason=u3exc.SSLError(err))
    exc = requests.exceptions.SSLError(pool)
    assert _text(exc, 'https://a.example.test/') == 'TLS handshake failed (record layer failure)'


def _verify_failure(message):
    err = ssl.SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: '
                                          'unable to get local issuer certificate (_ssl.c:1032)')
    err.reason = 'CERTIFICATE_VERIFY_FAILED'
    err.verify_message = message
    inner = u3exc.SSLError(err)
    pool = u3exc.MaxRetryError(None, '/health', reason=inner)
    return requests.exceptions.SSLError(pool)


def test_a_certificate_verification_failure_gives_the_verify_reason():
    exc = _verify_failure('unable to get local issuer certificate')
    assert reachability.cert_verify_reason(exc) == 'unable to get local issuer certificate'


def test_a_verification_failure_without_a_verify_message_falls_back_to_the_ssl_reason():
    assert reachability.cert_verify_reason(_verify_failure(None)) == 'certificate verify failed'


def test_other_failures_have_no_verify_reason():
    assert reachability.cert_verify_reason(requests.exceptions.SSLError('certificate rejected')) == ''
    assert reachability.cert_verify_reason(_failure(_closed_port_url('https'))) == ''
    srv = _Raw(_plain_http)
    try:
        assert reachability.cert_verify_reason(_failure(srv.url('https'))) == ''
    finally:
        srv.close()


def test_a_reset_connection():
    srv = _Raw(_reset_after_request)
    try:
        url = srv.url()
        assert _text(_failure(url), url) == 'connection reset'
    finally:
        srv.close()


def test_a_connection_closed_without_an_answer():
    srv = _Raw(_close_after_request)
    try:
        url = srv.url()
        assert _text(_failure(url), url) == 'connection closed without a response'
    finally:
        srv.close()


def test_an_unknown_error_falls_back_to_the_innermost_cause():
    inner = ValueError('the innermost reason')
    outer = requests.exceptions.ConnectionError(inner)
    assert _text(outer, 'https://a.example.test/') == 'the innermost reason'
    assert _text(Exception('x' * 500), '') == 'x' * reachability.DETAIL_MAX


def test_text_only_errors_still_classify():
    assert _text(OSError('[Errno 111] Connection refused'), '') == 'connection refused'
    assert _text(Exception('Read timed out. (read timeout=5)'), '') == 'timed out waiting for a response'
    assert _text(Exception('something timed out'), '') == 'connection timed out'


def test_reasons_are_translatable_messages():
    url = _closed_port_url()
    msg = reachability.failure_reason(_failure(url), url)
    assert isinstance(msg, i18n.Message) and msg.spec == {'id': 'connection refused', 'ctx': 'check failure'}, msg.spec


def test_the_probe_reports_the_reason_for_an_unreachable_route():
    url = _closed_port_url('https')
    r = reachability.probe(url, '', ssrf=lambda u: True)
    assert r['ok'] is False and r['error'] == 'connection refused', r


def test_verdicts_are_unchanged(connect_fails):
    refused = _failure(_closed_port_url())
    assert reachability._classify_failure(refused) == 'down'
    assert reachability._down_why(refused) == 'refused'
    srv = _Raw(_plain_http)
    try:
        assert reachability._classify_failure(_failure(srv.url('https'))) == 'down'
    finally:
        srv.close()
    srv = _Raw(_never_answer)
    try:
        assert reachability._classify_failure(_failure(srv.url(), timeout=0.3)) == 'unknown'
    finally:
        srv.close()
    connect_fails(socket.timeout('timed out'))
    assert reachability._classify_failure(_failure('https://app.example.test/')) == 'unknown'
    connect_fails(socket.gaierror(socket.EAI_NONAME, 'Name or service not known'))
    assert reachability._classify_failure(_failure('https://app.example.test/')) == 'unknown'
    connect_fails(OSError(errno.EHOSTUNREACH, 'No route to host'))
    assert reachability._down_why(_failure('https://app.example.test/')) == 'no_route'
