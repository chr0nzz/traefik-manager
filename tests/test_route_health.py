import pytest

from core import route_health as rh

HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
ON  = {'route_check_enabled': True, 'route_check_interval': 300, 'self_route': {}}


@pytest.fixture
def mon(monkeypatch, tmp_path):
    from core import monitor
    monkeypatch.setattr(monitor, '_state_path', lambda: str(tmp_path / 'monitor.json'))
    monkeypatch.setattr(monitor, '_lock_path', lambda: str(tmp_path / 'monitor.lock'))
    monkeypatch.setattr(monitor, '_agent_servers', lambda: [])
    monkeypatch.setattr(rh.reachability, 'ssrf_ok', lambda url: True)
    monitor._state.clear()
    yield monitor
    monitor._state.clear()


def _app(name, host='app.example.com', tls=True, target='http://10.0.0.5:80', service='svc',
         enabled=True, proto='http'):
    return {'id': name, 'name': name, 'rule': 'Host(`%s`)' % host, 'tls': tls, 'target': target,
            'service_name': service, 'enabled': enabled, 'protocol': proto}


def _host(apps, services=None):
    return lambda: [('host', '', apps, services or {'http': []})]


class _Probe:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def __call__(self, url, fallback=''):
        self.calls.append((url, fallback))
        if self.ok:
            return {'ok': True, 'latency_ms': 12, 'status_code': 200}
        return {'ok': False, 'latency_ms': 8, 'status_code': 502,
                'error': 'The proxy answered 502, the backend is not reachable'}


def _state(mon, rid, server='host'):
    return mon._section(rh.SECTION).get(mon._server_key(server, rid))


def test_a_route_needs_two_failed_checks_before_it_is_down(mon):
    probe = _Probe(ok=False)
    first = rh.check(_host([_app('photos')]), now=0, probe=probe, settings=ON)
    assert first == [], 'one failed check is not yet an outage: %r' % first
    assert _state(mon, 'photos')['state'] == 'pending'

    second = rh.check(_host([_app('photos')]), now=300, probe=probe, settings=ON)
    assert len(second) == 1
    type_, msg, cat = second[0]
    assert (type_, cat) == ('error', 'traefik')
    assert msg == 'Route photos is unreachable (The proxy answered 502, the backend is not reachable)'
    assert _state(mon, 'photos')['state'] == 'down'


def test_a_route_that_was_up_shows_pending_after_one_failure(mon):
    rh.check(_host([_app('photos')]), now=0, probe=_Probe(ok=True), settings=ON)
    rh.check(_host([_app('photos')]), now=300, probe=_Probe(ok=False), settings=ON)
    entry = _state(mon, 'photos')
    assert entry['state'] == 'pending', 'a failed check must not keep reading as up while it is confirmed'
    assert entry['last']['status_code'] == 502
    mon._write_state()
    assert rh.snapshot('host', settings=ON)['routes']['photos']['pending'] is True


def test_recovery_is_reported_once(mon):
    rh.check(_host([_app('photos')]), now=0, probe=_Probe(ok=False), settings=ON)
    rh.check(_host([_app('photos')]), now=300, probe=_Probe(ok=False), settings=ON)

    back = rh.check(_host([_app('photos')]), now=600, probe=_Probe(ok=True), settings=ON)
    assert [(t, m) for t, m, _c in back] == [('success', 'Route photos is reachable again')]

    again = rh.check(_host([_app('photos')]), now=900, probe=_Probe(ok=True), settings=ON)
    assert again == [], 'a route that stays up must not keep reporting'


def test_a_route_first_seen_healthy_says_nothing(mon):
    raised = rh.check(_host([_app('photos')]), now=0, probe=_Probe(ok=True), settings=ON)
    assert raised == []
    assert _state(mon, 'photos')['state'] == 'up'


