
import os
import stat


import core.agents_store as agents_store
import core.config as config_mod
import core.settings as settings_mod
from conftest import SETTINGS_PATH


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_saving_settings_does_not_leave_the_file_world_readable():
    os.chmod(SETTINGS_PATH, 0o644)
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
                               password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
                               setup_complete=True)
    assert not _mode(SETTINGS_PATH) & 0o077, \
        f'manager.yml holds the password hash and encrypted secrets, mode is {_mode(SETTINGS_PATH):o}'


def test_saving_agents_does_not_leave_the_file_world_readable():
    agents_store.save_agents_file([])
    from core import env
    assert not _mode(env.AGENTS_PATH) & 0o077, \
        f'agents.yml holds agent API keys, mode is {_mode(env.AGENTS_PATH):o}'


def test_a_stricter_mode_an_operator_chose_is_kept():
    os.chmod(SETTINGS_PATH, 0o400)
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=s['auth_enabled'],
                               password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
                               setup_complete=True)
    assert _mode(SETTINGS_PATH) == 0o400, 'a save must not widen a mode the operator narrowed'
    os.chmod(SETTINGS_PATH, 0o600)


def test_an_already_wide_file_is_narrowed_at_startup(tmp_path):
    wide = tmp_path / 'manager.yml'
    wide.write_text('domains: []\n')
    os.chmod(wide, 0o644)
    config_mod.tighten_secret_files(str(wide))
    assert not _mode(str(wide)) & 0o077, 'an upgraded install should be narrowed, not left open'


