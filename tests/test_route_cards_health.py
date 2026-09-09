import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _block():
    src = _read('static', 'js', 'dashboard.js')
    start = src.index('let _sdApiStatusMap = null;')
    end = src.index('async function loadOverviewStats() {')
    return src[start:end]


HARNESS = r'''
const window = globalThis;
const _esc = s => String(s == null ? '' : s);
Date.now = () => 1000 * 1000;
const CARDS = [];
function card(rid, routekey, protocol) {
    const el = { className: '', title: '' };
    const c = { dataset: { rid, routekey, protocol: protocol || 'http', domains: 'app.example.com' }, querySelector: () => el, appendChild() {}, dot: el };
    CARDS.push(c); return c;
}
const document = { querySelectorAll: () => CARDS, createElement: () => ({ style: {} }), getElementById: () => null };
'''


def _run(body):
    stub = HARNESS + _block() + '\n' + body
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _apply(setup):
    return _run(setup + "\n_sdApplyRouteCards();\nconsole.log(JSON.stringify(CARDS.map(c => [c.dot.className, c.dot.title])));")


def test_a_loaded_router_with_no_check_result_is_not_green():
    res = _apply("_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');")
    cls, title = res[0]
    assert 'status-online' not in cls, 'Traefik saying the router loaded is not proof the backend answers'
    assert cls == 'status-dot status-unknown' and 'not checked yet' in title, res


def test_a_wildcard_route_says_why_it_is_not_checked():
    res = _run("""
_sdApiStatusMap = { wild: { status: 'enabled', error: [], eps: [] } };
const c = card('wild', 'wild'); c.dataset.domains = '*.example.com|{sub}.example.org';
_sdApplyRouteCards();
console.log(JSON.stringify([c.dot.className, c.dot.title]));
""")
    assert res[0] == 'status-dot status-unknown'
    assert 'no host to check' in res[1] and 'Set a link' in res[1], res


def test_a_dead_backend_paints_the_card_red_from_the_background_check():
    res = _apply("""
_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');
_rhIngest({ enabled: true, interval: 300, checked_at: 990, routes: { photos: { state: 'down', source: 'ping', status_code: 502, error: 'The proxy answered 502, the backend is not reachable', at: 990 } } });
""")
    cls, title = res[0]
    assert cls == 'status-dot status-offline' and '502' in title and 'checked just now' in title, res


def test_a_reachable_backend_is_green_with_the_reason():
    res = _apply("""
_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');
_rhIngest({ enabled: true, routes: { photos: { state: 'up', source: 'traefik', servers: { up: 2, total: 2 }, at: 900 } } });
""")
    cls, title = res[0]
    assert cls == 'status-dot status-online' and '2 of 2 servers' in title and '1m ago' in title, res


def test_a_degraded_pool_is_amber_on_the_card_and_names_the_dead_server():
    res = _apply("""
_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');
_rhIngest({ enabled: true, routes: { photos: { state: 'degraded', source: 'servers', servers: { up: 1, total: 2 }, down_servers: ['http://10.0.0.22:80'], at: 990 } } });
""")
    cls, title = res[0]
    assert cls == 'status-dot status-checking' and '1 of 2' in title and '10.0.0.22' in title, res


def test_a_manual_ping_survives_a_redraw():
    res = _run("""
_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');
window._rhRemember('photos', { ok: false, error: 'Timeout', latency_ms: null });
_sdApplyRouteCards();
const first = CARDS[0].dot.className;
_sdApplyRouteCards();
console.log(JSON.stringify({ first, second: CARDS[0].dot.className, title: CARDS[0].dot.title }));
""")
    assert res['first'] == 'status-dot status-offline'
    assert res['second'] == 'status-dot status-offline', 'the redraw threw the ping result away, this is the reported bug'
    assert 'pinged' in res['title'] and 'Timeout' in res['title'], res


def test_the_newer_of_ping_and_background_result_wins():
    res = _run("""
window._rhRemember('photos', { ok: false, error: 'Timeout' });
_rhIngest({ enabled: true, routes: { photos: { state: 'up', source: 'ping', latency_ms: 5, status_code: 200, at: 500 } } });
const keptPing = window._rhGet('photos').state;
_rhIngest({ enabled: true, routes: { photos: { state: 'up', source: 'ping', latency_ms: 5, status_code: 200, at: 2000 } } });
console.log(JSON.stringify({ keptPing, later: window._rhGet('photos').state }));
""")
    assert res['keptPing'] == 'down', 'a ping made after the last background pass must not be overwritten by that older pass'
    assert res['later'] == 'up', 'a newer background pass replaces the ping'


def test_checks_switched_off_say_so_instead_of_guessing():
    res = _apply("""
_sdApiStatusMap = { photos: { status: 'enabled', error: [], eps: [] } }; card('photos', 'photos');
_rhIngest({ enabled: false, routes: {} });
""")
    cls, title = res[0]
    assert cls == 'status-dot status-unknown' and 'off in Settings' in title, res


def test_stream_routes_and_broken_routers_keep_their_traefik_colour():
    res = _apply("""
_sdApiStatusMap = { db: { status: 'enabled', error: [], eps: [] }, bad: { status: 'disabled', error: ['middleware "x@file" does not exist'], eps: [] } };
card('db', 'db', 'tcp'); card('bad', 'bad');
""")
    assert res[0][0] == 'status-dot status-online' and 'stream' in res[0][1], res
    assert res[1][0] == 'status-dot status-offline' and 'does not exist' in res[1][1], res


