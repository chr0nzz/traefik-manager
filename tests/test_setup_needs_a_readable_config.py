"""The setup wizard hands an admin password to whoever reaches it first, so it may only run
when the install is provably new. A manager.yml that exists but cannot be read or parsed must
never be mistaken for a first run."""

import os

import pytest

import core.settings as settings_mod
from conftest import SETTINGS_PATH

GOOD = SETTINGS_PATH.read_text()

CORRUPTIONS = {
    'yaml syntax error':  "domains:\n  - example.com\n  cert_resolver: [unclosed\n",
    'a top-level list':   "- example.com\n- letsencrypt\n",
    'a bare scalar':      "just a string, not a mapping\n",
    'binary junk':        "\x00\x01\x02 not yaml at all\n",
}


@pytest.fixture(autouse=True)
def _restore_settings_file():
    yield
    SETTINGS_PATH.write_text(GOOD)
    os.chmod(SETTINGS_PATH, 0o600)
    settings_mod.load_settings(fresh=True)


def _reload(text=None, mode=None):
    if text is not None:
        SETTINGS_PATH.write_text(text)
    if mode is not None:
        os.chmod(SETTINGS_PATH, mode)
    settings_mod.load_settings(fresh=True)


@pytest.mark.parametrize('label', list(CORRUPTIONS))
def test_a_corrupt_settings_file_is_not_a_fresh_install(anon_client, label):
    _reload(CORRUPTIONS[label])
    assert settings_mod.settings_unreadable(), f'{label} should be reported as unreadable'
    r = anon_client.get('/setup')
    assert r.status_code == 503, \
        f'{label} left the anonymous setup wizard reachable (status {r.status_code})'


@pytest.mark.parametrize('label', list(CORRUPTIONS))
def test_a_corrupt_settings_file_cannot_set_a_password(anon_client, label):
    _reload(CORRUPTIONS[label])
    r = anon_client.post('/setup', data={'password': 'attacker-chosen-password',
                                         'confirm_password': 'attacker-chosen-password'})
    assert r.status_code == 503, f'{label} accepted an anonymous password POST'
    with anon_client.session_transaction() as sess:
        assert not sess.get('authenticated'), f'{label} handed out an authenticated session'


def test_an_unreadable_settings_file_is_not_a_fresh_install(anon_client):
    if os.geteuid() == 0:
        pytest.skip('root can read a 0000 file, so this mode cannot be tested as root')
    _reload(GOOD, mode=0o000)
    assert settings_mod.settings_unreadable(), 'an unreadable file should be reported as such'
    assert anon_client.get('/setup').status_code == 503


def test_a_healthy_settings_file_still_works(anon_client):
    _reload(GOOD)
    assert settings_mod.settings_unreadable() == '', 'a good file must not be flagged'
    s = settings_mod.load_settings(fresh=True)
    assert s['password_hash'], 'the real password hash should still load'
    r = anon_client.get('/setup')
    assert r.status_code != 503, 'a readable file must not trip the guard'


def test_a_missing_settings_file_is_still_a_fresh_install(anon_client):
    SETTINGS_PATH.unlink()
    try:
        settings_mod.load_settings(fresh=True)
        assert settings_mod.settings_unreadable() == '', \
            'a genuinely absent file is a first run, not a failure'
    finally:
        SETTINGS_PATH.write_text(GOOD)
        settings_mod.load_settings(fresh=True)
