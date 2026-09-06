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
const _esc = s => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const DOTS = {};
function mkDot(rid) {
    const cls = new Set();
    const d = { title: '', classList: { add: (...a) => a.forEach(x => cls.add(x)), remove: (...a) => a.forEach(x => cls.delete(x)), contains: x => cls.has(x) }, _cls: cls };
    DOTS[rid] = d; return d;
}
const document = { querySelectorAll: sel => { const m = sel.match(/data-rid="(.*)"\]$/); const d = m && DOTS[m[1].replace(/\\"/g,'"')]; return d ? [d] : []; } };
const CALLS = [];
let RESPONSES = {};
globalThis.fetch = async (url) => { CALLS.push(url); const key = decodeURIComponent((url.match(/url=([^&]*)/) || [])[1] || ''); return { json: async () => RESPONSES[key] }; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
'''


def _run(body):
    src = _src()
    stub = (HARNESS + _fn('_dskPingTarget', src) + '\n' + _fn('_dskApplyPing', src) + '\n'
            + 'let _dskPingGen = 0;\n' + _fn('_dskPingPass', src) + '\n' + body)
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_only_routes_without_traefik_health_data_are_pinged():
    res = _run('''
mkDot('a'); mkDot('b'); mkDot('c');
RESPONSES = { 'https://a.example.com': { ok: true, latency_ms: 12, status_code: 200 } };
_dskPingPass([
  { r: { id: 'a', target: '' }, s: { ping: true,  url: 'https://a.example.com' } },
  { r: { id: 'b', target: '' }, s: { ping: false, url: 'https://b.example.com' } },
  { r: { id: 'c', target: '' }, s: { ping: true,  url: '' } },
]);
await sleep(30);
console.log(JSON.stringify({ calls: CALLS.length, pinged_a: CALLS.some(u => u.includes('a.example.com')),
  pinged_b: CALLS.some(u => u.includes('b.example.com')), a_ok: DOTS.a._cls.has('sig-cell-ok') }));
''')
    assert res['calls'] == 1, 'only the route Traefik cannot vouch for should be pinged: %r' % res
    assert res['pinged_a'] and not res['pinged_b'], 'a route with Traefik health data must not be pinged: %r' % res
    assert res['a_ok'] is True


def test_a_dead_backend_goes_red_and_says_why():
    res = _run('''
mkDot('x');
RESPONSES = { 'https://x.example.com': { ok: false, error: 'The proxy answered 503, the backend is not reachable' } };
_dskPingPass([{ r: { id: 'x', target: '' }, s: { ping: true, url: 'https://x.example.com' } }]);
await sleep(30);
console.log(JSON.stringify({ err: DOTS.x._cls.has('sig-cell-err'), ok: DOTS.x._cls.has('sig-cell-ok'), title: DOTS.x.title }));
''')
    assert res['err'] is True and res['ok'] is False, res
    assert '503' in res['title'], 'the tooltip should carry the reason: %r' % res['title']


def test_the_backend_address_is_sent_as_the_fallback_only_when_it_is_a_url():
    res = _run('''
mkDot('p'); mkDot('q');
RESPONSES = { 'https://p.example.com': { ok: true, latency_ms: 1, status_code: 200 },
              'https://q.example.com': { ok: true, latency_ms: 1, status_code: 200 } };
_dskPingPass([
  { r: { id: 'p', target: 'http://10.0.0.5:8080' }, s: { ping: true, url: 'https://p.example.com' } },
  { r: { id: 'q', target: 'N/A' },                  s: { ping: true, url: 'https://q.example.com' } },
]);
await sleep(30);
const p = CALLS.find(u => u.includes('p.example.com')), q = CALLS.find(u => u.includes('q.example.com'));
console.log(JSON.stringify({ p_fb: /fallback=/.test(p), q_fb: /fallback=/.test(q), p_val: decodeURIComponent((p.match(/fallback=([^&]*)/)||[])[1]||'') }));
''')
    assert res['p_fb'] is True and res['p_val'] == 'http://10.0.0.5:8080', res
    assert res['q_fb'] is False, 'a non-URL target must not be sent as a fallback: %r' % res


def test_a_result_from_a_previous_render_is_discarded():
    res = _run('''
mkDot('s');
let release; RESPONSES = { 'https://s.example.com': new Promise(r => { release = r; }) };
globalThis.fetch = async (url) => { CALLS.push(url); return { json: () => RESPONSES['https://s.example.com'] }; };
_dskPingPass([{ r: { id: 's', target: '' }, s: { ping: true, url: 'https://s.example.com' } }]);
_dskPingGen++;
release({ ok: true, latency_ms: 1, status_code: 200 });
await sleep(30);
console.log(JSON.stringify({ touched: DOTS.s._cls.has('sig-cell-ok') || DOTS.s._cls.has('sig-cell-err') }));
''')
    assert res['touched'] is False, 'a stale ping result must not paint a re-rendered dashboard'


def test_the_plate_tags_the_dot_with_the_route_id():
    assert 'data-rid="\' + _esc(r.id) + \'"' in _fn('_dskPlate', _src()), \
        'the ping pass finds dots by route id, so the plate must emit it'


def test_traefik_health_still_wins_over_the_ping():
    src = _src()
    body = _fn('_dskState', src)
    health = body.index("} else if (svc && svc.total) {")
    ping = body.index("} else if (lnk.url) {")
    assert health < ping, 'the ping branch must come after the Traefik health branch, or it is not a hybrid'
    tail = body[ping:]
    assert 's.ping   = true' in tail or 's.ping = true' in tail
