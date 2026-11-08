import os

OIDC_ENV_VARS = (
    'OIDC_ENABLED', 'OIDC_PROVIDER_URL', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET',
    'OIDC_DISPLAY_NAME', 'OIDC_ALLOWED_EMAILS', 'OIDC_ALLOWED_GROUPS',
    'OIDC_GROUPS_CLAIM', 'OIDC_ALLOW_ANY_AUTHENTICATED', 'OIDC_AUTO_LOGIN',
)


def _boot(monkeypatch, tmp_path, body, env_overrides=None):
    import core.crypto as crypto_mod
    import core.env as env_mod
    import core.settings as settings_mod
    cfg = tmp_path / 'cfg'
    cfg.mkdir(exist_ok=True)
    monkeypatch.setattr(env_mod, 'SETTINGS_PATH', str(cfg / 'manager.yml'))
    monkeypatch.setattr(env_mod, 'OTP_KEY_PATH', str(cfg / '.otp_key'))
    monkeypatch.setattr(env_mod, 'AGENTS_PATH', str(cfg / 'agents.yml'))
    for name in OIDC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in (env_overrides or {}).items():
        monkeypatch.setenv(name, value)
    if body is not None:
        with open(env_mod.SETTINGS_PATH, 'w') as fh:
            fh.write(body)
    crypto_mod.clear_plaintext_seen()
    return env_mod, crypto_mod, settings_mod


BASE = """
domains: [example.com]
auth_enabled: true
password_hash: '$2b$12$abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUVWXYZ0123'
setup_complete: true
oidc_enabled: true
oidc_client_id: tm
"""


def test_plaintext_secret_is_read_not_dropped(monkeypatch, tmp_path):
    _, _, settings = _boot(monkeypatch, tmp_path,
                           BASE + "oidc_client_secret: hand-written-secret\n")
    assert settings.load_settings()['oidc_client_secret'] == 'hand-written-secret'


def test_plaintext_read_is_flagged(monkeypatch, tmp_path):
    _, crypto, settings = _boot(monkeypatch, tmp_path,
                                BASE + "oidc_client_secret: hand-written-secret\n")
    crypto.clear_plaintext_seen()
    settings.load_settings()
    assert crypto.plaintext_secrets_seen() is True


def test_encrypted_secret_is_not_flagged(monkeypatch, tmp_path):
    env, crypto, settings = _boot(monkeypatch, tmp_path, BASE)
    token = crypto.encrypt_secret('hand-written-secret')
    with open(env.SETTINGS_PATH, 'a') as f:
        f.write("oidc_client_secret: %s\n" % token)
    crypto.clear_plaintext_seen()
    assert settings.load_settings()['oidc_client_secret'] == 'hand-written-secret'
    assert crypto.plaintext_secrets_seen() is False


def test_undecryptable_secret_is_not_treated_as_plaintext(monkeypatch, tmp_path):
    env, crypto, settings = _boot(monkeypatch, tmp_path, BASE)
    token = crypto.encrypt_secret('hand-written-secret')
    os.unlink(env.OTP_KEY_PATH)
    with open(env.SETTINGS_PATH, 'a') as f:
        f.write("oidc_client_secret: %s\n" % token)
    crypto.clear_plaintext_seen()
    assert settings.load_settings()['oidc_client_secret'] == ''
    assert crypto.plaintext_secrets_seen() is False


def test_resave_encrypts_plaintext_and_keeps_other_fields(monkeypatch, tmp_path):
    env, crypto, settings = _boot(monkeypatch, tmp_path,
                                  BASE + "oidc_client_secret: hand-written-secret\n")
    cur = settings.load_settings()
    settings.save_settings(
        domains=cur['domains'], cert_resolver=cur['cert_resolver'],
        traefik_api_url=cur['traefik_api_url'], auth_enabled=cur['auth_enabled'],
        password_hash=cur['password_hash'], visible_tabs=cur['visible_tabs'])
    raw = open(env.SETTINGS_PATH).read()
    assert 'hand-written-secret' not in raw
    assert 'oidc_client_secret: gAAAAA' in raw
    again = settings.load_settings()
    assert again['oidc_client_secret'] == 'hand-written-secret'
    assert again['oidc_enabled'] is True
    assert again['oidc_client_id'] == 'tm'
    assert again['password_hash'] == cur['password_hash']


