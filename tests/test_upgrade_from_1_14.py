import os
from pathlib import Path

from core import settings as settings_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MANAGER_YML_1_14 = (
    "domains:\n  - example.com\n"
    "cert_resolver: letsencrypt\n"
    "traefik_api_url: http://traefik:8080\n"
    "auth_enabled: true\n"
    "setup_complete: true\n"
    "must_change_password: false\n"
    "password_hash: '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQR'\n"
    "default_theme: light\n"
    "ui_prefs:\n  showDocsLink: false\n  compactStatCards: true\n"
)


def _settings_path():
    return Path(settings_mod.env.SETTINGS_PATH)


def _with_1_14_settings():
    original = _settings_path().read_text()
    _settings_path().write_text(MANAGER_YML_1_14)
    return original


def test_a_1_14_manager_yml_loads_with_the_new_defaults():
    original = _with_1_14_settings()
    try:
        s = settings_mod.load_settings()
        assert s['default_language'] == ''
        assert s['default_theme'] == 'light'
        assert s['ui_prefs'].get('showDocsLink') is False
        assert 'showLangPicker' not in s['ui_prefs']
    finally:
        _settings_path().write_text(original)


def test_a_1_14_install_still_renders_english_at_the_old_urls(client):
    original = _with_1_14_settings()
    try:
        for path in ('/', '/api/settings', '/static/manifest.json'):
            r = client.get(path)
            assert r.status_code == 200, path
        html = client.get('/').get_data(as_text=True)
        assert '<html lang="en"' in html
        assert "if (!pref('showLangPicker', true))" in html
        assert client.get('/api/settings').get_json()['default_language'] == ''
    finally:
        _settings_path().write_text(original)


def test_saving_other_settings_keeps_a_1_14_file_valid(client):
    original = _with_1_14_settings()
    try:
        r = client.post('/api/settings/theme', json={'default_theme': 'dark'},
                        headers={'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'})
        assert r.status_code == 200
        s = settings_mod.load_settings()
        assert s['default_theme'] == 'dark' and s['default_language'] == ''
        assert s['ui_prefs'].get('compactStatCards') is True
    finally:
        _settings_path().write_text(original)


def test_native_installs_compile_the_catalogues():
    with open(os.path.join(ROOT, 'scripts', 'setup-assets.sh'), encoding='utf-8') as fh:
        script = fh.read()
    assert 'venv/bin/pybabel' in script and 'compile -d "$REPO_ROOT/locale" -D messages' in script
    assert 'stays in English' in script, 'a failed compile must not fail tm update'


def test_new_python_dependencies_are_pinned_in_requirements():
    with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as fh:
        reqs = fh.read().split()
    assert 'Flask-Babel==4.0.0' in reqs and 'Babel==2.18.0' in reqs
