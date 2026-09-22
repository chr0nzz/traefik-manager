import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOSTILE = [
    {'name': "x');alert(1)//.20260914_101010.bak", 'modified': '<svg onload=alert(1)>', 'size': 10},
    {'name': '<img src=x onerror=alert(1)>.20260914_101010.bak', 'modified': '2026-09-14', 'size': '<b>9</b>'},
    {'name': 'quote"and\'both.20260914_101010.bak', 'modified': '2026-09-14', 'size': 1, 'restoreBlocked': True},
    {'name': 'plain.yml.20260914_101010.bak', 'modified': '2026-09-14', 'size': 2048},
]


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _fn(name, src):
    m = re.search(r'(function ' + name + r'\(.*?\n\})', src, re.S)
    assert m, 'the %s function moved' % name
    return m.group(1)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.handlers = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            if key.startswith('on') and key != 'onclick' or (key == 'onclick' and value):
                self.handlers.append((key, value))

    def handle_data(self, data):
        self.text.append(data)


def _render(backups):
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed')
    core = _read('static', 'js', 'core.js')
    modal = _read('static', 'js', 'settings-modal.js')
    i18n = _read('static', 'js', 'i18n.js')
    script = '\n'.join([
        '(function (window, document) {\n' + i18n + '\n})(globalThis, { getElementById: () => null, documentElement: { lang: "en" } });',
        _fn('_esc', core),
        _fn('_jsArg', core),
        'function formatBytes(n) { return String(n) + " B"; }',
        'const box = { innerHTML: "" };',
        'const document = { getElementById: () => box };',
        _fn('_renderBackupList', modal),
        '_renderBackupList("x", %s);' % json.dumps(backups),
        'console.log(box.innerHTML);',
    ])
    r = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_a_hostile_backup_name_cannot_inject_markup():
    parsed = _Tags()
    parsed.feed(_render(HOSTILE))
    assert 'img' not in parsed.tags and 'svg' not in parsed.tags and 'b' not in parsed.tags, (
        'an agent controls these names, so a crafted one ran script in the host admin session')
    text = ''.join(parsed.text)
    assert '<img src=x onerror=alert(1)>' in text and '<svg onload=alert(1)>' in text, \
        'the hostile text should still be shown, just as text'


def test_a_hostile_backup_name_survives_the_click_handler_intact():
    parsed = _Tags()
    parsed.feed(_render(HOSTILE))
    names = {b['name'] for b in HOSTILE}
    calls = [v for k, v in parsed.handlers if k == 'onclick' and v.startswith(('restoreBackup', 'deleteBackup'))]
    assert calls, 'the backup rows lost their buttons'
    for call in calls:
        m = re.match(r'^(restoreBackup|deleteBackup)\((".*")\)$', call, re.S)
        assert m, 'the name broke out of the call: %r' % call
        assert json.loads(m.group(2)) in names, 'the name did not round trip: %r' % call
    blocked = [c for c in calls if 'quote' in c and c.startswith('restoreBackup')]
    assert not blocked, 'a blocked restore must not get a working Restore handler'
