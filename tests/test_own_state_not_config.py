import os

import pytest

from core import env as env_mod


@pytest.fixture
def shared(tmp_path):
    state = tmp_path / 'config'
    state.mkdir()
    for name in ('manager.yml', 'notifications.yml', 'agents.yml', 'dashboard.yml', 'templates.yml'):
        (state / name).write_text('x: 1\n')
    (state / 'routes.yml').write_text('http:\n  routers: {}\n')
    return state


def _scan(state, backup=None):
    return [os.path.basename(p) for p in
            env_mod.scan_config_dir(str(state), settings_path=str(state / 'manager.yml'),
                                    backup_dir=str(backup) if backup else str(state / 'backups'))]


def test_the_settings_file_is_not_traefik_config(shared):
    names = _scan(shared)
    assert 'manager.yml' not in names, \
        'reading our own settings as Traefik config is what put them in the git backup'
    assert 'routes.yml' in names, 'real config must still be found'


def test_none_of_our_own_state_is_treated_as_config(shared):
    names = set(_scan(shared))
    for own in ('manager.yml', 'notifications.yml', 'agents.yml', 'dashboard.yml', 'templates.yml'):
        assert own not in names, f'{own} is Traefik Manager state, not Traefik config'


def test_the_backup_directory_is_not_scanned(shared):
    clone = shared / 'backups' / 'git-repo' / 'dynamic'
    clone.mkdir(parents=True)
    (clone / 'copied.yml').write_text('http:\n  routers: {}\n')
    assert 'copied.yml' not in _scan(shared), \
        'the backup clone would be re-read as live config and pushed again'


def test_a_separate_config_directory_is_untouched(tmp_path):
    state = tmp_path / 'state'
    traefik = tmp_path / 'traefik'
    state.mkdir()
    traefik.mkdir()
    (state / 'manager.yml').write_text('x: 1\n')
    (traefik / 'routes.yml').write_text('http:\n  routers: {}\n')
    found = env_mod.scan_config_dir(str(traefik), settings_path=str(state / 'manager.yml'),
                                    backup_dir=str(tmp_path / 'backups'))
    assert [os.path.basename(p) for p in found] == ['routes.yml']


def test_a_users_own_file_named_like_ours_elsewhere_is_still_config(tmp_path):
    state = tmp_path / 'state'
    traefik = tmp_path / 'traefik'
    state.mkdir()
    traefik.mkdir()
    (state / 'manager.yml').write_text('x: 1\n')
    (traefik / 'dashboard.yml').write_text('http:\n  routers: {}\n')
    found = env_mod.scan_config_dir(str(traefik), settings_path=str(state / 'manager.yml'),
                                    backup_dir=str(tmp_path / 'backups'))
    assert [os.path.basename(p) for p in found] == ['dashboard.yml'], \
        'only our own directory is excluded, not every file that shares a name'


def test_is_own_state_knows_what_belongs_to_us(shared):
    settings = str(shared / 'manager.yml')
    backup   = str(shared / 'backups')
    assert env_mod.is_own_state(settings, settings, backup) is True
    assert env_mod.is_own_state(str(shared / 'backups' / 'git-repo' / 'x.yml'), settings, backup) is True
    assert env_mod.is_own_state(str(shared / 'routes.yml'), settings, backup) is False


def test_the_live_scan_uses_the_same_rule():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'core', 'env.py'), encoding='utf-8').read()
    assert 'CONFIG_PATHS = scan_config_dir(_config_dir)' in src, \
        'the glob must go through the same exclusion the tests cover'


def test_the_push_refuses_our_own_files_even_if_listed():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'core', 'git.py'), encoding='utf-8') as fh:
        src = fh.read()
    body = src[src.index('for p in env.CONFIG_PATHS:'):]
    assert 'env.is_own_state(p)' in body, \
        'a hand written CONFIG_PATHS could still list manager.yml, so the push needs its own guard'
    assert body.index('is_own_state') < body.index('shutil.copy2'), 'the guard must come before the copy'
