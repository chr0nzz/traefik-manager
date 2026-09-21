import importlib
import os

import pytest

pytestmark = pytest.mark.usefixtures('restore_core_env')


def _reload(monkeypatch, tmp_path, static_path, dynamic_path=None):
    dynamic_path = dynamic_path or str(tmp_path / 'dyn' / 'dynamic.yml')
    os.makedirs(os.path.dirname(dynamic_path), exist_ok=True)
    monkeypatch.setenv('CONFIG_PATH', dynamic_path)
    os.makedirs(str(tmp_path / 'cfg'), exist_ok=True)
    monkeypatch.setenv('SETTINGS_PATH', str(tmp_path / 'cfg' / 'manager.yml'))
    monkeypatch.setenv('BACKUP_DIR', str(tmp_path / 'backups'))
    monkeypatch.setenv('STATIC_CONFIG_PATH', static_path)
    import core.env as env_mod
    importlib.reload(env_mod)
    import core.config as config_mod
    importlib.reload(config_mod)
    return env_mod, config_mod


def test_static_config_outside_the_dynamic_dir_is_writable(monkeypatch, tmp_path):
    static = str(tmp_path / 'etc' / 'traefik' / 'traefik.yml')
    os.makedirs(os.path.dirname(static), exist_ok=True)
    open(static, 'w').write('api: {}\n')

    env_mod, config_mod = _reload(monkeypatch, tmp_path, static)
    assert config_mod.safe_file_path(static) == os.path.realpath(static), (
        'a native install keeps traefik.yml outside the dynamic config dir, and it must '
        'still be writable: allowed=%r' % (env_mod.ALLOWED_FILE_PREFIXES,))


def test_registering_a_settings_path_opens_it(monkeypatch, tmp_path):
    static = str(tmp_path / 'elsewhere' / 'traefik.yml')
    os.makedirs(os.path.dirname(static), exist_ok=True)
    open(static, 'w').write('api: {}\n')

    env_mod, config_mod = _reload(monkeypatch, tmp_path, '')
    assert config_mod.safe_file_path(static) == '', 'unregistered path should be blocked'

    env_mod.set_settings_paths('static', static)
    importlib.reload(config_mod)
    assert config_mod.safe_file_path(static) == os.path.realpath(static)


def test_an_unrelated_path_is_still_blocked(monkeypatch, tmp_path):
    static = str(tmp_path / 'etc' / 'traefik' / 'traefik.yml')
    os.makedirs(os.path.dirname(static), exist_ok=True)
    _reload(monkeypatch, tmp_path, static)
    import core.config as config_mod
    assert config_mod.safe_file_path('/etc/shadow') == ''
    assert config_mod.safe_file_path('/etc/passwd') == ''


def test_the_app_directory_is_not_writable_as_a_whole(monkeypatch, tmp_path):
    static = str(tmp_path / 'etc' / 'traefik' / 'traefik.yml')
    os.makedirs(os.path.dirname(static), exist_ok=True)
    env_mod, config_mod = _reload(monkeypatch, tmp_path, static)
    assert '/app/' not in env_mod.ALLOWED_FILE_PREFIXES
    assert config_mod.safe_file_path('/app/gunicorn.conf.py') == ''
    assert config_mod.safe_file_path('/app/core/auth.py') == ''
