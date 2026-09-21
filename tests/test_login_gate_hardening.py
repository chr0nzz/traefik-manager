"""The open redirect in next, the forced-password-change gate, and reporting two-factor that
is switched on but cannot be used."""

import pytest

import app as tm
import core.settings as settings_mod


# --- open redirect -------------------------------------------------------------------------

@pytest.mark.parametrize('probe', [
    '/\t/evil.example/pwned',
    '/\n/evil.example/pwned',
    '/\r/evil.example/pwned',
    '/\x00/evil.example/pwned',
    '//evil.example/pwned',
    '/\\evil.example',
])
def test_next_cannot_be_talked_into_leaving_the_site(probe):
    with tm.app.test_request_context('/login'):
        landed = tm._safe_next(probe)
    assert not landed.replace('\\', '/').startswith('//'), \
        f'{probe!r} produced {landed!r}, which leaves the site'


def test_an_ordinary_next_still_works():
    with tm.app.test_request_context('/login'):
        assert tm._safe_next('/settings') == '/settings'


# --- the forced password change is not skipped by a made-up API key ------------------------

def test_a_bogus_api_key_does_not_skip_the_forced_password_change(client):
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=True,
                               password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
                               setup_complete=True, must_change_password=True)
    r = client.get('/api/settings', headers={'X-Api-Key': 'not-a-real-key'})
    assert r.status_code == 403, \
        'presence of the header used to be enough to skip the gate, whatever the value was'


# --- two-factor that cannot be read says so ------------------------------------------------

def test_otp_status_admits_when_the_secret_cannot_be_read(client, monkeypatch):
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=True,
                               password_hash=s['password_hash'], visible_tabs=s['visible_tabs'],
                               setup_complete=True, otp_enabled=True, otp_secret='')
    body = client.get('/api/auth/otp/status').get_json()
    assert body['otp_enabled'] is True
    assert body['otp_secret_unreadable'] is True, \
        'reporting otp_enabled alone hides that the second factor cannot actually be asked for'
