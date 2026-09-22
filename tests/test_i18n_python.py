import ast
import hashlib
import os
import re

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from flask_babel import get_domain

from core import i18n
from tests.conftest import tm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = 'tm-i18n-api-key'
HDR = {'X-CSRF-Token': 'testtoken', 'X-Requested-With': 'fetch'}
PLACEHOLDER = re.compile(r'%\((\w+)\)s')


def _gettext_calls():
    with open(os.path.join(ROOT, 'app.py'), encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'gettext':
            yield node


def test_python_messages_are_literals_with_matching_placeholders():
    calls = list(_gettext_calls())
    assert len(calls) > 200
    for call in calls:
        assert len(call.args) == 1 and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str), \
            f'app.py:{call.lineno} passes a non-literal message'
        msgid = call.args[0].value
        names = {kw.arg for kw in call.keywords}
        assert None not in names, f'app.py:{call.lineno} passes **kwargs'
        used = set(PLACEHOLDER.findall(msgid))
        assert used == names, f'app.py:{call.lineno} placeholders {sorted(used)} do not match arguments {sorted(names)}'
        if not names:
            assert '%(' not in msgid, f'app.py:{call.lineno} has a placeholder but no value'
        else:
            leftover = PLACEHOLDER.sub('', msgid.replace('%%', ''))
            assert '%' not in leftover, f'app.py:{call.lineno} has a bare % that breaks formatting'


def test_every_python_message_formats_in_english():
    for call in _gettext_calls():
        msgid = call.args[0].value
        values = {kw.arg: 'x' for kw in call.keywords}
        rendered = msgid % values if values else msgid
        assert '%(' not in rendered


@pytest.fixture
def german(tmp_path, monkeypatch):
    catalog = Catalog(locale='de')
    catalog.add('Unknown language', 'Unbekannte Sprache')
    catalog.add('Not authenticated', 'Nicht angemeldet')
    target = tmp_path / 'de' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    with open(target / 'messages.mo', 'wb') as fh:
        write_mo(fh, catalog)
    app = tm.app
    monkeypatch.setattr(app.extensions['babel'], 'translation_directories', [str(tmp_path)])
    monkeypatch.setattr(i18n, 'available_tags', lambda locale_dir=None: ('en', 'de'))
    with app.test_request_context('/'):
        monkeypatch.setattr(get_domain(), 'cache', {})
    return app


@pytest.fixture
def keyed(monkeypatch):
    from core import auth as auth_mod
    from core import settings as settings_mod
    real_load = settings_mod.load_settings

    def with_key():
        s = dict(real_load())
        s['api_keys'] = [{'name': 'test', 'hash': 'sha256:' + hashlib.sha256(KEY.encode()).hexdigest()}]
        return s

    monkeypatch.setattr(settings_mod, 'load_settings', with_key)
    monkeypatch.setattr(tm, 'load_settings', with_key, raising=False)
    monkeypatch.setattr(auth_mod.settings_mod, 'load_settings', with_key)


def test_a_browser_session_gets_its_language(german, client):
    r = client.post('/api/settings/language', json={'default_language': 'xx'},
                    headers={**HDR, 'Accept-Language': 'de-DE,de;q=0.9'})
    assert r.status_code == 400
    assert r.get_json()['error'] == 'Unbekannte Sprache'


def test_a_browser_session_without_a_preference_gets_english(german, client):
    r = client.post('/api/settings/language', json={'default_language': 'xx'}, headers=HDR)
    assert r.get_json()['error'] == 'Unknown language'


def test_api_keys_always_get_the_english_contract(german, keyed, monkeypatch):
    monkeypatch.setattr(tm, 'load_settings', lambda: {**tm._settings.load_settings(), 'default_language': 'de'}, raising=False)
    client = tm.app.test_client()
    r = client.post('/api/settings/language', json={'default_language': 'xx'},
                    headers={'X-Api-Key': KEY, 'Accept-Language': 'de'})
    assert r.status_code == 400
    assert r.get_json()['error'] == 'Unknown language'


def test_api_keys_can_still_ask_for_a_language_explicitly(german, keyed):
    client = tm.app.test_client()
    r = client.post('/api/settings/language?lang=de', json={'default_language': 'xx'}, headers={'X-Api-Key': KEY})
    assert r.get_json()['error'] == 'Unbekannte Sprache'


def test_unauthenticated_api_errors_follow_the_browser(german):
    client = tm.app.test_client()
    r = client.get('/api/settings', headers={'Accept-Language': 'de'})
    assert r.status_code == 401
    assert r.get_json()['error'] == 'Nicht angemeldet'
    r = client.get('/api/settings', headers={'X-Api-Key': 'wrong', 'Accept-Language': 'de'})
    assert r.get_json()['error'] == 'Not authenticated'


def test_background_work_without_a_request_stays_english(german):
    from flask_babel import gettext
    assert gettext('Unknown language') == 'Unknown language'
