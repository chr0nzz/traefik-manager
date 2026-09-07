import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import json, os, sys, tempfile
d = tempfile.mkdtemp()
a = os.path.join(d, 'a.yml')
b = os.path.join(d, 'b.yml')
open(a, 'w').write(
    "http:\n  middlewares:\n    auth:\n      basicAuth:\n        users: ['u:x']\n"
    "  services:\n    pool:\n      weighted:\n        services:\n"
    "          - name: leaf\n            weight: 1\n"
    "    leaf:\n      loadBalancer:\n        servers: [{url: 'http://10.0.0.1:80'}]\n")
open(b, 'w').write(
    "http:\n  routers:\n    web:\n      rule: Host(`w.example.com`)\n"
    "      service: pool\n      middlewares: [auth]\n")
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = a + ',' + b
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


def router_mws():
    return ((C.load_config(b).get('http') or {}).get('routers') or {}).get('web', {}).get('middlewares')


def router_svc():
    return ((C.load_config(b).get('http') or {}).get('routers') or {}).get('web', {}).get('service')


out = {}
r = c.post('/save-middleware', data={
    'csrf_token': 't', 'middlewareName': 'authelia', 'isMwEdit': 'true',
    'originalMwId': 'auth', 'mwProtocol': 'http', 'originalMwProtocol': 'http',
    'middlewareContent': "basicAuth:\n  users: ['u:x']\n"}, headers=H)
out['mw_rename_status'] = r.status_code
out['router_mws_after_rename'] = router_mws()

adopt = c.post('/api/services/pool/ownership', headers=H, json={'adopt': True})
out['adopt_status'] = adopt.status_code

r = c.post('/api/services', headers=H, json={
    'name': 'renamed', 'type': 'weighted', 'originalName': 'pool',
    'children': [{'kind': 'service', 'name': 'leaf', 'weight': 1, 'percent': 0}]})
out['svc_rename_status'] = r.status_code
out['router_svc_after_rename'] = router_svc()

r = c.post('/delete-middleware/authelia', data={'csrf_token': 't'}, headers=H)
out['delete_without_force'] = r.status_code

r = c.post('/delete-middleware/authelia', data={'csrf_token': 't', 'force': 'true'}, headers=H)
out['delete_force_status'] = r.status_code
out['router_mws_after_force'] = router_mws()
print('@@' + json.dumps(out))
'''


def _run(tmp_path):
    script = ('ROOT = %r\n' % ROOT) + PROBE
    path = str(tmp_path / 'probe_mf.py')
    with open(path, 'w') as fh:
        fh.write(script)
    res = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in res.stdout.splitlines() if ln.startswith('@@')]
    assert line, res.stdout + res.stderr
    return json.loads(line[0][2:])


def test_a_middleware_rename_reaches_a_router_in_another_file(tmp_path):
    res = _run(tmp_path)
    assert res['mw_rename_status'] in (200, 302), res
    assert res['router_mws_after_rename'] == ['authelia'], \
        'the router lives in another config file and was left pointing at the old name: %r' % res


def test_a_service_rename_reaches_a_router_in_another_file(tmp_path):
    res = _run(tmp_path)
    assert res['svc_rename_status'] == 200, res
    assert res['router_svc_after_rename'] == 'renamed', \
        'the router in another file still points at the old service: %r' % res


def test_a_used_middleware_in_another_file_is_still_refused(tmp_path):
    res = _run(tmp_path)
    assert res['delete_without_force'] == 409, \
        'the router using it lives in another file and was not seen: %r' % res


def test_force_delete_strips_a_reference_in_another_file(tmp_path):
    res = _run(tmp_path)
    assert res['delete_force_status'] == 200, res
    assert not res['router_mws_after_force'], \
        'the reference in the other file was left behind: %r' % res
