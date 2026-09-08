import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core import reachability

HDR = {'X-Requested-With': 'fetch'}


class _Server:
    def __init__(self, code, location=None):
        outer = self
        self.hits = 0

        class H(BaseHTTPRequestHandler):
            def do_HEAD(self):
                outer.hits += 1
                self.send_response(code)
                if location:
                    self.send_header('Location', location)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(('127.0.0.1', 0), H)
        self.url = 'http://127.0.0.1:%d' % self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


def _closed_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return 'http://127.0.0.1:%d' % port


@pytest.fixture
def probe():
    return lambda url, fb='': reachability.probe(url, fb, ssrf=lambda u: True)


def test_a_redirect_to_the_same_host_is_still_up(probe):
    s = _Server(302, '/login')
    try:
        r = probe(s.url)
        assert r['ok'] is True and 'unverified' not in r
    finally:
        s.close()


def test_a_redirect_to_another_host_sends_the_check_to_the_backend(probe):
    front, back = _Server(302, 'https://auth.example.com/outpost'), _Server(200)
    try:
        r = probe(front.url, back.url)
        assert r['ok'] is True and r['via_target'] is True, r
        assert back.hits == 1, 'the backend must be asked, the proxy only proved the auth layer answers'
    finally:
        front.close(); back.close()


def test_a_dead_backend_behind_forward_auth_is_down(probe):
    front = _Server(302, 'https://auth.example.com/outpost')
    try:
        r = probe(front.url, _closed_port())
        assert r['ok'] is False, 'a 302 from the auth layer hid an app that refuses connections: %r' % r
        assert 'auth.example.com' in r['error'] and 'refused' in r['error'], r['error']
    finally:
        front.close()


def test_a_backend_that_cannot_be_reached_is_reported_unverified_not_down(probe):
    front = _Server(302, 'https://auth.example.com/outpost')
    try:
        r = probe(front.url, 'http://no-such-host.invalid:8080')
        assert r['ok'] is True and r['unverified'] is True, r
        assert 'auth.example.com' in r['note'] and 'no-such-host' in r['note'], r['note']
        r2 = probe(front.url)
        assert r2['ok'] is True and r2['unverified'] is True and 'no address to check' in r2['note'], r2
    finally:
        front.close()


def test_the_ping_endpoint_carries_the_verdict(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm, '_ssrf_ok', lambda u: True)
    front = _Server(302, 'https://auth.example.com/')
    try:
        r = client.get('/api/ping?url=%s&fallback=%s' % (front.url, _closed_port()), headers=HDR).get_json()
        assert r['ok'] is False and 'auth.example.com' in r['error']
    finally:
        front.close()


def test_the_monitor_keeps_the_note_for_the_tooltip(monkeypatch, tmp_path):
    from core import monitor, route_health as rh
    monkeypatch.setattr(monitor, '_state_path', lambda: str(tmp_path / 'monitor.json'))
    monkeypatch.setattr(monitor, '_agent_servers', lambda: [])
    monkeypatch.setattr(rh.reachability, 'ssrf_ok', lambda u: True)
    monitor._state.clear()
    app = {'id': 'x', 'name': 'x', 'rule': 'Host(`x.example.com`)', 'tls': True, 'target': 'N/A',
           'service_name': 's', 'enabled': True, 'protocol': 'http'}
    fake = lambda url, fb='': {'ok': True, 'latency_ms': 3, 'status_code': 302, 'unverified': True, 'note': 'redirected to auth'}
    rh.check(lambda: [('host', '', [app], {'http': []})], now=0, probe=fake,
             settings={'route_check_enabled': True, 'route_check_interval': 300})
    monitor._write_state()
    entry = rh.snapshot('host', settings={'route_check_enabled': True})['routes']['x']
    assert entry['state'] == 'up' and entry['unverified'] is True and entry['note'] == 'redirected to auth'
    monitor._state.clear()
