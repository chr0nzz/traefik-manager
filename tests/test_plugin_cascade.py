import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import json, os, sys, tempfile
d = tempfile.mkdtemp()
dyn = os.path.join(d, 'dynamic.yml')
static = os.path.join(d, 'traefik.yml')
open(static, 'w').write(
    "experimental:\n  plugins:\n    fail2ban:\n"
    "      moduleName: github.com/tomMoulard/fail2ban\n      version: v0.8.3\n")
open(dyn, 'w').write(
    "http:\n  middlewares:\n    ban:\n      plugin:\n        fail2ban:\n"
    "          rules:\n            bantime: 3h\n    other:\n      compress: {}\n")
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = dyn
os.environ['STATIC_CONFIG_PATH'] = static
open(os.environ['SETTINGS_PATH'], 'w').write(
    "domains: [example.com]\nauth_enabled: false\nsetup_complete: true\n")
sys.path.insert(0, ROOT)
import app as A
from core import config as C

c = A.app.test_client()
with c.session_transaction() as s:
    s['authenticated'] = True
    s['last_active'] = 9e9
    s['csrf_token'] = 't'
H = {'X-CSRF-Token': 't', 'X-Requested-With': 'fetch'}

RENAMED = ("experimental:\n  plugins:\n    f2b:\n"
           "      moduleName: github.com/tomMoulard/fail2ban\n      version: v0.8.3\n")
REMOVED = "experimental:\n  plugins: {}\n"

out = {}
r = c.post('/api/static/config', headers=H, json={'content': RENAMED})
out['rename_save_status'] = r.status_code
mw = (C.load_config(dyn).get('http') or {}).get('middlewares') or {}
out['middleware_after_rename'] = json.dumps(mw.get('ban'), default=str)
out['untouched_middleware'] = json.dumps(mw.get('other'), default=str)

r = c.post('/api/static/config', headers=H, json={'content': REMOVED})
out['remove_save_status'] = r.status_code
out['remove_body'] = json.dumps(r.get_json(), default=str)[:200]
out['static_after_remove'] = open(static).read()
print('@@' + json.dumps(out))
'''


def _run(tmp_path):
    script = ('ROOT = %r\n' % ROOT) + PROBE
    path = str(tmp_path / 'probe_plugin.py')
    with open(path, 'w') as fh:
        fh.write(script)
    res = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in res.stdout.splitlines() if ln.startswith('@@')]
    assert line, res.stdout + res.stderr
    return json.loads(line[0][2:])


def test_renaming_a_plugin_moves_the_middlewares_using_it(tmp_path):
    res = _run(tmp_path)
    assert res['rename_save_status'] == 200, res
    assert 'f2b' in res['middleware_after_rename'], \
        'the middleware still names the old plugin: %s' % res['middleware_after_rename']
    assert 'fail2ban' not in res['middleware_after_rename']


def test_renaming_a_plugin_leaves_other_middlewares_alone(tmp_path):
    res = _run(tmp_path)
    assert 'compress' in res['untouched_middleware'], res['untouched_middleware']
    assert 'plugin' not in res['untouched_middleware']


def test_removing_a_plugin_still_in_use_is_refused(tmp_path):
    res = _run(tmp_path)
    assert res['remove_save_status'] == 409, \
        'removing a plugin a middleware still uses must be refused: %s' % res['remove_body']
    assert 'ban' in res['remove_body'], 'the refusal must name the middlewares: %s' % res['remove_body']
    assert 'f2b' in res['static_after_remove'], 'the plugin was removed despite being in use'
