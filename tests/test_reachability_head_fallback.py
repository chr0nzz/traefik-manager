import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from core import reachability


class _Server:
    def __init__(self, head=None, get=200):
        outer = self
        self.methods = []

        class H(BaseHTTPRequestHandler):
            def do_HEAD(self):
                outer.methods.append('HEAD')
                if head is None:
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                self.send_response(head)
                self.end_headers()

            def do_GET(self):
                outer.methods.append('GET')
                self.send_response(get)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(('127.0.0.1', 0), H)
        self.url = 'http://127.0.0.1:%d/' % self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def _closed_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return 'http://127.0.0.1:%d/' % port


def _probe(url, fallback=''):
    return reachability.probe(url, fallback, ssrf=lambda u: True)


def test_a_backend_that_drops_head_is_checked_with_get():
    s = _Server(head=None, get=401)
    try:
        r = _probe(s.url)
        assert r['ok'] is True and r['status_code'] == 401, r
        assert s.methods == ['HEAD', 'GET'], s.methods
    finally:
        s.close()


def test_a_proxy_502_on_head_is_rechecked_with_get():
    s = _Server(head=502, get=200)
    try:
        r = _probe(s.url)
        assert r['ok'] is True and r['status_code'] == 200, r
    finally:
        s.close()


def test_a_proxy_502_on_head_falls_back_to_a_backend_that_drops_head():
    front, back = _Server(head=502, get=502), _Server(head=None, get=401)
    try:
        r = _probe(front.url, back.url)
        assert r['ok'] is True and r.get('via_target') is True and r['status_code'] == 401, r
    finally:
        front.close()
        back.close()


def test_head_not_allowed_is_rechecked_with_get():
    for code in reachability.NO_HEAD:
        s = _Server(head=code, get=200)
        try:
            r = _probe(s.url)
            assert r['ok'] is True and r['status_code'] == 200, (code, r)
        finally:
            s.close()


def test_a_502_on_both_methods_is_still_down():
    s = _Server(head=502, get=502)
    try:
        r = _probe(s.url)
        assert r['ok'] is False and r['status_code'] == 502, r
    finally:
        s.close()


def test_a_working_head_does_not_send_a_get():
    s = _Server(head=200, get=200)
    try:
        assert _probe(s.url)['ok'] is True
        assert s.methods == ['HEAD'], s.methods
    finally:
        s.close()


def test_a_refused_connection_is_not_retried():
    calls = []

    def get(*a, **kw):
        calls.append(a)
        raise AssertionError('a refused port must not be retried with GET')

    r = reachability.probe(_closed_port(), '', ssrf=lambda u: True, head=None, get=get)
    assert r['ok'] is False and r['error'] == 'connection refused', r
    assert not calls


def test_the_get_body_is_not_downloaded():
    seen = {}

    class _Resp:
        status_code = 200
        headers = {}

        def close(self):
            seen['closed'] = True

    def head(*a, **kw):
        raise ConnectionResetError('connection reset')

    def get(url, **kw):
        seen.update(kw)
        return _Resp()

    r = reachability.probe('http://app.example.test/', '', ssrf=lambda u: True, head=head, get=get)
    assert r['ok'] is True, r
    assert seen.get('stream') is True and seen.get('closed') is True, seen
    assert seen.get('allow_redirects') is False and seen.get('verify') is False, seen


def test_an_injected_head_without_get_never_falls_back():
    def head(*a, **kw):
        raise ConnectionResetError('connection reset')

    r = reachability.probe('http://app.example.test/', '', ssrf=lambda u: True, head=head)
    assert r['ok'] is False and r['error'] == 'connection reset', r


def test_backend_state_uses_get_when_head_is_dropped():
    s = _Server(head=None, get=401)
    try:
        assert reachability.backend_state(s.url, ssrf=lambda u: True) == 'up'
    finally:
        s.close()
