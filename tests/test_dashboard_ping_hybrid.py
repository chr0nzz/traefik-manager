import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'dashboard-tab.js')


def _src():
    with open(JS, encoding='utf-8') as fh:
        return fh.read()


def _fn(name, src):
    m = re.search(r'((?:async )?function ' + name + r'\(.*?\n\})', src, re.S)
    assert m, 'the %s helper moved' % name
    return m.group(1)


HARNESS = r'''
const _esc = s => String(s == null ? '' : s);
const _rmConfig = { route_overrides: {} };
const _rmStatusBlind = false;
let SVC = null, HEALTH = {}, META = { loaded: true, enabled: true };
function _dskTerse(m) { return m; }
function _dskRouterState() { return { up: true, err: false, msg: '' }; }
function _dskSvcState() { return SVC; }
function _dashLaunchInfo() { return { url: 'https://x.example.com', hosts: 1 }; }
const window = { _rhGet: rid => HEALTH[rid] || null, get _rhMeta() { return META; } };
Date.now = () => 1000 * 1000;
'''


def _run(body):
    src = _src()
    stub = HARNESS + _fn('_dskChecksOn', src) + '\n' + _fn('_dskAgo', src) + '\n' + _fn('_dskState', src) + '\n' + body
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _state(setup):
    return _run(setup + "\nconst s = _dskState({ id: 'a', name: 'a', enabled: true });"
                        "\nconsole.log(JSON.stringify({ dot: s.dot, tip: s.dotTip, health: s.health, note: s.note }));")


def test_a_dead_backend_from_the_background_check_is_red_and_says_why():
    s = _state("HEALTH = { a: { state: 'down', source: 'ping', error: 'The proxy answered 503, the backend is not reachable', at: 940 } };")
    assert s['dot'] == 'sig-cell-err' and s['health'] == 'down'
    assert '503' in s['tip'] and 'checked 1m ago' in s['tip'], s['tip']
    assert s['note'] == 'backend unreachable'


def test_a_reachable_route_is_green_with_latency_and_age():
    s = _state("HEALTH = { a: { state: 'up', source: 'ping', latency_ms: 42, status_code: 200, at: 990 } };")
    assert s['dot'] == 'sig-cell-ok' and s['health'] == 'up'
    assert 'Online' in s['tip'] and '42ms' in s['tip'] and 'just now' in s['tip'], s['tip']


def test_traefik_health_still_wins_over_the_background_check():
    up = _state("SVC = { up: 1, total: 1 }; HEALTH = { a: { state: 'down', source: 'ping', at: 990 } };")
    assert up['dot'] == 'sig-cell-ok', 'Traefik says the backend is up, that is authoritative: %r' % up
    down = _state("SVC = { up: 0, total: 2 }; HEALTH = { a: { state: 'up', source: 'ping', at: 990 } };")
    assert down['dot'] == 'sig-cell-err', down


def test_a_degraded_pool_from_the_background_check_is_amber_with_the_dead_server_named():
    s = _state("HEALTH = { a: { state: 'degraded', source: 'servers', servers: { up: 1, total: 2 }, down_servers: ['http://10.0.0.22:80'], at: 990 } };")
    assert s['dot'] == 'sig-cell-warn' and s['health'] == 'warn'
    assert '1 of 2' in s['tip'] and '10.0.0.22' in s['tip'], s
    assert 'degraded' in s['note']


def test_an_unchecked_route_stays_neutral_and_says_it_is_waiting():
    s = _state("HEALTH = {};")
    assert s['dot'] == '' and 'not been checked yet' in s['tip'], s


def test_a_route_with_no_host_points_at_the_link_setting():
    s = _run("HEALTH = {}; _dashLaunchInfo = () => ({ url: null, why: 'no launch URL, wildcard host. <b>Set one in edit</b>', glyph: 'ph-bold ph-link-break' });"
             "\nconst s = _dskState({ id: 'a', name: 'a', enabled: true });"
             "\nconsole.log(JSON.stringify({ dot: s.dot, tip: s.dotTip }));")
    assert s['dot'] == '' and 'no host to check' in s['tip'] and 'Set a link' in s['tip'], s


def test_checks_switched_off_are_named_in_the_tooltip():
    s = _state("HEALTH = {}; META = { loaded: true, enabled: false };")
    assert s['dot'] == '' and 'off in Settings' in s['tip'], s


def test_one_failed_check_is_not_yet_red():
    s = _state("HEALTH = { a: { state: 'pending', source: 'ping', error: 'Timeout', at: 990 } };")
    assert s['dot'] == '' and 'confirming' in s['tip'] and 'Timeout' in s['tip'], s


def test_the_dashboard_no_longer_pings_from_the_browser():
    src = _src()
    assert '/api/ping' not in src, 'the background check owns reachability, the browser must not ping'
    assert '_dskPingPass' not in src
    assert 'window._rhLoad' in _fn('refreshDashboardTab', src.replace('window.refreshDashboardTab = async function', 'async function refreshDashboardTab')), \
        'the dashboard must load the background result before it draws'


def test_the_plate_still_tags_the_dot_with_the_route_id():
    assert 'data-rid="\' + _esc(r.id) + \'"' in _fn('_dskPlate', _src())


def test_the_browser_does_not_believe_server_status_without_a_health_check():
    routemap = _read_js('routemap.js')
    guard = routemap[routemap.index('_rmSvcStatus = _rmStatusMap('):routemap.index('return { up: up, total: keys.length };')]
    assert 'up === keys.length && !(sv.loadBalancer && sv.loadBalancer.healthCheck)' in guard, \
        'Traefik reports every server UP without a health check, the dashboard must not paint green from it'
    dash = _read_js('dashboard.js')
    body = dash[dash.index('function _sdBackends(s) {'):dash.index('function _sdComposite(s) {')]
    assert 'up === keys.length && !(s.loadBalancer && s.loadBalancer.healthCheck)' in body


def _read_js(name):
    with open(os.path.join(ROOT, 'static', 'js', name), encoding='utf-8') as fh:
        return fh.read()


def _alarm(down, warn):
    src = _src()
    stub = ("const _esc = s => String(s == null ? '' : s);\n"
            "function _dskSpec(p) { return JSON.stringify(p); }\n"
            + _fn('_dskAlarm', src)
            + "\nconsole.log(JSON.stringify(_dskAlarm({ name: 'Media' }, %d, %d)));" % (down, warn))
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_a_pod_with_both_a_down_and_a_degraded_route_reports_both():
    html = _alarm(1, 1)
    assert '1</b><span class="sig-fl">down' in html, html
    assert '1</b><span class="sig-fl">degraded' in html, \
        'the degraded count is swallowed whenever a down route is present: %r' % html


def test_a_pod_with_only_one_kind_reports_only_that_kind():
    assert '"sig-fl">degraded' not in _alarm(2, 0)
    assert '"sig-fl">down' not in _alarm(0, 3)
    assert _alarm(0, 0) == ''


def test_the_hidden_roll_up_names_both_kinds():
    src = _src()
    body = src[src.index('const hidden = list.slice(limit);'):src.index('pod.appendChild(btn);')]
    assert "(hDown ? ', ' + hDown + ' of them down' : '') + (hWarn ? ', ' + hWarn + ' of them degraded' : '')" in body, \
        'the +N more aria label still collapses degraded into down'
    assert body.count('class="dsk-more-w"') == 1 and body.count('class="dsk-more-n"') == 1
