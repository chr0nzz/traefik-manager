import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import json, os, re, sys
import bcrypt
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
h = bcrypt.hashpw(b'TempPass123!', bcrypt.gensalt(rounds=12)).decode()
open(os.environ['SETTINGS_PATH'], 'w').write(BODY % h)
sys.path.insert(0, ROOT)
import app as A


def tok(c, path):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', c.get(path).get_data(as_text=True))
    return m.group(1) if m else ''


admin = A.app.test_client()
admin.post('/login', data={'csrf_token': tok(admin, '/login'), 'password': 'TempPass123!'})
RECOVERY(admin, tok)
after = A.load_settings()

attacker = A.app.test_client()
before_hash = after['password_hash']
r = attacker.post('/setup', data={'csrf_token': tok(attacker, '/setup'),
                                  'password': 'AttackerOwns1!', 'confirm': 'AttackerOwns1!'})
print('@@' + json.dumps({
    'reset_flag_after_recovery': after['setup_password_reset'],
    'must_change_after_recovery': after['must_change_password'],
    'setup_status': r.status_code,
    'password_taken_over': before_hash != A.load_settings()['password_hash'],
    'attacker_authenticated': attacker.get('/api/routes').status_code == 200,
}))
'''

RESET_STATE = """
domains: [example.com]
auth_enabled: true
setup_complete: true
password_hash: '%s'
must_change_password: true
setup_password_reset: true
"""

STALE_FLAG_STATE = """
domains: [example.com]
auth_enabled: true
setup_complete: true
password_hash: '%s'
must_change_password: false
setup_password_reset: true
"""


def _run(recovery_src, tmp_path, state=None):
    import json
    script = ('BODY = %r\nROOT = %r\n' % (state or RESET_STATE, ROOT)) + recovery_src + PROBE
    path = str(tmp_path / 'probe.py')
    with open(path, 'w') as fh:
        fh.write(script)
    out = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    return json.loads(line[0][2:])


FORCED_CHANGE = '''
def RECOVERY(c, tok):
    c.post('/force-change-password', data={'csrf_token': tok(c, '/force-change-password'),
           'new_password': 'MyRealPassword1!', 'confirm_password': 'MyRealPassword1!'})
'''

API_CHANGE = '''
def RECOVERY(c, tok):
    r = c.post('/api/auth/change-password',
               json={'current_password': 'TempPass123!', 'new_password': 'MyRealPassword1!',
                     'confirm_password': 'MyRealPassword1!'},
               headers={'X-CSRF-Token': tok(c, '/'), 'X-Requested-With': 'fetch'})
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True))
'''


def test_the_forced_change_closes_the_reset_window(tmp_path):
    res = _run(FORCED_CHANGE, tmp_path)
    assert res['must_change_after_recovery'] is False
    assert res['reset_flag_after_recovery'] is False, \
        'the reset window stayed open after the admin completed the flow the app sent them to'
    assert res['password_taken_over'] is False, \
        'an unauthenticated request reset the admin password'
    assert res['attacker_authenticated'] is False


def test_changing_the_password_in_settings_closes_a_stale_reset_window(tmp_path):
    res = _run(API_CHANGE, tmp_path, state=STALE_FLAG_STATE)
    assert res['reset_flag_after_recovery'] is False
    assert res['password_taken_over'] is False
    assert res['attacker_authenticated'] is False


NO_RECOVERY = '''
def RECOVERY(c, tok):
    pass
'''


NO_LOGIN_PROBE = r'''
import json, os, re, sys
import bcrypt
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
h = bcrypt.hashpw(b'TempPass123!', bcrypt.gensalt(rounds=12)).decode()
open(os.environ['SETTINGS_PATH'], 'w').write(BODY % h)
sys.path.insert(0, ROOT)
import app as A
c = A.app.test_client()
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', c.get('/setup').get_data(as_text=True))
before = A.load_settings()['password_hash']
r = c.post('/setup', data={'csrf_token': m.group(1) if m else '',
                           'password': 'Recovered1!', 'confirm': 'Recovered1!'})
print('@@' + json.dumps({
    'recovery_worked': before != A.load_settings()['password_hash'],
    'window_closed_after': A.load_settings()['setup_password_reset'] is False,
}))
'''


def test_the_window_still_works_for_an_admin_who_cannot_log_in(tmp_path):
    import json
    script = ('BODY = %r\nROOT = %r\n' % (RESET_STATE, ROOT)) + NO_LOGIN_PROBE
    path = str(tmp_path / 'probe_recover.py')
    with open(path, 'w') as fh:
        fh.write(script)
    out = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    res = json.loads(line[0][2:])
    assert res['recovery_worked'] is True, \
        'the CLI reset window must still work, or nobody can recover a lost password'
    assert res['window_closed_after'] is True, 'and it must close behind itself'


LOGIN_ONLY = '''
def RECOVERY(c, tok):
    pass
'''

LOGIN_PROBE = r'''
import json, os, re, sys
import bcrypt
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
h = bcrypt.hashpw(b'TempPass123!', bcrypt.gensalt(rounds=12)).decode()
open(os.environ['SETTINGS_PATH'], 'w').write(BODY % h)
sys.path.insert(0, ROOT)
import app as A


def tok(c, path):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', c.get(path).get_data(as_text=True))
    return m.group(1) if m else ''


admin = A.app.test_client()
admin.post('/login', data={'csrf_token': tok(admin, '/login'), 'password': 'TempPass123!'})
flag = A.load_settings()['setup_password_reset']

attacker = A.app.test_client()
before = A.load_settings()['password_hash']
attacker.post('/setup', data={'csrf_token': tok(attacker, '/setup'),
                              'password': 'AttackerOwns1!', 'confirm': 'AttackerOwns1!'})
print('@@' + json.dumps({
    'flag_after_login': flag,
    'password_taken_over': before != A.load_settings()['password_hash'],
}))
'''


def test_a_successful_login_closes_a_stale_reset_window(tmp_path):
    import json
    script = ('BODY = %r\nROOT = %r\n' % (STALE_FLAG_STATE, ROOT)) + LOGIN_PROBE
    path = str(tmp_path / 'probe_login.py')
    with open(path, 'w') as fh:
        fh.write(script)
    out = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    res = json.loads(line[0][2:])
    assert res['flag_after_login'] is False, \
        'an instance carrying the stale flag stays exploitable until someone changes a password'
    assert res['password_taken_over'] is False