def test_the_cards_carry_the_route_id_and_pings_are_remembered():
    routes = _read('static', 'js', 'routes.js')
    assert routes.count('data-rid="${_esc(app.id)}"') == 2, 'both card layouts must expose the route id'
    ping_all = routes[routes.index('async function pingAllRoutes'):routes.index('const _ROUTE_ICON_CDN')]
    assert 'window._rhRemember(' in ping_all and '_sdApplyRouteCards()' in ping_all
    assert '_sdApplyRouteCards(false)' not in routes and '_sdApplyRouteCards(true)' not in _read('static', 'js', 'dashboard.js')


def test_the_overview_refresh_loads_and_polls_the_background_result():
    dash = _read('static', 'js', 'dashboard.js')
    assert "fetch('/api/routes/health'" in dash[dash.index('async function loadOverviewStats'):]
    assert 'window._rhPoll' in _read('static', 'js', 'init.js')


def test_settings_expose_the_toggle_and_interval():
    tpl = _read('templates', 'modals', 'settings_modal.html')
    assert 'id="toggle-route-check"' in tpl and 'id="routeCheckInterval"' in tpl
    for v in ('60', '300', '900', '1800'):
        assert 'value="%s"' % v in tpl[tpl.index('id="routeCheckInterval"'):tpl.index('</select>', tpl.index('id="routeCheckInterval"'))]
    js = _read('static', 'js', 'settings-modal.js')
    assert "/api/settings/route-health" in js
    assert 'data.route_check_enabled' in js and 'data.route_check_interval' in js


def _stats_run(body):
    src = _read('static', 'js', 'dashboard.js')
    import re as _re
    tally = _re.search(r'(function _sdTally\(.*?\n\})', src, _re.S).group(1)
    aria = _re.search(r'(function _sdAria\(.*?\n\})', src, _re.S).group(1)
    stub = HARNESS + 'const _sdNum = n => String(n);\n' + _block() + '\n' + tally + '\n' + aria + '\n' + body
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_stats_card_counts_a_dead_backend_as_unreachable():
    res = _stats_run("""
const objs = [{ name: 'play-app@file', short: 'play-app', status: 'enabled', cell: 'ok', reason: '', kind: 'http' },
              { name: 'ok@file', short: 'ok', status: 'enabled', cell: 'ok', reason: '', kind: 'http' }];
_rhIngest({ enabled: true, routes: { 'play.yml::play-app': { state: 'down', source: 'ping', error: 'The proxy answered 502, the backend is not reachable', at: 990 } } });
_sdApplyHealth(objs);
const t = _sdTally(objs);
console.log(JSON.stringify({ cell: objs[0].cell, reason: objs[0].reason, down: t.down, err: t.err, ok: t.ok, aria: _sdAria('HTTP routers', 2, t) }));
""")
    assert res['cell'] == 'err' and res['down'] == 1 and res['err'] == 1 and res['ok'] == 1, res
    assert '502' in res['reason'] and '1 unreachable' in res['aria'], res


def test_a_recovered_route_returns_the_card_to_healthy_on_the_next_render():
    res = _stats_run("""
const objs = [{ name: 'play-app@file', short: 'play-app', status: 'enabled', cell: 'ok', reason: '', kind: 'http' }];
_rhIngest({ enabled: true, routes: { 'play-app': { state: 'down', source: 'ping', at: 900 } } });
_sdApplyHealth(objs);
const before = objs[0].cell;
_rhIngest({ enabled: true, routes: { 'play-app': { state: 'up', source: 'ping', latency_ms: 4, status_code: 200, at: 1200 } } });
_sdApplyHealth(objs);
console.log(JSON.stringify({ before, after: objs[0].cell, down: _sdTally(objs).down }));
""")
    assert res == {'before': 'err', 'after': 'ok', 'down': 0}, res


def test_a_router_traefik_already_flags_is_left_alone():
    res = _stats_run("""
const objs = [{ name: 'bad@file', short: 'bad', status: 'disabled', cell: 'err', reason: 'disabled - middleware missing', kind: 'http' }];
_rhIngest({ enabled: true, routes: { bad: { state: 'down', source: 'ping', at: 900 } } });
_sdApplyHealth(objs);
console.log(JSON.stringify({ reason: objs[0].reason, down: _sdTally(objs).down }));
""")
    assert res['reason'] == 'disabled - middleware missing' and res['down'] == 0, res


def test_the_unreachable_flag_reaches_the_card_and_the_routes_filter():
    dash = _read('static', 'js', 'dashboard.js')
    assert "'unreachable', hGo + ';apistatus=unreachable'" in dash
    assert "'backends unreachable'" in dash
    assert "_sdApplyHealth(model.objs.http);" in dash[dash.index('function _sdRender(model) {'):]
    assert "if (_sdModel) _sdRender(_sdModel);" in dash, 'the minute poll must redraw the cards, not only the dots'
    routes = _read('static', 'js', 'routes.js')
    assert "card.dataset.health === _apiStatusFilter" in routes


def test_icon_urls_are_pinned_to_the_branch_the_cdn_keeps_fresh():
    import glob
    hits = []
    for path in glob.glob(os.path.join(ROOT, 'static', 'js', '*.js')) + [os.path.join(ROOT, 'app.py')]:
        with open(path, encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                if 'selfhst/icons' in line and 'selfhst/icons@main' not in line:
                    hits.append('%s:%d' % (os.path.basename(path), i))
    assert not hits, 'the unversioned jsDelivr path serves icons months out of date, pin @main: %r' % hits
