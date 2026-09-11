from datetime import datetime, timedelta, timezone

import pytest

import app as tm
import core.crowdsec as crowd
from conftest import post_json


@pytest.fixture(autouse=True)
def _cs_clean(monkeypatch):
    for var in ('CROWDSEC_LAPI_URL', 'CROWDSEC_API_KEY', 'CROWDSEC_MACHINE_ID', 'CROWDSEC_MACHINE_PASSWORD',
                'CROWDSEC_CLIENT_CERT', 'CROWDSEC_CLIENT_KEY', 'CROWDSEC_CA_CERT',
                'CROWDSEC_STREAM_FRESH_SECONDS', 'CROWDSEC_ALERT_LIMIT'):
        monkeypatch.delenv(var, raising=False)
    crowd.cs_stream_reset()
    crowd.cs_alerts_reset()
    yield
    crowd.cs_stream_reset()
    crowd.cs_alerts_reset()


def _dec(did, value, origin='crowdsec', type_='ban', scope='Ip', scenario='test/x'):
    return {'id': did, 'value': value, 'origin': origin, 'type': type_, 'scope': scope,
            'scenario': scenario, 'duration': '4h'}


def _alert(aid, ip='1.2.3.4', scenario='crowdsecurity/x', events=1):
    return {'id': aid, 'uuid': f'u{aid}', 'scenario': scenario, 'scenario_version': '0.1',
            'events_count': events, 'capacity': 0, 'leakspeed': '0', 'simulated': False,
            'machine_id': 'm1', 'message': 'msg', 'start_at': 'now', 'stop_at': 'now',
            'created_at': 'now', 'source': {'ip': ip, 'scope': 'Ip'}, 'meta': [],
            'events': [{'x': 1}], 'decisions': [], 'labels': None, 'scenario_hash': 'h',
            'remediation': True}


def _configure(monkeypatch, key='k'):
    monkeypatch.setenv('CROWDSEC_LAPI_URL', 'http://lapi:8080')
    if key:
        monkeypatch.setenv('CROWDSEC_API_KEY', key)


def _stub(monkeypatch, decisions=(), dec_mode='full', alerts=(), alert_mode='cache'):
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream',
                        lambda force_full=False: (list(decisions), dec_mode))
    monkeypatch.setattr(tm._crowd, 'cs_alerts',
                        lambda limit, force_full=False: (list(alerts), alert_mode))


def test_summary_shape_and_counts(client, monkeypatch):
    _configure(monkeypatch)
    decisions = [
        _dec(1, '1.1.1.1', origin='capi'),
        _dec(2, '2.2.2.2', origin='lists'),
        _dec(3, '3.3.3.3', origin='lists'),
        _dec(4, '4.4.4.4', origin='crowdsec'),
        _dec(5, '5.5.5.5', origin='cscli'),
        _dec(6, '6.6.6.6', origin='manual'),
        _dec(7, '7.7.7.0/24', origin='', scope='Range'),
    ]
    _stub(monkeypatch, decisions=decisions)
    r = client.get('/api/crowdsec/summary')
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) == {'version', 'decisions', 'alerts'}
    d = body['decisions']
    assert d['ok'] is True and d['error'] == '' and d['stale'] == ''
    assert d['total'] == 7
    assert d['own'] == 4
    assert d['subscribed'] == 3
    assert d['wide'] == 1
    assert d['origins'] == {'capi': 1, 'lists': 2, 'crowdsec': 1, 'cscli': 1, 'manual': 1, '': 1}
    assert d['types'] == {'ban': 7}
    assert [row['id'] for row in d['rows']] == [7, 6, 5]
    assert d['rows_more'] == 0
    a = body['alerts']
    assert a == {'ok': True, 'error': '', 'status': 200, 'limit': crowd.cs_alert_limit(),
                'capped': False, 'rows': []}


def test_summary_row_cap_and_rows_more(client, monkeypatch):
    _configure(monkeypatch)
    decisions = [_dec(i, f'own-{i}', origin='cscli') for i in range(1, 520)]
    _stub(monkeypatch, decisions=decisions)
    r = client.get('/api/crowdsec/summary')
    d = r.get_json()['decisions']
    assert len(d['rows']) == 500
    assert d['rows_more'] == 19
    assert [row['id'] for row in d['rows'][:3]] == [519, 518, 517]