def test_traefik_health_data_wins_over_pinging(mon):
    probe    = _Probe(ok=True)
    services = {'http': [{'name': 'svc@file', 'loadBalancer': {'healthCheck': {'path': '/'}}, 'serverStatus': {'http://10.0.0.5:80': 'DOWN'}}]}
    raised   = rh.check(_host([_app('photos')], services), now=0, probe=probe, settings=ON)
    assert probe.calls == [], 'Traefik already knows the backend state, do not ping it'
    assert [(t, m) for t, m, _c in raised] == [('error', 'Route photos backend is down, 0 of 1 servers up')]
    assert _state(mon, 'photos')['state'] == 'down', 'a Traefik health check is authoritative, no hysteresis'


def test_server_status_without_a_health_check_is_not_believed(mon):
    probe    = _Probe(ok=False)
    services = {'http': [{'name': 'svc@file', 'loadBalancer': {'servers': [{'url': 'http://10.0.0.5:80'}]},
                          'serverStatus': {'http://10.0.0.5:80': 'UP'}}]}
    rh.check(_host([_app('photos')], services), now=0, probe=probe, settings=ON)
    assert probe.calls, 'Traefik marks every server UP when there is no health check, so the route must be pinged'
    assert _state(mon, 'photos')['last']['source'] == 'ping'


def test_a_degraded_backend_is_a_warning_then_a_recovery(mon):
    two = {'http': [{'name': 'svc@file', 'loadBalancer': {'healthCheck': {'path': '/'}}, 'serverStatus': {'a': 'UP', 'b': 'DOWN'}}]}
    raised = rh.check(_host([_app('photos')], two), now=0, probe=_Probe(), settings=ON)
    assert [(t, m) for t, m, _c in raised] == [('warning', 'Route photos backend is degraded, 1 of 2 servers up')]

    healed = {'http': [{'name': 'svc@file', 'loadBalancer': {'healthCheck': {'path': '/'}}, 'serverStatus': {'a': 'UP', 'b': 'UP'}}]}
    raised = rh.check(_host([_app('photos')], healed), now=300, probe=_Probe(), settings=ON)
    assert [(t, m) for t, m, _c in raised] == [('success', 'Route photos is reachable again')]


def test_the_check_waits_for_its_own_interval(mon):
    probe = _Probe()
    rh.check(_host([_app('photos')]), now=0, probe=probe, settings=ON)
    rh.check(_host([_app('photos')]), now=100, probe=probe, settings=ON)
    assert len(probe.calls) == 1, 'a second run inside the interval must not ping again'
    rh.check(_host([_app('photos')]), now=300, probe=probe, settings=ON)
    assert len(probe.calls) == 2


def test_turning_the_check_off_stops_pinging_and_says_so(mon):
    probe = _Probe()
    off   = dict(ON, route_check_enabled=False)
    assert rh.check(_host([_app('photos')]), now=0, probe=probe, settings=off) == []
    assert probe.calls == []
    mon._write_state()
    snap = rh.snapshot('host', settings=off)
    assert snap['enabled'] is False and snap['routes'] == {}


def test_agent_messages_carry_the_agent_name(mon, monkeypatch):
    agent = {'id': 'a1', 'name': 'VPS One', 'url': 'http://agent'}
    monkeypatch.setattr(mon, '_agent_servers', lambda: [('a1', 'VPS One', agent)])
    src = lambda: [('a1', 'VPS One', [_app('photos')], {'http': []})]
    rh.check(src, now=0, probe=_Probe(ok=False), settings=ON)
    raised = rh.check(src, now=300, probe=_Probe(ok=False), settings=ON)
    assert raised[0][1].startswith('VPS One: Route photos is unreachable')
    mon._write_state()
    assert 'photos' in rh.snapshot('a1', settings=ON)['routes']
    assert rh.snapshot('host', settings=ON)['routes'] == {}, 'agent results must not leak into the host view'


def test_a_route_that_disappears_is_forgotten(mon):
    rh.check(_host([_app('photos')]), now=0, probe=_Probe(), settings=ON)
    assert _state(mon, 'photos')
    rh.check(_host([]), now=300, probe=_Probe(), settings=ON)
    assert _state(mon, 'photos') is None