def test_oidc_env_vars_apply_when_absent_from_file(monkeypatch, tmp_path):
    _, _, settings = _boot(monkeypatch, tmp_path, BASE.replace('oidc_enabled: true\noidc_client_id: tm\n', ''),
                           {'OIDC_ENABLED': 'true', 'OIDC_PROVIDER_URL': 'https://id.example.com',
                            'OIDC_CLIENT_ID': 'from-env', 'OIDC_CLIENT_SECRET': 'env-secret',
                            'OIDC_DISPLAY_NAME': 'Authentik', 'OIDC_ALLOWED_EMAILS': 'a@b.c',
                            'OIDC_ALLOWED_GROUPS': 'admins', 'OIDC_GROUPS_CLAIM': 'roles',
                            'OIDC_ALLOW_ANY_AUTHENTICATED': 'yes', 'OIDC_AUTO_LOGIN': '1'})
    s = settings.load_settings()
    assert s['oidc_enabled'] is True
    assert s['oidc_provider_url'] == 'https://id.example.com'
    assert s['oidc_client_id'] == 'from-env'
    assert s['oidc_client_secret'] == 'env-secret'
    assert s['oidc_display_name'] == 'Authentik'
    assert s['oidc_allowed_emails'] == 'a@b.c'
    assert s['oidc_allowed_groups'] == 'admins'
    assert s['oidc_groups_claim'] == 'roles'
    assert s['oidc_allow_any_authenticated'] is True
    assert s['oidc_auto_login'] is True


def test_file_wins_over_env(monkeypatch, tmp_path):
    _, _, settings = _boot(monkeypatch, tmp_path, BASE, {'OIDC_CLIENT_ID': 'from-env'})
    assert settings.load_settings()['oidc_client_id'] == 'tm'


def test_env_bool_words(monkeypatch, tmp_path):
    _, _, settings = _boot(monkeypatch, tmp_path, BASE)
    for word in ('1', 'true', 'TRUE', 'yes', 'on'):
        monkeypatch.setenv('TM_PROBE', word)
        assert settings._env_bool('TM_PROBE', False) is True, word
    for word in ('0', 'false', 'FALSE', 'no', 'off'):
        monkeypatch.setenv('TM_PROBE', word)
        assert settings._env_bool('TM_PROBE', True) is False, word
    monkeypatch.delenv('TM_PROBE', raising=False)
    assert settings._env_bool('TM_PROBE', True) is True
    monkeypatch.setenv('TM_PROBE', 'maybe')
    assert settings._env_bool('TM_PROBE', True) is True


STARTUP_PROBE = r'''
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
open(os.environ['SETTINGS_PATH'], 'w').write(BODY)
sys.path.insert(0, ROOT)
import app
raw = open(os.environ['SETTINGS_PATH']).read()
print('@@' + json.dumps({
    'plain_on_disk': 'hand-written-secret' in raw,
    'encrypted': 'oidc_client_secret: gAAAAA' in raw,
    'secret': app.load_settings()['oidc_client_secret'],
    'notices': [n['msg'] for n in app._noti._notifications if 'plain text' in n['msg']],
    'categories': [n['category'] for n in app._noti._notifications if 'plain text' in n['msg']],
}))
'''


def _startup(tmp_path, body):
    import json
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = ("BODY = %r\nROOT = %r\n" % (body, root)) + STARTUP_PROBE
    path = str(tmp_path / 'probe.py')
    with open(path, 'w') as f:
        f.write(script)
    out = subprocess.run([os.sys.executable, path], capture_output=True, text=True, cwd=root)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    return json.loads(line[0][2:])


def test_startup_reencrypts_plaintext_and_notifies(tmp_path):
    res = _startup(tmp_path, BASE + "oidc_client_secret: hand-written-secret\n")
    assert res['plain_on_disk'] is False
    assert res['encrypted'] is True
    assert res['secret'] == 'hand-written-secret'
    assert len(res['notices']) == 1
    assert res['categories'] == ['security']