def test_summary_unchanged_then_new_version_after_delta(client, monkeypatch):
    _configure(monkeypatch)
    _stub(monkeypatch, decisions=[_dec(1, '1.1.1.1')])
    v1 = client.get('/api/crowdsec/summary').get_json()['version']

    r2 = client.get('/api/crowdsec/summary', query_string={'version': v1})
    assert r2.get_json() == {'version': v1, 'unchanged': True}

    _stub(monkeypatch, decisions=[_dec(1, '1.1.1.1'), _dec(2, '2.2.2.2')], dec_mode='delta')
    r3 = client.get('/api/crowdsec/summary', query_string={'version': v1})
    body3 = r3.get_json()
    assert body3['version'] != v1
    assert body3['decisions']['total'] == 2


def test_handled_true_and_false(client, monkeypatch):
    _configure(monkeypatch)
    _stub(monkeypatch, decisions=[_dec(1, '9.9.9.9', scope='Ip')],
         alerts=[_alert(1, ip='9.9.9.9'), _alert(2, ip='8.8.8.8')])
    r = client.get('/api/crowdsec/summary')
    rows = {row['id']: row for row in r.get_json()['alerts']['rows']}
    assert rows[1]['handled'] is True
    assert rows[2]['handled'] is False


def test_trimmed_keys_and_no_events(client, monkeypatch):
    _configure(monkeypatch)
    _stub(monkeypatch, decisions=[], alerts=[_alert(1)])
    r = client.get('/api/crowdsec/summary')
    row = r.get_json()['alerts']['rows'][0]
    assert 'events' not in row
    assert 'decisions' not in row
    assert 'labels' not in row
    assert 'scenario_hash' not in row
    assert 'remediation' not in row
    assert set(row) - {'handled'} <= set(tm.CS_SUMMARY_ALERT_KEYS)


def test_decisions_not_ok_without_a_key_while_alerts_still_ok(client, monkeypatch):
    _configure(monkeypatch, key='')
    _stub(monkeypatch, alerts=[_alert(1)])
    r = client.get('/api/crowdsec/summary')
    body = r.get_json()
    assert body['decisions']['ok'] is False
    assert 'bouncer' in body['decisions']['error'].lower()
    assert body['decisions']['total'] == 0 and body['decisions']['rows'] == []
    assert body['alerts']['ok'] is True
    assert body['alerts']['rows'][0]['id'] == 1
    assert 'handled' not in body['alerts']['rows'][0]


def test_summary_requires_a_lapi_url(client):
    r = client.get('/api/crowdsec/summary')
    assert r.status_code == 503
    assert r.get_json() == {'error': 'CrowdSec not configured'}


_SEARCH_DECISIONS = [
    _dec(1, '1.1.1.1', origin='capi', type_='ban', scenario='crowdsecurity/ssh-bf'),
    _dec(2, '2.2.2.2', origin='lists', type_='ban', scenario='blocklist'),
    _dec(3, '3.3.3.3', origin='cscli', type_='ban', scenario='manual-ban'),
    _dec(4, '4.4.4.4', origin='manual', type_='captcha', scenario='manual-captcha'),
    _dec(5, '5.5.5.5', origin='crowdsec', type_='ban', scenario='crowdsecurity/http-probing'),
]


def _search(client, monkeypatch, **params):
    _configure(monkeypatch)
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream',
                        lambda force_full=False: (list(_SEARCH_DECISIONS), 'full'))
    return client.get('/api/crowdsec/decisions/search', query_string=params)


def test_search_order_is_own_first_then_id_desc(client, monkeypatch):
    r = _search(client, monkeypatch)
    body = r.get_json()
    assert [row['id'] for row in body['rows']] == [5, 4, 3, 2, 1]
    assert body['total'] == 5


def test_search_paging(client, monkeypatch):
    r = _search(client, monkeypatch, per='2', page='1')
    body = r.get_json()
    assert [row['id'] for row in body['rows']] == [5, 4]
    assert body['pages'] == 3 and body['per'] == 2 and body['page'] == 1

    r2 = _search(client, monkeypatch, per='2', page='3')
    assert [row['id'] for row in r2.get_json()['rows']] == [1]

    r3 = _search(client, monkeypatch, per='2', page='99')
    body3 = r3.get_json()
    assert body3['page'] == 3
    assert [row['id'] for row in body3['rows']] == [1]


@pytest.mark.parametrize('origin,expected', [
    ('subscribed', [2, 1]),
    ('own', [5, 4, 3]),
    ('byhand', [4, 3]),
    ('capi', [1]),
])
def test_search_origin_filter(client, monkeypatch, origin, expected):
    r = _search(client, monkeypatch, origin=origin)
    assert [row['id'] for row in r.get_json()['rows']] == expected


