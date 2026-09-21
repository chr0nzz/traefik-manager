
import pytest
import requests

import app as tm
import core.reachability as reach


class _Resp:
    def __init__(self, status=200, location='', payload=None):
        self.status_code = status
        self.headers = {'Location': location} if location else {}
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code}')


METADATA = 'http://169.254.169.254/latest/meta-data/'


def _guard(url):
    return '169.254.' not in url and 'blocked' not in url


def test_a_redirect_cannot_reach_an_address_the_guard_refuses():
    hops = []

    def _get(url, **kwargs):
        hops.append(url)
        assert kwargs.get('allow_redirects') is False, \
            'safe_get must do its own redirect handling, or the hop check is pointless'
        if 'start' in url:
            return _Resp(302, METADATA)
        return _Resp(200, payload={'secret': 'leaked'})

    with pytest.raises(reach.BlockedTarget):
        reach.safe_get('http://start.example.com/', ssrf=_guard, getter=_get)
    assert hops == ['http://start.example.com/'], \
        f'the blocked address must never be requested, but hops were {hops}'


def test_an_ordinary_redirect_is_still_followed():
    def _get(url, **kwargs):
        if 'start' in url:
            return _Resp(302, 'https://idp.example.com/real')
        return _Resp(200, payload={'issuer': 'https://idp.example.com'})

    resp = reach.safe_get('https://start.example.com/', ssrf=_guard, getter=_get)
    assert resp.status_code == 200 and resp.json()['issuer'] == 'https://idp.example.com'


def test_a_private_address_is_still_allowed():
    for addr in ('http://10.0.0.5:8080', 'http://192.168.1.10:8080', 'http://127.0.0.1:8080',
                 'http://172.16.4.2:8080'):
        assert reach.ssrf_ok(addr), f'{addr} must stay reachable'


def test_the_addresses_the_guard_exists_for_are_still_refused():
    assert not reach.ssrf_ok('http://169.254.169.254/'), 'cloud metadata must stay blocked'
    assert not reach.ssrf_ok('http://224.0.0.1/'), 'multicast must stay blocked'
    assert not reach.ssrf_ok('http://0.0.0.0/'), 'the unspecified address must stay blocked'


def test_a_redirect_loop_stops():
    def _get(url, **kwargs):
        return _Resp(302, 'https://a.example.com/next')

    with pytest.raises(reach.BlockedTarget):
        reach.safe_get('https://a.example.com/', ssrf=_guard, getter=_get)


def test_a_redirect_to_a_non_http_scheme_is_refused():
    def _get(url, **kwargs):
        return _Resp(302, 'file:///etc/passwd')

    with pytest.raises(reach.BlockedTarget):
        reach.safe_get('https://start.example.com/', ssrf=_guard, getter=_get)


def _probe(client, monkeypatch, endpoint, payload):
    seen = {}

    def _get(url, **kwargs):
        seen['allow_redirects'] = kwargs.get('allow_redirects')
        return _Resp(200, payload={'Version': '3.0'})

    monkeypatch.setattr(tm.requests, 'get', _get)
    monkeypatch.setattr(tm, '_ssrf_ok', lambda u: True)
    r = client.post(endpoint, json=payload,
                    headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
    assert r.status_code == 200, f'{endpoint} returned {r.status_code}: {r.data[:160]}'
    return seen


def test_the_traefik_api_probe_does_not_follow_a_redirect(client, monkeypatch):
    seen = _probe(client, monkeypatch, '/api/settings/test-connection',
                  {'url': 'http://traefik.example.com:8080', 'user': 'admin',
                   'password': 'hunter2'})
    assert seen.get('allow_redirects') is False, \
        'the Traefik API probe still follows redirects, so the password can reach the target'


def test_the_crowdsec_probe_does_not_follow_a_redirect(client, monkeypatch):
    import core.settings as settings_mod
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=True,
                               password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
                               setup_complete=False)
    try:
        seen = _probe(client, monkeypatch, '/setup/test-crowdsec',
                      {'url': 'http://crowdsec.example.com:8080', 'key': 'lapi-key'})
    finally:
        settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                                   traefik_api_url=s['traefik_api_url'], auth_enabled=True,
                                   password_hash=s['password_hash'],
                                   visible_tabs=s['visible_tabs'], setup_complete=True)
    assert seen.get('allow_redirects') is False, \
        'the CrowdSec probe still follows redirects, so the LAPI key can reach the target'