def test_only_enabled_http_routes_with_a_real_host_are_checked(mon):
    probe = _Probe()
    apps  = [_app('photos'),
             _app('paused', enabled=False),
             _app('wild', host='*.example.com'),
             _app('tmpl', host='{sub}.example.com'),
             _app('db', proto='tcp'),
             _app('me', host='tm.example.com')]
    settings = dict(ON, self_route={'domain': 'tm.example.com'})
    rh.check(_host(apps), now=0, probe=probe, settings=settings)
    assert [u for u, _f in probe.calls] == ['https://app.example.com']
    me = _state(mon, 'me')
    assert me['state'] == 'up' and me['last']['self'] is True, 'our own route is not pinged but must not read as unchecked'
    assert _state(mon, 'paused') is None and _state(mon, 'wild') is None
    mon._write_state()
    assert rh.snapshot('host', settings=settings)['routes']['me']['self'] is True


def test_a_dashboard_link_makes_a_wildcard_route_checkable(mon):
    probe = _Probe()
    apps  = [_app('wild', host='*.example.com'), _app('plain'), _app('off')]
    links = {'wild': {'url': 'https://photos.example.com/'}, 'plain': {'url': 'https://elsewhere.example.com'},
             'off': {'url': 'https://nope.example.com', 'link_disabled': True}}
    rh.check(_host(apps), now=0, probe=probe, settings=ON, overrides_for=lambda server: links)
    assert sorted(u for u, _f in probe.calls) == ['https://app.example.com', 'https://elsewhere.example.com', 'https://photos.example.com/'], probe.calls
    assert _state(mon, 'wild')['state'] == 'up', 'a wildcard route with a link set on the dashboard must be checked at that link'


def test_a_dashboard_link_to_ourselves_reads_as_self(mon):
    probe = _Probe()
    settings = dict(ON, self_route={'domain': 'tm.example.com'})
    rh.check(_host([_app('wild', host='*.example.com')]), now=0, probe=probe, settings=settings,
             overrides_for=lambda server: {'wild': {'url': 'https://tm.example.com/dashboard'}})
    assert probe.calls == [] and _state(mon, 'wild')['last']['self'] is True


def test_the_ping_uses_the_scheme_the_route_serves_and_the_backend_as_fallback(mon):
    probe = _Probe()
    rh.check(_host([_app('plain', tls=False, target='http://10.0.0.9:8080')]), now=0, probe=probe, settings=ON)
    assert probe.calls == [('http://app.example.com', 'http://10.0.0.9:8080')]


def test_the_snapshot_exposes_what_the_card_needs(mon):
    rh.check(_host([_app('photos')]), now=0, probe=_Probe(ok=False), settings=ON)
    mon._write_state()
    snap = rh.snapshot('host', settings=ON)
    entry = snap['routes']['photos']
    assert entry['state'] == 'pending' and entry['pending'] is True
    assert entry['source'] == 'ping' and entry['status_code'] == 502 and entry['at'] == 0
    assert snap['interval'] == 300 and snap['checked_at'] == 0


def test_health_endpoint_reads_the_last_pass(client, mon):
    rh.check(_host([_app('photos')]), now=50, probe=_Probe(), settings=ON)
    mon._write_state()
    data = client.get('/api/routes/health', headers=HDR).get_json()
    assert data['enabled'] is True
    assert data['routes']['photos']['state'] == 'up'
    assert client.get('/api/routes/health?agent_id=nope', headers=HDR).status_code == 404


def test_settings_endpoint_saves_toggle_and_interval(client, app_module):
    r = client.post('/api/settings/route-health', json={'enabled': False, 'interval': 900}, headers=HDR)
    assert r.status_code == 200, r.get_json()
    s = app_module.load_settings()
    assert s['route_check_enabled'] is False and s['route_check_interval'] == 900

    bad = client.post('/api/settings/route-health', json={'interval': 42}, headers=HDR)
    assert bad.status_code == 400
    assert app_module.load_settings()['route_check_interval'] == 900, 'a rejected interval must not be saved'

    shown = client.get('/api/settings', headers=HDR).get_json()
    assert shown['route_check_enabled'] is False and shown['route_check_interval'] == 900


def test_the_check_is_registered_with_the_monitor(app_module):
    from core import monitor
    names = [name for name, _i, _fn in monitor._checks]
    assert 'routes' in names
