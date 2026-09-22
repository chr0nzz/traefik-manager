import os
import re
import subprocess
import sys

import pytest

from core import env

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


@pytest.mark.parametrize('raw,expected', [
    ('', ''),
    ('   ', ''),
    ('/traefik-manager', '/traefik-manager'),
    ('/tm/', '/tm'),
    ('  /a/b  ', '/a/b'),
    ('/', ''),
    ('traefik-manager', ''),
    ('https://evil.example/x', ''),
    ('//evil.example', ''),
])
def test_base_path_is_validated(monkeypatch, raw, expected):
    monkeypatch.setenv('BASE_PATH', raw)
    assert env.base_path() == expected


def test_base_path_defaults_to_empty(monkeypatch):
    monkeypatch.delenv('BASE_PATH', raising=False)
    assert env.base_path() == ''


def _render(base):
    script = (
        'import os, sys\n'
        'os.environ["BASE_PATH"] = %r\n'
        'sys.path.insert(0, %r)\n'
        'sys.argv = ["pytest"]\n'
        'sys.path.insert(0, %r)\n'
        'import conftest\n'
        'import app as tm\n'
        'c = tm.app.test_client()\n'
        'with tm.app.test_request_context():\n'
        '    out = tm.render_template("manifest.json")\n'
        'sys.stdout.write(out)\n'
    ) % (base, ROOT, os.path.join(ROOT, 'tests'))
    res = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr[-2000:]
    return res.stdout


def test_the_manifest_is_unchanged_without_a_base_path():
    out = _render('')
    assert '"start_url": "/"' in out
    assert '"scope": "/"' in out
    assert '"src": "/static/icons/icon-48x48.png"' in out


def test_the_manifest_carries_the_base_path_when_set():
    out = _render('/traefik-manager')
    assert '"start_url": "/traefik-manager/"' in out
    assert '"scope": "/traefik-manager/"' in out
    assert '"src": "/traefik-manager/static/icons/icon-48x48.png"' in out


def test_no_template_still_hardcodes_a_static_path():
    offenders = []
    tpl = os.path.join(ROOT, 'templates')
    for dirpath, _dirs, files in os.walk(tpl):
        for name in files:
            if not name.endswith(('.html', '.json')):
                continue
            path = os.path.join(dirpath, name)
            for i, line in enumerate(_read(os.path.relpath(path, ROOT)).splitlines(), 1):
                if '"/static/' in line:
                    offenders.append(f'{os.path.relpath(path, ROOT)}:{i}')
    assert not offenders, 'these bypass base_path: %s' % offenders


def test_the_fetch_wrapper_prefixes_relative_urls():
    js = _read('static', 'js', 'core.js')
    assert 'function tmUrl(' in js
    assert 'input = tmUrl(input)' in js, 'the single fetch wrapper must apply the prefix'


def test_tm_url_is_a_no_op_without_a_base_path():
    js = _read('static', 'js', 'core.js')
    m = re.search(r'function tmUrl\(path\) \{(.*?)\n\}', js, re.S)
    assert m, 'tmUrl not found'
    assert 'if (!TM_BASE) return path;' in m.group(1), \
        'an empty base path must return the url untouched'


def test_the_login_redirect_goes_through_tm_url():
    js = _read('static', 'js', 'core.js')
    assert "tmUrl('/login')" in js
    assert "window.location.href = '/login?next='" not in js


def test_the_service_worker_registers_under_the_prefix():
    js = _read('static', 'js', 'init.js')
    assert "tmUrl('/static/sw.js')" in js


def test_both_page_templates_publish_the_base_path():
    for tpl in ('index.html', 'login.html'):
        assert 'name="tm-base-path"' in _read('templates', tpl), tpl


def test_no_script_hardcodes_a_static_path_outside_fetch():
    offenders = []
    js_dir = os.path.join(ROOT, 'static', 'js')
    for name in sorted(os.listdir(js_dir)):
        if not name.endswith('.js'):
            continue
        rel = os.path.join('static', 'js', name)
        for i, line in enumerate(_read(rel).splitlines(), 1):
            for hit in re.finditer(r"""['"]/static/""", line):
                before = line[:hit.start()]
                if before.rstrip().endswith('fetch('):
                    continue
                if 'tmUrl(' in line[max(0, hit.start() - 12):hit.start()]:
                    continue
                offenders.append('%s:%d' % (rel, i))
    assert not offenders, (
        'these bypass BASE_PATH - wrap them in tmUrl(), since only fetch() is '
        'rewritten automatically: %s' % offenders)


def test_the_monaco_loader_follows_the_base_path():
    src = _read(os.path.join('static', 'js', 'static-config.js'))
    first = src.splitlines()[0]
    assert 'require.config' in first, 'the Monaco loader config moved'
    assert 'tmUrl(' in first, \
        'the AMD loader injects script tags, so the fetch wrapper never sees it'


@pytest.mark.parametrize('script_root, next_url, expected', [
    ('', '/', '/'),
    ('', '/?tab=routes', '/?tab=routes'),
    ('/en', '/', '/en/'),
    ('/tm', '/', '/tm/'),
    ('/tm/de', '/', '/tm/de/'),
    ('/tm', '/de/', '/tm/de/'),
    ('/tm', '/tm/', '/tm/'),
    ('/tm', '/tm', '/tm'),
    ('/tm', '//evil.example', '/tm/'),
    ('', 'https://evil.example', '/'),
])
def test_next_stays_under_base_path_and_language(app_module, script_root, next_url, expected):
    with app_module.app.test_request_context('/login', base_url='http://localhost' + script_root):
        assert app_module._safe_next(next_url) == expected
