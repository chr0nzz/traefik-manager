import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import core.settings as settings_mod
from core import oidc_tokens

ISSUER = 'https://idp.example.com'
CLIENT_ID = 'tm-client'
CLIENT_SECRET = 'tm-secret'
JWKS_URI = f'{ISSUER}/jwks'

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(key=_KEY, kid='k1'):
    pub = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    pub.update({'kid': kid, 'use': 'sig', 'alg': 'RS256'})
    return {'keys': [pub]}


def _cfg(**over):
    cfg = {'issuer': ISSUER, 'jwks_uri': JWKS_URI,
           'id_token_signing_alg_values_supported': ['RS256', 'HS256']}
    cfg.update(over)
    return cfg


def _token(key=_KEY, alg='RS256', kid='k1', **over):
    now = int(time.time())
    claims = {'iss': ISSUER, 'aud': CLIENT_ID, 'exp': now + 300, 'iat': now,
              'email': 'admin@example.com', 'email_verified': True, 'nonce': 'n-1'}
    claims.update(over)
    headers = {'kid': kid} if alg.startswith(('RS', 'ES', 'PS')) else None
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


@pytest.fixture(autouse=True)
def _serve_jwks(monkeypatch):
    oidc_tokens.reset_cache()

    class _JwksResp:
        status_code = 200

        def json(self):
            return _jwks()

        def raise_for_status(self):
            return None

    monkeypatch.setattr('core.oidc_tokens.requests.get', lambda *a, **k: _JwksResp())
    yield
    oidc_tokens.reset_cache()


