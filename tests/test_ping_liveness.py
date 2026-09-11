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


def _dead_url():
    import socket
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return 'http://127.0.0.1:%d' % port


def _ping_pool(client, url, servers):
    q = '/api/ping?url=' + url + ''.join('&servers=' + s for s in servers)
    return client.get(q, headers=HDR).get_json()


def test_a_dead_member_of_a_pool_reads_as_degraded(client):
    up, front = _Server(200), _Server(200)
    dead = _dead_url()
    try:
        r = _ping_pool(client, front.url, [up.url, dead])
        assert r['state'] == 'degraded', 'the proxy answers, so only checking it hides the dead server: %r' % r
        assert r['ok'] is True and r['source'] == 'servers'
        assert r['servers'] == {'up': 1, 'total': 2}
        assert r['down_servers'] == [dead]
    finally:
        up.close(); front.close()


def test_a_pool_with_every_member_dead_is_down(client):
    front = _Server(200)
    try:
        r = _ping_pool(client, front.url, [_dead_url(), _dead_url()])
        assert r['state'] == 'down' and r['ok'] is False, r
        assert r['servers']['up'] == 0
    finally:
        front.close()


def test_a_healthy_pool_is_up(client):
    a, b, front = _Server(200), _Server(204), _Server(200)
    try:
        r = _ping_pool(client, front.url, [a.url, b.url])
        assert r['state'] == 'up' and r['ok'] is True and 'down_servers' not in r, r
        assert a.hits == 1 and b.hits == 1, 'every server must be asked, not just the first'
    finally:
        a.close(); b.close(); front.close()


def test_a_single_server_falls_back_to_checking_the_route(client):
    only, front = _Server(200), _Server(200)
    try:
        r = _ping_pool(client, front.url, [only.url])
        assert r.get('source') != 'servers', 'one server is not a pool: %r' % r
        assert r['ok'] is True and only.hits == 0
    finally:
        only.close(); front.close()


def test_a_pool_member_the_guard_refuses_is_never_requested(client, monkeypatch):
    import app as tm
    reached = []
    real = tm.requests.head

    def watched(target, **kw):
        reached.append(target)
        return real(target, **kw)

    monkeypatch.setattr(tm.requests, 'head', watched)
    monkeypatch.setattr(tm, '_ssrf_ok', lambda u: 'blocked' not in u)
    good, front = _Server(200), _Server(200)
    try:
        r = _ping_pool(client, front.url, [good.url, 'http://blocked.example'])
        assert not any('blocked' in t for t in reached), 'a pool member reached a refused address'
        assert r.get('source') != 'servers', 'an unreachable verdict must not be counted as down: %r' % r
    finally:
        good.close(); front.close()
