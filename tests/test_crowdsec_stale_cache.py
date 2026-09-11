import os
import re
from datetime import datetime, timedelta, timezone

import pytest

import core.crowdsec as crowd
from core.crowdsec import CrowdSecUnavailable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(age_seconds, ready=True):
    return {'fp': 'x', 'items': {'1': {'id': 1, 'origin': 'crowdsec', 'value': '1.2.3.4'}},
            'synced': datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
            'ready': ready, 'owner': -1, 'stamp': None}


def test_a_fresh_cache_after_a_failure_is_not_called_stale():
    mode = crowd._cs_stale_mode(60, CrowdSecUnavailable('HTTP 401'))
    assert mode == 'cache'


def test_an_old_cache_after_a_failure_is_reported_as_stale():
    mode = crowd._cs_stale_mode(crowd.CS_STALE_AFTER_SECONDS + 1, CrowdSecUnavailable('HTTP 401'))
    assert mode.startswith('stale:')
    _, age, why = mode.split(':', 2)
    assert int(age) > crowd.CS_STALE_AFTER_SECONDS
    assert 'HTTP 401' in why, 'the reason must survive so the user knows it is an auth problem'


def test_an_unknown_age_is_not_guessed_as_stale():
    assert crowd._cs_stale_mode(None, CrowdSecUnavailable('boom')) == 'cache'


def test_the_endpoint_flags_a_stale_read(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream',
                        lambda force_full=False: ([{'id': 1, 'origin': 'crowdsec', 'value': '1.2.3.4'}],
                                                  'stale:7200:HTTP 401 from /v1/watchers/login'))
    monkeypatch.setattr(tm, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(tm, '_cs_api_key', lambda: 'k')
    r = client.get('/api/crowdsec/decisions')
    assert r.status_code == 200
    note = r.headers.get('X-CS-Stale')
    assert note, 'a stale read must be announced, not passed off as current'
    assert '2 hours' in note
    assert 'HTTP 401' in note
    assert r.get_json()[0]['id'] == 1, 'the cached rows are still returned'


def test_a_live_read_carries_no_stale_header(client, monkeypatch):
    import app as tm
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream',
                        lambda force_full=False: ([{'id': 1, 'origin': 'crowdsec'}], 'full'))
    monkeypatch.setattr(tm, '_cs_lapi_url', lambda: 'http://lapi:8080')
    monkeypatch.setattr(tm, '_cs_api_key', lambda: 'k')
    r = client.get('/api/crowdsec/decisions')
    assert 'X-CS-Stale' not in r.headers


@pytest.mark.parametrize('seconds,text', [
    (90, '1 minute'), (600, '10 minutes'), (3600, '1 hour'),
    (7200, '2 hours'), (172800, '2 days'),
])
def test_the_age_reads_naturally(seconds, text):
    import app as tm
    assert tm._cs_age_text(seconds) == text


def test_the_bans_card_says_when_its_numbers_are_old():
    with open(os.path.join(ROOT, 'static', 'js', 'crowdsec.js'), encoding='utf-8') as fh:
        js = fh.read()
    m = re.search(r"key: 'bans', accent: d\.stale(.*?)\n\s*sub:", js, re.S)
    assert m, 'the live bans card no longer reacts to a stale read'
    assert 'Bans in force (stale)' in m.group(1)
    assert 'note: d.stale' in m.group(1)


def test_the_client_reads_the_header():
    with open(os.path.join(ROOT, 'static', 'js', 'crowdsec.js'), encoding='utf-8') as fh:
        js = fh.read()
    assert '_csDecStale = _csLapiOk ? String(dec.stale' in js
    assert 'stale: _csDecStale' in js


def test_the_stream_marks_an_old_cache_stale_when_the_refresh_fails(tmp_path, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(seconds=crowd.CS_STALE_AFTER_SECONDS + 600)
    doc = {'fp': 'fp1', 'items': {'1': {'id': 1, 'origin': 'crowdsec'}},
           'synced': old, 'ready': True, 'owner': -1, 'stamp': None}

    monkeypatch.setattr(crowd, '_cs_fingerprint', lambda: 'fp1')
    monkeypatch.setattr(crowd, '_cs_shared_read', lambda fp, known=None: dict(doc))
    monkeypatch.setattr(crowd, '_cs_fresh', lambda d, now: False)

    def boom(method, path, **kw):
        raise CrowdSecUnavailable('HTTP 401 from /v1/watchers/login')

    monkeypatch.setattr(crowd, '_cs_request_strict', boom)

    items, mode = crowd.cs_decisions_stream(force_full=True)
    assert items and items[0]['id'] == 1, 'the cached rows must still be served'
    assert mode.startswith('stale:'), \
        'a failed refresh over an old cache must be announced, not passed off as current'
    assert 'HTTP 401' in mode


def test_the_stream_does_not_cry_stale_over_a_recent_cache(tmp_path, monkeypatch):
    recent = datetime.now(timezone.utc) - timedelta(seconds=30)
    doc = {'fp': 'fp1', 'items': {'1': {'id': 1}}, 'synced': recent,
           'ready': True, 'owner': -1, 'stamp': None}
    monkeypatch.setattr(crowd, '_cs_fingerprint', lambda: 'fp1')
    monkeypatch.setattr(crowd, '_cs_shared_read', lambda fp, known=None: dict(doc))
    monkeypatch.setattr(crowd, '_cs_fresh', lambda d, now: False)

    def boom(method, path, **kw):
        raise CrowdSecUnavailable('HTTP 502')

    monkeypatch.setattr(crowd, '_cs_request_strict', boom)
    _items, mode = crowd.cs_decisions_stream(force_full=True)
    assert mode == 'cache', 'a blip over fresh data is not staleness'