def test_a_token_signed_by_the_provider_is_accepted():
    claims = oidc_tokens.verify(_token(), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert claims['email'] == 'admin@example.com' and claims['nonce'] == 'n-1'


def test_a_token_signed_by_another_key_is_refused():
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(key=_OTHER_KEY), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert 'signature' in str(err.value).lower(), \
        'a forged id_token is the whole point of verifying it: %s' % err.value


def test_an_unsigned_token_is_refused():
    now = int(time.time())
    none_token = jwt.encode({'iss': ISSUER, 'aud': CLIENT_ID, 'exp': now + 300, 'iat': now},
                            key=None, algorithm=None)
    with pytest.raises(oidc_tokens.IdTokenError):
        oidc_tokens.verify(none_token, _cfg(), CLIENT_ID, CLIENT_SECRET)


def test_a_token_for_another_client_is_refused():
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(aud='someone-else'), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert 'another client' in str(err.value)


def test_a_token_from_another_issuer_is_refused():
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(iss='https://evil.example.com'), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert 'another provider' in str(err.value)


def test_an_expired_token_is_refused():
    now = int(time.time())
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(exp=now - 3600, iat=now - 7200), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert 'expired' in str(err.value)


def test_a_token_without_an_expiry_is_refused():
    now = int(time.time())
    token = jwt.encode({'iss': ISSUER, 'aud': CLIENT_ID, 'iat': now}, _KEY,
                       algorithm='RS256', headers={'kid': 'k1'})
    with pytest.raises(oidc_tokens.IdTokenError):
        oidc_tokens.verify(token, _cfg(), CLIENT_ID, CLIENT_SECRET)


def test_a_shared_secret_token_is_verified_against_the_client_secret():
    claims = oidc_tokens.verify(_token(key=CLIENT_SECRET, alg='HS256'), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert claims['email'] == 'admin@example.com'
    with pytest.raises(oidc_tokens.IdTokenError):
        oidc_tokens.verify(_token(key='not-the-secret', alg='HS256'), _cfg(), CLIENT_ID, CLIENT_SECRET)


def test_an_algorithm_the_provider_does_not_advertise_is_refused():
    cfg = _cfg(id_token_signing_alg_values_supported=['RS256'])
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(key=CLIENT_SECRET, alg='HS256'), cfg, CLIENT_ID, CLIENT_SECRET)
    assert 'does not advertise' in str(err.value)


def test_a_provider_without_a_jwks_uri_cannot_be_trusted():
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(_token(), _cfg(jwks_uri=''), CLIENT_ID, CLIENT_SECRET)
    assert 'jwks_uri' in str(err.value)


def test_a_token_naming_another_authorized_party_is_refused():
    token = _token(aud=[CLIENT_ID, 'other-client'], azp='other-client')
    with pytest.raises(oidc_tokens.IdTokenError) as err:
        oidc_tokens.verify(token, _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert 'authorized party' in str(err.value)


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code, self.text = payload, status, str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError('unexpected 4xx')


def _enable_oidc():
    s = settings_mod.load_settings()
    settings_mod.save_settings(
        domains=s['domains'], cert_resolver=s['cert_resolver'],
        traefik_api_url=s['traefik_api_url'], auth_enabled=True,
        password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
        setup_complete=True, oidc_enabled=True,
        oidc_provider_url=ISSUER, oidc_client_id=CLIENT_ID, oidc_client_secret=CLIENT_SECRET,
        oidc_allowed_emails='admin@example.com',
    )


def _start(client, monkeypatch):
    _enable_oidc()
    discovery = {
        'issuer': ISSUER,
        'authorization_endpoint': f'{ISSUER}/authorize',
        'token_endpoint': f'{ISSUER}/token',
        'jwks_uri': JWKS_URI,
        'id_token_signing_alg_values_supported': ['RS256'],
    }

    def _get(url, *a, **k):
        return _Resp(_jwks() if url == JWKS_URI else discovery)

    monkeypatch.setattr('app.requests.get', _get)
    r = client.get('/auth/oidc/login')
    q = parse_qs(urlparse(r.headers['Location']).query)
    return q['state'][0], q['nonce'][0]


def test_the_callback_refuses_a_forged_id_token(anon_client, monkeypatch):
    client = anon_client
    state, nonce = _start(client, monkeypatch)
    forged = _token(key=_OTHER_KEY, nonce=nonce)
    monkeypatch.setattr('app.requests.post', lambda *a, **k: _Resp({'id_token': forged, 'access_token': 'x'}))
    r = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    home = client.get('/')
    assert home.status_code == 302 and '/login' in home.headers['Location'], \
        'a forged id_token must not open a session'


def test_the_callback_accepts_a_real_id_token(anon_client, monkeypatch):
    client = anon_client
    state, nonce = _start(client, monkeypatch)
    good = _token(nonce=nonce)
    monkeypatch.setattr('app.requests.post', lambda *a, **k: _Resp({'id_token': good, 'access_token': 'x'}))
    r = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert r.status_code == 302, r.data[:200]
    assert '/login' not in r.headers['Location'], 'a valid token should land in the app, not back at the login page'
    assert client.get('/').status_code == 200, 'a verified id_token opens a session'


def test_the_key_fetch_looks_like_traefik_manager_not_a_bot(monkeypatch):
    seen = {}

    class _Resp:
        status_code = 200

        def json(self):
            return _jwks()

        def raise_for_status(self):
            return None

    def _get(url, timeout=None, headers=None, **k):
        seen.update({'url': url, 'headers': headers or {}, 'timeout': timeout})
        return _Resp()

    monkeypatch.setattr('core.oidc_tokens.requests.get', _get)
    oidc_tokens.reset_cache()
    oidc_tokens.verify(_token(), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert seen['url'] == JWKS_URI and seen['timeout'], 'the key fetch needs a timeout'
    assert 'traefik-manager' in seen['headers'].get('User-Agent', ''), \
        'urllib default agents are blocked by WAFs in front of some providers'


def test_the_keys_are_cached_and_refetched_when_the_key_id_is_new(monkeypatch):
    calls = []

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    def _get(url, **k):
        calls.append(url)
        return _Resp(_jwks(kid='rotated') if len(calls) > 1 else _jwks(kid='old'))

    monkeypatch.setattr('core.oidc_tokens.requests.get', _get)
    oidc_tokens.reset_cache()
    with pytest.raises(oidc_tokens.IdTokenError):
        oidc_tokens.verify(_token(kid='missing'), _cfg(), CLIENT_ID, CLIENT_SECRET)
    assert len(calls) == 2, 'a key id the cache does not know must trigger one refetch, for key rotation'


def test_a_provider_that_sends_no_id_token_is_refused(anon_client, monkeypatch):
    client = anon_client
    state, _nonce = _start(client, monkeypatch)
    monkeypatch.setattr('app.requests.post', lambda *a, **k: _Resp({'access_token': 'x'}))
    monkeypatch.setattr('app.requests.get',
                        lambda *a, **k: _Resp({'sub': 'u1', 'email': 'admin@example.com',
                                               'email_verified': True}))
    r = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert r.status_code == 302
    assert '/login' in r.headers['Location'], 'no id_token means nothing was verified'
    assert client.get('/').status_code != 200, 'an unsigned userinfo response must not open a session'


def test_a_replayed_callback_is_refused(anon_client, monkeypatch):
    client = anon_client
    state, nonce = _start(client, monkeypatch)
    good = _token(nonce=nonce)
    monkeypatch.setattr('app.requests.post', lambda *a, **k: _Resp({'id_token': good, 'access_token': 'x'}))
    first = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert '/login' not in first.headers['Location'], 'the first callback should succeed'
    replay = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert '/login' in replay.headers['Location'], 'state is single-use, so a replay must be refused'


def test_userinfo_for_another_subject_cannot_override_the_id_token(anon_client, monkeypatch):
    client = anon_client
    state, nonce = _start(client, monkeypatch)
    good = _token(nonce=nonce, sub='u1', email=None)
    monkeypatch.setattr('app.requests.post', lambda *a, **k: _Resp({'id_token': good, 'access_token': 'x'}))

    def _get(url, *a, **k):
        if url.endswith('/userinfo'):
            return _Resp({'sub': 'someone-else', 'email': 'admin@example.com',
                          'email_verified': True})
        return _Resp(_jwks())

    monkeypatch.setattr('app.requests.get', _get)
    r = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert '/login' in r.headers['Location'], 'userinfo for a different sub must not grant access'


def test_an_absent_email_verified_claim_is_not_treated_as_verified(anon_client, monkeypatch):
    client = anon_client
    state, nonce = _start(client, monkeypatch)
    unasserted = _token(nonce=nonce, email_verified=None)
    monkeypatch.setattr('app.requests.post',
                        lambda *a, **k: _Resp({'id_token': unasserted, 'access_token': 'x'}))
    r = client.get(f'/auth/oidc/callback?code=abc&state={state}')
    assert '/login' in r.headers['Location'], \
        'an allowlisted email needs the provider to assert it verified the address'
