import core.crowdsec as crowd


class _Resp:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._payload = payload if payload is not None else {}
        self.content = b'{}'

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f'HTTP {self.status_code}')


def _machine(monkeypatch, tokens):
    monkeypatch.setattr(crowd, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(crowd, '_cs_machine_id', lambda: 'm')
    monkeypatch.setattr(crowd, '_cs_machine_password', lambda: 'p')
    monkeypatch.setattr(crowd, '_cs_has_cert', lambda: False)
    monkeypatch.setattr(crowd, '_cs_tls_kwargs', lambda: {})
    monkeypatch.setattr(crowd, 'cs_timeout', lambda: 3)
    logins = []

    def fake_post(url, **kw):
        logins.append(url)
        return _Resp(200, {'token': tokens[min(len(logins) - 1, len(tokens) - 1)],
                           'expire': '2099-01-01T00:00:00Z'})

    monkeypatch.setattr(crowd.requests, 'post', fake_post)
    crowd.cs_jwt_reset()
    return logins


def test_a_refused_token_triggers_one_relogin(monkeypatch):
    logins = _machine(monkeypatch, ['stale-token', 'fresh-token'])
    sent = []

    def fake_request(method, url, **kw):
        sent.append(kw['headers']['Authorization'])
        return _Resp(401) if len(sent) == 1 else _Resp(200, {'ok': True})

    monkeypatch.setattr(crowd.requests, 'request', fake_request)
    out = crowd._cs_machine_request('GET', '/v1/alerts')
    assert out == {'ok': True}, 'the retry must return the real answer'
    assert sent == ['Bearer stale-token', 'Bearer fresh-token'], \
        'a signing key change leaves a cached token invalid until we log in again'
    assert len(logins) == 2


def test_a_working_token_is_not_thrown_away(monkeypatch):
    logins = _machine(monkeypatch, ['good-token'])
    monkeypatch.setattr(crowd.requests, 'request',
                        lambda method, url, **kw: _Resp(200, {'ok': True}))
    crowd._cs_machine_request('GET', '/v1/alerts')
    crowd._cs_machine_request('GET', '/v1/alerts')
    assert len(logins) == 1, 'the token cache must still work'


def test_a_second_refusal_is_not_retried_forever(monkeypatch):
    _machine(monkeypatch, ['a', 'b'])
    calls = []

    def always_401(method, url, **kw):
        calls.append(url)
        return _Resp(401)

    monkeypatch.setattr(crowd.requests, 'request', always_401)
    assert crowd._cs_machine_request('GET', '/v1/alerts') is None
    assert len(calls) == 2, 'exactly one retry, never a loop'


def test_reset_clears_the_cache(monkeypatch):
    _machine(monkeypatch, ['t1'])
    monkeypatch.setattr(crowd.requests, 'request',
                        lambda method, url, **kw: _Resp(200, {'ok': True}))
    crowd._cs_machine_request('GET', '/v1/alerts')
    assert crowd._cs_jwt_cache['token']
    crowd.cs_jwt_reset()
    assert not crowd._cs_jwt_cache['token'] and crowd._cs_jwt_cache['expiry'] is None


def test_the_alerts_endpoint_retries_too():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'app.py'), encoding='utf-8') as fh:
        src = fh.read()
    with open(os.path.join(root, 'core', 'crowdsec.py'), encoding='utf-8') as fh:
        core_src = fh.read()
    start = src.index('def api_cs_alerts(')
    body = src[start:src.index('\n@app.route', start)]
    assert '_crowd.cs_alerts(' in body, 'the alerts endpoint reads the shared alert cache'
    fetch = core_src[core_src.index('def _cs_alert_fetch('):core_src.index('\ndef ', core_src.index('def _cs_alert_fetch(') + 10)]
    assert 'cs_jwt_reset()' in fetch, \
        'the alert fetch builds its own header, so it needs the retry of its own'
    assert 'resp.status_code == 401' in fetch
