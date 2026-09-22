
import gzip
import io
import os

import pytest

import core.config as config_mod
import core.env as env
import core.geoip as geoip
import core.settings as settings_mod


def _enable_otp_without_a_readable_secret(password_hash):
    s = settings_mod.load_settings(fresh=True)
    settings_mod.save_settings(domains=s['domains'], cert_resolver=s['cert_resolver'],
                               traefik_api_url=s['traefik_api_url'], auth_enabled=True,
                               password_hash=password_hash, visible_tabs=s['visible_tabs'],
                               setup_complete=True, otp_enabled=True, otp_secret='')


def test_a_password_alone_cannot_sign_in_when_the_otp_secret_is_unreadable(anon_client, app_module):
    pw_hash = app_module._hash_password('correct-horse-battery')
    _enable_otp_without_a_readable_secret(pw_hash)
    with anon_client.session_transaction() as sess:
        sess['csrf_token'] = 'testtoken'
    r = anon_client.post('/login', data={'password': 'correct-horse-battery',
                                         'csrf_token': 'testtoken'},
                         follow_redirects=False)
    assert r.status_code == 200, 'a refused sign-in re-renders the login page'
    assert b'cannot be read' in r.data, 'the page should say why it was refused'
    with anon_client.session_transaction() as sess:
        assert not sess.get('authenticated'), \
            'the password alone must not sign in while two-factor is switched on'
        assert not sess.get('otp_pending'), 'there is no code to ask for'


def test_admin_password_still_recovers_access(anon_client, app_module, monkeypatch):
    _enable_otp_without_a_readable_secret('')
    monkeypatch.setenv('ADMIN_PASSWORD', 'recovery-password')
    with anon_client.session_transaction() as sess:
        sess['csrf_token'] = 'testtoken'
    r = anon_client.post('/login', data={'password': 'recovery-password',
                                         'csrf_token': 'testtoken'},
                         follow_redirects=False)
    assert r.status_code == 302 and '/login' not in r.headers.get('Location', ''), \
        'ADMIN_PASSWORD must still get an operator back in'


class _StreamResp:
    def __init__(self, blob, chunk=64 * 1024):
        self._blob, self._chunk, self.status_code = blob, chunk, 200

    def iter_content(self, chunk_size=None):
        size = chunk_size or self._chunk
        for i in range(0, len(self._blob), size):
            yield self._blob[i:i + size]


def _gzip_of(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as fh:
        fh.write(payload)
    return buf.getvalue()


def test_an_ordinary_database_still_unpacks(tmp_path):
    payload = b'x' * (2 * 1024 * 1024)
    dest = tmp_path / 'db.mmdb'
    written = geoip._stream_gunzip(_StreamResp(_gzip_of(payload)), str(dest))
    assert written == len(payload) and dest.read_bytes() == payload


def test_a_gzip_bomb_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(geoip, 'MAX_UNPACKED_BYTES', 4 * 1024 * 1024)
    bomb = _gzip_of(b'\0' * (16 * 1024 * 1024))
    assert len(bomb) < 100 * 1024, 'the compressed bomb should be small, that is the point'
    dest = tmp_path / 'db.mmdb'
    with pytest.raises(geoip.GeoIPTooLarge):
        geoip._stream_gunzip(_StreamResp(bomb), str(dest))


def test_an_oversized_download_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(geoip, 'MAX_DOWNLOAD_BYTES', 256 * 1024)
    blob = _gzip_of(os.urandom(2 * 1024 * 1024))
    dest = tmp_path / 'db.mmdb'
    with pytest.raises(geoip.GeoIPTooLarge):
        geoip._stream_gunzip(_StreamResp(blob), str(dest))


def test_a_bare_selector_cannot_resolve_to_manager_yml(monkeypatch):
    config_dir = os.path.dirname(env.SETTINGS_PATH)
    monkeypatch.setattr(env, 'ACTIVE_CONFIG_DIR', config_dir)
    name = os.path.basename(env.SETTINGS_PATH).rsplit('.', 1)[0]
    assert env.is_own_state(env.SETTINGS_PATH), 'the settings file is own state, by definition'
    assert config_mod.resolve_config_path(name) == '', \
        f'{name!r} resolved to Traefik Manager\'s own settings file'


def test_an_ordinary_config_name_still_resolves(monkeypatch, tmp_path):
    monkeypatch.setattr(env, 'ACTIVE_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(config_mod, 'is_safe_path', lambda p: True)
    resolved = config_mod.resolve_config_path('dynamic')
    assert resolved == str(tmp_path / 'dynamic.yml'), \
        'an ordinary Traefik config must still resolve'
