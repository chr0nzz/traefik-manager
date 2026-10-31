import os
import re
import subprocess
import sys
import tempfile

import bcrypt

import app as tm
from tests.conftest import PASSWORD_HASH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_stale_read_does_not_replace_a_password_another_worker_saved(monkeypatch, caplog):
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    monkeypatch.setattr(tm, 'load_settings', lambda *a, **k: {'password_hash': ''})
    tm._ensure_password()
    assert tm._settings.load_settings()['password_hash'] == PASSWORD_HASH
    assert 'AUTO-GENERATED PASSWORD' not in caplog.text


def test_workers_starting_together_generate_one_password():
    d = tempfile.mkdtemp(prefix='tm-autopw-')
    env = {k: v for k, v in os.environ.items() if k != 'ADMIN_PASSWORD'}
    env.update({
        'SETTINGS_PATH': os.path.join(d, 'manager.yml'),
        'BACKUP_DIR': os.path.join(d, 'backups'),
        'CONFIG_PATHS': os.path.join(d, 'dynamic.yml'),
        'TRAEFIK_API_URL': 'http://traefik.invalid:8080',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    with open(env['CONFIG_PATHS'], 'w') as fh:
        fh.write('http:\n  routers: {}\n')
    probe = 'import sys; sys.path.insert(0, %r); import app' % ROOT
    procs = [
        subprocess.Popen([sys.executable, '-c', probe], env=env, cwd=d,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(4)
    ]
    output = ''.join(p.communicate(timeout=120)[0] for p in procs)
    assert all(p.returncode == 0 for p in procs), output
    printed = re.findall(r'Password: (\S+)', output)
    assert len(printed) == 1, output
    with open(env['SETTINGS_PATH']) as fh:
        stored = re.search(r"password_hash: '?([^'\s]+)", fh.read()).group(1)
    assert bcrypt.checkpw(printed[0].encode(), stored.encode())