def test_search_type_filter(client, monkeypatch):
    r = _search(client, monkeypatch, type='captcha')
    assert [row['id'] for row in r.get_json()['rows']] == [4]


def test_search_ip_filter(client, monkeypatch):
    r = _search(client, monkeypatch, ip='3.3.3.3')
    assert [row['id'] for row in r.get_json()['rows']] == [3]


def test_search_scenario_filter(client, monkeypatch):
    r = _search(client, monkeypatch, scenario='manual-ban')
    assert [row['id'] for row in r.get_json()['rows']] == [3]


def test_search_q_matches_scenario_substring(client, monkeypatch):
    r = _search(client, monkeypatch, q='http-probing')
    assert [row['id'] for row in r.get_json()['rows']] == [5]


def test_facet_totals_ignore_other_filters_but_keep_q(client, monkeypatch):
    r = _search(client, monkeypatch, origin='own', type='captcha')
    body = r.get_json()
    assert [row['id'] for row in body['rows']] == [4]
    assert body['facet_totals']['origin'] == 3
    assert body['facet_totals']['type'] == 1


def test_facet_totals_fall_back_to_q_alone_when_unset(client, monkeypatch):
    r = _search(client, monkeypatch, q='crowdsecurity')
    body = r.get_json()
    assert body['total'] == 2
    assert body['facet_totals'] == {'origin': 2, 'type': 2}


def test_search_requires_a_lapi_url(client):
    r = client.get('/api/crowdsec/decisions/search')
    assert r.status_code == 503


def test_alerts_cache_full_then_delta_then_cap(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def fake(path):
        calls.append(path)
        if 'since' not in path:
            return [_alert(1), _alert(2)]
        return [_alert(3)]

    monkeypatch.setattr(crowd, '_cs_alert_fetch', fake)
    rows, mode = crowd.cs_alerts(2)
    assert mode == 'full'
    assert sorted(r['id'] for r in rows) == [1, 2]

    rows, mode = crowd.cs_alerts(2)
    assert mode == 'delta'
    assert sorted(r['id'] for r in rows) == [2, 3], 'the cache must cap to the newest `limit` ids'
    assert 'since=' in calls[1]


def test_alerts_cache_reports_stale_after_lapi_dies(monkeypatch):
    _configure(monkeypatch)
    old = datetime.now(timezone.utc) - timedelta(seconds=crowd.CS_STALE_AFTER_SECONDS + 600)
    doc = {'fp': crowd._cs_alert_fp(), 'limit': 10, 'items': {'1': _alert(1)}, 'synced': old,
          'ready': True, 'owner': -1, 'stamp': None}
    monkeypatch.setattr(crowd, '_cs_shared_read', lambda fp, known=None, **kw: dict(doc))
    monkeypatch.setattr(crowd, '_cs_fresh', lambda d, now: False)

    def boom(path):
        raise crowd.CrowdSecUnavailable('LAPI 500: boom', 500)

    monkeypatch.setattr(crowd, '_cs_alert_fetch', boom)
    rows, mode = crowd.cs_alerts(10, force_full=True)
    assert mode.startswith('stale:')
    assert rows and rows[0]['id'] == 1


def test_post_decision_resets_the_alerts_cache(client, monkeypatch):
    _configure(monkeypatch)
    crowd._cs_alert_cache.update({'ready': True})
    monkeypatch.setattr(tm, '_cs_request', lambda *a, **k: {'ok': True})
    resp = post_json(client, '/api/crowdsec/decisions', {'value': '1.2.3.4', 'type': 'ban'})
    assert resp.status_code == 200
    assert crowd._cs_alert_cache['ready'] is False


def test_the_list_endpoints_still_return_arrays(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(tm._crowd, 'cs_decisions_stream',
                        lambda force_full=False: ([_dec(1, '1.1.1.1')], 'full'))
    r = client.get('/api/crowdsec/decisions')
    assert isinstance(r.get_json(), list)

    class _Resp:
        status_code = 200
        ok = True
        content = b'[]'

        def json(self):
            return [_alert(9)]

    monkeypatch.setattr(tm.requests, 'get', lambda *a, **k: _Resp())
    r2 = client.get('/api/crowdsec/alerts')
    assert isinstance(r2.get_json(), list)
    assert r2.headers.get('X-CS-Alert-Limit')
