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
open(a, 'w').write(
    "http:\n  routers:\n    app:\n      rule: Host(`app.example.com`)\n      service: app\n"
    "  services:\n    app:\n      loadBalancer:\n        servers: [{url: 'http://10.0.0.1:80'}]\n")
open(b, 'w').write(
    "http:\n  routers:\n    app-lan:\n      rule: Host(`app.lan`)\n      service: app\n")
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
mode = sys.argv[1]
extra = {}
if mode == 'same-name':
    open(b, 'w').write(
        "http:\n  routers:\n    app:\n      rule: Host(`app.lan`)\n      service: app\n")
if mode == 'lazy':
    reads = []
    real = A.load_config
    A.load_config = lambda p=None: (reads.append(os.path.basename(p or '')), real(p))[1]
    cfg = C.load_config(a)
    cfg['http']['routers']['app-alt'] = {'rule': 'Host(`alt.example.com`)', 'service': 'app'}
    others = A._other_configs(current=a, cache={})
    shared = A._service_shared(cfg, 'app', 'app', others)
    first = list(reads)
    A._service_shared({}, 'app', 'app', others)
    A._service_shared({}, 'app', 'app', others)
    print('@@' + json.dumps({'shared': shared, 'first': first, 'reads': reads}))
    sys.exit(0)
if mode == 'agent-reenable':
    store = {'a.yml': C.load_config(a), 'b.yml': C.load_config(b)}
    A._agent_by_id = lambda i: {'id': i, 'name': 'x', 'url': 'http://x'}
    A._agent_load_configs = lambda ag: json.loads(json.dumps(store))
    A._agent_write_config = lambda ag, f, cfg: store.__setitem__(f, json.loads(json.dumps(cfg)))
    c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': False, 'agent_id': 'ag1'})
    store['a.yml']['http']['services']['app']['loadBalancer']['servers'] = [{'url': 'http://10.0.0.9:80'}]
    r = c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': True, 'agent_id': 'ag1'})
    http = store['a.yml'].get('http') or {}
elif mode == 'agent-disable':
    store = {'a.yml': C.load_config(a), 'b.yml': C.load_config(b)}
    A._agent_by_id = lambda i: {'id': i, 'name': 'x', 'url': 'http://x'}
    A._agent_load_configs = lambda ag: json.loads(json.dumps(store))
    A._agent_write_config = lambda ag, f, cfg: store.__setitem__(f, cfg)
    r = c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': False, 'agent_id': 'ag1'})
    http = store['a.yml'].get('http') or {}
else:
    if mode == 'delete':
        r = c.post('/delete/app', data={'csrf_token': 't', 'configFile': 'a.yml'}, headers=H)
    elif mode == 'edit':
        open(a, 'a').write("    other:\n      loadBalancer:\n        servers: [{url: 'http://10.0.0.2:80'}]\n")
        r = c.post('/save', headers=H, data={
            'csrf_token': 't', 'isEdit': 'true', 'originalId': 'a.yml::app', 'configFile': 'a.yml',
            'serviceName': 'app', 'subdomain': 'app.example.com', 'protocol': 'http', 'serviceRef': 'other',
            'scheme': 'http', 'targetIp': '10.0.0.1', 'targetPort': '80'})
    elif mode == 'reenable':
        c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': False})
        edited = C.load_config(a)
        edited['http']['services']['app']['loadBalancer']['servers'] = [{'url': 'http://10.0.0.9:80'}]
        C.save_config(edited, a)
        r = c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': True})
    else:
        r = c.post('/api/routes/a.yml::app/toggle', headers=H, json={'enable': False})
    http = C.load_config(a).get('http') or {}
print('@@' + json.dumps({'status': r.status_code,
                         'routers': sorted((http.get('routers') or {})),
                         'services': sorted((http.get('services') or {})),
                         'urls': [sv.get('url') for sv in ((((http.get('services') or {}).get('app') or {})
                                  .get('loadBalancer') or {}).get('servers') or [])]}))
'''


def _run(tmp_path, mode):
    script = ('ROOT = %r\n' % ROOT) + PROBE
    path = str(tmp_path / 'probe_shared.py')
    with open(path, 'w') as fh:
        fh.write(script)
    res = subprocess.run([sys.executable, path, mode], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in res.stdout.splitlines() if ln.startswith('@@')]
    assert line, res.stdout + res.stderr
    return json.loads(line[0][2:])


def test_delete_keeps_a_service_used_by_a_router_in_another_file(tmp_path):
    res = _run(tmp_path, 'delete')
    assert res['status'] == 200, res
    assert res['routers'] == [], res
    assert res['services'] == ['app'], 'app-lan in b.yml still uses it: %r' % res


def test_disable_keeps_a_service_used_by_a_router_in_another_file(tmp_path):
    res = _run(tmp_path, 'disable')
    assert res['status'] == 200, res
    assert res['routers'] == [], res
    assert res['services'] == ['app'], 'app-lan in b.yml still uses it: %r' % res


def test_agent_disable_keeps_a_service_used_by_a_router_in_another_file(tmp_path):
    res = _run(tmp_path, 'agent-disable')
    assert res['status'] == 200, res
    assert res['routers'] == [], res
    assert res['services'] == ['app'], 'app-lan in b.yml still uses it: %r' % res


def test_switching_a_route_to_another_service_keeps_one_another_file_uses(tmp_path):
    res = _run(tmp_path, 'edit')
    assert res['status'] == 200, res
    assert 'app' in res['services'], 'app-lan in b.yml still uses it: %r' % res


def test_reenable_keeps_edits_made_to_a_shared_service_while_disabled(tmp_path):
    res = _run(tmp_path, 'reenable')
    assert res['status'] == 200, res
    assert res['routers'] == ['app'], res
    assert res['urls'] == ['http://10.0.0.9:80'], 'the edit was overwritten by the snapshot: %r' % res


def test_agent_reenable_keeps_edits_made_to_a_shared_service_while_disabled(tmp_path):
    res = _run(tmp_path, 'agent-reenable')
    assert res['status'] == 200, res
    assert res['routers'] == ['app'], res
    assert res['urls'] == ['http://10.0.0.9:80'], 'the edit was overwritten by the snapshot: %r' % res


def test_a_router_with_the_same_name_in_another_file_still_counts(tmp_path):
    res = _run(tmp_path, 'same-name')
    assert res['status'] == 200, res
    assert res['routers'] == [], res
    assert res['services'] == ['app'], 'app in b.yml still uses it: %r' % res


def test_other_files_are_read_only_when_needed_and_only_once(tmp_path):
    res = _run(tmp_path, 'lazy')
    assert res['shared'] is True, res
    assert res['first'] == [], 'shared within a.yml, b.yml should not be read: %r' % res
    assert res['reads'] == ['b.yml'], 'b.yml should be read once and reused: %r' % res
