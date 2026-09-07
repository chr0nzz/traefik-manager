import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HDR = {'X-Requested-With': 'fetch'}


class _Server:
    def __init__(self, code):
        self.hits = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_HEAD(self):
                outer.hits += 1
                self.send_response(code)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(('127.0.0.1', 0), H)
        self.url = 'http://127.0.0.1:%d' % self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


def _ping(client, url, fallback=''):
    q = '/api/ping?url=' + url
    if fallback:
        q += '&fallback=' + fallback
    return client.get(q, headers=HDR).get_json()


def test_a_gateway_error_from_the_proxy_is_not_up(client):
    s = _Server(502)
    try:
        assert _ping(client, s.url)['ok'] is False, \
            'a 502 means the proxy could not reach the backend, so the route is down'
    finally:
        s.close()


def test_a_redirect_is_still_up(client):
    s = _Server(302)
    try:
        assert _ping(client, s.url)['ok'] is True, 'a redirect means the route answered'
    finally:
        s.close()


def test_an_auth_challenge_is_still_up(client):
    for code in (401, 403):
        s = _Server(code)
        try:
            assert _ping(client, s.url)['ok'] is True, \
                '%d means up but protected, not down' % code
        finally:
            s.close()


def test_an_application_error_is_still_up(client):
    s = _Server(500)
    try:
        assert _ping(client, s.url)['ok'] is True, \
            'a 500 is the app answering badly, not an unreachable route'
    finally:
        s.close()


def test_a_gateway_error_falls_through_to_the_backend(client):
    proxy, backend = _Server(503), _Server(200)
    try:
        res = _ping(client, proxy.url, backend.url)
        assert res['ok'] is True, 'the backend answered, so the route is up: %r' % res
        assert res.get('via_target') is True, 'the result should say it came from the backend'
        assert backend.hits == 1, 'the backend was never tried: %r' % res
    finally:
        proxy.close()
        backend.close()


def test_both_unreachable_reports_down(client):
    proxy, backend = _Server(503), _Server(502)
    try:
        res = _ping(client, proxy.url, backend.url)
        assert res['ok'] is False, 'neither answered, so it is down: %r' % res
    finally:
        proxy.close()
        backend.close()
