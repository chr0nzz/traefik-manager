import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'static', 'js', 'dashboard-tab.js')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _status_fn():
    src = _read('static', 'js', 'dashboard-tab.js')
    m = re.search(r'(function _dskStatus\(.*?\n\})', src, re.S)
    assert m, 'the status helper moved'
    return m.group(1)


def _run(route, st, svc):
    stub = ('const _esc = s => String(s == null ? "" : s);\n'
            'const _rmStatusBlind = false;\n'
            'function _dskTerse(m) { return m; }\n'
            'function _dskLink() { return { url: "", hosts: 0 }; }\n'
            'function _dskOverride() { return {}; }\n'
            + _status_fn()
            + '\nconsole.log(JSON.stringify(_dskStatus(%s, %s, %s, {})));'
              % (json.dumps(route), json.dumps(st), json.dumps(svc)))
    out = subprocess.run(['node', '-e', stub], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_healthy_route_gets_a_colour():
    src = _read('static', 'js', 'dashboard-tab.js')
    at = src.index("'Router loaded, '")
    branch = src[max(0, at - 400):at]
    tail = branch[branch.rindex('} else'):]
    assert 's.dot' in tail, (
        'the healthy branch never sets a dot class, so a working route renders grey')
    assert 'sig-cell-ok' in tail, 'a healthy route should read as up at a glance'


def test_the_healthy_class_is_styled_green():
    css = _read('static', 'css', 'app.css')
    assert re.search(r'\.sig-cell-ok\s*\{[^}]*var\(--green\)', css), \
        'sig-cell-ok has no green background, so the dot stays grey'


def test_the_other_states_keep_their_colours():
    css = _read('static', 'css', 'app.css')
    assert re.search(r'\.sig-cell-err\s*\{[^}]*var\(--red\)', css)
    assert re.search(r'\.sig-cell-warn\s*\{[^}]*var\(--yellow\)', css)


def test_green_is_only_used_when_traefik_knows_the_backend_is_up():
    src = _read('static', 'js', 'dashboard-tab.js')
    at = src.index("'Router loaded, '")
    branch = src[max(0, at - 400):at]
    guard = branch[branch.rindex('} else'):]
    assert 'svc && svc.total' in guard, (
        'green must require real backend health, or an offline app behind a healthy proxy '
        'is confidently reported as up')


def test_an_unknown_backend_stays_neutral_and_says_so():
    src = _read('static', 'js', 'dashboard-tab.js')
    at = src.index('Traefik reports no backend health')
    branch = src[src.rindex('} else {', 0, at):at]
    assert not re.search(r's\.dot\s*=', branch), \
        'with no health check we do not know, so the dot should stay neutral'
    assert 'no backend health' in src[at - 60:at + 60], 'the tooltip should say why'
