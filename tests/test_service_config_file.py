import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
a = os.path.join(d, 'a.yml')
b = os.path.join(d, 'b.yml')
open(a, 'w').write('http:\n  routers: {}\n  services: {}\n')
open(b, 'w').write('http:\n  routers: {}\n  services: {}\n')
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = a + ',' + b
open(os.environ['SETTINGS_PATH'], 'w').write(
    "domains: [example.com]\nauth_enabled: false\nsetup_complete: true\n")
sys.path.insert(0, ROOT)
import app as A
from core import config as C

HDR = {'X-CSRF-Token': 't', 'X-Requested-With': 'fetch'}
c = A.app.test_client()
with c.session_transaction() as s:
    s['authenticated'] = True
    s['last_active'] = 9e9
    s['csrf_token'] = 't'


def svcs(path):
    return sorted((C.load_config(path).get('http') or {}).get('services') or {})


def server(path, name):
    s = ((C.load_config(path).get('http') or {}).get('services') or {}).get(name) or {}
    return [x.get('url') for x in (s.get('loadBalancer') or {}).get('servers') or []]


def save(name, addr, cfg_file, original=''):
    body = {'name': name, 'type': 'loadBalancer', 'configFile': cfg_file,
            'children': [{'kind': 'manual', 'address': addr, 'scheme': 'http',
                          'weight': 1, 'percent': 0}]}
    if original:
        body['originalName'] = original
    return c.post('/api/services', json=body, headers=HDR)


out = {}
save('pool', '10.0.0.1:80', 'b.yml')
out['created_in_b'] = svcs(b)
out['created_in_a'] = svcs(a)

r2 = save('pool', '10.0.0.9:80', '')
out['edit_status'] = r2.status_code
out['a_after_edit'] = svcs(a)
out['b_after_edit'] = svcs(b)
out['b_servers'] = server(b, 'pool')

r3 = save('renamed', '10.0.0.9:80', '', original='pool')
out['rename_status'] = r3.status_code
out['a_after_rename'] = svcs(a)
out['b_after_rename'] = svcs(b)
print('@@' + json.dumps(out))
'''


def _run(tmp_path):
    script = ('ROOT = %r\n' % ROOT) + PROBE
    path = str(tmp_path / 'probe_cf.py')
    with open(path, 'w') as fh:
        fh.write(script)
    out = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    return json.loads(line[0][2:])


def test_editing_a_service_writes_to_the_file_it_lives_in(tmp_path):
    res = _run(tmp_path)
    assert res['created_in_b'] == ['pool'], res
    assert res['created_in_a'] == [], 'the chosen config file was ignored on create'
    assert res['edit_status'] == 200, res
    assert res['a_after_edit'] == [], \
        'the edit was duplicated into the first config file'
    assert res['b_after_edit'] == ['pool']
    assert res['b_servers'] == ['http://10.0.0.9:80'], \
        'the edit did not reach the file the service lives in'


def test_renaming_a_service_in_a_second_file_works(tmp_path):
    res = _run(tmp_path)
    assert res['rename_status'] == 200, res
    assert res['b_after_rename'] == ['renamed'], res
    assert res['a_after_rename'] == []
