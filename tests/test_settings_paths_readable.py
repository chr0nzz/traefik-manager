import importlib
import os

import pytest

pytestmark = pytest.mark.usefixtures('restore_core_env')


def _boot(monkeypatch, tmp_path, env_overrides=None):
    dyn = str(tmp_path / 'dyn' / 'dynamic.yml')
    os.makedirs(os.path.dirname(dyn), exist_ok=True)
    os.makedirs(str(tmp_path / 'cfg'), exist_ok=True)
    monkeypatch.setenv('CONFIG_PATH', dyn)
    monkeypatch.setenv('SETTINGS_PATH', str(tmp_path / 'cfg' / 'manager.yml'))
    monkeypatch.setenv('BACKUP_DIR', str(tmp_path / 'backups'))
    for k in ('ACCESS_LOG_PATH', 'ACME_JSON_PATH', 'STATIC_CONFIG_PATH', 'PLUGINS_DIR'):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env_overrides or {}).items():
        monkeypatch.setenv(k, v)
    import core.env as env_mod
    importlib.reload(env_mod)
    import core.config as config_mod
    importlib.reload(config_mod)
    return env_mod, config_mod


def test_access_log_from_settings_is_readable(monkeypatch, tmp_path):
    log = str(tmp_path / 'var' / 'log' / 'traefik' / 'access.log')
    os.makedirs(os.path.dirname(log), exist_ok=True)
    open(log, 'w').write('{}\n')

    env_mod, config_mod = _boot(monkeypatch, tmp_path)
    assert config_mod.readable_config_path(log) == '', \
        'unregistered path should start out blocked'

    env_mod.set_settings_paths('log', log)
    assert config_mod.readable_config_path(log) == os.path.realpath(log), (
        'a path set only in manager.yml must be readable once registered; '
        'allowed=%r' % (env_mod.READ_PATHS,))


def test_env_only_still_works(monkeypatch, tmp_path):
    log = str(tmp_path / 'elsewhere' / 'access.log')
    os.makedirs(os.path.dirname(log), exist_ok=True)
    open(log, 'w').write('{}\n')
    _, config_mod = _boot(monkeypatch, tmp_path, {'ACCESS_LOG_PATH': log})
    assert config_mod.readable_config_path(log) == os.path.realpath(log)


def test_comma_separated_paths_all_register(monkeypatch, tmp_path):
    a = str(tmp_path / 'acme1' / 'acme.json')
    b = str(tmp_path / 'acme2' / 'acme.json')
    for f in (a, b):
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, 'w').write('{}')
    env_mod, config_mod = _boot(monkeypatch, tmp_path)
    env_mod.set_settings_paths('acme', a + ',' + b)
    assert config_mod.readable_config_path(a) == os.path.realpath(a)
    assert config_mod.readable_config_path(b) == os.path.realpath(b)


def test_unrelated_paths_stay_blocked(monkeypatch, tmp_path):
    env_mod, config_mod = _boot(monkeypatch, tmp_path)
    env_mod.set_settings_paths('log', str(tmp_path / 'ok' / 'access.log'))
    assert config_mod.readable_config_path('/etc/shadow') == ''
    assert config_mod.readable_config_path('/etc/passwd') == ''