def test_startup_is_quiet_when_nothing_is_plaintext(tmp_path):
    res = _startup(tmp_path, BASE)
    assert res['notices'] == []


UNWRITABLE_PROBE = r'''
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
open(os.environ['SETTINGS_PATH'], 'w').write(BODY)
sys.path.insert(0, ROOT)
import app
from core import crypto


def _read():
    return crypto.decrypt_secret('hand-written-secret')


def _boom(_):
    raise OSError(13, 'Read-only file system')


crashed = False
try:
    handled = app._reencrypt_file('manager.yml', _read, _boom)
except Exception:
    crashed, handled = True, None
print('@@' + json.dumps({
    'crashed': crashed,
    'handled': handled,
    'plaintext_read': _read(),
}))
'''


def test_a_rewrite_that_fails_does_not_stop_startup(tmp_path):
    import json
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = ("BODY = %r\nROOT = %r\n" % (BASE, root)) + UNWRITABLE_PROBE
    path = str(tmp_path / 'probe_ro.py')
    with open(path, 'w') as f:
        f.write(script)
    out = subprocess.run([os.sys.executable, path], capture_output=True, text=True, cwd=root)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    res = json.loads(line[0][2:])
    assert res['crashed'] is False
    assert res['handled'] is False
    assert res['plaintext_read'] == 'hand-written-secret'


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_every_oidc_setting_has_a_variable():
    source = _read('core', 'settings.py')
    start = source.index("'oidc_enabled':")
    end = source.index("'default_theme':")
    keys = [ln.split(':')[0].strip().strip("'")
            for ln in source[start:end].splitlines() if ln.strip().startswith("'oidc_")]
    assert len(keys) == len(OIDC_ENV_VARS)
    for key in keys:
        assert key.upper() in source[start:end], f'{key} has no environment variable'


def test_the_docs_list_every_oidc_variable():
    docs = _read('docs', 'env-vars.md')
    for name in OIDC_ENV_VARS:
        assert '`%s`' % name in docs, f'{name} is undocumented'


def test_the_docs_explain_hand_written_secrets():
    assert 'Hand-written secrets' in _read('docs', 'manager-yml.md')


AGENTS_PROBE = r'''
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
os.environ['SETTINGS_PATH'] = os.path.join(d, 'manager.yml')
os.environ['BACKUP_DIR'] = os.path.join(d, 'backups')
os.environ['CONFIG_PATHS'] = os.path.join(d, 'dynamic.yml')
open(os.environ['CONFIG_PATHS'], 'w').write('http:\n  routers: {}\n')
open(os.environ['SETTINGS_PATH'], 'w').write(BODY)
open(os.path.join(d, 'agents.yml'), 'w').write(
    'agents:\n'
    '- id: a1\n'
    '  name: edge\n'
    '  url: https://edge.example.com\n'
    '  api_key: hand-written-agent-key\n')
sys.path.insert(0, ROOT)
import app
raw = open(os.path.join(d, 'agents.yml')).read()
print('@@' + json.dumps({
    'plain_on_disk': 'hand-written-agent-key' in raw,
    'encrypted': 'gAAAAA' in raw,
    'key': [a['api_key'] for a in app._ag.load_agents()],
    'notices': [n['msg'] for n in app._noti._notifications if 'plain text' in n['msg']],
}))
'''


def test_startup_reencrypts_agents_file(tmp_path):
    import json
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = ("BODY = %r\nROOT = %r\n" % (BASE, root)) + AGENTS_PROBE
    path = str(tmp_path / 'probe_ag.py')
    with open(path, 'w') as f:
        f.write(script)
    out = subprocess.run([os.sys.executable, path], capture_output=True, text=True, cwd=root)
    line = [ln for ln in out.stdout.splitlines() if ln.startswith('@@')]
    assert line, out.stdout + out.stderr
    res = json.loads(line[0][2:])
    assert res['plain_on_disk'] is False
    assert res['encrypted'] is True
    assert res['key'] == ['hand-written-agent-key']
    assert len(res['notices']) == 1
    assert 'agents.yml' in res['notices'][0]
